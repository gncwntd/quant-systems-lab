# Streaming paper simulation

The local server now runs a persistent forward simulator alongside the read-only MT5 demo bridge:

`demo snapshot → freshness check → sampled M1 midpoint candle → closed-candle SMA signal → risk checks → hypothetical bid/ask fill → SQLite audit`

This is a fixed-rule engineering baseline for observing new data. It does not train a model, submit broker orders or establish a trading advantage. Existing daily ECB/CSV experiments remain separate.

## Run

Keep the user-configured MT5 demo and [quote bridge](MT5_BRIDGE.md) running, then start:

```sh
python3 tools/run_lab.py serve
```

Open `http://127.0.0.1:8765/#paper`. The server automatically collects valid new snapshots and runs the simulation; the browser only displays state. Closing the browser does not stop the worker. Stopping the server or computer does stop it. There is no OS startup service or uptime guarantee.

The default database is ignored `.local/runtime/lab.sqlite3`. A separate workspace can be selected with `--database .local/runtime/another-lab.sqlite3`; existing experiments are not copied into that workspace. Use `--quote-file` to select a different local bridge export.

## Frozen baseline settings

| Setting | Value |
| --- | --- |
| Instrument / account currency | EURUSD / USD |
| Candle / input price | One raw-server-clock minute / sampled `(bid + ask) / 2` |
| Rule | Fast SMA 5 > slow SMA 20: long; otherwise cash |
| Initial simulated capital | USD 10,000 |
| Fixed position | EUR 1,000, subject to cash and 50% equity entry limits |
| Hypothetical entry / exit | Ask + 0.2 pip / bid − 0.2 pip |
| Commission assumption | 0.35 basis points of USD notional per side |
| Entry spread limit | 3 pips |
| Drawdown halt | 2% of observed simulated equity peak |
| Maximum accepted-sample gap | 10 seconds |

These parameters were chosen for a small inspectable baseline, not optimized or calibrated against a broker. Slippage and commission are explicit assumptions. Observed bid/ask already embeds the spread; no extra spread fee is charged. Financing/swaps, margin, execution latency, depth and broker fills are unmodeled.

The settings, engine version and engine-file SHA-256 are stored with the session. A changed engine or configuration cannot silently resume the session: startup rejects the mismatch. Preserve the original database and select a new one for a different engine. The first version has no in-place parameter editor or reset button.

## Time ordering and candle completeness

Only validated fresh quotes from the session's original demo source enter the simulation. Repeated source timestamps are ignored, backward source timestamps are rejected, and provider changes cannot alter the session's marks or fills. Sampling is approximately one second and is not an exhaustive tick feed.

Buckets use the raw MT5 server timestamp, explicitly displayed as server clock rather than UTC. Audit/fill observations use bridge UTC heartbeat time. The computer clock must be synchronized, as described in the bridge contract. These timestamps do not measure network or execution latency.

The startup minute is partial and excluded from SMA history. A new minute closes the previous sampled candle. A candle qualifies for warm-up only if it was not marked partial and has at least two samples; any accepted-sample gap over ten seconds resets continuity first. Thus “complete” means passing these sampling checks, not complete exchange tick coverage. Missing minutes are never fabricated.

Signals use the last twenty qualifying closed candles. A decision calculated when the next minute arrives can first fill using that newly observed quote; the current forming candle cannot enter its own signal. If an entry is blocked by spread or exposure limits, the latest closed-candle target may retry on later fresh quotes. Startup needs approximately twenty-to-twenty-one uninterrupted minutes before a signal; this is a data warm-up, not a promise of a trade.

After a gap, the forming candle is discarded, SMA history is cleared, and new entries wait for fresh warm-up. Existing exposure is retained and marked on the next accepted quote. A gap does not create an imaginary exit at an unavailable price. Restart uses the same stored position/cash and timestamp; downtime over the gap threshold resets warm-up on the next accepted sample. Shorter interruptions are tolerated by that explicit threshold.

## Accounting, risk and controls

Buying deducts EUR quantity × simulated ask-side fill plus commission from USD cash. Selling returns quantity × simulated bid-side fill minus commission. Realized P&L includes both side commissions and both fill-price slippage adjustments.

Open exposure is marked at estimated liquidation value: current bid minus assumed exit slippage and exit commission. Open net P&L includes the entry fee and estimated exit fee, so realized plus open P&L reconciles with total equity minus starting capital. “Fees paid” reports commissions actually incurred by simulated fills; estimated exit commission is included in valuation without being counted as paid yet. “Slippage included” is descriptive and is not subtracted a second time.

The drawdown check runs on every accepted fresh quote and again after an entry's costs. A breach closes simulated exposure at the available bid-side estimate and permanently halts new entries for that session. Spread limits block entries, not risk or signal exits. Gaps can produce losses beyond the threshold; this is not a guaranteed stop.

**Pause entries** persists across restarts and blocks new positions. Collection, marking and strategy/risk exits continue. **Resume entries** allows the latest valid target to enter on a later accepted quote, subject to all checks. Neither control changes MT5 trading permissions. A halted session cannot be re-enabled through this button.

Stale/unavailable sources perform no fills and retain the last accounting state. The UI labels marks as a last estimate whenever observations or the worker are not current. These values must not be read as current liquidatable broker balances.

## Storage and API

Every accepted snapshot, resulting state and audit event is committed together in a SQLite transaction. Failures roll back the entire step. Serialized transactions and timestamp deduplication prevent duplicate workers from filling the same timestamp twice. Run one server per workspace in normal operation.

- `paper_state`: current session, frozen settings/version/hash, position/cash, twenty SMA closes, last sixty closed candles, fifty closed trades and thirty recent events.
- `paper_samples`: rolling latest 10,000 accepted snapshots, with source and timestamps; older samples are deliberately pruned. This is a bounded operational buffer, not permanent full-market history.
- `paper_audit`: session-linked controls, signals, entries, exits, gaps and feed-state transitions. These records are not pruned by sample retention.

All tables live in ignored local SQLite. No account identifier, broker password or real account balance is requested. Existing historical datasets/runs are preserved.

`GET /api/paper` reads current state and worker/valuation freshness. `GET /api/paper/export` downloads the current bounded state snapshot, not the full retained sample/audit tables. `POST /api/paper/control` accepts only a boolean `enabled`, protected by the existing loopback, Host and same-origin JSON checks. It controls only this hypothetical simulation.

The [paper event journal](PAPER_JOURNAL.md) now exposes complete session audit inspection, independent accounting checks and full cutoff JSONL/CSV audit exports. It does not export the rolling price buffer or modify the frozen engine/session.

The worker is a background thread with cooperative shutdown and a visible error/offline state. The browser polls independently, with request timeout handling. No real trading endpoint or network broker integration is introduced.

## Verification and next work

Synthetic tests exercise delayed closed-candle entries, ask/bid accounting, no duplicate spread charge, entry-cost and market-move drawdown halts, pause/exit behavior, gaps, source changes, duplicate/backward ticks, restart preservation, transaction rollback, retention and browser-independent collection. Loopback integration tests verify controls, export, input rejection and historical-record isolation. Synthetic inputs exist only in tests, never as preloaded performance in the live workspace.

Next: inspect forward operational behavior, add independent session comparison and historical broker data, validate timestamp/coverage assumptions, and compare strategies on time-ordered data. Model training and controlled adaptation remain subsequent work. Simulated fills and a vendor demo feed do not validate executable profitability.
