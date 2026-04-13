from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from bs4 import BeautifulSoup
from google.cloud import monitoring_v3
from google.oauth2 import service_account
import requests as http
import urllib3
import websocket
import json
import time
import re

# Suppress insecure request warnings for Proxmox (often self-signed)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ---------------------------------------------------------------------------
# Configuration & Error Constants
# ---------------------------------------------------------------------------

# Config keys
CONFIG_CLAUDE_AI_SESSION = 'claude_ai_session'
CONFIG_OLLAMA_COM_SESSION = 'ollama_com_session'
CONFIG_PROXMOX_HOST = 'proxmox_host'
CONFIG_PROXMOX_TOKEN_ID = 'proxmox_token_id'
CONFIG_PROXMOX_TOKEN_SECRET = 'proxmox_token_secret'
CONFIG_GEMINI_SERVICE_ACCOUNT = 'gemini_service_account'
CONFIG_TRUENAS_HOST = 'truenas_host'
CONFIG_TRUENAS_API_KEY = 'truenas_api_key'

# Error codes
class ErrorCode:
    NO_CONFIG = 'no_config'
    NO_COOKIE = 'no_cookie'
    INCOMPLETE_CONFIG = 'incomplete_config'
    AUTH_FAILED = 'auth_failed'
    NO_ORGS = 'no_orgs'
    USAGE_ENDPOINT_NOT_FOUND = 'usage_endpoint_not_found'
    PARSE_EXCEPTION = 'parse_exception'
    PARSE_FAILED = 'parse_failed'
    API_ERROR = 'api_error'


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AppConfig(db.Model):
    key   = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, default='')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_config(key, default=''):
    c = db.session.get(AppConfig, key)
    return c.value if c else default


def set_config(key, value):
    c = db.session.get(AppConfig, key)
    if c:
        c.value = value
    else:
        db.session.add(AppConfig(key=key, value=value))
    db.session.commit()


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        claude_cookie  = request.form.get(CONFIG_CLAUDE_AI_SESSION, '').strip()
        ollama_cookie  = request.form.get(CONFIG_OLLAMA_COM_SESSION, '').strip()
        proxmox_host   = request.form.get(CONFIG_PROXMOX_HOST, '').strip()
        proxmox_token_id = request.form.get(CONFIG_PROXMOX_TOKEN_ID, '').strip()
        proxmox_secret = request.form.get(CONFIG_PROXMOX_TOKEN_SECRET, '').strip()
        gemini_json    = request.form.get(CONFIG_GEMINI_SERVICE_ACCOUNT, '').strip()

        if claude_cookie:
            set_config(CONFIG_CLAUDE_AI_SESSION, claude_cookie)
        if ollama_cookie:
            set_config(CONFIG_OLLAMA_COM_SESSION, ollama_cookie)
        if proxmox_host:
            set_config(CONFIG_PROXMOX_HOST, proxmox_host)
        if proxmox_token_id:
            set_config(CONFIG_PROXMOX_TOKEN_ID, proxmox_token_id)
        if proxmox_secret:
            set_config(CONFIG_PROXMOX_TOKEN_SECRET, proxmox_secret)
        if gemini_json:
            set_config(CONFIG_GEMINI_SERVICE_ACCOUNT, gemini_json)

        truenas_host    = request.form.get(CONFIG_TRUENAS_HOST, '').strip()
        truenas_api_key = request.form.get(CONFIG_TRUENAS_API_KEY, '').strip()
        if truenas_host:    set_config(CONFIG_TRUENAS_HOST, truenas_host)
        if truenas_api_key: set_config(CONFIG_TRUENAS_API_KEY, truenas_api_key)

        return redirect(url_for('settings'))

    return render_template('settings.html',
                           has_claude_cookie=bool(get_config(CONFIG_CLAUDE_AI_SESSION, '')),
                           has_ollama_cookie=bool(get_config(CONFIG_OLLAMA_COM_SESSION, '')),
                           proxmox_host=get_config(CONFIG_PROXMOX_HOST, ''),
                           proxmox_token_id=get_config(CONFIG_PROXMOX_TOKEN_ID, ''),
                           has_proxmox_secret=bool(get_config(CONFIG_PROXMOX_TOKEN_SECRET, '')),
                           has_gemini_config=bool(get_config(CONFIG_GEMINI_SERVICE_ACCOUNT, '')),
                           truenas_host=get_config(CONFIG_TRUENAS_HOST, ''),
                           has_truenas_api_key=bool(get_config(CONFIG_TRUENAS_API_KEY, '')))


