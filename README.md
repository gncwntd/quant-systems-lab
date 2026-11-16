# Quant Systems Lab

An open-source laboratory for market-data systems engineering and reproducible quantitative research.

**Status:** repository foundation. The parser, order book, trading engine and dashboard are not implemented yet. No trading performance is claimed.

## Direction

- Build a small, correct C market-data parser, order book reconstruction engine and deterministic replay tool.
- Measure correctness, throughput, latency and memory use with reproducible workloads.
- Develop a separate Python research track for EUR/USD, including transaction costs and time-ordered validation.
- Add a dashboard for engineering metrics and research results.
- Explore concurrency, networking, modern C++ and HDL simulation through later scoped experiments.

Nasdaq order events and broker FX quotes are different data sources. They require separate adapters and execution assumptions. A reconstructed order book is not a matching engine, and replay alone does not establish realistic fills.

## Quick start

Requires Git and Python 3.10 or newer. No third-party Python packages, market-data downloads or account credentials are needed for the foundation checks.

```sh
git clone https://github.com/gncwntd/quant-systems-lab.git
cd quant-systems-lab
python3 tools/check_repository.py
python3 -m unittest discover -s tests -v
```

The repository check examines Git index contents, not ignored personal files. It enforces a publication boundary and checks local Markdown links; it does not prove that a repository contains no sensitive information. Inspect the staged diff before every commit.

## Project guide

- [Roadmap and checkpoints](docs/ROADMAP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data and publication policy](docs/PUBLICATION_POLICY.md)
- [Development workflow](docs/DEVELOPMENT.md)
- [Engineering measurement contract](docs/BENCHMARKS.md)
- [Foundation report](docs/reports/2026-11-16-foundation.md)
- [Contributing](CONTRIBUTING.md), [conduct](CODE_OF_CONDUCT.md), [security](SECURITY.md)

Use GitHub Issues for actionable work and milestone tracking. Discuss large changes before implementing them. Each completed checkpoint needs evidence and a short report, including failed experiments and limitations.

## License and commercial use

Project-authored code and documentation are licensed under [Apache-2.0](LICENSE), unless a file explicitly states otherwise. External data and third-party components retain their own licenses; the project license grants no rights to those datasets.

Commercial use is permitted under the license. Commercial users do not owe the authors a royalty or share of trading profits. Paid support, integration, hosted services or separately licensed future products may be developed; none are currently offered. Contributors retain their copyright and contribute under the project license. Commercial relicensing of third-party contributions is not assumed.

This is research software. Simulation and demo results do not guarantee live results. No live broker connection or automated deployment is part of the foundation.
