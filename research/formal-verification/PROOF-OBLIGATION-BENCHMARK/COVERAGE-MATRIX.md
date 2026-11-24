# Finite coverage target v1

**Status:** proposed executable development coverage, not independent review or mathematical completeness. Tracks [#394](https://github.com/aivibeflow/LLMLang/issues/394).

The target is 16 taxonomy entries × 5 scenario dimensions = 80 cells. A label alone does not count. Each entry maps to a specific composed case with executed positive, negative, boundary, conditional and composed witnesses. The coverage command verifies both valid candidates, rejects the selected mutation, checks outside-assumption controls separately, and requires a two-node obligation dependency. Each case-level witness exercises the label in context; this is not a Cartesian product of every form and every domain, nor a claim that every individual obligation has its own isolated mutation. O1 and O2 are recorded separately; a bounded pass of O2 does not discharge O1 or produce a proof.

| Taxonomy entry | Witness case |
|---|---|
| FORM-01 | [POB-025](cases/POB-025.json) |
| FORM-02 | [POB-026](cases/POB-026.json) |
| FORM-03 | [POB-030](cases/POB-030.json) |
| FORM-04 | [POB-028](cases/POB-028.json) |
| FORM-05 | [POB-031](cases/POB-031.json) |
| FORM-06 | [POB-027](cases/POB-027.json) |
| DOMAIN-01 | [POB-026](cases/POB-026.json) |
| DOMAIN-02 | [POB-027](cases/POB-027.json) |
| DOMAIN-03 | [POB-025](cases/POB-025.json) |
| DOMAIN-04 | [POB-038](cases/POB-038.json) |
| DOMAIN-05 | [POB-029](cases/POB-029.json) |
| DOMAIN-06 | [POB-030](cases/POB-030.json) |
| DOMAIN-07 | [POB-031](cases/POB-031.json) |
| DOMAIN-08 | [POB-035](cases/POB-035.json) |
| DOMAIN-09 | [POB-033](cases/POB-033.json) |
| DOMAIN-10 | [POB-034](cases/POB-034.json) |

Machine-readable [coverage target](coverage-target.json) and [checker](coverage_matrix.py). Reproduce:

```sh
python research/PROOF-OBLIGATION-BENCHMARK/run.py coverage
python research/PROOF-OBLIGATION-BENCHMARK/test_runner.py
```

## Distinct third-cohort semantic profiles

| Case | Profile | Boundary and limitation |
|---|---|---|
| [POB-025](cases/POB-025.json) | Guarded dependent index | Lengths 0..3, indices -1..3; arrays contain their indices; admission 0<=i<n. |
| [POB-026](cases/POB-026.json) | Conditional machine arithmetic | Operands 0..3; admission x+y<=3; modulo-4 machine result outside admission. |
| [POB-027](cases/POB-027.json) | Conditional reassociation | Triples over 0..2; operation add/sub; admission add. |
| [POB-028](cases/POB-028.json) | Exclusive mutation and frame | Alias flag and values 0..2; admission no alias; abstract two-cell memory. |
| [POB-029](cases/POB-029.json) | Budget and cleanup | Requested units and budget 0..3; admission n<=budget; no allocation failure other than budget. |
| [POB-030](cases/POB-030.json) | Quorum agreement | Three voter bitmasks for values A and B; disjoint votes admitted under non-equivocation; no leader election or liveness claim. |
| [POB-031](cases/POB-031.json) | Conditional liveness on lassos | Nonempty periods of length 1..3 over {0,1}; admission at least one service action; fixed repeating period. |
| [POB-032](cases/POB-032.json) | Release/acquire visibility abstraction | Boolean synchronization edge and stale-read choice; admitted edge present; axiomatic toy model, not full hardware memory semantics. |
| [POB-033](cases/POB-033.json) | Journal-based failure atomicity | Journal flag, old values 0..2, failure flag; admission journal exists; crash modeled as failure before commit. |
| [POB-034](cases/POB-034.json) | Verified capability and isolation | Validation flag, caller authorization and protected values 0..2; admission trusted check enabled. |
| [POB-035](cases/POB-035.json) | Overlapping queue histories | Four valid event permutations for one enqueue and one dequeue plus two additional schedules (six total); atomic profile admitted; empty queue initially. |
| [POB-036](cases/POB-036.json) | IEEE binary64 special-value preservation | Named binary64 values +0,-0,+1,-1,+inf,-inf,nan; strict profile admitted; compare NaN class, not payload. |
| [POB-037](cases/POB-037.json) | Crash recovery of a committed write | Crash cut 0 before prepare, 1 after prepare, 2 after commit; durable protocol flag; old values 0..2; admission durable flag. |
| [POB-038](cases/POB-038.json) | Generation-tagged handle lifetime | Handle/current generations 0..2, live flag; admission generation check enabled; no wraparound within model. |
| [POB-039](cases/POB-039.json) | Randomized success guarantee | Four equiprobable pairs if independent; correlated distribution repeats (0,0),(1,1); admission independence. |
| [POB-040](cases/POB-040.json) | Linear resource growth | n 0..5, per-item cost 0..3; admission cost<=2; finite count model. |

The corpus now contains 40 proposed public families (108 reference/mutation/alternative runs). The third cohort adds per-obligation outputs and assumption violations to existing finite smoke evidence. The six forms and ten domains are covered at the declared five-dimension target if the executable gate succeeds. Independent review, private held-out families, richer combinations, full weak-memory models, unbounded proof, general distributed consensus, full type soundness, numerical error propagation, and actual backend/LLM evaluation remain outstanding. Do not equate a finite witness or matrix saturation with exhaustive semantics. Evidence conflicts, unsupported capabilities, invalidation and backend-specific failures remain tracked in #395 and #397.

The third-cohort models are synthetic finite profiles, not assertions of LLMLang language rules. Use the [independent review gate](COVERAGE-AND-REVIEW.md) before promoting any case to reviewed.
