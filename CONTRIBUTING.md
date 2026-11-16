# Contributing

The project is at the repository-foundation stage. Small contributions to specifications, synthetic fixtures, documentation and verification are welcome.

## Before coding

Read the [roadmap](docs/ROADMAP.md), [architecture](docs/ARCHITECTURE.md) and [publication policy](docs/PUBLICATION_POLICY.md). Open an issue for a substantial change and describe its purpose, scope, acceptance criteria and dependencies. Do not introduce a new subsystem before its scope is agreed.

Code, identifiers, commit messages and public documentation must be in English. AI-assisted contributions are allowed; the contributor remains responsible for understanding, testing and licensing the submitted work.

## Submit a change

1. Fork the repository and create a short-lived branch such as `feat/itch-framing`, `fix/bounds-check` or `docs/replay-contract`.
2. Make a focused change. Add meaningful tests for behavior or security boundaries; documentation-only edits do not need artificial tests.
3. Run the checks in [the development guide](docs/DEVELOPMENT.md). Stage only intended public files and inspect `git diff --cached` and `git diff --cached --stat`.
4. Open a PR linked to its issue. Explain the problem, result, validation and limitations. Include measurement evidence for performance claims.
5. Address review feedback. A maintainer merges after required checks pass, normally using squash merge.

Never submit account credentials, personal trading history, private conversations or data without redistribution rights. Use synthetic fixtures for correctness tests.

## Ownership and license

You must have the right to submit your contribution. Unless explicitly agreed otherwise, intentionally submitted contributions use Apache-2.0, the same license as the project. You retain your copyright. There is no copyright assignment, separate CLA or mandatory DCO sign-off at this stage. A PR does not authorize the maintainer to relicense your work under arbitrary future terms.

The initial maintainer is [@gncwntd](https://github.com/gncwntd). External changes receive maintainer review. During the single-maintainer phase, maintainer-authored changes use PRs and CI without requiring an unavailable second reviewer. Ownership and review rules can evolve with active maintainers.
