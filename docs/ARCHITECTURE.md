# Architecture direction

Status: a working local [research application](RESEARCH_APP.md) and an initial [C reference book](REFERENCE_BOOK.md). Daily research is the active delivery path. Broker execution, adaptive models and real feed parsing remain future work.

## Systems track

Source-specific byte stream → bounded parser → validated order events → book reconstruction → deterministic replay → measurements and summaries.

Start with a single-thread reference implementation and a documented subset of Nasdaq TotalView-ITCH 5.0. Agree framing, byte order, supported messages, error handling and capacity behavior at E00. Do not claim full protocol support. A reference model and small synthetic fixtures should establish correctness before optimization.

The first working component is the event-to-book portion: fixed-capacity C11 storage, validated ADD/CANCEL/EXECUTE/DELETE updates and best-quote aggregation. It uses source-independent integer prices. Its prototype contract is documented separately; no ITCH message layout has been selected or implemented yet.

Book reconstruction follows reported events. It does not simulate a venue's matching engine or establish how hypothetical orders would fill. Execution simulation is a later component with explicit assumptions.

## Research track

EUR/USD source adapter → data-quality checks → features and reference strategy → cost-aware historical simulation → time-ordered validation → stress tests → optional demo forward testing.

Implemented now: strict daily CSV/ECB import, provenance hashes, a manually configured SMA reference strategy, delayed single-price simulation with estimated side/carrying costs, observation-level drawdown halt, matched-cost long-EUR baseline, descriptive regime summary and seeded block-bootstrap stress. The loopback HTTP API serves a buildless dashboard and stores datasets and completed runs in ignored local SQLite storage.

The present simulator uses daily reference prices, not broker fills. It does not provide a trained model, automated parameter search, genuinely untouched holdout validation, intraday execution, margin accounting or realistic funding data. See the methodology contract before interpreting its output.

The [MT5 demo bridge](MT5_BRIDGE.md) is a separate observation path: read-only MQL5 script → common local JSON → validated loopback quote endpoint → dashboard. It exposes bid/ask/spread and freshness, without injecting snapshot data into historical experiments. Quote archives, historical broker adapters and execution remain future components.

The [streaming paper path](STREAMING_PAPER.md) now consumes new validated snapshots independently of the browser. A server worker builds sampled minute midpoint candles, calculates a closed-candle SMA target and applies hypothetical bid/ask fills with explicit costs and risk checks. SQLite transactions persist cash, exposure, settings/hash, audit events and a rolling 10,000-snapshot buffer. This does not inject new observations into the daily reference simulator or send broker orders.

A separate [read-only audit layer](PAPER_JOURNAL.md) reconstructs the simulated account from stored fills, pages session events by stable IDs and streams complete cutoff audit exports in bounded batches. It checks accounting independently of the strategy module without changing its frozen fingerprint or rules.

All transformations must use information available at the decision time. Record unsuccessful experiments as well as selected models. Periodic retraining and walk-forward validation are distinct processes; neither guarantees improvement.

FX broker quotes and Nasdaq events have different market structure, timestamp semantics and visibility. OHLC bars cannot reconstruct the original order book or queue positions. Preserve those distinctions at adapter boundaries.

## Shared infrastructure

Share experiment identifiers, versions, report formats and observability where useful. The dashboard consumes recorded summaries and displays source, mode and freshness. Its lifetime must not define the lifetime of a later execution service.

The dashboard is now implemented with a local Python standard-library server. It can import data, run experiments, inspect equity/trades/risk, reload saved runs and export JSON/CSV. There are no order-placement or credential endpoints.

Expected component locations are `core/`, `python/`, `dashboard/`, `tests/`, `benchmarks/` and, later, `hdl/`. Add directories when their work begins rather than creating empty subsystems. Choose a C–Python interface only after its data and ownership contract is clear.

Concurrency, special allocators, kernel bypass and FPGA work require a scoped learning objective or measured bottleneck. A passing HDL simulation does not establish hardware timing, resources or network performance.
