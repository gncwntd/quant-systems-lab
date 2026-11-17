'use strict';
const $ = id => document.getElementById(id);
let state = null, current = null, busy = false;
const number = (x, digits = 2) => x === null || x === undefined ? '—' : Number(x).toLocaleString('en-US', {maximumFractionDigits: digits, minimumFractionDigits: digits});
const money = x => x === null || x === undefined ? '—' : (x < 0 ? '−$' : '$') + number(Math.abs(x));
const percent = x => x === null || x === undefined ? '—' : number(x) + '%';
function node(tag, className, text) { const e = document.createElement(tag); if (className) e.className = className; if (text !== undefined) e.textContent = text; return e; }
function message(text, error = false) { $('message').textContent = text; $('message').className = 'message' + (error ? ' error' : ''); $('message').hidden = !text; }
function setBusy(value) { busy = value; $('run').disabled = value || !state?.dataset; $('fetch-ecb').disabled = value; $('data-file').disabled = value; $('run').textContent = value ? 'Processing…' : 'Run experiment →'; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed.');
  return result;
}
function cell(row, text, className) { const e = node('td', className, text); row.append(e); return e; }
function emptyTable(id, text, columns) { const row = node('tr'); const c = cell(row, text, 'empty-row'); c.colSpan = columns; $(id).replaceChildren(row); }
function checkpointList(items) {
  $('checkpoint-list').replaceChildren(...items.map(item => {
    const row = node('div', 'checkpoint'); row.append(node('span', 'checkpoint-id', item.id));
    const detail = node('div'); detail.append(node('div', 'checkpoint-title', item.title), node('div', 'checkpoint-status', item.status)); row.append(detail); return row;
  }));
}
async function refresh(loadLatest = false) {
  state = await api('/api/state');
  const d = state.dataset;
  $('chart-empty').querySelector('h3').textContent = d ? 'Run your first experiment' : 'Start with a dataset';
  $('chart-empty').querySelector('p').textContent = d ? 'Your daily observations are ready. Review the assumptions and run the reference strategy.' : 'Import daily EUR/USD observations, then run your first experiment.';
  $('source-summary').textContent = d ? `${d.source} · ${d.rows.toLocaleString()} observations · ${d.start} → ${d.end}` : 'No dataset loaded';
  $('source-kind').textContent = d ? (d.kind === 'reference_rate' ? 'REFERENCE RATES' : 'USER-SUPPLIED DAILY') : 'AWAITING DATA';
  $('data-quality').textContent = d ? `SHA ${d.sha256.slice(0, 12)} · max gap ${d.max_calendar_gap_days} calendar days. ${d.quality}` : '';
  checkpointList(state.checkpoints);
  $('run-count').textContent = `${state.runs.length}${state.runs.length === 50 ? '+' : ''} RUNS`;
  if (!state.runs.length) emptyTable('experiment-rows', 'No experiments yet.', 7);
  else $('experiment-rows').replaceChildren(...state.runs.map(run => {
    const row = node('tr'); cell(row, run.created.slice(0, 16).replace('T', ' ') + ' · ' + run.id.slice(0, 6));
    cell(row, `${run.config.fast} / ${run.config.slow}`);
    cell(row, percent(run.metrics.return_pct), run.metrics.return_pct >= 0 ? 'positive' : 'negative');
    cell(row, percent(run.metrics.max_drawdown_pct)); cell(row, String(run.metrics.trades)); cell(row, run.dataset_id.slice(0, 8));
    const button = node('button', 'text-button', 'Inspect →'); button.addEventListener('click', async () => { try { render(await api('/api/run?id=' + run.id)); } catch (e) { message(e.message, true); } }); cell(row, '').append(button); return row;
  }));
  setBusy(busy);
  if (loadLatest && d) {
    const latest = state.runs.find(run => run.dataset_id === d.sha256);
    if (latest) render(await api('/api/run?id=' + latest.id));
  }
}
function svg(tag, attrs, text) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs).forEach(([key, value]) => e.setAttribute(key, value));
  if (text !== undefined) e.textContent = text;
  return e;
}
function chart(run) {
  const target = $('equity-chart'); target.replaceChildren();
  const points = run.points, reference = run.benchmark.points;
  const values = points.map(p => p.equity).concat(reference.map(p => p.equity), [run.config.capital]);
  let lo = Math.min(...values), hi = Math.max(...values); const padding = Math.max((hi - lo) * .18, run.config.capital * .003); lo -= padding; hi += padding;
  const width = 860, height = 300, left = 66, right = 18, top = 16, bottom = 35;
  const x = i => left + i / Math.max(1, points.length - 1) * (width - left - right);
  const y = value => top + (hi - value) / (hi - lo) * (height - top - bottom);
  for (let i = 0; i <= 4; i++) {
    const value = lo + i / 4 * (hi - lo), py = y(value);
    target.append(svg('line', {x1: left, y1: py, x2: width - right, y2: py, stroke: '#e9eee2', 'stroke-dasharray': '3 5'}));
    target.append(svg('text', {x: left - 12, y: py + 3, 'text-anchor': 'end', fill: '#96a18c', 'font-size': 9, 'font-family': 'monospace'}, number(value, 0)));
  }
  [0, .25, .5, .75, 1].forEach(f => {
    const i = Math.round((points.length - 1) * f);
    target.append(svg('text', {x: x(i), y: height - 10, 'text-anchor': f === 0 ? 'start' : (f === 1 ? 'end' : 'middle'), fill: '#96a18c', 'font-size': 9, 'font-family': 'monospace'}, points[i].date));
  });
  const coordinates = series => series.map((p, i) => `${x(i)},${y(p.equity)}`).join(' ');
  target.append(svg('line', {x1: left, y1: y(run.config.capital), x2: width - right, y2: y(run.config.capital), stroke: '#aab7a0', 'stroke-dasharray': '5 5'}));
  target.append(svg('polygon', {points: `${left},${height - bottom} ${coordinates(points)} ${x(points.length - 1)},${height - bottom}`, fill: '#edf3e4', opacity: '.8'}));
  target.append(svg('polyline', {points: coordinates(reference), fill: 'none', stroke: '#c2b398', 'stroke-width': 1.6}));
  target.append(svg('polyline', {points: coordinates(points), fill: 'none', stroke: '#497849', 'stroke-width': 2.2, 'stroke-linejoin': 'round'}));
  $('chart-empty').hidden = true;
}
function render(run) {
  current = run; const m = run.metrics;
  Object.entries(run.config).forEach(([name, value]) => { const field = $('experiment-form').elements.namedItem(name); if (field) field.value = value; });
  if (state?.dataset && run.dataset_id !== state.dataset.sha256) message('Viewing an archived experiment from a different dataset. A new run will use the active dataset shown above.');
  $('return').textContent = percent(m.return_pct); $('return').className = m.return_pct >= 0 ? 'positive' : 'negative';
  $('pnl').textContent = `${money(m.net_pnl)} net · ${money(m.final_equity)} final equity`;
  $('drawdown').textContent = percent(m.max_drawdown_pct); $('sharpe').textContent = number(m.sharpe); $('trade-count').textContent = String(m.trades);
  $('costs').textContent = `${money(m.costs)} estimated total costs`;
  $('evaluation').textContent = `${run.evaluation_start} → ${run.evaluation_end} · ${run.points.length} observations · delayed execution`;
  $('chart-range').textContent = `RUN ${run.id.slice(0, 8)} · DATA ${run.dataset_id.slice(0, 8)}`;
  $('engine-state').textContent = m.halted ? '● Drawdown halt triggered' : '● Simulation completed';
  $('regime-label').textContent = run.regime.label; $('regime-detail').textContent = `${run.dataset.end} · latest dataset observation · ${run.regime.volatility_label || ''} volatility`;
  $('volatility').textContent = percent(run.regime.volatility_pct); $('sma-gap').textContent = percent(run.regime.gap_pct);
  const mc = run.monte_carlo;
  $('mc-loss').textContent = mc.available ? percent(mc.loss_probability_pct) : '—';
  $('mc-range').textContent = mc.available ? `${money(mc.final_p05)} / ${money(mc.final_p95)}` : '—';
  $('mc-breach').textContent = mc.available ? percent(mc.drawdown_breach_pct) : '—';
  $('mc-note').textContent = mc.available ? `${mc.paths} paths · ${mc.horizon_observations} observations · blocks of ${mc.block_size} · seed ${mc.seed}. Conditional historical resampling, not a forecast.` : mc.reason;
  $('assumptions').replaceChildren(...run.assumptions.map(text => node('li', '', text)));
  $('risk-events').replaceChildren(...run.events.map(event => node('p', '', `${event.date} · ${event.message}`)));
  if (!run.trades.length) emptyTable('trade-rows', 'No closed trades under this configuration.', 7);
  else $('trade-rows').replaceChildren(...run.trades.map(trade => {
    const row = node('tr'); cell(row, `${trade.entry_date} → ${trade.exit_date}`); cell(row, trade.side); cell(row, number(Math.abs(trade.units), 1));
    cell(row, `${number(trade.entry_price, 5)} / ${number(trade.exit_price, 5)}`); cell(row, money(trade.costs));
    cell(row, money(trade.net_pnl), trade.net_pnl >= 0 ? 'positive' : 'negative'); cell(row, trade.reason.replaceAll('_', ' ')); return row;
  }));
  $('export-json').disabled = false; $('export-csv').disabled = false; chart(run);
}
async function importAction(action) {
  if (busy) return;
  setBusy(true); message('Importing and validating daily observations…');
  try {
    const meta = await action(); await refresh(false);
    current = null; $('equity-chart').replaceChildren(); $('chart-empty').hidden = false;
    ['return', 'drawdown', 'sharpe', 'trade-count', 'volatility', 'sma-gap', 'mc-loss', 'mc-range', 'mc-breach'].forEach(id => { $(id).textContent = '—'; });
    $('return').className = ''; $('pnl').textContent = 'New dataset loaded; run an experiment.';
    $('costs').textContent = 'Includes estimated trading costs'; $('evaluation').textContent = 'No experiment selected for the new dataset.';
    $('chart-range').textContent = 'NO EXPERIMENT SELECTED'; $('regime-label').textContent = 'Awaiting experiment';
    $('regime-detail').textContent = 'A backward-looking trend and volatility summary.';
    $('mc-note').textContent = 'Conditional resampling of historical net returns. Not a forecast.';
    $('assumptions').replaceChildren(node('li', '', 'New dataset selected. Run an experiment to inspect its assumptions.'));
    $('export-json').disabled = true; $('export-csv').disabled = true;
    $('risk-events').replaceChildren(); emptyTable('trade-rows', 'Run an experiment to inspect its trades.', 7);
    message(`${meta.rows.toLocaleString()} observations imported. Choose settings and run an experiment.`);
  } catch (error) { message(error.message, true); }
  finally { setBusy(false); }
}
$('fetch-ecb').addEventListener('click', () => importAction(() => api('/api/fetch-ecb', {start: $('ecb-start').value, end: $('ecb-end').value})));
$('data-file').addEventListener('change', event => {
  const file = event.target.files[0]; if (!file) return;
  if (file.size > 5000000) { message('CSV limit is 5 MB.', true); return; }
  importAction(async () => api('/api/import', {name: file.name, csv: await file.text()}));
});
$('experiment-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy || !state?.dataset) return;
  const config = Object.fromEntries(new FormData(event.target).entries());
  setBusy(true); message('Running a cost-aware simulation and historical stress resampling…');
  try { render(await api('/api/backtest', {dataset_id: state.dataset.sha256, config})); await refresh(false); message('Experiment recorded. Inspect costs, assumptions and trade outcomes before drawing conclusions.'); }
  catch (error) { message(error.message, true); }
  finally { setBusy(false); }
});
$('export-json').addEventListener('click', () => { if (current) window.location.href = '/api/export?id=' + current.id; });
$('export-csv').addEventListener('click', () => { if (current) window.location.href = '/api/export?id=' + current.id + '&format=csv'; });
document.querySelectorAll('.nav').forEach(a => a.addEventListener('click', () => { document.querySelectorAll('.nav').forEach(n => n.classList.remove('active')); a.classList.add('active'); }));
refresh(true).catch(error => message('Could not reach the local API: ' + error.message, true));