# ---------------------------------------------------------------------------
# Gemini (Google Cloud Monitoring) live usage
# ---------------------------------------------------------------------------

@app.route('/api/gemini-usage')
def api_gemini_usage():
    gemini_json = get_config(CONFIG_GEMINI_SERVICE_ACCOUNT, '')
    if not gemini_json:
        return jsonify({'error': ErrorCode.NO_CONFIG}), 200

    try:
        info = json.loads(gemini_json)
        project_id = info.get('project_id')
        credentials = service_account.Credentials.from_service_account_info(info)
        client = monitoring_v3.MetricServiceClient(credentials=credentials)
        
        # Define the time interval (last 24 hours)
        now = time.time()
        seconds = int(now)
        nanos = int((now - seconds) * 10**9)
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": seconds, "nanos": nanos},
            "start_time": {"seconds": seconds - 86400, "nanos": nanos},
        })

        # Try several common metrics for Gemini usage
        metrics_to_try = [
            'serviceruntime.googleapis.com/api/request_count',
            'generativelanguage.googleapis.com/generate_content_requests'
        ]
        
        usage_data = []
        
        for metric_type in metrics_to_try:
            # Filter for the Generative Language API
            filter_str = (
                f'metric.type = "{metric_type}" AND '
                'resource.labels.service = "generativelanguage.googleapis.com"'
            )
            
            try:
                pages = client.list_time_series(
                    request={
                        "name": f"projects/{project_id}",
                        "filter": filter_str,
                        "interval": interval,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    }
                )
                
                for series in pages:
                    # Identify the label (method name or metric name)
                    label = series.metric.labels.get('method') or \
                            series.metric.type.split('/')[-1].replace('_', ' ').title()
                    
                    # Sum up points in the interval
                    total_count = sum(p.value.int64_value for p in series.points)
                    
                    if total_count > 0:
                        # Clean up label if it's a full method path
                        if '.' in label:
                            label = label.split('.')[-1].replace('_', ' ').title()
                            
                        usage_data.append({
                            'label': label,
                            'usage': total_count
                        })
                
                # If we found data for one metric, we can stop or combine
                if usage_data:
                    break
            except Exception:
                continue

        return jsonify({'ok': True, 'project_id': project_id, 'data': usage_data})
    except Exception as e:
        return jsonify({'error': ErrorCode.API_ERROR, 'details': str(e)}), 200


# ---------------------------------------------------------------------------
# Proxmox live status
# ---------------------------------------------------------------------------

