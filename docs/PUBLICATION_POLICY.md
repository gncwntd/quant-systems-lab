# Data and publication policy

## Commit to Git

- Project source, tests, documentation, development tools and CI definitions.
- Small project-authored synthetic fixtures, identified as synthetic.
- Reference strategies, reproducible experiment recipes and placeholder configuration.
- Selected technical reports with source provenance, versions, assumptions and limitations.

## Keep outside Git

- Tokens, account identifiers, real environment configuration, private keys and certificates.
- Personal planning, conversations, private learning notes and brokerage records.
- Raw or licensed market data, trained model files, runtime state and large traces.
- Build products, package caches and generated binaries.

The initial local planning archive is ignored and must never be force-added. Prefer external storage for future personal records and datasets. Do not paste sensitive content into issues, PRs, Actions logs or public artifacts.

## Data provenance

Public access to a dataset does not establish redistribution rights. Before including any external fixture, document its source, license, redistribution permission and attribution. Otherwise publish acquisition instructions and hashes, not the data. No external market data is bundled at foundation stage.

The Apache-2.0 project license does not relicense third-party data. Dataset-derived model weights require a separate publication review. Git LFS is a storage mechanism, not a privacy or license exception.

## Before publishing

Use explicit staging paths and inspect the full staged diff, including commit author information. Run the repository checks after staging. These checks detect selected file and content patterns; they are not comprehensive secret detection or a substitute for review. Enable GitHub secret scanning and push protection as an additional layer. Inspect the full history before the first push.

Release assets and uploaded CI artifacts require the same review as source. Initially no artifact upload, package publishing, live deployment or credentials are needed by CI. Runtime broker credentials will not be stored in GitHub Actions.

If a secret is exposed, revoke it first and assess history, artifacts and external copies. Deleting the latest file or adding an ignore pattern does not undo exposure.
