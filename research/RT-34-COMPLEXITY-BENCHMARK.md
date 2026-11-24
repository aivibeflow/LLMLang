# RT-34 — Complexity inference and resource-contract benchmark plan

**Status:** Proposed case inventory and evaluation protocol; no executable corpus or measured results claimed  
**Updated:** 2026-11-24  
**Research:** [RT-34](RT-34-AUTOMATIC-COMPLEXITY-INFERENCE.md) · [Issue #412](https://github.com/aivibeflow/LLMLang/issues/412)

## 1. Independent tracks

- CF (contract formalization): given intent, clarify required metrics, computational model, size domain and outcomes; do not silently invent a complexity guarantee. Preserve functional meaning and explicit non-requirements.
- POB (proof obligations): given canonical contract and implementation/model, generate resource obligations, infer or check bounds, distinguish assumptions and correspondence, route to eligible backend, validate evidence independently.
- Problem complexity: given specification/model, validate a lower bound theorem or reduction and a witness of attainable upper bound. Do not infer implementation complexity from a task theorem.
- Measurement: run finite workloads with exact counters and repeatable conditions; fit candidate scaling separately from proof. No finite sample proves an unbounded bound.

These CXB IDs are planning identifiers, not assigned CF/POB case IDs. Allocate stable IDs in the existing corpora when implementing fixtures; do not replace existing functional cases or claim current corpus coverage. Every row requires independent review of the expected result, formal models, and negative controls before scoring.

## 2. Proposed case matrix

Unless stated otherwise use nonnegative unbounded natural sizes and a specified constant-cost abstract primitive model; all tight claims concern worst case. Include n=0,1 and sufficiently large sizes with separate base cases.

| ID | Case and discriminator | Expected claim / negative control | Track |
|---|---|---|---|
| CXB-001 | Array sum, arbitrary contents | Theta(n) operations; unread entry changes exact sum | CF/POB/problem |
| CXB-002 | Random-access lookup | Theta(1) with fixed-cost index; linked-list variant O(n) | CF/POB |
| CXB-003 | Unsorted membership | Theta(n); early exit does not improve worst case | POB/problem |
| CXB-004 | Binary search, sorted random access | Theta(log n); sortedness and comparator cost required | CF/POB/problem |
| CXB-005 | Copying insertion vs merge sort, same CF-005 contract | Theta(n^2) vs Theta(n log n); do not invent resource requirement | CF/POB |
| CXB-006 | Comparison sorting lower bound | Omega(n log n) with arbitrary distinct keys; integer counting sort not covered | problem |
| CXB-007 | Sorting with explicit O(n log n) contract | Merge passes; quadratic worst-case family refutes insertion variant | CF/POB |
| CXB-008 | Nested loops with independent and dependent bounds | Theta(n^2), triangular sum; branch infeasibility variant | POB |
| CXB-009 | Geometric loop, n halves | Theta(log n); stuttering mutation invalidates termination | POB |
| CXB-010 | Linear recurrence and divide-and-conquer | Theta(n), Theta(n log n) with proved lower bounds; wrong split/base rejected | POB |
| CXB-011 | Naive Fibonacci vs memoized | Theta(phi^n) calls vs O(n) arithmetic ops; bit complexity separate | POB |
| CXB-012 | Dynamic array doubling | Amortized O(1) append, worst-case Theta(n); additive growth mutation | CF/POB |
| CXB-013 | BFS with adjacency list | O(V+E) traversal including initialization; matrix representation variant | CF/POB |
| CXB-014 | Explicit pairs and subsets | Theta(n^2), Theta(n*2^n) output writes; lazy/shared representation differs | CF/POB/problem |
| CXB-015 | Higher-order map with symbolic callback cost | O(n + sum callback costs); unknown callback cannot become O(1) | POB |
| CXB-016 | Pipeline sort/deduplicate/calculate | O(n log n) with size preservation; expanding intermediate mutant | POB |
| CXB-017 | Big-integer operations and Unicode indexing | Cost-profile dependence; reject unit-cost assumption outside its scope | CF/POB |
| CXB-018 | Memory lifetime vs total allocation | Sequential allocate/free vs simultaneous live buffers; peak not cumulative | POB |
| CXB-019 | Recursive depth vs tail-call lowering | Source frame depth vs target stack claim; target proof required | POB |
| CXB-020 | Parallel independent tasks vs serialized dependency | Separate work and span; scheduler assumptions explicit | CF/POB |
| CXB-021 | Randomized quicksort | Expected O(n log n) for appropriate uniform pivot randomness; worst-case Theta(n^2) | CF/POB |
| CXB-022 | External function without resource summary | UNKNOWN/UNSUPPORTED, not constant cost; assumed summary stays conditional | POB |
| CXB-023 | Self-recursion with finite fuel | Exhaustion is not successful termination; no unbounded theorem from finite trace | POB |
| CXB-024 | Correct algorithm plus unnecessary nested work | Functional contract holds; declared smaller bound may be refuted by family | CF/POB |
| CXB-025 | Piecewise and multivariate size domain | Uniform constants over declared domain; no single-variable substitution without proof | POB |
| CXB-026 | Bounded or empty admitted input family | Report nonvacuity/limited scope; do not advertise meaningful unbounded optimality | CF/POB |
| CXB-027 | Change callee body/contract/model and proof binding | Revalidate exact provider evidence and dependent closure; stale reuse rejected | POB |
| CXB-028 | Source-preserving result but extra target work | Functional correspondence does not certify target cost | POB |
| CXB-029 | Finite observations compatible with divergent asymptotics | EMPIRICAL only; arbitrary threshold can hide expensive path | POB/measurement |
| CXB-030 | Undischarged assumptions, solver timeout, malformed certificate | Conditional/unknown/error separated; no proof promotion | POB |
| CXB-031 | Costly failure/cleanup and exceptional paths | Include promised outcomes; success-only bound cannot discharge all outcomes | CF/POB |
| CXB-032 | Sorting optimality with different memory/time metrics | Match model, input domain and metric; no cross-metric optimality | problem/POB |

## 3. Case schema and oracle

Record case revision; intent and clarification transcript; typed input/size/representation domain and nonvacuity; functional contract; resource requirement (if any); exact cost rules and outcome aggregation; implementation and mutation source; expected upper/lower/tight/optimality claim; independent symbolic proof or reference theorem with assumptions; finite counterexample or asymptotic counterexample family as appropriate; proof-obligation origin and translation scope; expected status and permitted evidence strength.

Each fixture must separate reference evidence from analyzer output, specify whether the oracle is finite or unbounded, and record what it does not establish. A finite run may validate a concrete budget or refute a universal pointwise inequality with fixed constants; it cannot by itself refute or prove Big O with existential constants. Include arithmetic overflow, unreachable branches, size-domain gaps, cost-profile mismatch, stale evidence, timeout and malformed proof controls. A different but valid upper bound should score as sound, with precision scored separately.

## 4. Pilot and reporting

First implement CXB-001, 004, 005, 008, 009, 010, 016, 022, 023, 024, 026, 027, 029, 030. Use a small typed IR and explicit cost evaluator plus separately checked symbolic derivations. Pin source, profile, tool versions and baseline; publish commands, case manifest and raw artifacts. Compare manual contracts, symbolic inference, candidate proof generation and independently checked proof. For CF, evaluate omission, overconstraint, model ambiguity, and correct clarification. For POB, measure false proven/refuted claims, correct abstention, proof coverage, bound tightness, evidence strength, proof-check time, inference time, memory, cost, and incremental reuse. For problem lower bounds, check model/domain/theorem matching independently. Report per class; no aggregate score may hide unsound success.

No normative grammar, cost profile or backend is selected. Case matrix is proposed, not executed, not an exhaustive taxonomy, and not independent validation of an implementation.
