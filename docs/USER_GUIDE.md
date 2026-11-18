# Using the research workspace

Start the local service with `python3 tools/run_lab.py serve` and open `http://127.0.0.1:8765/`. For streaming observations, the configured MT5 demo terminal and quote bridge must also run. This application computes hypothetical positions locally; it has no broker order endpoint.

## Who opens and closes the paper position?

The worker starts automatically with the server, collects qualifying closed minute candles and evaluates its frozen SMA 5/20 rule. When the fast average is above the slow average, the target is long; otherwise the target is cash. New entries require fresh data, warm-up, acceptable spread, sufficient cash and the exposure limit. Current fixed size is EUR 1,000 from USD 10,000 simulated starting capital.

A cash signal closes a simulated long using the next available eligible bid-side quote at the new-minute decision. The two-percent drawdown rule can also close simulated exposure and halt new entries: it measures a fall from the virtual account's observed equity peak, not a guaranteed two-percent stop on an individual entry.

There are no manual Buy/Sell or Close now buttons in this version. **Pause entries** blocks new simulated positions; it does not close an existing one. Observation, marks and strategy/risk exits continue while paused. **Resume entries** allows a valid target to enter on a later accepted quote, subject to checks. Details are in [the streaming contract](STREAMING_PAPER.md).

## What happens when the computer or server stops?

Stopping the application does **not** automatically close an open paper position. The database retains committed cash, exposure and audit records. While the server/computer is off, the simulator cannot obtain quotes, evaluate exits or invent fills.

After restart, the same frozen session resumes from the database. Acquisition must be restored; a long gap restarts SMA warm-up, while any retained open position is marked and risk-checked on fresh data. A gap is not an exit at an unavailable historical price. The dashboard flags old marks. MT5 scripts need to be reattached or launched using the documented startup configuration after a terminal restart.

This differs from a historical backtest's explicit final liquidation: the historical engine closes remaining hypothetical exposure at the dataset's last observation so the completed experiment has a final ledger. That behavior does not apply to shutting down the forward worker.

## What is a backtest, and what does five trades mean?

A backtest replays past observations through declared strategy, timing, cost and risk assumptions to calculate hypothetical results. It is a simulation on already-known historical data, rather than new observations arriving after the experiment started.

The current daily engine uses imported daily prices and separate settings. It does not modify the minute paper strategy. Signals are delayed one observation, estimated costs are deducted and results are stored with source/configuration hashes. See [research methodology](RESEARCH_APP.md).

“Five closed trades” means five hypothetical entry–exit pairs. They can include wins, losses, risk exits or final-dataset liquidation. It does not mean five profitable trades, five real broker transactions, or the five best results from a search. A positive total may depend on one large winner and several losers; inspect the ledger, not only the return.

Daily SMA 20/60 and minute SMA 5/20 have different inputs, time horizons and cost sensitivity. Their results should not be treated as the same experiment. Source/period differences also prevent a fair direct comparison until those conditions are matched.

## What do the sixty Python tests check?

At this implementation checkpoint the suite contains sixty test methods, many with several inputs/subcases:

| Area | Methods | Examples |
| --- | ---: | --- |
| Streaming paper engine and persistence | 16 | Closed-candle timing, bid/ask costs and P&L, risk/exposure/spread checks, pauses, duplicate/backward ticks, gaps, restart and transaction rollback |
| Independent journal and accounting | 8 | Rebuild balances from fills, detect tampered/broken records, stable pagination, full cutoff exports and spreadsheet formula protection |
| Quote bridge reader | 7 | Freshness, invalid/missing prices, clock errors, disconnection, demo-only flags and regression guard against trading APIs |
| MT5 daily history | 6 | Closed/forming bars, ordering/OHLC bounds, provenance, limits and isolated import without altering paper state |
| Historical research and storage | 12 | Signal delay, accounting/costs, risk limits, no future-price effect on earlier equity, carrying/short examples, reproducible resampling and saved experiments |
| Local HTTP API | 6 | Imports/exports, paper controls, journal endpoints, invalid requests, Host/same-origin checks and path isolation |
| Publication boundary | 5 | Reject selected private/generated/sensitive files, binary/oversize content and broken public links |

Run `python3 -m unittest discover -s tests -v`. These are software behavior checks using isolated, mostly synthetic fixtures, not sixty trading experiments or evidence of a profitable strategy. They do not prove complete security, accurate external data or execution realism.

Additional checks are separate: JavaScript syntax, local browser interactions, local MetaEditor compilation, and the C reference component's CTest cases. Hosted CI builds the C component with GCC/Clang and sanitizers; it does not run MT5 or make trades. See [development workflow](DEVELOPMENT.md).
