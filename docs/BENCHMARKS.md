# Engineering measurement contract

No engine benchmark exists yet. Agree the first workload and baseline at E00/E03.

Each published result must identify the commit, workload and data hash, synthetic/external provenance, supported message scope, CPU, OS, compiler, optimization flags, thread count and relevant machine settings.

State what is timed: parsing, state updates, replay, I/O or end-to-end processing. Separate those scopes. Include warm-up, repetitions, sample count, timing method, units and timing overhead. Report memory use and correctness checks alongside throughput and latency distributions.

Do not claim p99.9 from an inadequate sample. Do not treat clock cycles as nanoseconds without validating the conversion and measurement conditions. Document serialization, core migration and clock assumptions if cycle counters are used.

Shared GitHub runners can run smoke workloads but are not the basis for strict low-latency performance gates. Hardware comparisons require comparable methods. Faster replay does not establish a more profitable strategy.
