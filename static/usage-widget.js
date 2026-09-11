(function () {
  const REFRESH_MS = 60_000;

  const liveSub = document.getElementById('live-usage-sub');
  const liveBars = document.getElementById('live-usage-bars');
  const ollamaSub = document.getElementById('ollama-usage-sub');
  const ollamaBars = document.getElementById('ollama-usage-bars');
  const geminiSub = document.getElementById('gemini-usage-sub');
  const geminiBars = document.getElementById('gemini-usage-bars');

  function setupLink(id, label, href) {
    const link = document.createElement('a');
    link.className = 'setup-link';
    link.href = href;
    link.textContent = label;
    return link;
  }

  async function loadClaude() {
    liveSub.textContent = 'loading…';
    liveBars.innerHTML = '';

    try {
      const res = await fetch('/api/claude-usage');
      const data = await res.json();
      if (data.error === 'no_cookie') {
        liveSub.textContent = 'no session cookie';
        liveBars.append(setupLink('/settings', 'Configure Claude.ai →'));
        return;
      }
      if (data.error === 'auth_failed') {
        liveSub.textContent = 'session expired';
        liveBars.append(setupLink('/settings', 'Update cookie →'));
        return;
      }
      if (data.error) {
        liveSub.textContent = 'error: ' + data.error;
        return;
      }

      liveSub.textContent = 'live';
      const usage = data.usage;
      const labels = {
        five_hour: '5-Hour Window',
        seven_day: '7-Day Window',
        extra_usage: 'Extra Usage',
      };
      const fields = Object.entries(usage)
        .map(([key, value]) => {
          if (!value || value.utilization == null) return null;
          const pct = Math.round(value.utilization);
          const resetStr = value.resets_at
            ? `resets ${new Date(value.resets_at).toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}`
            : '';
          return { label: labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()), pct, resetStr };
        })
        .filter(Boolean);

      if (!fields.length) {
        liveBars.innerHTML = '<p style="font-size:.8rem;color:#718096">No usage data available.</p>';
        return;
      }

      liveBars.innerHTML = fields
        .map(
          (f) => `
            <div class="usage-bar-wrap">
              <div class="usage-bar-label">
                <span>${f.label}</span>
                <span class="usage-pct-right">
                  <strong>${f.pct}%</strong>
                  ${f.resetStr ? `<span style="color:#4a5568;margin-left:.5rem">${f.resetStr}</span>` : ''}
                </span>
              </div>
              <div class="usage-bar-track">
                <div class="usage-bar-fill ${f.pct > 85 ? 'danger' : f.pct > 60 ? 'warn' : ''}"
                     style="width:${Math.min(f.pct, 100)}%"></div>
              </div>
            </div>`
        )
        .join('');
    } catch (e) {
      liveSub.textContent = 'error: ' + e.message;
    }
  }

  async function loadOllama() {
    ollamaSub.textContent = 'loading…';
    ollamaBars.innerHTML = '';
    try {
      const res = await fetch('/api/ollama-com-usage');
      const data = await res.json();
      if (data.error === 'no_cookie') {
        ollamaSub.textContent = 'no session cookie';
        ollamaBars.append(setupLink('/settings', 'Configure Ollama.com →'));
        return;
      }
      if (data.error === 'auth_failed') {
        ollamaSub.textContent = 'session expired';
        ollamaBars.append(setupLink('/settings', 'Update cookie →'));
        return;
      }
      if (data.error) {
        ollamaSub.textContent = 'error: ' + data.error;
        return;
      }

      ollamaSub.textContent = 'live';
      const usage = data.data;
      if (!Array.isArray(usage) || !usage.length) {
        ollamaBars.innerHTML = '<p style="font-size:.8rem;color:#718096">No usage data found.</p>';
        return;
      }

      ollamaBars.innerHTML = usage
        .filter((item) => item && item.pct != null)
        .map(
          (f) => `
            <div class="usage-bar-wrap">
              <div class="usage-bar-label">
                <span>${f.label}</span>
                <span class="usage-pct-right">
                  <strong>${f.pct}%</strong>
                  ${f.resets_at ? `<span style="color:#4a5568;margin-left:.5rem">resets ${new Date(f.resets_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>` : ''}
                </span>
              </div>
              <div class="usage-bar-track">
                <div class="usage-bar-fill ${f.pct > 85 ? 'danger' : f.pct > 60 ? 'warn' : ''}"
                     style="width:${Math.min(f.pct, 100)}%"></div>
              </div>
            </div>`
        )
        .join('');
    } catch (e) {
      ollamaSub.textContent = 'error: ' + e.message;
    }
  }

  async function loadGemini() {
    geminiSub.textContent = 'loading…';
    geminiBars.innerHTML = '';
    try {
      const res = await fetch('/api/gemini-usage');
      const data = await res.json();
      if (data.error === 'no_config') {
        geminiSub.textContent = 'not configured';
        geminiBars.append(setupLink('/settings', 'Configure Gemini →'));
        return;
      }
      if (data.error) {
        geminiSub.textContent = 'error: ' + data.error;
        return;
      }

      geminiSub.textContent = 'last 24h';
      const quotas = data.data || [];
      if (!quotas.length) {
        geminiBars.innerHTML = '<p style="font-size:.8rem;color:#718096">No usage data found.</p>';
        return;
      }

      geminiBars.innerHTML = quotas
        .map(
          (q) => `
            <div class="usage-bar-wrap">
              <div class="usage-bar-label">
                <span>${q.label}</span>
                <span class="usage-pct-right">
                  <strong>${q.usage.toLocaleString()}</strong>
                </span>
              </div>
              <div class="usage-bar-track">
                <div class="usage-bar-fill" style="width:100%; opacity:0.3;"></div>
              </div>
            </div>`
        )
        .join('');
    } catch (e) {
      geminiSub.textContent = 'error: ' + e.message;
    }
  }

  async function refresh() {
    await Promise.all([loadClaude(), loadOllama(), loadGemini()]);
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
})();
