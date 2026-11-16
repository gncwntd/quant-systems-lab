# Development workflow

## Foundation checks

Use Python 3.10+ and Git. After cloning:

```sh
python3 tools/check_repository.py
python3 -m unittest discover -s tests -v
```

Before a commit, stage explicit public paths, then run:

```sh
git diff --cached --check
git diff --cached --stat
git diff --cached
python3 tools/check_repository.py
```

The checker reads blob contents from the Git index. A PR checkout indexes the committed version. Locally, it checks exactly what is staged, so unstaged edits cannot mask sensitive staged content. Hooks are optional convenience and are not the enforcement boundary.

## Branch and review policy

Use short-lived `feat/`, `fix/` or `docs/` branches targeting `main`. Required checks should run for every PR, including documentation-only changes. The intended required check is **Repository checks**. Maintainers review external contributions and merge using squash. A second approval is not required while there is only one maintainer. Block force-push and branch deletion on `main`.

## CI growth

The foundation workflow checks publication rules, local documentation links and the policy checker's tests. No C source exists yet, so it does not claim to compile or test a trading engine.

At E01, add GCC and Clang builds, warnings, correctness tests and ASan/UBSan. Add Python and dashboard validation when those components appear. Keep commands runnable locally. Pin external Actions to full commit SHAs and update them through reviewed PRs.

Fork PR jobs use GitHub-hosted runners with read-only permissions and no secrets. Do not execute untrusted contributions through privileged `pull_request_target` jobs or on personal/self-hosted trading machines.

## Issue and release lifecycle

Track work as Backlog → Ready → In progress → In review → Done where a Project board is available. Use Issues and milestones even if a board is not configured. Each issue needs purpose, scope and measurable acceptance criteria. Link PRs and reports instead of maintaining another full task list in Markdown.

No automated release exists yet. Later releases will use a maintainer-created `v0.x.y` tag pointing to a tested `main` commit, source/asset review, checksums and release notes. Publishing packages or deploying a broker-connected service requires a separate workflow. Do not interpret a successful CI run as deployment authorization.
