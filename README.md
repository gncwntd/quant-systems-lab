# Quant Systems Lab

An open-source EUR/USD research workspace with a local dashboard, reproducible experiments and market-data engineering components.

**Status:** local data import, cost-aware daily backtesting, descriptive regimes, historical stress resampling, experiment storage and a dashboard are implemented. A small C reference book is also available. No broker execution, adaptive model or validated trading advantage is established.

A [read-only MT5 demo bridge](docs/MT5_BRIDGE.md) adds a separate EUR/USD bid/ask, spread and freshness monitor. It needs an existing user-configured demo terminal; it does not send orders or provide historical tick storage.

The [streaming paper simulator](docs/STREAMING_PAPER.md) turns new demo observations into sampled M1 candles, closed-candle SMA signals and hypothetical bid/ask fills. Position, net P&L, controls and audit records persist locally, independently of browser polling. Warm-up needs twenty complete minutes; no synthetic trades are preloaded.

The [paper event journal](docs/PAPER_JOURNAL.md) adds event filters/inspection, independent account reconstruction and full cutoff audit downloads in JSONL/CSV. Accounting checks do not verify current prices or trading profitability.

A [closed-D1 MT5 history adapter](docs/MT5_HISTORY.md) provides a separate read-only export and bounded assessment/import path. It needs a one-shot script run in the configured demo terminal; actual source availability and suitability must be assessed. Daily history is separate from M1 forward testing.

## Direction

- Deliver an inspectable EUR/USD research flow: data → strategy → costs/risk → results → experiment journal.
- Validate financial accounting and time ordering before adding model complexity.
- Add broker-quality data, robust validation and demo execution in subsequent checkpoints.
- Preserve C systems components as supporting work, with optimization driven by actual requirements.

Nasdaq order events and broker FX quotes are different data sources. They require separate adapters and execution assumptions. A reconstructed order book is not a matching engine, and replay alone does not establish realistic fills.

## Quick start

Requires Python 3.10 or newer. The research app uses only the Python standard library and buildless HTML/CSS/JavaScript.

```sh
git clone https://github.com/gncwntd/quant-systems-lab.git
cd quant-systems-lab
python3 tools/run_lab.py serve
```

Open `http://127.0.0.1:8765`. Load ECB reference rates or import a daily `date,close` EUR/USD CSV, then run an experiment. No synthetic performance is preloaded. Data and completed experiments persist only under ignored `.local/runtime/`. JSON reports and the trade ledger can be exported from the dashboard.

ECB daily reference rates are informational observations, not tradable bid/ask quotes. The app labels them accordingly and uses explicit estimated costs. This is a plumbing/research baseline; a result does not establish executable profitability. See [research methodology](docs/RESEARCH_APP.md).

To fetch reference data from the command line:

```sh
python3 tools/run_lab.py fetch-ecb --start 2022-01-01 --end 2026-11-17
```

### Development checks

```sh
python3 -m unittest discover -s tests -v
node --check dashboard/app.js
python3 tools/check_repository.py
```

The publication checker examines Git index contents, not ignored personal files. Stage explicit public files and review the diff before using it to verify a commit candidate. Tests include loopback HTTP checks, requiring permission to open local sockets.

### Run the C reference book

Requires CMake 3.16+ and a C11 compiler:

```sh
cmake -S . -B build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug
ctest --test-dir build/debug --output-on-failure
./build/debug/book_demo
```

The demo processes eight project-authored synthetic events. It ends at bid 99.98 × 7, ask 100.02 × 5 and a spread of 0.04 at the demo's price scale. See the [prototype contract](docs/REFERENCE_BOOK.md) for capacity, validation and sanitizer commands. This component accepts decoded events; it does not decode ITCH bytes or match incoming orders.

## Project guide

- [Using the workspace: positions, shutdowns, backtests and tests](docs/USER_GUIDE.md)
- [Roadmap and checkpoints](docs/ROADMAP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Research app and methodology](docs/RESEARCH_APP.md)
- [Data and publication policy](docs/PUBLICATION_POLICY.md)
- [Development workflow](docs/DEVELOPMENT.md)
- [Engineering measurement contract](docs/BENCHMARKS.md)
- [Foundation report](docs/reports/2026-11-16-foundation.md)
- [Reference book implementation report](docs/reports/2026-11-17-reference-book.md)
- [Research dashboard implementation report](docs/reports/2026-11-17-research-app.md)
- [Contributing](CONTRIBUTING.md), [conduct](CODE_OF_CONDUCT.md), [security](SECURITY.md)

Use GitHub Issues for actionable work and milestone tracking. Discuss large changes before implementing them. Each completed checkpoint needs evidence and a short report, including failed experiments and limitations.

## License and commercial use

Project-authored code and documentation are licensed under [Apache-2.0](LICENSE), unless a file explicitly states otherwise. External data and third-party components retain their own licenses; the project license grants no rights to those datasets.

Commercial use is permitted under the license. Commercial users do not owe the authors a royalty or share of trading profits. Paid support, integration, hosted services or separately licensed future products may be developed; none are currently offered. Contributors retain their copyright and contribute under the project license. Commercial relicensing of third-party contributions is not assumed.

This is research software. Simulation and demo results do not guarantee live results. No live broker connection or automated deployment is part of the foundation.
