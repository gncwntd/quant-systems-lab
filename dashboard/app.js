'use strict';
const $ = id => document.getElementById(id);
let state = null, current = null, busy = false;
const number = (x, digits = 2) => x === null || x === undefined ? '—' : Number(x).toLocaleString('en-US', {maximumFractionDigits: digits, minimumFractionDigits: digits});
const money = x => x === null || x === undefined ? '—' : (x < 0 ? '−$' : '$') + number(Math.abs(x));
const percent = x => x === null || x === undefined ? '—' : number(x) + '%';
function node(tag, className, text) { const e = document.createElement(tag); if (className) e.className = className; if (text !== undefined) e.textContent = text; return e; }
function message(text, error = false) { $('message').textContent = text; $('message').className = 'message' + (error ? ' error' : ''); $('message').hidden = !text; }
function setBusy(value) { busy = value; $('run').disabled = value || !state?.dataset; $('fetch-ecb').disabled = value; $('data-file').disabled = value; $('run').textContent = value ? 'Processing…' : 'Run experiment →'; }
async function api(path, body, signal) {
  const response = await fetch(path, {...(body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}), signal});
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
  $('source-kind').textContent = d ? ({reference_rate:'REFERENCE RATES', mt5_demo_daily:'MT5 DEMO D1'}[d.kind] || 'USER-SUPPLIED DAILY') : 'AWAITING DATA';
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

async function refreshQuotes() {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3000);
  try {
    const snapshot = await api('/api/quotes', undefined, controller.signal);
    $('quote-source').textContent = `${snapshot.source} · EUR/USD`;
    $('quote-status').textContent = snapshot.status.toUpperCase();
    $('quote-status').className = snapshot.status === 'fresh' ? 'tag positive' : 'tag muted';
    const q = snapshot.quote;
    $('quote-bid').textContent = q ? number(q.bid, q.digits) : '—';
    $('quote-ask').textContent = q ? number(q.ask, q.digits) : '—';
    $('quote-spread').textContent = q ? number(q.spread_pips, 2) : '—';
    $('quote-age').textContent = q ? `${number(q.quote_age_seconds, 1)} s` : '—';
    $('quote-reason').textContent = snapshot.reason;
    $('quote-clock').textContent = q ? `Observed ${new Date(q.heartbeat_utc * 1000).toISOString().replace('T', ' ')} · quote age uses the MT5 server-clock estimate. No tick archive.` : snapshot.note;
    $('quote-bid').closest('.quote-grid').classList.toggle('quote-inactive', snapshot.status !== 'fresh');
  } catch {
    $('quote-status').textContent = 'OFFLINE';
    ['quote-bid', 'quote-ask', 'quote-spread', 'quote-age'].forEach(id => { $(id).textContent = '—'; });
    $('quote-reason').textContent = 'Local quote API unavailable; reconnecting.';
    $('quote-clock').textContent = 'One-second snapshots. Separate from daily reference-rate backtests.';
  } finally {
    window.clearTimeout(timeout);
    window.setTimeout(refreshQuotes, 1000);
  }
}
refreshQuotes();

