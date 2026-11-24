# Second cohort: coverage, provenance and review

Status: proposed, author-level cross-checks only. Supports [#394](https://github.com/aivibeflow/LLMLang/issues/394); independent adjudication is still required. The 24 public families are development data, not a hidden test set. No claim of scientific completeness.

## New falsifiers and hand-derived witnesses

| Case | Mutant witness | Why rejected |
|---|---|---|
| POB-013 | x=0 | Required admissible witness incorrectly rejected; prevents vacuous acceptance. |
| POB-014 | present integer 0 | Truthiness discards a valid typed value. |
| POB-015 | n=-2, d=0 | Zero is not the required error outcome. |
| POB-016 | x=-2 | Raw argument violates nonnegative callee precondition even though its square is correct. |
| POB-017 | deliveries 0,0 | Retry credits twice instead of once. |
| POB-018 | n=-5 | -2.5 rounds to -2 (even), not -3. |
| POB-019 | uniform four-outcome space | 3:1 output mass contradicts the required 1:1 distribution. |
| POB-020 | R0,R1,W0,W1 | Both reads observe zero; non-atomic writes leave final counter 1 instead of 2. |
| POB-021 | id=0, enabled=false | Defaulting changes explicit false to true. |
| POB-022 | p=0,s=0,t=1 | Public step counts differ even though public values match. |
| POB-023 | n=1 | Stuttering violates strict descent and the bounded termination contract. |
| POB-024 | x=3 | Target admits value rejected by source upper bound. |

Each new case has two valid candidates and a mutation; tests check hand-derived witnesses explicitly. This is a separate-method author cross-check, not independent review. Some alternatives share logic with the reference and do not establish implementation independence. The runner checks the case-level conjunction, not each decomposed obligation independently.

## Source crosswalk (inspiration, not equivalence)

Pinned source revision: `680f01f213e550c4e19c28e9271c2828ee409537`. These sources motivate selected semantic features; the finite cases narrow their scope and do not inherit proofs or normative status.

| Case | Source at pinned revision |
|---|---|
| POB-001 | [CF-001-sum-array.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/CONTRACT-FORMALIZATION-CORPUS/cases/CF-001-sum-array.md) |
| POB-002 | [CF-003-first-match.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/CONTRACT-FORMALIZATION-CORPUS/cases/CF-003-first-match.md) |
| POB-003 | [CF-005-sort-array.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/CONTRACT-FORMALIZATION-CORPUS/cases/CF-005-sort-array.md) |
| POB-004 | [CF-004-reverse-range.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/CONTRACT-FORMALIZATION-CORPUS/cases/CF-004-reverse-range.md) |
| POB-013 | [RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) |
| POB-014 | [RESEARCH-SCENARIO-62-OPTIONAL-VALUES-AND-NULLABILITY.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-62-OPTIONAL-VALUES-AND-NULLABILITY.md) |
| POB-015 | [RESEARCH-SCENARIO-45-NUMERIC-SEMANTICS-AND-OVERFLOW.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-45-NUMERIC-SEMANTICS-AND-OVERFLOW.md) |
| POB-016 | [RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md) |
| POB-017 | [RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md) |
| POB-018 | [RESEARCH-SCENARIO-78-FLOATING-POINT-REPRODUCIBILITY-AND-IEEE-EDGES.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-78-FLOATING-POINT-REPRODUCIBILITY-AND-IEEE-EDGES.md) |
| POB-020 | [RESEARCH-SCENARIO-61-CONCURRENT-MUTABLE-STATE-AND-MEMORY-MODEL.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-61-CONCURRENT-MUTABLE-STATE-AND-MEMORY-MODEL.md) |
| POB-021 | [RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md) |
| POB-022 | [RESEARCH-SCENARIO-38-EFFECTS-CAPABILITIES-AND-AUTHORITY.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-38-EFFECTS-CAPABILITIES-AND-AUTHORITY.md) |
| POB-023 | [RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) |
| POB-024 | [RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md](https://github.com/aivibeflow/LLMLang/blob/680f01f213e550c4e19c28e9271c2828ee409537/research/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md) |
| POB-019 | Synthetic four-outcome probability model; no external source. |

## Coverage and gaps

All six forms and ten domains have at least one labeled seed, but label presence is not adequacy. POB-020 exercises six sequentially consistent interleavings and final-state refinement, not general linearizability or weak memory; POB-017 assumes single atomic durable receiver, not a consensus protocol. POB-019 is an exact finite distribution, not statistical testing or a PRNG guarantee. POB-018 uses rational half-ties, not IEEE NaN, signed zero or numerical stability. POB-014 is option elimination, not a complete type system. POB-016 checks a single caller/callee relation, not a general proof DAG. POB-022 observes an abstract cost trace, not actual timing leakage. POB-024 tests one finite predicate correspondence, not compiler correctness.

Still required: actual concurrency history linearizability, weak-memory litmus tests, distributed partitions/crash recovery and consensus, unbounded progress and fairness, dependent typing and memory ownership, IEEE semantics, randomized algorithms with explicit distributions, resource growth, incompatible contracts, stale evidence, unsupported/unknown/error and backend conflict controls (coordinate #395 and #397). Add cases only where they discriminate new failures.

## Independent review gate

A reviewer not authoring the candidate/oracle must record exact case revision and content hash, reviewer identity, review date, separately derived oracle or proof, positive/negative witness replay, scope/assumptions review, equivalent allowed solutions, discrepancies and adjudication. Use a second reviewer to resolve conflicts. A status may become reviewed only after that evidence is committed; preserve older revisions. Hold-out cases must be privately curated and frozen before experiments, with family separation from public examples. Do not call the public seed held-out or claim training contamination is absent.

## Third-cohort update

See [finite coverage matrix](COVERAGE-MATRIX.md) for added bounded profiles and the executable coverage target. The historical gaps above describe the second cohort; the new fixtures address some of them at explicit finite scope, not as general proofs. Independent adjudication remains required.
