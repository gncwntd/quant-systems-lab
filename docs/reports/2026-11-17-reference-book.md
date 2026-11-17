# First reference book — 17 November 2026

Implementation record: local verification before publication. The repository history and PR checks record the subsequent publication state. E02 preparation, not a completed checkpoint.

## Result

A C11 library accepts already-decoded ADD, CANCEL, EXECUTE and DELETE events for a single instrument. It tracks up to 64 active orders without heap allocation and computes best quotes and aggregated quantities. Integer price units keep the library independent of a source's display scale.

The synthetic demo reproduces eight worked events and finishes with bid 99.98 × 7, ask 100.02 × 5 and spread 4 units at scale 100. No input decoder, matching engine or external market data is involved.

## Validation

- GCC 12.3.0, C11, Debug, warnings treated as errors.
- Five CTest cases: event scenario, rejected-input state preservation, capacity/reuse, numeric/quote limits and demo execution.
- AddressSanitizer and UndefinedBehaviorSanitizer build with the same cases.
- Python publication-policy tests remain separate from C correctness tests.

Final local results: 5/5 Debug CTest cases, 5/5 sanitizer CTest cases and 5/5 Python policy tests passed. All 28 public candidate files passed publication/content/link checks without staging; tracked whitespace checks passed.

The initial sandboxed sanitizer run was blocked by LeakSanitizer's ptrace restriction. An explicitly authorized run outside that restriction passed all five cases. Runtime checks were not disabled. Clang is not installed locally; GCC/Clang CI commands are prepared but their hosted execution has not been verified for these changes.

## Boundaries

Lookup and quote generation are bounded linear scans, not a performance-optimized engine. Replacement, feed sequencing, protocol framing, exchange/session semantics, parsing, matching and realistic fills remain future work. Rejected events leave state unchanged; no implicit order correction is performed. The prototype contract is in [REFERENCE_BOOK.md](../REFERENCE_BOOK.md).

No throughput benchmark or financial return is claimed. There is no broker connection or live deployment. No new Git branch, commit, push or PR was created in this session.
