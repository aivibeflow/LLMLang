# LLMLang: Analytical Estimate of Compilation Speedup from Caching

**Status:** Research estimate; not a benchmark  
**Date:** 2026-11-17  
**Related:** [Semantic Compilation Cache](SEMANTIC-COMPILATION-CACHE.md)

## 1. Purpose and limitations

This note estimates the potential compilation speedup from LLMLang's proposed semantic action cache. It is an analytical model, not a measurement of an existing LLMLang compiler. LLMLang does not yet have a production compiler or representative workload benchmark from which actual cache hit rates could be measured.

The model is intended to:
- identify which compilation stages offer the largest opportunity;
- estimate speedup for common change patterns;
- expose assumptions that a prototype must measure;
- define a benchmark plan and avoid treating optimistic estimates as guarantees.

## 2. Model

Normalize the uncached build cost to 1 (or 100%). Divide it into stages (i), each with baseline cost share (w_i) and reusable-work fraction (h_i).

The fraction of total work avoided is:

`R = Σ(w_i × h_i)`

where `Σw_i = 1`.

Let `O` be cache overhead as a fraction of the uncached baseline, including key construction, dependency checks, cache lookup, artifact retrieval, validation, and bookkeeping. The estimated speedup is:

`S = 1 / (1 - R + O)`

This is an Amdahl-style model. It assumes the stage costs and hit fractions are representative and that cached outputs are valid and reusable. It does not account for parallelism changes; a later model should include critical-path length as well as total work.

## 3. Assumed uncached cost distribution

The following distribution is a deliberately generic starting point for a compiler with semantic analysis and an LLVM-based backend. It is not an assertion about measured LLVM or LLMLang timings.

| Stage | Baseline cost share |
|---|---:|
| SPG construction / parsing | 8% |
| Semantic normalization | 7% |
| Type checking | 10% |
| Contract validation / analysis | 10% |
| Dependency analysis | 8% |
| Target lowering | 12% |
| LLVM optimization | 20% |
| Code generation | 15% |
| Link / package | 10% |
| **Total** | **100%** |

The backend stages (lowering, optimization, code generation, link/package) account for 57% in this model. Semantic front-end and analysis stages account for the other 43%. This is important: caching only object files leaves much of LLMLang's potential reuse unrealized.

## 4. Scenario assumptions

The hit fraction below means the fraction of the *baseline work for that stage* avoided, not the fraction of files or graph nodes with a cache hit.

| Stage | Local edit | Component edit | Repeated identical build |
|---|---:|---:|---:|
| SPG construction / parsing | 90% | 60% | 99% |
| Semantic normalization | 95% | 70% | 99% |
| Type checking | 95% | 70% | 99% |
| Contract validation / analysis | 95% | 70% | 99% |
| Dependency analysis | 95% | 65% | 99% |
| Target lowering | 95% | 65% | 99% |
| LLVM optimization | 90% | 55% | 99% |
| Code generation | 90% | 55% | 99% |
| Link / package | 50% | 30% | 90% |

Interpretation:
- **Local edit:** one small implementation node changes; unrelated operations and their downstream products remain reusable. Some global or aggregate work remains.
- **Component edit:** several connected operations change, invalidating a larger dependency closure.
- **Repeated identical build:** the exact same semantic inputs, target, toolchain, configuration, and action implementations are built again with a warm cache. Link/package work is less reusable because final aggregation, signing, or packaging may still be required.
- **Cold build:** all hit fractions are zero; caching cannot accelerate the first build and may make it slightly slower due to cache population.

These are illustrative assumptions, deliberately not best-case maxima. Actual values depend on graph granularity, dependency completeness, build topology, and workload. A local implementation edit is detected through the changed `ImplHash`; downstream action keys change only where their declared result-determining inputs include that identity or a derived artifact. No separate dirty-flag/source-change mechanism is assumed. This relies on complete hash inputs and sound action keys.

## 5. Calculated results

Using the cost distribution in section 3 and hit fractions in section 4:

| Scenario | Baseline work avoided (R) | Speedup at 1% overhead | At 2% overhead | At 4% overhead |
|---|---:|---:|---:|---:|
| Local edit | 88.35% | 7.91× | 7.33× | 6.39× |
| Component edit | 58.95% | 2.38× | 2.32× | 2.22× |
| Repeated identical build | 98.10% | 34.48× | 25.64× | 16.95× |
| Cold build | 0% | 0.99× | 0.98× | 0.96× |

