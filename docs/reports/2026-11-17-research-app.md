# EUR/USD research dashboard — 17 November 2026

Implementation record: written after local verification and before publication. The repository history and PR checks record the subsequent publication state.

## Delivered behavior

A working loopback research dashboard connects strict CSV/ECB import, a cost-aware delayed SMA reference simulation, equity/ledger views, descriptive market regimes, historical block-bootstrap stress, observation-level drawdown controls, saved experiment inspection, checkpoint status and JSON/CSV export. It uses Python's standard library and buildless browser assets.

The existing C prototype is preserved as a supporting component. The main delivery path is now an inspectable end-to-end research application. Broker-connected execution and adaptive models remain future work.

## Actual source and first result

The ECB adapter imported 1,247 daily reference observations from 2022-01-03 through 2026-11-16. Source hash: `78f13628820ff34978e27e7c9e9ce8554cb76dc686f06e9bc4214407cca4f1d6`. Observations are kept only in ignored local storage.

The first run was initiated through the browser using defaults: SMA 20/60, long/cash, USD 10,000 capital, 0.5 exposure, 1 pip spread, 0.2 pip slippage per side, 0.35 bps commission per side, zero estimated carrying cost, 10% drawdown halt and the last 30% evaluation window.

Evaluation: 2025-06-02 through 2026-11-16, 375 observations. Modeled net return approximately −1.79%, final equity USD 9,820.84, maximum drawdown 3.53%, five closed trades and estimated costs USD 4.77. No parameter search was performed to replace this negative result.

This result is a single approximate reference-data experiment, not proof of executable strategy performance. Exact records and assumptions remain in the local experiment journal.

## Verification

Tests cover delayed decisions, future-data independence of past equity, trade/equity reconciliation, costs without double counting, drawdown including cost-triggered breaches, short/carry accounting, configuration/data rejection, deterministic sampling, persistence and real loopback HTTP behavior. Browser QA verified data loading and a completed run, visible metrics, chart, ledger and journal. JavaScript syntax and publication-boundary checks are also performed before handoff. Hosted CI for these changes has not run.

Final local results: all 20 Python tests passed, including three real loopback HTTP tests; JavaScript syntax and Python compilation passed. All 42 public candidate files passed publication/content/local-link checks without staging. The final engine was rerun through the browser with unchanged default parameters and reproduced the same displayed result; both completed runs remain in the local journal. The final run also records the loaded engine-file hash. This was reproducibility verification, not a parameter search.

## Open limits

The [methodology](../RESEARCH_APP.md) describes reference-price execution, modeled costs and reusable evaluation data. No predictive model training, true untouched holdout, broker fills, intraday risk management or live orders are implemented. Remote GitHub Project board setup remains separately pending its account scope; no additional account permissions were requested for this delivery.
