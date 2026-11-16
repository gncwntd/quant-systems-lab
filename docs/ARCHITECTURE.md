# Architecture direction

Status: proposed boundaries; implementation has not started.

## Systems track

Source-specific byte stream → bounded parser → validated order events → book reconstruction → deterministic replay → measurements and summaries.

Start with a single-thread reference implementation and a documented subset of Nasdaq TotalView-ITCH 5.0. Agree framing, byte order, supported messages, error handling and capacity behavior at E00. Do not claim full protocol support. A reference model and small synthetic fixtures should establish correctness before optimization.

Book reconstruction follows reported events. It does not simulate a venue's matching engine or establish how hypothetical orders would fill. Execution simulation is a later component with explicit assumptions.

## Research track

EUR/USD source adapter → data-quality checks → features and reference strategy → cost-aware historical simulation → time-ordered validation → stress tests → optional demo forward testing.

All transformations must use information available at the decision time. Record unsuccessful experiments as well as selected models. Periodic retraining and walk-forward validation are distinct processes; neither guarantees improvement.

FX broker quotes and Nasdaq events have different market structure, timestamp semantics and visibility. OHLC bars cannot reconstruct the original order book or queue positions. Preserve those distinctions at adapter boundaries.

## Shared infrastructure

Share experiment identifiers, versions, report formats and observability where useful. The dashboard consumes recorded summaries and displays source, mode and freshness. Its lifetime must not define the lifetime of a later execution service.

Expected component locations are `core/`, `python/`, `dashboard/`, `tests/`, `benchmarks/` and, later, `hdl/`. Add directories when their work begins rather than creating empty subsystems. Choose a C–Python interface only after its data and ownership contract is clear.

Concurrency, special allocators, kernel bypass and FPGA work require a scoped learning objective or measured bottleneck. A passing HDL simulation does not establish hardware timing, resources or network performance.
