(() => {
  const sub = document.getElementById('codex-usage-sub');
  const bars = document.getElementById('codex-usage-bars');
  const daily = document.getElementById('codex-daily-usage');
  const count = new Intl.NumberFormat();
  let loading = false;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  function windowLabel(minutes) {
    if (!minutes) return 'Usage window';
    if (minutes % 1440 === 0) return `${minutes / 1440}-Day Window`;
    if (minutes % 60 === 0) return `${minutes / 60}-Hour Window`;
    return `${minutes}-Minute Window`;
  }
  function resetLabel(timestamp) {
    if (!timestamp) return '';
    const left = Math.ceil((timestamp * 1000 - Date.now()) / 60000);
    if (left <= 0) return 'Reset due — awaiting refresh';
    const days = Math.floor(left / 1440);
    const hours = Math.floor((left % 1440) / 60);
    const minutes = left % 60;
    return `Resets in ${days ? `${days}d ` : ''}${hours ? `${hours}h ` : ''}${minutes}m`;
  }
  function drawWindows(windows) {
    bars.replaceChildren();
    for (const item of windows) {
      const wrap = el('div', undefined, 'usage-bar-wrap');
      const label = `${item.name} · ${windowLabel(item.window_minutes)}`;
      const top = el('div', undefined, 'usage-bar-label');
      top.append(el('span', label), el('strong', `${item.used_percent}% used`));
      const track = el('div', undefined, 'usage-bar-track');
      track.setAttribute('role', 'progressbar');
      track.setAttribute('aria-label', label);
      track.setAttribute('aria-valuemin', '0');
      track.setAttribute('aria-valuemax', '100');
      track.setAttribute('aria-valuenow', String(item.used_percent));
      const fill = el('div', undefined, `usage-bar-fill ${item.used_percent > 85 ? 'danger' : item.used_percent > 60 ? 'warn' : ''}`);
      fill.style.width = `${item.used_percent}%`;
      track.append(fill);
      const reset = el('p', resetLabel(item.resets_at), 'codex-note');
      if (item.resets_at) reset.title = new Date(item.resets_at * 1000).toLocaleString();
      wrap.append(top, track, reset);
      bars.append(wrap);
    }
    if (!windows.length) bars.append(el('p', 'Usage limits are unavailable for this account.', 'codex-note'));
  }
  function drawDaily(buckets) {
    daily.replaceChildren();
    daily.append(el('h3', 'Daily tokens', 'codex-daily-title'));
    if (!buckets || !buckets.length) {
      daily.append(el('p', buckets ? 'No daily activity reported.' :
        'Daily history is unavailable for this account or Codex version.', 'codex-note'));
      return;
    }
    const total = buckets.reduce((sum, b) => sum + b.tokens, 0);
    daily.append(el('p', `${count.format(total)} tokens across ${buckets.length} reported days`, 'codex-note'));
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 600 140');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Daily token usage. Exact dates and counts are in the table below.');
    svg.classList.add('codex-daily-chart');
    const first = Date.parse(buckets[0].date);
    const last = Date.parse(buckets[buckets.length - 1].date);
    const days = Math.round((last - first) / 86400000) + 1;
    const step = 600 / days;
    const max = Math.max(1, ...buckets.map(b => b.tokens));
    for (const bucket of buckets) {
      const rect = document.createElementNS(svgNS, 'rect');
      const height = bucket.tokens / max * 130;
      rect.setAttribute('x', String((Date.parse(bucket.date) - first) / 86400000 * step + step * 0.15));
      rect.setAttribute('y', String(140 - height));
      rect.setAttribute('width', String(step * 0.7));
      rect.setAttribute('height', String(height));
      rect.setAttribute('rx', '2');
      const title = document.createElementNS(svgNS, 'title');
      title.textContent = `${bucket.date}: ${count.format(bucket.tokens)} tokens`;
      rect.append(title);
      svg.append(rect);
    }
    const axis = el('div', undefined, 'codex-chart-axis');
    axis.append(el('span', buckets[0].date), el('span', buckets[buckets.length - 1].date));
    const details = el('details');
    details.append(el('summary', 'View daily values'));
    const table = el('table', undefined, 'codex-daily-table');
    const head = el('thead');
    const heading = el('tr');
    for (const text of ['Date', 'Tokens']) {
      const th = el('th', text); th.scope = 'col'; heading.append(th);
    }
    head.append(heading);
    const body = el('tbody');
    for (const bucket of buckets) {
      const row = el('tr');
      row.append(el('td', bucket.date), el('td', count.format(bucket.tokens)));
      body.append(row);
    }
    table.append(head, body);
    details.append(table);
    daily.append(svg, axis, details);
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    try {
      const response = await fetch('/api/codex-usage', {signal: AbortSignal.timeout(55000)});
      if (!response.ok) throw new Error('request_failed');
      const data = await response.json();
      if (data.error) {
        const messages = {
          login_required: 'Connect your ChatGPT account in Settings.',
          chatgpt_required: 'Sign in with ChatGPT to see subscription usage.',
          not_installed: 'Update the Stats image to enable Codex.',
          storage_unavailable: 'Codex storage is unavailable.',
          unavailable: 'Unable to refresh. Check your Codex login in Settings.'
        };
        sub.textContent = 'not connected';
        bars.replaceChildren(el('p', messages[data.error] || 'Usage unavailable.', 'codex-note'));
        const link = el('a', 'Codex setup →', 'setup-link');
        link.href = '/settings#codex';
        bars.append(link);
        daily.replaceChildren();
        return;
      }
      sub.textContent = `${data.stale ? 'Stale · last updated' : 'Updated'} ${new Date(data.updated_at * 1000).toLocaleTimeString()}`;
      drawWindows(data.windows);
      drawDaily(data.daily);
    } catch (_) {
      sub.textContent = 'Refresh failed · displayed data may be stale';
    } finally {
      loading = false;
    }
  }
  refresh();
  setInterval(refresh, 60000);
})();