let paperCurrent = null, paperBusy = false;
const utcTime = seconds => new Date(seconds * 1000).toISOString().slice(0, 19).replace('T', ' ');
function paperCandles(state) {
  const target = $('paper-candles'); target.replaceChildren();
  const bars = state.candles.concat(state.candle ? [state.candle] : []).slice(-40);
  if (!bars.length) {
    target.append(svg('text', {x: 430, y: 85, 'text-anchor': 'middle', fill: '#8b977f', 'font-size': 12}, 'Waiting for sampled minute candles'));
    return;
  }
  let lo = Math.min(...bars.map(b => b.low)), hi = Math.max(...bars.map(b => b.high));
  const pad = Math.max((hi - lo) * .2, .00005); lo -= pad; hi += pad;
  const x = i => 75 + (i + .5) * 760 / bars.length;
  const y = price => 12 + (hi - price) / (hi - lo) * 125;
  [0, .5, 1].forEach(f => {
    const value = lo + (hi-lo)*f;
    target.append(svg('line', {x1: 65, y1: y(value), x2: 845, y2: y(value), stroke: '#e9eee2'}));
    target.append(svg('text', {x: 57, y: y(value)+3, 'text-anchor': 'end', fill: '#8b977f', 'font-size': 10}, number(value, 5)));
  });
  bars.forEach((bar, i) => {
    const color = bar.close >= bar.open ? '#507f47' : '#b76651';
    const opacity = bar.complete ? 1 : .4;
    target.append(svg('line', {x1: x(i), x2: x(i), y1: y(bar.high), y2: y(bar.low), stroke: color, opacity}));
    const width = Math.min(12, 520 / bars.length);
    const candle = svg('rect', {x: x(i)-width/2, y: Math.min(y(bar.open), y(bar.close)), width,
      height: Math.max(1.5, Math.abs(y(bar.open)-y(bar.close))), fill: color, opacity});
    candle.append(svg('title', {}, `${utcTime(bar.server_minute)} raw server clock · sampled midpoint O ${number(bar.open,5)} H ${number(bar.high,5)} L ${number(bar.low,5)} C ${number(bar.close,5)} · ${bar.samples} samples · ${bar.complete ? 'complete' : 'partial / forming'}`));
    target.append(candle);
  });
  target.append(svg('text', {x: 75, y: 162, fill: '#8b977f', 'font-size': 9}, `${utcTime(bars[0].server_minute).slice(11,16)} → ${utcTime(bars.at(-1).server_minute).slice(11,16)} · RAW MT5 SERVER CLOCK · sampled midpoint OHLC · pale = partial / forming`));
}
function renderPaper(state) {
  paperCurrent = state;
  const cfg = state.config;
  $('paper-config').textContent = `Sampled M1 · SMA ${cfg.fast} / ${cfg.slow} · long / cash · ${number(cfg.units,0)} EUR · ${cfg.max_spread_pips} pip entry limit · ${cfg.max_drawdown_pct}% drawdown halt`;
  const status = state.worker_status !== 'running' ? `WORKER ${state.worker_status.toUpperCase()}` :
    state.feed !== 'fresh' ? state.feed.toUpperCase() : state.halted ? 'HALTED' : !state.enabled ? 'ENTRIES PAUSED' : state.signal;
  $('paper-status').textContent = status;
  $('paper-status').className = state.valuation_current ? 'tag positive' : 'tag muted';
  $('paper-equity').textContent = money(state.equity);
  $('paper-pnl').textContent = money(state.net_pnl);
  $('paper-pnl').className = state.net_pnl >= 0 ? 'positive' : 'negative';
  $('paper-position').textContent = state.position ? `LONG ${number(state.position.units,0)}` : 'FLAT';
  $('paper-entry').textContent = state.position ? `Entry ${number(state.position.price,5)} · ${utcTime(state.position.observed_utc)} UTC` : '';
  $('paper-signal').textContent = state.signal;
  $('paper-warmup').textContent = `${state.closes.length} / ${cfg.slow} complete M1 candles · session ${state.id.slice(0,8)}`;
  $('paper-reason').textContent = state.reason;
  $('paper-valuation').textContent = `${state.valuation_current ? 'Current estimated liquidation value' : 'LAST ESTIMATE · price/worker is not current'}${state.last_observed_utc ? ' · observed '+utcTime(state.last_observed_utc)+' UTC' : ' · awaiting first sample'}. Realized ${money(state.realized_pnl)} · open net ${money(state.unrealized_pnl)}.`;
  $('paper').classList.toggle('paper-inactive', !state.valuation_current);
  $('paper-stats').textContent = `${state.observations.toLocaleString()} accepted samples · ${state.retained_samples.toLocaleString()} retained (limit 10,000) · ${state.gaps} gaps · ${state.closed_count} closed trades · ${number(state.max_drawdown_pct,3)}% max drawdown · fees paid ${money(state.fees)} · slippage included ${money(state.slippage)}. Model: ${cfg.slippage_pips} pip + ${cfg.commission_bps} bps / side; observed spread already in fills.`;
  $('paper-toggle').textContent = state.enabled ? 'Pause entries' : 'Resume entries';
  $('paper-toggle').disabled = paperBusy || state.halted || state.worker_status !== 'running';
  $('paper-export').disabled = false;
  if (!state.trades.length) emptyTable('paper-trades', state.position ? 'Virtual position is open. Closed-trade results appear after a strategy or risk exit.' : state.signal === 'WARMUP' ? 'No closed virtual trades yet. Collecting complete candles for warm-up.' : 'No closed virtual trades yet. Waiting for an eligible entry.', 5);
  else $('paper-trades').replaceChildren(...state.trades.slice(-8).reverse().map(trade => {
    const row = node('tr'); cell(row, `${utcTime(trade.entry_utc)} → ${utcTime(trade.exit_utc)}`);
    cell(row, number(trade.units,0)); cell(row, `${number(trade.entry_price,5)} / ${number(trade.exit_price,5)}`);
    cell(row, money(trade.net_pnl), trade.net_pnl >= 0 ? 'positive' : 'negative'); cell(row, trade.reason.replaceAll('_',' ')); return row;
  }));
  const event = state.events.at(-1);
  $('paper-event').textContent = event ? `Latest event · ${utcTime(event.observed_utc)} UTC · ${event.message}` : 'No strategy events yet.';
  paperCandles(state);
}
async function refreshPaper() {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3000);
  try { renderPaper(await api('/api/paper', undefined, controller.signal)); }
  catch {
    $('paper-status').textContent = 'WORKER UNREACHABLE';
    $('paper').classList.add('paper-inactive');
    $('paper-reason').textContent = 'Local simulation API unavailable. Displayed values are frozen estimates.';
    $('paper-toggle').disabled = true;
    $('paper-valuation').textContent = 'LAST ESTIMATE · waiting for the simulation API.';
  } finally { window.clearTimeout(timeout); window.setTimeout(refreshPaper, 2000); }
}
$('paper-toggle').addEventListener('click', async () => {
  if (!paperCurrent || paperBusy) return;
  paperBusy = true; $('paper-toggle').disabled = true;
  try { renderPaper(await api('/api/paper/control', {enabled: !paperCurrent.enabled})); }
  catch (error) { message('Paper control failed: '+error.message, true); }
  finally { paperBusy = false; if (paperCurrent) renderPaper(paperCurrent); }
});
$('paper-export').addEventListener('click', () => { window.location.href = '/api/paper/export'; });
refreshPaper();