@app.route('/api/proxmox-status')
def api_proxmox_status():
    host = get_config(CONFIG_PROXMOX_HOST, '')
    token_id = get_config(CONFIG_PROXMOX_TOKEN_ID, '')
    secret = get_config(CONFIG_PROXMOX_TOKEN_SECRET, '')

    if not all([host, token_id, secret]):
        return jsonify({'error': ErrorCode.INCOMPLETE_CONFIG}), 200

    # Ensure host has protocol
    if not host.startswith('http'):
        host = f'https://{host}'
    
    # Proxmox uses a specific token format in the Authorization header
    headers = {
        'Authorization': f'PVEAPIToken={token_id}={secret}',
        'Accept': 'application/json'
    }

    try:
        # Get cluster resources (nodes, VMs, containers)
        url = f"{host.rstrip('/')}/api2/json/cluster/resources"
        r = http.get(url, headers=headers, timeout=10, verify=False)

        if not r.ok:
            return jsonify({'error': ErrorCode.API_ERROR, 'details': r.text, 'status': r.status_code}), 200

        data = r.json().get('data', [])
        resources = [res for res in data if res.get('type') in ['node', 'qemu', 'lxc']]

        # Enrich each node with detailed stats from its status endpoint
        node_names = [res['node'] for res in resources if res.get('type') == 'node']
        node_stats = {}
        for node in node_names:
            try:
                sr = http.get(f"{host.rstrip('/')}/api2/json/nodes/{node}/status",
                              headers=headers, timeout=10, verify=False)
                if sr.ok:
                    node_stats[node] = sr.json().get('data', {})
            except Exception:
                pass

        # Merge stats into node resources
        for res in resources:
            if res.get('type') == 'node' and res['node'] in node_stats:
                res.update(node_stats[res['node']])

        # Enrich running QEMU VMs with disk usage via guest agent
        SKIP_FS_TYPES = {'vfat', 'erofs', 'tmpfs', 'devtmpfs', 'squashfs', 'iso9660', 'zram'}
        for res in resources:
            if res.get('type') != 'qemu' or res.get('status') != 'running':
                continue
            try:
                ar = http.get(
                    f"{host.rstrip('/')}/api2/json/nodes/{res['node']}/qemu/{res['vmid']}/agent/get-fsinfo",
                    headers=headers, timeout=5, verify=False)
                if not ar.ok:
                    continue
                items = ar.json().get('data', {}).get('result') or []

                # Detect Windows by presence of drive-letter mountpoints
                is_windows = any(':\\' in (f.get('mountpoint') or '') for f in items)

                if is_windows:
                    # Windows: one entry per drive letter (C:\, D:\, etc.)
                    seen = {}
                    for fs in items:
                        mp = fs.get('mountpoint', '')
                        if len(mp) == 3 and mp[1:] == ':\\':  # e.g. C:\
                            seen[mp] = fs
                else:
                    # Linux: prefer '/', fall back to largest writable partition
                    seen = {}
                    candidates = [f for f in items
                                  if f.get('type', '').lower() not in SKIP_FS_TYPES
                                  and f.get('total-bytes', 0) > 0]
                    root = next((f for f in candidates if f.get('mountpoint') == '/'), None)
                    if root:
                        seen['/'] = root
                    elif candidates:
                        largest = max(candidates, key=lambda f: f.get('total-bytes', 0))
                        largest = dict(largest)
                        largest['mountpoint'] = 'data'
                        seen['data'] = largest

                disks = [
                    {
                        'label': f.get('mountpoint', f.get('name', '')),
                        'used':  f.get('used-bytes',  0),
                        'total': f.get('total-bytes', 0),
                    }
                    for f in seen.values()
                    if f.get('total-bytes', 0) > 0
                ]
                if disks:
                    res['agent_disks'] = disks
            except Exception:
                pass

        return jsonify({'ok': True, 'resources': resources})
    except Exception as e:
        return jsonify({'error': ErrorCode.API_ERROR, 'details': str(e)}), 200


@app.route('/api/ceph-status')
def api_ceph_status():
    host   = get_config(CONFIG_PROXMOX_HOST, '')
    token_id = get_config(CONFIG_PROXMOX_TOKEN_ID, '')
    secret = get_config(CONFIG_PROXMOX_TOKEN_SECRET, '')

    if not all([host, token_id, secret]):
        return jsonify({'error': ErrorCode.INCOMPLETE_CONFIG}), 200

    if not host.startswith('http'):
        host = f'https://{host}'

    headers = {
        'Authorization': f'PVEAPIToken={token_id}={secret}',
        'Accept': 'application/json'
    }

    try:
        r = http.get(f"{host.rstrip('/')}/api2/json/cluster/ceph/status",
                     headers=headers, timeout=10, verify=False)
        if not r.ok:
            return jsonify({'error': ErrorCode.API_ERROR, 'details': r.text}), 200

        data = r.json().get('data', {})
        pgmap  = data.get('pgmap', {})
        health = data.get('health', {})
        osdmap = data.get('osdmap', {})

        checks = []
        for key, val in (health.get('checks') or {}).items():
            checks.append({
                'severity': val.get('severity', ''),
                'message':  val.get('summary', {}).get('message', key),
            })

        return jsonify({
            'ok': True,
            'health':          health.get('status', 'HEALTH_UNKNOWN'),
            'checks':          checks,
            'bytes_used':      pgmap.get('bytes_used', 0),
            'bytes_total':     pgmap.get('bytes_total', 0),
            'bytes_avail':     pgmap.get('bytes_avail', 0),
            'read_bytes_sec':  pgmap.get('read_bytes_sec', 0),
            'write_bytes_sec': pgmap.get('write_bytes_sec', 0),
            'read_op_sec':     pgmap.get('read_op_per_sec', 0),
            'write_op_sec':    pgmap.get('write_op_per_sec', 0),
            'num_osds':        osdmap.get('num_osds', 0),
            'num_up_osds':     osdmap.get('num_up_osds', 0),
            'num_in_osds':     osdmap.get('num_in_osds', 0),
            'num_pgs':         pgmap.get('num_pgs', 0),
        })
    except Exception as e:
        return jsonify({'error': ErrorCode.API_ERROR, 'details': str(e)}), 200






# ---------------------------------------------------------------------------
# TrueNAS SCALE WebSocket helper + route
# ---------------------------------------------------------------------------