The cold-build row illustrates that populating a cache can add cost. The value of caching appears on subsequent builds and across workspaces/CI when artifacts are shared.

A practical initial expectation from this model is:
- a small local edit: around **6–8×**;
- a component-level edit: around **2.2–2.4×**;
- a repeated identical warm build: potentially **17–34×**.

These are scenario outputs, not performance promises. They should not be quoted as measured LLMLang results.

## 6. Sensitivity and important caveats

### 6.1 Cache granularity

If actions are cached only at whole-module or whole-file granularity, a one-function change may invalidate a large amount of work. Function- or semantic-subgraph-level actions can improve reuse, but excessively fine granularity adds lookup, metadata, serialization, and scheduling overhead.

The useful unit is the smallest independently reusable semantic computation whose complete inputs can be identified cheaply and soundly.

### 6.2 Dependency completeness

A false cache hit is a correctness defect, not a performance trade-off. Hidden inputs (environment variables, headers, compiler flags, target features, toolchain binaries, runtime versions, generated files) must be represented in the Action Key or make the action non-cacheable. For implementation changes, a changed hash-relevant semantic input must change `ImplHash`; consuming actions then get new `ActionKey` values. This content-addressed identity propagation replaces separate dirty flags or source-change tracking. If an input is omitted from `ImplHash` or `ActionKey`, the resulting stale hit is a dependency-completeness bug.

The model assumes all cache hits are sound. It does not assign a performance benefit to unsafe reuse.

### 6.3 Parallel builds

The formula estimates total work/time under a simplified sequential model. In a highly parallel build, removing work from non-critical branches may reduce CPU consumption without reducing wall-clock time proportionally. Conversely, cache reuse may shorten the critical path and improve wall-clock time substantially.

A real benchmark must record:
- wall-clock time;
- total CPU time;
- peak memory;
- number and duration of executed actions;
- cache lookup and artifact transfer time;
- critical-path duration;
- local and remote hit rates.

### 6.4 Remote cache

A remote cache can increase the hit rate across machines but introduces network transfer and validation costs. Large artifacts may cost more to download than to rebuild. The policy should consider artifact size, expected recomputation time, network latency/bandwidth, and trust requirements.

### 6.5 Verification and tests

Test and proof actions can have a high reuse value because they may be expensive relative to compilation. They should be measured separately from compile time and tied to exact implementation, contract, assumptions, target, test/model, and tool versions. A reused proof/test result must not be reported as evidence for changed inputs.

## 7. Break-even condition

Caching an action is beneficial when:

`lookup + validation + retrieval < recomputation`

For a remote artifact, include transfer and decompression cost. If an action is very cheap or its output is very large, it may be better not to cache it.

A cache policy should therefore use measured action cost and artifact characteristics rather than caching every node indiscriminately.

## 8. Benchmark plan

Build a small representative LLMLang program with:
- independent operations;
- a dependency chain;
- shared types and contracts;
- at least one operation whose body is inlined into a caller;
- one separately linked operation;
- multiple target profiles.

Run the following controlled cases:
1. cold build with an empty cache;
2. identical warm rebuild;
3. change one leaf implementation;
4. change one shared type/layout;
5. change one contract;
6. change one target/toolchain input;
7. change one operation that is inlined into a caller;
8. change one operation that is called through a stable separately linked boundary.

For every run, compare cached and uncached outputs and record the metrics in section 6.3. Add adversarial cases for undeclared environment inputs, corrupted artifacts, and stale test/proof evidence.

Report results by action kind and by edit scenario, not just one aggregate hit-rate percentage. Validate both semantic correctness and performance.

## 9. Conclusions

The analytical model suggests that semantic-action caching could make LLMLang's common small-edit workflow several times faster, while exact repeated builds could become much faster still. The largest architectural opportunity is to cache semantic analysis and backend work at independently reusable graph boundaries, not merely final object files.

The estimate is most sensitive to:
1. how much of the dependency graph remains unaffected by a change;
2. whether actions are granular enough to reuse that unaffected work;
3. whether all result-determining inputs are captured;
4. how expensive cache lookup and artifact transfer are;
5. whether the reused work lies on the wall-clock critical path.

The binding benchmark now measures action invalidation for a synthetic C workload under exact and separate linkage. It provides evidence about which actions can be reused. The timing ranges above remain hypotheses until compiler overhead, wall-clock distributions, and representative workloads are measured. [RT-11 Binding Invalidation Benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md)
