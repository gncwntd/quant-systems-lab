# Reference order book: prototype contract

Status: implemented locally as a small reference component. This is preparation for E02, not completion of the ITCH parser, E00, E01 or the full reconstruction checkpoint.

## Scope

C11, one instrument per book, one thread, 64 active orders, no heap allocation. Events are already-decoded project-authored structures. There is no network, file decoder, broker integration, matching engine, queue simulation or trade strategy.

An ADD supplies a nonzero 64-bit ID, BUY/SELL side, positive 32-bit integer price and positive 32-bit quantity. IDs must be unique among active orders. CANCEL and EXECUTE subtract a positive quantity from a named order; full reduction removes it. DELETE removes the named order regardless of its remaining quantity. Side and price fields are ignored for reductions; DELETE ignores quantity too. EXECUTE is a reported source event, not an instruction to match opposite orders. Replacement is deferred.

Prices are source-independent integer units; the library does not set a scale. The synthetic demo displays 100 units as 1.00. This is not an ITCH wire format or an FX lot specification.

## State and errors

Initialize with `qsl_book_init` before other operations. Callers must not mutate storage directly. The API rejects unknown event types, zero IDs, invalid ADD fields, duplicate active IDs, missing target IDs, excessive reductions and capacity overflow. Rejection leaves the entire book unchanged. Slots and removed IDs can be reused. No implicit correction or clamping is performed.

Quote generation aggregates quantities at the highest buy and lowest sell prices. Quantities are summed into 64-bit values; the fixed capacity and 32-bit per-order limit bound the total. Empty sides have availability flags; spread is unavailable if either side is absent. Signed 64-bit spread arithmetic allows a crossed/locked reported state without unsigned underflow. Reconstruction reports that state; it does not invent trades to resolve it.

Order lookup, free-slot lookup and quote generation use bounded linear scans. This is an understandable reference implementation, not a low-latency performance claim. No benchmark has been run.

## Build and run

Requires CMake 3.16+ and a C11 compiler:

```sh
cmake -S . -B build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug
ctest --test-dir build/debug --output-on-failure
./build/debug/book_demo
```

For GCC or Clang runtime checks:

```sh
cmake -S . -B build/sanitize -DCMAKE_BUILD_TYPE=Debug -DQSL_ENABLE_SANITIZERS=ON
cmake --build build/sanitize
ctest --test-dir build/sanitize --output-on-failure
```

The demo replays the eight synthetic learning events. Its final quote is bid 99.98 × 7, ask 100.02 × 5 and spread 4 integer units (0.04 at demo scale). It prints N/A when either quote side is absent.

## Validation

CTest covers the teaching sequence, aggregation, full removal, best-price changes, rejected-event atomicity, null arguments, capacity/reuse and numeric limits. A separate smoke test runs the demo. Python publication-policy tests remain independent. Hosted CI must verify the new jobs after these changes are published; local success is not a hosted CI result.
