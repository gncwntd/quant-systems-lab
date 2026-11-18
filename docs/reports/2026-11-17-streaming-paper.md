# R05 — Streaming paper simulation

Date: 17 November 2026. Status: implemented and verified locally; feature-branch changes remain uncommitted and unpublished.

## Delivery

The local server consumes fresh MT5 demo snapshots independently of the browser, builds sampled one-minute midpoint candles and evaluates a fixed SMA 5/20 long/cash rule from closed complete candles. Hypothetical fills use ask/bid with explicit commission and slippage assumptions. The dashboard shows candles, warm-up, signal, virtual exposure, estimated equity/P&L, recent closed trades, risk state and pause/resume controls.

SQLite transactions preserve simulation state, frozen configuration/engine hash, audit events and the latest 10,000 accepted samples. The existing daily datasets and experiment journal remain separate. See [the operating and accounting contract](../STREAMING_PAPER.md).

## Verification

- Forty-five Python tests passed, including sixteen new forward-engine/persistence tests and a new HTTP control/export test.
- Synthetic streams verified closed-candle timing, ask/bid reconciliation, explicit costs without duplicate spread charging, market-move and entry-cost drawdown checks, pause/exits, spread/exposure blocks, duplicate/backward timestamps, source changes, gap warm-up reset, restart preservation, atomic rollback, bounded samples and a real background thread.
- JavaScript syntax and whitespace checks passed. The public-source candidate boundary was reviewed; no private market observations, screenshots, database or compiled binary was staged.
- Real-source smoke verification: worker running, MetaQuotes-Demo fresh, accepted sample count increasing and sampled candles forming. The session remained in warm-up with no simulated fill yet observed on the real source.
- Browser verification: warm-up/candle/account panel rendered; pause and resume changed the intended simulation control, with collection continuing. No broker controls or trading-permission changes were used.
- Existing local reference dataset and both completed historical experiments were preserved. A private SQLite backup was taken before enabling the worker.

## Limits and next checkpoint

This is a forward simulation, not broker execution. A subsequent read-only review verified the first real-source hypothetical entry: twenty qualifying closed candles, the specified SMA direction, later-minute execution, ask-side slippage, commission and entry risk limits. Independent audit reconstruction agreed with the open account. Source quotes, timestamps and personal position evidence remain private. A real-source closed round trip and longer operational reliability still need observation. No return or model-learning claim is made. Broker timestamp semantics, actual costs, financing and execution remain unvalidated.

The rolling sample buffer is deliberately bounded; historical capture/export and dataset suitability require additional work. Resume after an engine/config change requires an independent workspace rather than silently modifying a frozen session. Next: inspect operational events and accounting during forward operation, add stronger session/data export and comparison, then assess historical broker data and strategy validation before adaptive models.
