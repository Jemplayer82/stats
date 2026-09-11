"""Read account metrics through Codex's stdio app-server; never start a turn."""
import fcntl
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import time


class CodexError(Exception):
    pass


class AppServer:
    def __init__(self):
        self.proc = None
        self.selector = selectors.DefaultSelector()
        self.buffer = b''
        self.next_id = 0
        self.deadline = time.monotonic() + 25

    def __enter__(self):
        try:
            self.proc = subprocess.Popen(
                ['codex', '-c', 'cli_auth_credentials_store="file"', 'app-server'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            self.selector.register(self.proc.stdout, selectors.EVENT_READ)
            self.call('initialize', {'clientInfo': {
                'name': 'stats_usage_dashboard', 'version': '1.0.0'},
                'capabilities': {'experimentalApi': True}})
            self.send({'method': 'initialized', 'params': {}})
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def send(self, message):
        self.proc.stdin.write((json.dumps(message) + '\n').encode())
        self.proc.stdin.flush()

    def call(self, method, params=None):
        self.next_id += 1
        request_id = self.next_id
        self.send({'id': request_id, 'method': method, 'params': params or {}})
        while True:
            if time.monotonic() >= self.deadline:
                raise CodexError('timeout')
            while b'\n' not in self.buffer:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0 or not self.selector.select(remaining):
                    raise CodexError('timeout')
                chunk = os.read(self.proc.stdout.fileno(), 65536)
                if not chunk:
                    raise CodexError('unavailable')
                self.buffer += chunk
                if len(self.buffer) > 8 * 1024 * 1024:
                    raise CodexError('invalid_response')
            line, self.buffer = self.buffer.split(b'\n', 1)
            message = json.loads(line)
            # This collector does not service agent/tool requests.
            if 'method' in message:
                if 'id' in message:
                    self.send({'id': message['id'], 'error': {
                        'code': -32601, 'message': 'Unsupported by usage collector'}})
                continue
            if message.get('id') != request_id:
                continue
            if 'error' in message:
                # Do not expose upstream errors, which can contain account details.
                raise CodexError('api_error')
            result = message.get('result')
            if not isinstance(result, dict):
                raise CodexError('invalid_response')
            return result

    def __exit__(self, *_):
        self.selector.close()
        if self.proc:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            self.proc.stdin.close()
            self.proc.stdout.close()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalize_limits(result):
    buckets = result.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        legacy = result.get('rateLimits')
        buckets = {'codex': legacy} if isinstance(legacy, dict) else {}
    windows = []
    for bucket_id, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        for slot in ('primary', 'secondary'):
            window = bucket.get(slot)
            if not isinstance(window, dict) or not number(window.get('usedPercent')):
                continue
            duration = window.get('windowDurationMins')
            reset = window.get('resetsAt')
            windows.append({
                'bucket': str(bucket_id),
                'name': str(bucket.get('limitName') or ('Codex' if bucket_id == 'codex' else bucket_id)),
                'slot': slot,
                'used_percent': max(0, min(100, window['usedPercent'])),
                'window_minutes': duration if number(duration) and duration > 0 else None,
                'resets_at': reset if number(reset) and reset > 0 else None,
            })
    return windows


def normalize_history(result):
    raw = result.get('dailyUsageBuckets')
    if not isinstance(raw, list):
        return None
    from datetime import date
    days = {}
    for bucket in raw:
        if not isinstance(bucket, dict) or not number(bucket.get('tokens')) or bucket['tokens'] < 0:
            continue
        try:
            day = date.fromisoformat(bucket.get('startDate', '')).isoformat()
        except (TypeError, ValueError):
            continue
        days[day] = bucket['tokens']
    return [{'date': day, 'tokens': days[day]} for day in sorted(days)[-30:]]


def collect():
    try:
        with AppServer() as rpc:
            account = rpc.call('account/read').get('account')
            if not account:
                return {'error': 'login_required'}
            if account.get('type') == 'apiKey':
                return {'error': 'chatgpt_required'}
            limits = normalize_limits(rpc.call('account/rateLimits/read'))
            history = None
            try:
                history = normalize_history(rpc.call('account/usage/read'))
            except (CodexError, OSError, ValueError, TypeError):
                pass  # Older CLI versions/accounts can supply quotas without history.
            return {'ok': True, 'windows': limits, 'daily': history,
                    'updated_at': int(time.time())}
    except FileNotFoundError:
        return {'error': 'not_installed'}
    except (CodexError, OSError, ValueError, TypeError):
        return {'error': 'unavailable'}


def get_usage():
    """Share a sanitized cache and a refresh lock across Gunicorn workers."""
    home = Path(os.environ.get('CODEX_HOME', '/data/codex'))
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    auth = home / 'auth.json'
    try:
        auth_version = auth.stat().st_mtime_ns
    except FileNotFoundError:
        auth_version = None
    cache_path = home / 'stats-usage.json'
    with (home / 'stats-usage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            cached = json.loads(cache_path.read_text())
        except (OSError, ValueError):
            cached = {}
        ttl = 60 if cached.get('payload', {}).get('error') or cached.get('payload', {}).get('stale') else 300
        same_auth = cached.get('auth_version') == auth_version
        if same_auth and time.time() - cached.get('checked_at', 0) < ttl:
            return cached['payload']
        payload = collect()
        previous = cached.get('payload', {})
        if payload.get('error') == 'unavailable' and same_auth and previous.get('ok'):
            payload = {**previous, 'stale': True}
        # Token refresh may have updated auth.json during the read.
        try:
            auth_version = auth.stat().st_mtime_ns
        except FileNotFoundError:
            auth_version = None
        tmp = cache_path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'checked_at': time.time(), 'auth_version': auth_version,
                                   'payload': payload}))
        os.chmod(tmp, 0o600)
        tmp.replace(cache_path)
        return payload
