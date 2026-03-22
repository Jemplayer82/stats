from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

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

# Cost per 1M tokens in USD (input, output)
COSTS = {
    'claude-opus-4-6':    (15.00, 75.00),
    'claude-sonnet-4-6':  (3.00,  15.00),
    'claude-haiku-4-5':   (0.80,  4.00),
    'claude-3-5-sonnet':  (3.00,  15.00),
    'claude-3-opus':      (15.00, 75.00),
}


class UsageEntry(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    platform     = db.Column(db.String(64), nullable=False)
    model        = db.Column(db.String(128), nullable=False)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens= db.Column(db.Integer, default=0)
    cost_usd     = db.Column(db.Float, default=0.0)
    note         = db.Column(db.Text, default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':            self.id,
            'platform':      self.platform,
            'model':         self.model,
            'input_tokens':  self.input_tokens,
            'output_tokens': self.output_tokens,
            'cost_usd':      self.cost_usd,
            'note':          self.note,
            'created_at':    self.created_at.strftime('%Y-%m-%d %H:%M'),
        }


def calc_cost(model, input_tokens, output_tokens):
    if model in COSTS:
        in_rate, out_rate = COSTS[model]
        return round((input_tokens * in_rate + output_tokens * out_rate) / 1_000_000, 6)
    return 0.0


with app.app_context():
    db.create_all()


@app.route('/')
def index():
    entries = UsageEntry.query.order_by(UsageEntry.created_at.desc()).all()

    stats = {}
    for p in PLATFORMS:
        platform_entries = [e for e in entries if e.platform == p]
        stats[p] = {
            'count':         len(platform_entries),
            'input_tokens':  sum(e.input_tokens for e in platform_entries),
            'output_tokens': sum(e.output_tokens for e in platform_entries),
            'cost_usd':      round(sum(e.cost_usd for e in platform_entries), 4),
        }

    total = {
        'count':         len(entries),
        'input_tokens':  sum(e.input_tokens for e in entries),
        'output_tokens': sum(e.output_tokens for e in entries),
        'cost_usd':      round(sum(e.cost_usd for e in entries), 4),
    }

    return render_template('index.html', entries=entries, stats=stats, total=total, platforms=PLATFORMS)


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

        cost = calc_cost(model, input_tokens, output_tokens)
        # Allow manual cost override
        manual_cost = request.form.get('cost_usd', '').strip()
        if manual_cost:
            try:
                cost = float(manual_cost)
            except ValueError:
                pass

        entry = UsageEntry(
            platform=platform,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            note=note,
        )
        db.session.add(entry)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('add.html', platforms=PLATFORMS, models=MODELS)


@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete(entry_id):
    entry = db.get_or_404(UsageEntry, entry_id)
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/api/models/<platform>')
def api_models(platform):
    return jsonify(MODELS.get(platform, []))


if __name__ == '__main__':
    app.run(debug=True)
