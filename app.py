from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import requests as http
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

PLATFORMS = ['Claude / Anthropic', 'Ollama']

MODELS = {
    'Claude / Anthropic': [
        'claude-opus-4-6',
        'claude-sonnet-4-6',
        'claude-haiku-4-5',
        'claude-3-5-sonnet',
        'claude-3-opus',
        'Other',
    ],
    'Ollama': [
        'llama3',
        'llama3.1',
        'llama3.2',
        'mistral',
        'phi3',
        'gemma2',
        'qwen2.5',
        'deepseek-r1',
        'Other',
    ],
}

# Cost per 1M tokens (input, output) in USD
COSTS = {
    'claude-opus-4-6':   (15.00, 75.00),
    'claude-sonnet-4-6': (3.00,  15.00),
    'claude-haiku-4-5':  (0.80,  4.00),
    'claude-3-5-sonnet': (3.00,  15.00),
    'claude-3-opus':     (15.00, 75.00),
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class UsageEntry(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    platform      = db.Column(db.String(64),  nullable=False)
    model         = db.Column(db.String(128), nullable=False)
    input_tokens  = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    cost_usd      = db.Column(db.Float,   default=0.0)
    note          = db.Column(db.Text,    default='')
    source        = db.Column(db.String(32), default='manual')  # manual | anthropic_api | ollama_proxy
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


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


def calc_cost(model, input_tokens, output_tokens):
    if model in COSTS:
        in_r, out_r = COSTS[model]
        return round((input_tokens * in_r + output_tokens * out_r) / 1_000_000, 6)
    return 0.0


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    entries = UsageEntry.query.order_by(UsageEntry.created_at.desc()).all()

    stats = {}
    for p in PLATFORMS:
        pe = [e for e in entries if e.platform == p]
        stats[p] = {
            'count':         len(pe),
            'input_tokens':  sum(e.input_tokens for e in pe),
            'output_tokens': sum(e.output_tokens for e in pe),
            'cost_usd':      round(sum(e.cost_usd for e in pe), 4),
        }

    total = {
        'count':         len(entries),
        'input_tokens':  sum(e.input_tokens for e in entries),
        'output_tokens': sum(e.output_tokens for e in entries),
        'cost_usd':      round(sum(e.cost_usd for e in entries), 4),
    }

    return render_template('index.html', entries=entries, stats=stats, total=total, platforms=PLATFORMS)


# ---------------------------------------------------------------------------
# Manual log
# ---------------------------------------------------------------------------

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        platform      = request.form['platform']
        model         = request.form['model']
        if model == 'Other':
            model = request.form.get('model_custom', 'Other').strip() or 'Other'
        input_tokens  = int(request.form.get('input_tokens') or 0)
        output_tokens = int(request.form.get('output_tokens') or 0)
        note          = request.form.get('note', '')
        cost          = calc_cost(model, input_tokens, output_tokens)

        manual_cost = request.form.get('cost_usd', '').strip()
        if manual_cost:
            try:
                cost = float(manual_cost)
            except ValueError:
                pass

        db.session.add(UsageEntry(
            platform=platform, model=model,
            input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost, note=note, source='manual',
        ))
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('add.html', platforms=PLATFORMS, models=MODELS)


@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete(entry_id):
    entry = db.get_or_404(UsageEntry, entry_id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        new_key    = request.form.get('anthropic_admin_key', '').strip()
        ollama_url = request.form.get('ollama_url', 'http://localhost:11434').strip()
        if new_key:
            set_config('anthropic_admin_key', new_key)
        set_config('ollama_url', ollama_url or 'http://localhost:11434')
        return redirect(url_for('settings'))

    raw_key    = get_config('anthropic_admin_key', '')
    masked_key = (raw_key[:12] + '…' + raw_key[-4:]) if len(raw_key) > 16 else ('*' * len(raw_key))
    ollama_url = get_config('ollama_url', 'http://localhost:11434')
    return render_template('settings.html',
                           masked_key=masked_key,
                           has_key=bool(raw_key),
                           ollama_url=ollama_url)


# ---------------------------------------------------------------------------
# Sync page + Anthropic sync endpoint
# ---------------------------------------------------------------------------

@app.route('/sync')
def sync():
    return render_template('sync.html')


@app.route('/sync/anthropic', methods=['POST'])
def sync_anthropic():
    api_key = get_config('anthropic_admin_key', '')
    if not api_key:
        return jsonify({'error': 'No Anthropic admin API key — go to Settings first.'}), 400

    days = int((request.json or {}).get('days', 30))
    now  = datetime.now(timezone.utc)
    starting_at = (now - timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z')
    ending_at   = now.strftime('%Y-%m-%dT%H:%M:%SZ')

    try:
        resp = http.get(
            'https://api.anthropic.com/v1/organizations/usage_report/messages',
            headers={
                'anthropic-version': '2023-06-01',
                'x-api-key': api_key,
            },
            params={
                'starting_at':  starting_at,
                'ending_at':    ending_at,
                'bucket_width': '1d',
                'group_by[]':   'model',
            },
            timeout=30,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 502

    if not resp.ok:
        return jsonify({'error': f'Anthropic API {resp.status_code}: {resp.text}'}), 502

    data    = resp.json()
    added   = 0
    skipped = 0

    # Flatten nested or flat bucket formats
    buckets = []
    for item in data.get('data', []):
        if 'buckets' in item:
            buckets.extend(item['buckets'])
        else:
            buckets.append(item)

    for bucket in buckets:
        start_str = bucket.get('start_time') or bucket.get('date', '')
        try:
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except (ValueError, AttributeError):
            continue

        model         = bucket.get('model', 'unknown')
        input_tokens  = (bucket.get('input_tokens', 0)
                         + bucket.get('cache_creation_input_tokens', 0)
                         + bucket.get('cache_read_input_tokens', 0))
        output_tokens = bucket.get('output_tokens', 0)

        exists = UsageEntry.query.filter_by(
            source='anthropic_api', model=model, created_at=start_dt
        ).first()

        if not exists:
            db.session.add(UsageEntry(
                platform='Claude / Anthropic',
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=calc_cost(model, input_tokens, output_tokens),
                source='anthropic_api',
                created_at=start_dt,
            ))
            added += 1
        else:
            skipped += 1

    db.session.commit()
    return jsonify({'added': added, 'skipped': skipped})


# ---------------------------------------------------------------------------
# Ollama proxy — point your apps at /proxy/ollama instead of :11434
# ---------------------------------------------------------------------------

SKIP_HEADERS = {'host', 'content-length', 'transfer-encoding', 'connection'}


@app.route('/proxy/ollama/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_ollama(path):
    ollama_url = get_config('ollama_url', 'http://localhost:11434')
    target     = f"{ollama_url}/{path}"
    body       = request.get_json(silent=True) or {}
    is_stream  = body.get('stream', path in ('api/generate', 'api/chat'))
    fwd_hdrs   = {k: v for k, v in request.headers if k.lower() not in SKIP_HEADERS}

    if is_stream:
        def generate():
            last = {}
            try:
                with http.request(
                    method=request.method, url=target,
                    json=body, headers=fwd_hdrs, stream=True, timeout=120,
                ) as r:
                    for line in r.iter_lines():
                        if line:
                            yield line + b'\n'
                            try:
                                last = json.loads(line)
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                yield (json.dumps({'error': str(e)}) + '\n').encode()
                return

            in_tok  = last.get('prompt_eval_count', 0)
            out_tok = last.get('eval_count', 0)
            model   = last.get('model') or body.get('model', 'unknown')
            if in_tok or out_tok:
                db.session.add(UsageEntry(
                    platform='Ollama', model=model,
                    input_tokens=in_tok, output_tokens=out_tok,
                    cost_usd=0.0, source='ollama_proxy',
                ))
                db.session.commit()

        return Response(stream_with_context(generate()), content_type='application/x-ndjson')

    try:
        r    = http.request(method=request.method, url=target,
                            json=body, headers=fwd_hdrs, timeout=120)
        data = r.json()
    except Exception as e:
        return jsonify({'error': str(e)}), 502

    in_tok  = data.get('prompt_eval_count', 0)
    out_tok = data.get('eval_count', 0)
    model   = data.get('model') or body.get('model', 'unknown')
    if in_tok or out_tok:
        db.session.add(UsageEntry(
            platform='Ollama', model=model,
            input_tokens=in_tok, output_tokens=out_tok,
            cost_usd=0.0, source='ollama_proxy',
        ))
        db.session.commit()

    return jsonify(data), r.status_code


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

@app.route('/api/models/<platform>')
def api_models(platform):
    return jsonify(MODELS.get(platform, []))


if __name__ == '__main__':
    app.run(debug=True)