let journalData = null, journalBefore = 0, journalLoading = false, journalGeneration = 0, journalController = null;
function renderJournal(report) {
  journalData = report;
  const check = report.reconciliation;
  $('journal-caption').textContent = `Session ${report.session.id.slice(0,8)} · ${report.session.source || 'awaiting source'} · engine ${report.session.engine_sha256.slice(0,10)}`;
  const labels = {passed:'FILLS RECONCILED', initial_balance:'INITIAL BALANCE ONLY', mismatch:'ACCOUNTING MISMATCH', invalid_audit:'INVALID AUDIT'};
  $('journal-status').textContent = labels[check.status] || 'UNKNOWN';
  $('journal-status').className = check.status === 'passed' ? 'tag positive' : 'tag muted';
  $('journal-check').textContent = check.status === 'initial_balance' ? 'Initial cash matches; no fills to verify yet.' : check.status === 'passed' ? `${check.entries_checked} ${check.entries_checked === 1 ? 'entry' : 'entries'} and ${check.exits_checked} ${check.exits_checked === 1 ? 'exit' : 'exits'} reconcile.` : 'Accounting check needs inspection.';
  $('journal-check').className = ['mismatch','invalid_audit'].includes(check.status) ? 'negative' : '';
  const journalMark = report.account.last_observed_utc ? `As of ${utcTime(report.account.last_observed_utc)} UTC` : 'Awaiting first price';
  $('journal-check-detail').textContent = check.errors.length ? check.errors.join(' ') : `${journalMark} · rebuilt cash ${money(check.expected.cash)} · realized ${money(check.expected.realized_pnl)} · open net ${money(check.expected.unrealized_pnl)} · fees paid ${money(check.expected.fees)}. Journal refreshes every 10 seconds.`;
  $('journal-page').textContent = `${report.total_records} total events · ${report.filtered_records} match filter · showing ${report.records.length} · cutoff #${report.audit_through_id} · ${journalBefore ? 'Older page; refresh latest to follow new events.' : 'Latest page follows every 10 seconds.'}`;
  $('journal-jsonl').disabled = false; $('journal-csv').disabled = false;
  if (!report.records.length) emptyTable('journal-rows', 'No events match this filter.', 4);
  else $('journal-rows').replaceChildren(...report.records.map(rowData => {
    const event = rowData.event, row = node('tr');
    cell(row, `#${rowData.id} · ${event.observed_utc ? utcTime(event.observed_utc) : 'Unknown time'}`);
    cell(row, event.kind.toUpperCase());
    cell(row, `${event.message || ''}${event.signal ? ' '+event.signal : ''}`, 'journal-message');
    const inspect = node('button','text-button','Inspect');
    inspect.addEventListener('click', () => { $('journal-detail').textContent = JSON.stringify(rowData,null,2); $('journal-detail').hidden = false; });
    cell(row,'').append(inspect);
    return row;
  }));
}
async function loadJournal(before = 0) {
  const generation = ++journalGeneration;
  journalController?.abort();
  const controller = new AbortController(); journalController = controller;
  const timeout = window.setTimeout(() => controller.abort(), 5000);
  journalLoading = true; journalBefore = before;
  $('journal-refresh').disabled = true; $('journal-older').disabled = true;
  const params = new URLSearchParams({before:String(before), limit:'25', kind:$('journal-filter').value});
  try {
    const report = await api('/api/paper/journal?'+params, undefined, controller.signal);
    if (generation === journalGeneration) renderJournal(report);
  } catch {
    if (generation === journalGeneration) {
      $('journal-status').textContent = 'JOURNAL UNAVAILABLE';
      $('journal-status').className = 'tag muted';
      $('journal-check').textContent = 'No current accounting check available.';
      $('journal-check-detail').textContent = 'Displayed events may be from the last successful request.';
    }
  } finally {
    window.clearTimeout(timeout);
    if (generation === journalGeneration) {
      journalLoading = false;
      $('journal-refresh').disabled = false;
      $('journal-older').disabled = !journalData?.next_before;
    }
  }
}
$('journal-refresh').addEventListener('click', () => loadJournal(0));
$('journal-older').addEventListener('click', () => { if (journalData?.next_before) loadJournal(journalData.next_before); });
$('journal-filter').addEventListener('change', () => { $('journal-detail').hidden = true; loadJournal(0); });
$('journal-jsonl').addEventListener('click', () => { window.location.href = '/api/paper/journal/export?format=jsonl'; });
$('journal-csv').addEventListener('click', () => { window.location.href = '/api/paper/journal/export?format=csv'; });
async function pollJournal() {
  if (!journalBefore && !journalLoading) await loadJournal(0);
  window.setTimeout(pollJournal, 10000);
}
pollJournal();