def _truenas_call(host, api_key, method, params=None):
    """Open a WebSocket to wss://<host>/api/current, authenticate, call one method."""
    import ssl
    ws = websocket.create_connection(
        f'wss://{host}/websocket',
        timeout=10,
        sslopt={"cert_reqs": ssl.CERT_NONE}
    )
    try:
        ws.send(json.dumps({"msg": "connect", "version": "1", "support": ["1"]}))
        resp = json.loads(ws.recv())
        if resp.get("msg") != "connected":
            raise RuntimeError(f"Handshake failed: {resp}")

        ws.send(json.dumps({"id": "auth", "msg": "method",
                            "method": "auth.login_with_api_key",
                            "params": [api_key]}))
        resp = json.loads(ws.recv())
        if not resp.get("result"):
            raise RuntimeError("Authentication failed")

        ws.send(json.dumps({"id": "call", "msg": "method",
                            "method": method,
                            "params": params or []}))
        resp = json.loads(ws.recv())
        if "error" in resp:
            raise RuntimeError(f"RPC error: {resp['error']}")
        return resp["result"]
    finally:
        ws.close()


@app.route('/api/truenas-status')
def api_truenas_status():
    host    = get_config(CONFIG_TRUENAS_HOST, '')
    api_key = get_config(CONFIG_TRUENAS_API_KEY, '')

    if not all([host, api_key]):
        return jsonify({'error': ErrorCode.INCOMPLETE_CONFIG}), 200

    # Strip any protocol prefix — we connect via ws://
    host = re.sub(r'^https?://', '', host).rstrip('/')

    try:
        pools   = _truenas_call(host, api_key, 'pool.query')
        alerts  = _truenas_call(host, api_key, 'alert.list')
        sysinfo = _truenas_call(host, api_key, 'system.info')
    except Exception as e:
        return jsonify({'error': ErrorCode.API_ERROR, 'details': str(e)}), 200

    active_alerts = [
        {'level': a['level'], 'text': a.get('formatted', a.get('text', ''))}
        for a in alerts
        if a.get('level') in ('CRITICAL', 'WARNING')
    ]

    pool_list = []
    for p in pools:
        scan = p.get('scan') or {}
        pool_list.append({
            'name':          p['name'],
            'status':        p['status'],
            'healthy':       p.get('healthy', True),
            'warning':       p.get('warning', False),
            'status_code':   p.get('status_code', ''),
            'status_detail': p.get('status_detail', ''),
            'fragmentation': p.get('fragmentation', 0),
            'allocated':     p.get('allocated', 0),
            'size':          p.get('size', 0),
            'free':          p.get('free', 0),
            'scan': {
                'function':       scan.get('function', ''),
                'state':          scan.get('state', ''),
                'percentage':     round(scan.get('percentage', 0), 1),
                'errors':         scan.get('errors', 0),
                'secs_left':      scan.get('total_secs_left'),
                'end_time':       (scan.get('end_time') or {}).get('$date'),
            },
        })

    # Network sparkline — last hour of bond1, downsampled to ~60 pts
    network = None
    try:
        net_raw = _truenas_call(host, api_key, 'reporting.get_data',
                                [[{'name': 'interface', 'identifier': 'bond1'}],
                                 {'unit': 'HOUR', 'page': 1}])
        pts = (net_raw[0].get('data') or []) if net_raw else []
        sampled = pts[::60] if pts else []
        network = {
            'interface': 'bond1',
            'rx': [round(p[1], 2) for p in sampled if len(p) > 1],
            'tx': [round(p[2], 2) for p in sampled if len(p) > 2],
        }
    except Exception:
        pass

    return jsonify({
        'ok':       True,
        'pools':    pool_list,
        'alerts':   active_alerts,
        'network':  network,
        'uptime':   sysinfo.get('uptime_seconds', 0),
        'hostname': sysinfo.get('hostname', ''),
        'version':  sysinfo.get('version', ''),
    })


# ---------------------------------------------------------------------------
# Claude.ai live usage scraper
# ---------------------------------------------------------------------------

CLAUDE_HEADERS = {
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'accept': 'application/json',
    'referer': 'https://claude.ai/',
    'origin': 'https://claude.ai',
}


def _claude_session_headers(cookie_val):
    cookie = cookie_val if cookie_val.startswith('sessionKey=') else f'sessionKey={cookie_val}'
    return {**CLAUDE_HEADERS, 'cookie': cookie}


