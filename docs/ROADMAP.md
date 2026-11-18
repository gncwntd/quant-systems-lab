# Roadmap and checkpoints

GitHub Issues are the source of truth for individual tasks. Milestones group work by checkpoint. This document summarizes acceptance criteria; it does not duplicate the complete issue backlog.

Every checkpoint report records purpose, inputs and versions, acceptance criteria, evidence, unsuccessful attempts, limitations and the next decision. A checkpoint is complete only when its criteria are met.

## Foundation

| ID | Output | Acceptance criteria | Status |
| --- | --- | --- | --- |
| G00 | Public repository foundation | English documentation, Apache-2.0, publication boundary, contribution process, passing checks, published repository and verified GitHub settings | Complete |
| G01 | Optional Project board | Account-level Projects access granted, board created and linked to existing issues | Awaiting account permission |

## Systems engineering

This track is supporting work. The active delivery path is the research application below; further low-level optimization is driven by research requirements.

| ID | Output | Acceptance criteria | Status |
| --- | --- | --- | --- |
| E00 | Parser and measurement contracts | Protocol subset, framing, failure behavior, C baseline, fixtures and measurement method agreed | Planned |
| E01 | C parser | Supported messages match fixtures; malformed/truncated input is safe; unsupported messages have defined behavior; sanitizer checks pass | Planned |
| E02 | Order book reconstruction | Add/cancel/delete/execute/replace behavior matches the chosen scope and reference results; identifiers and volume invariants checked | Reference prototype in progress; replacement and source integration deferred |
| E03 | Replay and benchmark | Same input produces same state summary; measurement report is reproducible and states its scope | Planned |
| E04 | Python integration and dashboard | Interface ownership defined; displayed summaries reconcile with engine output | Planned |
| E05 | Concurrency experiment | Ordering, loss and backpressure behavior verified against the single-thread reference; costs measured | Planned |
| E06 | Execution simulation | Latency, priority and fill assumptions documented; counterfactual market response limitations disclosed | Planned |
| E07 | HDL experiment | Small component matches C test vectors, including reset and backpressure; simulation and hardware claims separated | Planned |

## Quantitative research

The local [research app](RESEARCH_APP.md) delivers the first complete data-to-report flow. These implementation milestones do not establish a trading advantage or broker readiness.

| ID | Delivery | Current evidence |
| --- | --- | --- |
| R01 | Daily CSV and ECB import with provenance | Real ECB import verified; broker-quality price suitability remains open |
| R02 | Delayed, cost-aware daily simulation and historical stress | Accounting, lookahead and risk controls tested; approximate reference-price model |
| R03 | Dashboard, local journal and exports | Published through PR #8; browser, API and hosted checks verified |
| R04 | Read-only MT5 demo quote monitor | Script, validated snapshots, freshness states and dashboard implemented; historical capture and execution remain separate work |
| R05 | Streaming paper simulation | Sampled M1 candles, closed-candle SMA, risk/cost-aware hypothetical fills, bounded sample buffer, persistent audit and dashboard controls; broker order execution remains unimplemented |
| R06 | Paper audit and accounting checks | Cursor-paged event inspection, full cutoff JSONL/CSV audit export and independent reconstruction of simulated cash/exposure/P&L; no signal-quality or execution validation claim |
| R07 | Closed-D1 MT5 history assessment | Actual 1,500-bar demo bundle validated, archived and imported; one declared daily baseline recorded. Source rights, time/price basis, execution costs and M1 suitability remain unverified |

| ID | Output | Acceptance criteria | Status |
| --- | --- | --- | --- |
| CP01 | Research scope | Instrument mechanics, costs, evaluation metrics and stopping criteria defined | Local methodology recorded; broker-specific calibration pending |
| CP02 | Data assessment | Source rights, coverage, timestamps, quality and cost availability documented | Reference-rate adapter complete; tradable bid/ask source pending |
| CP03 | Reference backtest | Reproducible rules, realistic timing/cost assumptions and leakage checks | Approximate daily baseline tested; broker-cost validation pending |
| CP04 | Research dashboard | Metrics reconcile with experiment records; data source and simulation mode visible | Implemented and verified locally for daily reference experiments |
| CP05 | Regime/model comparison | Time-ordered unseen-period comparison against the reference; all trials logged | Planned |
| CP06 | Robustness assessment | Walk-forward, cost shocks, appropriate resampling and uncertainty reported against predeclared criteria | Planned |
| CP07 | Demo forward testing | Fixed versions, new data, recovery and broker-state reconciliation tested | Planned |
| CP08 | Capital decision | Evidence, operational limits and explicit owner decision; progression is optional | Planned |
| CP09 | Controlled adaptation | Candidate/current model comparison, rollback and independent validation for new assets | Planned |

No completion dates, message-rate targets or trading returns are promised. A few profitable trades or a fixed number of demo weeks do not establish statistical sufficiency. The next priority is suitable broker/demo data and stronger strategy validation, not additional instructional exercises.

An initial [C reference book](REFERENCE_BOOK.md) and synthetic demo were implemented as a bounded first coding exercise. E00 and E01 remain planned: this does not establish a wire protocol, feed framing or full reconstruction contract. The prototype is not a completed E02 checkpoint.

## Active engineering backlog

- [First parser contract](https://github.com/gncwntd/quant-systems-lab/issues/1)
- [Synthetic fixtures and reference states](https://github.com/gncwntd/quant-systems-lab/issues/2)
- [Replay baseline and measurement method](https://github.com/gncwntd/quant-systems-lab/issues/3)

Issues and milestones are active. A Project board is not yet configured because the current GitHub authorization lacks Projects scope.
