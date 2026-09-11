import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import codex_usage as usage


class LimitsTests(unittest.TestCase):
    def test_multi_bucket_wins_and_missing_windows_are_not_zero(self):
        result = usage.normalize_limits({
            'rateLimits': {'primary': {'usedPercent': 99}},
            'rateLimitsByLimitId': {
                'codex': {'primary': {'usedPercent': 8, 'windowDurationMins': 10080}, 'secondary': None},
                'spark': {'limitName': 'Spark', 'primary': {'usedPercent': 0, 'windowDurationMins': 300},
                          'secondary': {'usedPercent': None}},
            }})
        self.assertEqual([w['used_percent'] for w in result], [8, 0])
        self.assertEqual(result[0]['window_minutes'], 10080)
        self.assertEqual(result[1]['name'], 'Spark')

    def test_legacy_clamps_percent_and_rejects_invalid_numbers(self):
        result = usage.normalize_limits({'rateLimits': {
            'primary': {'usedPercent': 120, 'resetsAt': 123456},
            'secondary': {'usedPercent': float('nan')}}})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['used_percent'], 100)
        self.assertEqual(result[0]['resets_at'], 123456)
        self.assertEqual(usage.normalize_limits({'rateLimits': {'primary': {'usedPercent': True}}}), [])

    def test_history_distinguishes_unavailable_empty_and_zero(self):
        self.assertIsNone(usage.normalize_history({}))
        self.assertEqual(usage.normalize_history({'dailyUsageBuckets': []}), [])
        self.assertEqual(usage.normalize_history({'dailyUsageBuckets': [
            {'startDate': '2026-09-11', 'tokens': 0},
            {'startDate': '2026-09-09', 'tokens': 42},
            {'startDate': 'bad', 'tokens': 1},
            {'startDate': '2026-09-10', 'tokens': -1},
        ]}), [{'date': '2026-09-09', 'tokens': 42}, {'date': '2026-09-11', 'tokens': 0}])


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {'CODEX_HOME': self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def expire(self):
        path = Path(self.tmp.name) / 'stats-usage.json'
        data = json.loads(path.read_text())
        data['checked_at'] = 0
        path.write_text(json.dumps(data))

    @patch.object(usage, 'collect')
    def test_cache_shared_and_login_invalidates(self, collect):
        collect.return_value = {'error': 'login_required'}
        usage.get_usage()
        usage.get_usage()
        self.assertEqual(collect.call_count, 1)
        (Path(self.tmp.name) / 'auth.json').write_text('{}')
        collect.return_value = {'ok': True, 'windows': [], 'daily': None, 'updated_at': 100}
        self.assertTrue(usage.get_usage()['ok'])
        self.assertEqual(collect.call_count, 2)

    @patch.object(usage, 'collect')
    def test_stale_retains_timestamp_but_logout_clears_it(self, collect):
        auth = Path(self.tmp.name) / 'auth.json'
        auth.write_text('{}')
        collect.return_value = {'ok': True, 'windows': [], 'daily': None, 'updated_at': 100}
        usage.get_usage()
        self.expire()
        collect.return_value = {'error': 'unavailable'}
        result = usage.get_usage()
        self.assertTrue(result['stale'])
        self.assertEqual(result['updated_at'], 100)
        auth.unlink()
        collect.return_value = {'error': 'login_required'}
        self.assertEqual(usage.get_usage(), {'error': 'login_required'})


class ProtocolTests(unittest.TestCase):
    def test_actual_stdio_handshake_and_sanitization(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / 'codex'
            fake.write_text('''#!/usr/bin/env python3
import json, sys
initialized = False
for line in sys.stdin:
    msg = json.loads(line)
    method = msg.get('method')
    if method == 'initialized':
        initialized = True
        continue
    if method == 'initialize':
        result = {}
    elif method == 'account/read':
        assert initialized
        result = {'account': {'type': 'chatgpt', 'email': 'private@example.com'}}
    elif method == 'account/rateLimits/read':
        result = {'rateLimits': {'primary': {'usedPercent': 23, 'windowDurationMins': 300}}, 'accountId': 'private'}
    elif method == 'account/usage/read':
        print(json.dumps({'id': msg['id'], 'error': {'code': -32601, 'message': 'unsupported'}}), flush=True)
        continue
    else:
        raise RuntimeError('Unexpected call: ' + str(method))
    print(json.dumps({'method': 'notification', 'params': {}}), flush=True)
    print(json.dumps({'id': msg['id'], 'result': result}), flush=True)
''')
            fake.chmod(0o700)
            with patch.dict(os.environ, {'PATH': tmp + os.pathsep + os.environ['PATH']}):
                result = usage.collect()
            self.assertTrue(result['ok'])
            self.assertEqual(result['windows'][0]['used_percent'], 23)
            self.assertIsNone(result['daily'])
            self.assertNotIn('private', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
