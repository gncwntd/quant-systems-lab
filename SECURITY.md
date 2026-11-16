# Security policy

## Supported scope

Only the current `main` branch is maintained during the pre-release stage. No production-readiness or live-trading guarantee is provided.

## Reporting

Use **Security → Report a vulnerability** on this repository when private vulnerability reporting is enabled. If it is unavailable, do not publish exploit details or credentials; open an issue asking for a private reporting channel without disclosing the vulnerability. Reports are handled on a best-effort basis; no response-time commitment is offered.

For an exposed credential, revoke or rotate it with its provider immediately. Removing a file from the latest commit does not remove copies from history, forks, logs or artifacts.

## Execution boundary

Public PR checks use GitHub-hosted runners and no broker/API credentials. Do not run untrusted PR code on a machine containing trading credentials. CI does not place trades, connect to a broker or deploy a live service. Sensitive values must not enter CI logs, issues or release assets.