@app.route('/api/claude-usage')
def api_claude_usage():
    """Fetch live usage limits from claude.ai and return JSON for the dashboard."""
    cookie = get_config(CONFIG_CLAUDE_AI_SESSION, '')
    if not cookie:
        return jsonify({'error': ErrorCode.NO_COOKIE}), 200

    hdrs = _claude_session_headers(cookie)

    # Step 1: get organization list
    try:
        r = http.get('https://claude.ai/api/organizations', headers=hdrs, timeout=10)
        if r.status_code == 401:
            return jsonify({'error': ErrorCode.AUTH_FAILED}), 200
        orgs = r.json()
        if not orgs:
            return jsonify({'error': ErrorCode.NO_ORGS}), 200
        org_id = orgs[0].get('uuid') or orgs[0].get('id', '')
    except Exception as e:
        return jsonify({'error': ErrorCode.API_ERROR, 'details': str(e)}), 200

    # Step 2: try several known usage endpoints
    usage_data = None
    for path in [
        f'/api/organizations/{org_id}/usage',
        f'/api/organizations/{org_id}/limits',
        f'/api/organizations/{org_id}/entitlements',
        '/api/usage',
    ]:
        try:
            r = http.get(f'https://claude.ai{path}', headers=hdrs, timeout=10)
            if r.ok:
                usage_data = r.json()
                break
        except Exception:
            continue

    if usage_data is None:
        return jsonify({'error': ErrorCode.USAGE_ENDPOINT_NOT_FOUND, 'org_id': org_id}), 200

    return jsonify({'ok': True, 'org_id': org_id, 'usage': usage_data})


# ---------------------------------------------------------------------------
# Ollama.com live usage scraper
# ---------------------------------------------------------------------------

OLLAMA_COM_HEADERS = {
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'max-age=0',
    'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'referer': 'https://ollama.com/',
}


def _ollama_session_headers(cookie_val):
    return {**OLLAMA_COM_HEADERS,
            'cookie': f'__Secure-session={cookie_val}'}


@app.route('/api/ollama-com-usage')
def api_ollama_com_usage():
    cookie = get_config(CONFIG_OLLAMA_COM_SESSION, '')
    if not cookie:
        return jsonify({'error': ErrorCode.NO_COOKIE}), 200

    hdrs = _ollama_session_headers(cookie)

    try:
        r = http.get('https://ollama.com/settings', headers=hdrs, timeout=15)
    except Exception as e:
        return jsonify({'error': ErrorCode.API_ERROR, 'details': str(e)}), 200

    if r.status_code == 401 or 'Sign in' in r.text[:2000]:
        return jsonify({'error': ErrorCode.AUTH_FAILED}), 200

    html = r.text
    fields = []
    debug_html_saved = False

    # Robust parsing with BeautifulSoup
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Look for the usage section
        # We search for elements containing 'usage' and then navigate to their parent/siblings
        usage_labels = soup.find_all(lambda tag: tag.name == "span" and "usage" in tag.text.lower())

        for label_tag in usage_labels:
            label_text = label_tag.get_text(strip=True)

            # Find the percentage (usually a sibling or in a parent container)
            # Pattern: label span -> percentage span -> progress bar -> data-time
            container = label_tag.parent
            if not container: continue

            # Find pct (e.g., "34.7% used")
            pct_tag = container.find(lambda tag: tag.name == "span" and "%" in tag.text)
            if not pct_tag: continue

            pct_match = re.search(r'([\d.]+)%', pct_tag.text)
            if not pct_match: continue
            pct = round(float(pct_match.group(1)))

            # Find reset time (usually in a [data-time] attribute nearby)
            reset_tag = container.find(lambda tag: tag.has_attr('data-time'))
            reset_time = reset_tag.get('data-time') if reset_tag else ''

            fields.append({
                'label': label_text,
                'pct': pct,
                'resets_at': reset_time
            })

    except Exception as e:
        # Save HTML snapshot for debugging once
        with open('debug_ollama_fail.html', 'w') as f:
            f.write(html)
        debug_html_saved = True
        return jsonify({'error': ErrorCode.PARSE_EXCEPTION, 'details': str(e), 'debug': 'See debug_ollama_fail.html'}), 200

    if not fields:
        # Save HTML snapshot only if not already saved in exception handler
        if not debug_html_saved:
            with open('debug_ollama_fail.html', 'w') as f:
                f.write(html)
        return jsonify({'error': ErrorCode.PARSE_FAILED, 'hint': 'Could not find usage blocks in page. See debug_ollama_fail.html'}), 200

    return jsonify({'ok': True, 'data': fields})




if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
