from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from bs4 import BeautifulSoup
from google.cloud import monitoring_v3
from google.oauth2 import service_account
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests as http
import urllib3
import json
import os
import time
import re
import threading
import fcntl

# Suppress insecure request warnings for Proxmox (often self-signed)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///usage.db')
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
CONFIG_UNIFI_API_KEY = 'unifi_api_key'
CONFIG_UNIFI_HOST = 'unifi_host'
CONFIG_UNIFI_USERNAME = 'unifi_username'
CONFIG_UNIFI_PASSWORD = 'unifi_password'
CONFIG_UNIFI_SITE = 'unifi_site'

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


class WanSample(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    ts           = db.Column(db.Integer, index=True)  # unix seconds
    wan_key      = db.Column(db.String(16), index=True)  # 'WAN' or 'WAN2'
    availability = db.Column(db.Float)   # 0-100, from UniFi's ping-monitor uptime_stats
    latency_ms   = db.Column(db.Float, nullable=True)


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


@app.route('/network')
def network():
    return render_template('network.html')


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

        unifi_host     = request.form.get(CONFIG_UNIFI_HOST, '').strip()
        unifi_username = request.form.get(CONFIG_UNIFI_USERNAME, '').strip()
        unifi_password = request.form.get(CONFIG_UNIFI_PASSWORD, '').strip()
        unifi_site     = request.form.get(CONFIG_UNIFI_SITE, '').strip()
        if unifi_host:     set_config(CONFIG_UNIFI_HOST, unifi_host)
        if unifi_username: set_config(CONFIG_UNIFI_USERNAME, unifi_username)
        if unifi_password: set_config(CONFIG_UNIFI_PASSWORD, unifi_password)
        if unifi_site:     set_config(CONFIG_UNIFI_SITE, unifi_site)

        return redirect(url_for('settings'))

    return render_template('settings.html',
                           has_claude_cookie=bool(get_config(CONFIG_CLAUDE_AI_SESSION, '')),
                           has_ollama_cookie=bool(get_config(CONFIG_OLLAMA_COM_SESSION, '')),
                           proxmox_host=get_config(CONFIG_PROXMOX_HOST, ''),
                           proxmox_token_id=get_config(CONFIG_PROXMOX_TOKEN_ID, ''),
                           has_proxmox_secret=bool(get_config(CONFIG_PROXMOX_TOKEN_SECRET, '')),
                           has_gemini_config=bool(get_config(CONFIG_GEMINI_SERVICE_ACCOUNT, '')),
                           truenas_host=get_config(CONFIG_TRUENAS_HOST, ''),
                           has_truenas_api_key=bool(get_config(CONFIG_TRUENAS_API_KEY, '')),
                           unifi_host=get_config(CONFIG_UNIFI_HOST, ''),
                           unifi_username=get_config(CONFIG_UNIFI_USERNAME, ''),
                           unifi_site=get_config(CONFIG_UNIFI_SITE, ''),
                           has_unifi_password=bool(get_config(CONFIG_UNIFI_PASSWORD, '')))


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
# TrueNAS SCALE REST helper + route
# ---------------------------------------------------------------------------

def _truenas_api(host, api_key, path, method='GET', body=None):
    """REST request to TrueNAS API v2.0."""
    resp = http.request(
        method,
        f'https://{host}/api/v2.0/{path}',
        headers={'Authorization': f'Bearer {api_key}'},
        json=body,
        timeout=(5, 5),
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()


@app.route('/api/truenas-status')
def api_truenas_status():
    host    = get_config(CONFIG_TRUENAS_HOST, '')
    api_key = get_config(CONFIG_TRUENAS_API_KEY, '')

    if not all([host, api_key]):
        return jsonify({'error': ErrorCode.INCOMPLETE_CONFIG}), 200

    # Strip any protocol prefix
    host = re.sub(r'^https?://', '', host).rstrip('/')

    try:
        pools   = _truenas_api(host, api_key, 'pool')
        alerts  = _truenas_api(host, api_key, 'alert/list')
        sysinfo = _truenas_api(host, api_key, 'system/info')
    except Exception as e:
        return jsonify({
            'error': ErrorCode.API_ERROR,
            'details': str(e),
            'attempted_url': f'https://{host}/api/v2.0/system/info',
        }), 200

    try:
        active_alerts = [
            {'level': a['level'], 'text': a.get('formatted', a.get('text', ''))}
            for a in alerts
            if isinstance(a, dict) and a.get('level') in ('CRITICAL', 'WARNING')
        ]

        pool_list = []
        for p in pools:
            if not isinstance(p, dict):
                continue
            scan = p.get('scan') or {}
            pool_list.append({
                'name':          p.get('name', ''),
                'status':        p.get('status', ''),
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
                    'percentage':     round(scan.get('percentage', 0) or 0, 1),
                    'errors':         scan.get('errors', 0),
                    'secs_left':      scan.get('total_secs_left'),
                    'end_time':       (scan.get('end_time') or {}).get('$date'),
                },
            })

        # Network sparkline — last hour of bond1, downsampled to ~60 pts
        network = None
        try:
            net_raw = _truenas_api(host, api_key, 'reporting/get_data', method='POST',
                                   body=[[{'name': 'interface', 'identifier': 'bond1'}],
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

        sysinfo = sysinfo if isinstance(sysinfo, dict) else {}
        return jsonify({
            'ok':       True,
            'pools':    pool_list,
            'alerts':   active_alerts,
            'network':  network,
            'uptime':   sysinfo.get('uptime_seconds', 0),
            'hostname': sysinfo.get('hostname', ''),
            'version':  sysinfo.get('version', ''),
        })
    except Exception as e:
        return jsonify({
            'error': ErrorCode.PARSE_EXCEPTION,
            'details': str(e),
            'pools_type': type(pools).__name__,
            'pools_sample': str(pools)[:300],
            'alerts_type': type(alerts).__name__,
            'sysinfo_type': type(sysinfo).__name__,
        }), 200


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
    # Accept either a full "name=value" string or a bare value (legacy)
    cookie_str = cookie_val if '=' in cookie_val else f'__Secure-session={cookie_val}'
    return {**OLLAMA_COM_HEADERS, 'cookie': cookie_str}


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

    # ollama.com now hosts its login flow on the signin.ollama.com subdomain
    # (WorkOS AuthKit). An expired/invalid cookie gets redirected there instead
    # of returning 401, so `requests` (which follows redirects) lands on a
    # different host. Checking the final host is robust to the sign-in page's
    # markup changing; the raw-text check is kept as a same-host fallback.
    landed_host = urlparse(r.url).hostname or ''
    if r.status_code == 401 or landed_host != 'ollama.com' or 'Sign in' in r.text:
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

            # Find reset time (data-time div is a sibling of the label/pct
            # row, not a descendant — both live under the same usage block)
            block = container.parent
            reset_tag = block.find(lambda tag: tag.has_attr('data-time')) if block else None
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
        if not debug_html_saved:
            with open('debug_ollama_fail.html', 'w') as f:
                f.write(html)
        soup2 = BeautifulSoup(html, 'html.parser')
        title = soup2.title.string if soup2.title else '(no title)'
        return jsonify({
            'error': ErrorCode.PARSE_FAILED,
            'hint': 'Could not find usage blocks in page.',
            'page_title': title,
            'page_snippet': html[:500],
        }), 200

    return jsonify({'ok': True, 'data': fields})




# ---------------------------------------------------------------------------
# UniFi Network (local UniFi OS API)
# ---------------------------------------------------------------------------

def _unifi_login(host, username, password):
    """Login to UniFi OS. Returns (session, csrf_token, api_prefix)."""
    s = http.Session()
    s.verify = False

    # UniFi OS (7+, UDM, UOS Server)
    r = s.post(f"{host}/api/auth/login",
               json={"username": username, "password": password},
               timeout=10, verify=False)
    if r.ok:
        try:
            body = r.json()
        except Exception:
            body = {}
        csrf = (body.get('csrf_token') or
                r.headers.get('X-Csrf-Token') or
                s.cookies.get('csrf_token', ''))
        return s, csrf, '/proxy/network'

    # Legacy UniFi Network Application (pre-7)
    r = s.post(f"{host}/api/login",
               json={"username": username, "password": password},
               timeout=10, verify=False)
    if not r.ok:
        raise Exception(f"Login failed (HTTP {r.status_code})")
    return s, '', ''


# Logging in on every single call (every 30s page poll + every 5min bg poll)
# was enough concurrent session churn to trip UniFi OS's login rate-limit,
# causing intermittent 401s. Cache one session per worker process and only
# re-login when it actually stops working.
_unifi_session_cache = {}
_unifi_session_lock = threading.Lock()


def _unifi_get(host, username, password, path):
    """GET an authenticated UniFi API path, reusing a cached session and
    re-logging in (once) only if the cached session has actually expired."""
    def do_request():
        with _unifi_session_lock:
            cached = _unifi_session_cache.get(host)
            if cached is None:
                session, csrf, prefix = _unifi_login(host, username, password)
                cached = {'session': session, 'csrf': csrf, 'prefix': prefix}
                _unifi_session_cache[host] = cached
        hdrs = {'X-Csrf-Token': cached['csrf']} if cached['csrf'] else {}
        return cached['session'].get(f"{host}{cached['prefix']}{path}", headers=hdrs, timeout=15, verify=False)

    r = do_request()
    if r.status_code in (401, 403):
        with _unifi_session_lock:
            _unifi_session_cache.pop(host, None)
        r = do_request()
    return r


@app.route('/api/unifi-status')
def api_unifi_status():
    host     = get_config(CONFIG_UNIFI_HOST, '')
    username = get_config(CONFIG_UNIFI_USERNAME, '')
    password = get_config(CONFIG_UNIFI_PASSWORD, '')
    site     = get_config(CONFIG_UNIFI_SITE, '') or 'default'

    if not all([host, username, password]):
        return jsonify({'error': ErrorCode.INCOMPLETE_CONFIG}), 200

    if not host.startswith('http'):
        host = f'https://{host}'

    try:
        r = _unifi_get(host, username, password, f"/api/s/{site}/stat/device")
        if not r.ok:
            return jsonify({'error': ErrorCode.API_ERROR, 'details': f"devices: HTTP {r.status_code}"}), 200
        devices_raw = r.json().get('data', [])

        r = _unifi_get(host, username, password, f"/api/s/{site}/stat/sta")
        clients_raw = r.json().get('data', []) if r.ok else []

        SKIP_FS = {'vfat', 'erofs', 'tmpfs', 'devtmpfs', 'squashfs', 'iso9660', 'zram'}

        devices = []
        for d in devices_raw:
            sys_stats = d.get('system-stats') or {}
            try: cpu = round(float(sys_stats.get('cpu', 0)), 1)
            except Exception: cpu = None
            try: mem = round(float(sys_stats.get('mem', 0)), 1)
            except Exception: mem = None

            device = {
                'id':      d.get('_id', ''),
                'name':    d.get('name') or d.get('hostname', 'Unknown'),
                'model':   d.get('model', ''),
                'type':    d.get('type', ''),
                'state':   d.get('state', 0),
                'uptime':  d.get('uptime', 0),
                'cpu':     cpu,
                'mem':     mem,
                'ip':      d.get('ip', ''),
                'version': d.get('version', ''),
                'num_sta': d.get('num_sta', 0),
            }

            if d.get('type') == 'uap':
                radio_map = {}
                for vap in (d.get('vap_table') or []):
                    radio = vap.get('radio', '')
                    if radio not in radio_map:
                        radio_map[radio] = {'radio': radio, 'num_sta': 0, 'channel': None}
                    radio_map[radio]['num_sta'] += vap.get('num_sta', 0)
                    if not radio_map[radio]['channel'] and vap.get('channel'):
                        radio_map[radio]['channel'] = vap['channel']
                if radio_map:
                    device['radios'] = list(radio_map.values())

            if d.get('type') == 'usw':
                ports = d.get('port_table') or []
                device['port_count'] = len(ports)
                device['ports_up'] = sum(1 for p in ports if p.get('up'))

            devices.append(device)

        clients = [
            {
                'mac':      c.get('mac', ''),
                'ip':       c.get('ip', ''),
                'name':     c.get('name') or c.get('hostname', ''),
                'is_wired': c.get('is_wired', False),
                'essid':    c.get('essid', ''),
                'signal':   c.get('signal'),
                'uptime':   c.get('uptime', 0),
                'rx_bytes': c.get('rx_bytes', 0),
                'tx_bytes': c.get('tx_bytes', 0),
                'vlan':     c.get('vlan'),
                'network':  c.get('network', ''),
            }
            for c in clients_raw
        ]

        return jsonify({
            'ok':               True,
            'devices':          devices,
            'clients':          clients,
            'total_clients':    len(clients_raw),
            'wired_clients':    sum(1 for c in clients_raw if c.get('is_wired')),
            'wireless_clients': sum(1 for c in clients_raw if not c.get('is_wired')),
        })
    except Exception as e:
        return jsonify({'error': ErrorCode.API_ERROR, 'details': str(e)}), 200


# ---------------------------------------------------------------------------
# WAN uptime poller — samples UniFi's live ping-monitor stats over time.
# UniFi doesn't store this history itself (only a live rolling window), so
# we poll and persist it ourselves to build a real uptime bar.
# ---------------------------------------------------------------------------

WAN_POLL_INTERVAL_S = 300  # 5 minutes


def _poll_wan_uptime_once():
    host     = get_config(CONFIG_UNIFI_HOST, '')
    username = get_config(CONFIG_UNIFI_USERNAME, '')
    password = get_config(CONFIG_UNIFI_PASSWORD, '')
    site     = get_config(CONFIG_UNIFI_SITE, '') or 'default'
    if not all([host, username, password]):
        return

    if not host.startswith('http'):
        host = f'https://{host}'

    r = _unifi_get(host, username, password, f"/api/s/{site}/stat/health")
    r.raise_for_status()

    wan_health = next((s for s in r.json().get('data', []) if s.get('subsystem') == 'wan'), None)
    if not wan_health:
        return

    now = int(time.time())
    for wan_key, stats in (wan_health.get('uptime_stats') or {}).items():
        availability = stats.get('availability')
        if availability is None:
            continue
        latencies = [m['latency_average'] for m in (stats.get('monitors') or [])
                     if m.get('latency_average') is not None]
        latency_ms = sum(latencies) / len(latencies) if latencies else None
        db.session.add(WanSample(ts=now, wan_key=wan_key, availability=availability, latency_ms=latency_ms))
    db.session.commit()


def _wan_poll_loop():
    while True:
        try:
            with app.app_context():
                _poll_wan_uptime_once()
        except Exception as e:
            print(f"[wan-poller] error: {e}")
        time.sleep(WAN_POLL_INTERVAL_S)


_wan_poller_lock_handle = None  # kept alive for the process lifetime — do not remove


def _start_wan_poller():
    """gunicorn runs multiple worker processes that each import this module;
    a non-blocking flock ensures only one of them actually polls, so we don't
    write duplicate/racing samples."""
    global _wan_poller_lock_handle
    lock_file = open('/data/.wan_poller.lock', 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return  # another worker already holds it
    _wan_poller_lock_handle = lock_file
    threading.Thread(target=_wan_poll_loop, daemon=True).start()


_start_wan_poller()


@app.route('/api/wan-uptime-history')
def api_wan_uptime_history():
    days = 1
    since = int(time.time()) - days * 86400
    samples = db.session.scalars(
        db.select(WanSample).where(WanSample.ts >= since).order_by(WanSample.ts)
    ).all()

    # Bucket into hourly blocks per WAN; a block's availability is the WORST
    # sample seen that hour, so brief outages aren't averaged away.
    buckets = {}
    for s in samples:
        hour_ts = s.ts - (s.ts % 3600)
        b = buckets.setdefault((s.wan_key, hour_ts), {'availability_min': s.availability, 'latencies': []})
        b['availability_min'] = min(b['availability_min'], s.availability)
        if s.latency_ms is not None:
            b['latencies'].append(s.latency_ms)

    wans = {}
    for (wan_key, hour_ts), b in buckets.items():
        wans.setdefault(wan_key, []).append({
            'ts':           hour_ts,
            'availability': round(b['availability_min'], 1),
            'latency_ms':   round(sum(b['latencies']) / len(b['latencies']), 1) if b['latencies'] else None,
        })
    for wan_key in wans:
        wans[wan_key].sort(key=lambda x: x['ts'])

    return jsonify({'ok': True, 'wans': wans, 'since': since, 'days': days})


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
