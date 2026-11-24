# RT-00 C — Cache estimate and benchmark recheck

**Date:** 2026-11-24
**Current-main baseline:** `8f9c354a21f8341550ba790997340471134d2208`
**Plan mapping:** §3.4 compilation speedup; §0.1 claim and reproducibility audit
**Status:** bounded arithmetic and cross-toolchain fixture recheck; no LLMLang speedup claim validated

## Question

Do the speedup figures in the analytical cache estimate follow from its published assumptions, and does the binding invalidation benchmark reproduce on a different compiler/host than its recorded Darwin run?

## Methods and observations

Recomputed `R = Σ(wᵢ × hᵢ)` and `S = 1 / (1 - R + O)` from the nine published stage weights, four hit-fraction vectors, and overhead values of 1%, 2%, and 4%. The results match the report: local edit avoids 88.35% of modeled work and yields 7.91×/7.33×/6.39×; component edit avoids 58.95% and yields 2.38×/2.32×/2.22×; warm identical build avoids 98.10% and yields 34.48×/25.64×/16.95×; cold build avoids 0% and yields 0.99×/0.98×/0.96×. This validates arithmetic only; stage shares and hit fractions remain assumptions.

Ran the current-main `research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/binding_build_benchmark.py` with Python 3.12 on Linux using `cc (Debian 14.2.0-19) 14.2.0`, target `x86_64-linux-gnu`. The program completed for exact and separate linkage, compared every incremental phase against a clean build, and reproduced the recorded action counts: cold 2 provider/16 caller compiles, 16 links and verifications; warm 0 actions; implementation change under separate linkage 1 provider/4 caller compiles, 12 links, 12 selected-binding verifications and 16 whole-snapshot verifications. Contract, snapshot-history, and compiler-flag cases also matched their expected table entries. The fixture's compile-input/output witness remained equal/different, respectively, demonstrating why compile-input identity cannot stand in for executable verification identity in this fixture.

The Linux run confirms the benchmark's fixture and count logic work on this toolchain. It does not reproduce the recorded Apple Clang 21.0.0 / arm64-Darwin result byte-for-byte, establish C compiler equivalence, measure elapsed time, or validate a production cache.

## Comparison and result

The two evidence items answer different questions. The analytical report supplies illustrative hit-rate and cost assumptions and internally consistent scenario arithmetic. The C benchmark measures stage-specific action invalidation in one synthetic call graph and verifies outputs against clean builds. Neither provides representative LLMLang hit rates, action costs, wall-clock speedup, parallel critical-path data, or proof of complete production dependency/environment capture.

Thus the model is arithmetically sound but empirically unvalidated. The action-count benchmark is independently repeatable on one additional compiler/host, but is not a compiler performance benchmark. Do not use the 6–8×, 2.2–2.4×, or 17–34× estimates as measured LLMLang outcomes when selecting the implementation.

## Remaining external prerequisites

- A representative executable LLMLang workload and a defined clean/incremental build harness.
- Controlled cold, identical-warm, local edit, shared-component edit, contract edit, target/toolchain change, and broad-change runs.
- Comparable baseline builds, repeated runs, pinned hardware/toolchains, and wall-clock, CPU, memory, hit/miss, lookup/transfer, and critical-path measurements.
- Output equivalence checks and adversarial undeclared-environment, corrupted-artifact, and stale evidence cases.
- Evidence that dependency and action-key inputs are complete before interpreting reuse as safe.

These depend on an integrated compiler/cache and representative LLMLang programs; §3.4 and the cache integration portions of §3.3 stay open. This recheck narrows confidence in existing fixtures and does not choose a production cache architecture.
