# Repository foundation — 16 November 2026

Checkpoint: G00. Status: complete. Optional Project board setup is tracked separately as G01.

## Decisions

- Public repository: Quant Systems Lab, under personal GitHub ownership.
- English code and public documentation.
- Apache-2.0 for project-authored work, with commercial services/products as possible future revenue paths; no downstream royalty obligation.
- Shared repository, short-lived branches, PR-based development and staged growth of CI.

## Deliverables

README, architecture and roadmap, publication/measurement policies, contribution and security guidance, issue/PR templates, a foundation CI workflow and repository policy checks.

Historical personal planning material is excluded from the public source set. No external dataset, model weight, credential or brokerage record is bundled.

## Limits

No parser, book reconstruction, replay engine, dashboard, broker adapter, trained model or benchmark has been implemented. GCC/Clang and sanitizer CI will be introduced with C code rather than reported as passing now. Release automation and live deployment are not configured.

## Next checkpoint

E00: agree the first message subset, framing and error behavior, synthetic fixtures, C baseline and measurement method.

## Verification evidence

- Published source: https://github.com/gncwntd/quant-systems-lab
- Initial commit: `227154c5d3ca7deb60390cf4afd5650e857fa1cd`.
- Initial hosted CI passed: https://github.com/gncwntd/quant-systems-lab/actions/runs/43863948815
- Local validation: 21 indexed files, zero publication errors, five passing policy tests and a clean staged whitespace check.
- Main protection: PR and up-to-date **Repository checks** required, administrators included; force-push and deletion disabled; zero independent approvals during the single-maintainer phase.
- Repository settings: squash merge only, merged-branch cleanup, secret scanning, push protection and private vulnerability reporting enabled.
- Actions settings: read-only default token, no workflow PR approval, and approval required for all external contributors.
- Initial work is tracked in issues 1–3 under the E00 milestone; the foundation is tracked in issue 4 under G00.
- Commit author uses the maintainer's GitHub noreply address.

## Remaining setup

The installed CLI has no `project` command, and the API token lacks Projects scope. No Project board was created. Existing Issues and milestones remain usable; G01 requires an account authorization update before API board creation. No account permission was silently broadened.
