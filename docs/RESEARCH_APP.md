# Local research app and methodology

## Run and inspect

Start `python3 tools/run_lab.py serve` and open `http://127.0.0.1:8765`. The service binds only to loopback and is not a production deployment. It accepts same-origin JSON mutations, validates the Host header and serves only named public static assets. Runtime data is stored under ignored `.local/runtime/lab.sqlite3`. No broker or API credentials are used.

Import a daily EUR/USD CSV with `date,close` columns, or use the explicit ECB import action. Dates must be ISO calendar dates, unique and increasing; prices must be finite and positive. Duplicates and malformed data are rejected rather than silently repaired. Imports require 30–10,000 observations, with a 5 MB file limit. A simulation also requires sufficient history for its chosen windows. This is not a complete data-quality or bid/ask audit.

The ECB adapter fetches only `EXR/D.USD.EUR.SP00.A`. It verifies USD per EUR, records source URL, range, observation count, gaps and a SHA-256 input hash. ECB rates are informational reference rates, not transaction prices. Raw imported observations remain local; the code license does not relicense external data.

## Reference simulation

- USD-denominated account and EUR units; exposure is capped at one times current equity, with no explicit leverage or margin model.
- Manually selected fast/slow SMA windows. Long/cash is the default; long/short is optional.
- A signal computed after observation t can first affect hypothetical execution at observation t+1. Existing exposure earns/loses the reference-price change before the next decision is applied.
- The evaluation start is the later of warm-up completion and the selected trailing fraction. Prior observations supply history, not a fitted training model. Repeated runs reuse this period; it is not an untouched statistical holdout.
- Side costs are absolute EUR quantity × (half-spread + slippage in USD per EUR) plus USD reference notional × commission bps. One EUR/USD pip is modeled as 0.0001. The full spread is paid over an unchanged-price round trip, not twice per side.
- Optional carrying cost is an unsigned bps estimate applied to previous reference notional per elapsed calendar day. It is not a broker swap/rollover model. Default zero is an unverified omission, not evidence of free financing.
- No same-side daily rebalancing. A signal change closes the prior position; a reversal may open the opposite side at the same observation with separate costs.
- A drawdown breach at an observation or its transaction costs closes exposure and halts new entries for that run. This is not an intraday guaranteed stop; adverse moves can exceed the threshold before an observation is available.
- Positions are liquidated at the last observation with estimated exit cost, and no new final-observation entry is opened. The ledger and equity should reconcile after this liquidation.

Single-price reference execution is a deliberately approximate baseline. There is no observed spread, depth, queue, latency, market impact, gap-fill or broker margin model. Actual tradability remains unvalidated.

## Comparisons and outputs

The dashboard reports net return, final equity, maximum observation-level drawdown, daily-return Sharpe (252 observations/year), closed trades and estimated costs. Sharpe is unavailable for zero variation or non-positive final equity. A long-EUR baseline uses the same evaluation range, exposure, costs and drawdown control; the cash line is flat initial equity. Baseline results are not strategy selection evidence.

The descriptive regime uses the latest fast/slow mean gap: above +0.2% is Trend up, below −0.2% is Trend down, otherwise Range. Volatility is trailing 20-return standard deviation annualized at 252 observations; 15% marks Elevated. These fixed descriptive labels are not a validated predictive regime model.

Monte Carlo uses 200 seeded circular five-return block samples from net evaluation returns, capped at a 252-observation horizon. It reports sampled final-equity quantiles and loss/drawdown frequencies. It preserves only short within-block dependence and does not rerun strategy/risk reactions, discover new regimes or forecast actual probabilities. Samples already include historical modeled costs; those costs are not added a second time.

Every completed run records configuration, engine version and loaded engine-file hash, frozen source metadata/hash, metrics, equity, trades, risk events and assumptions in local SQLite. Invalid requests return errors without an experiment record. JSON exports preserve the report; CSV exports contain closed trades. Re-importing a source or inspecting a historical result does not prove it is new unseen data.

## Boundaries and next delivery

The app has no live trading, broker login, online learning, autonomous strategy promotion or hosting. The next data milestone is a suitable broker/demo source with verified timestamps and transaction-cost information, followed by robust time-ordered comparison and demo forward testing. The C reference book remains available as a secondary systems component.

## Official source references

- [ECB API examples](https://data.ecb.europa.eu/help/api/data-examples)
- [ECB reference-rate framework](https://www.ecb.europa.eu/stats/pdf/exchange/Frameworkfortheeuroforeignexchangereferencerates.en.pdf)

Implementation status is recorded in [the research app report](reports/2026-11-17-research-app.md).
