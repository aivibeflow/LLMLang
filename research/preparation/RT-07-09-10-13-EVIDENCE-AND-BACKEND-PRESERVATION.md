# Research Preparation — RT-07/09/10/13 Evidence and Backend Preservation

**Status** — Prepared, with the bounded integer corpus executed in Scenario 96A.

**Priority:** P0/P1 — execute after a bounded source-semantic slice is explicit.  
**Related open questions:** LL-008, LL-013–020; RT-07, RT-09, RT-10 and RT-13 gates.

## 1. Objective

Define what each evidence class proves and prepare a narrow executable preservation gate that compares source/reference semantics with a second implementation or backend. Include the LLVM-specific semantic hazards without assuming LLVM is the selected backend.

## 2. Existing material

Read:
- [Formal verification architecture](../formal-verification/RT-07/LLMLang-FORMAL-VERIFICATION.md)
- [Scenario 34 — source-to-query correspondence](../formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md)
- [Scenario 96 — LLVM UB, poison and semantic preservation](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md)
- [Scenario 133 — generated Rust for owned results](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md)
- [RT-03/04 shared corpus](../language-design/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md)
- [Research State](../research-management/RESEARCH-STATE-2026-11-19.md), Gates C and A

Scenario 133 is a bounded generated-Rust result for COR-13 and its tested transfer rules. It does not by itself establish a general translation pipeline, a second production backend, native foreign-effect correspondence or whole-language preservation.

Scenario 96A executes the integer portion of the LLVM discriminators at O0 and O3. The two profiles preserve the tested observations, and the differential corpus detects a lost overflow error in structurally valid IR. [LLVM integer preservation](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md)

## 3. Evidence schema to prepare

For every evidence item specify:

| Field | Required meaning |
|---|---|
| Claim ID | Stable identifier for the exact proposition |
| Subject | Exact source/semantic snapshot and affected entities |
| Assumptions | Environment, semantic profile, target and excluded behaviors |
| Evidence class | Test, property test, differential test, model check, proof, refinement or trusted observation |
| Producer | Tool/implementation identity and version |
| Checker | Independent checker or explicit trusted boundary |
| Inputs | Exact fixtures, configuration, toolchain, target and dependency closure |
| Result | Pass, fail, unknown, timeout, unsupported or not run |
| Reuse rule | Exact conditions that keep evidence valid |
| Provenance | Commit, command, raw artifact digest and reproduction route |

Do not give tests a proof status. Do not let a successful solver return establish UNSAT without the stated checking basis. Distinguish producer identity from verifier identity and from content hash.

## 4. Source/backend preservation questions

- What exact source subset is accepted by the reference semantics?
- Which observable events must be preserved: values, errors, ordered effects and payloads, resource state, cancellation, diagnostics and rejected inputs?
- What is the supported subset and fail-closed behavior of each backend?
- How are integer overflow, division, pointer bounds/provenance, LLVM poison/undefined behavior, floating-point modes, atomics and ABI constraints mapped?
- Which source constructs are intentionally unsupported by a target?
- How are runtime and foreign calls included in the observation contract?
- Which optimization flags or passes change the required proof/validation obligations?

## 5. Vertical-slice preparation

After Gate A names a bounded source fragment, choose one shared workload spanning:
- typed call and state update;
- ordered observable effect with payload;
- explicit error and cancellation path;
- owned-resource acquisition/transfer/cleanup;
- one alias-sensitive later call;
- an unsupported construct that must be rejected.

Run it through:
1. the declared reference semantics;
2. a second independently implemented semantics or backend;
3. a generated target implementation where useful.

Compare full traces and final resource states, not only return values. Keep the reference oracle independent from code generation. Pin compilers, linkers, target triples, flags, runtime/library versions and environment.

## 6. LLVM-specific preparation

Prepare discriminators for:
- signed/unsigned overflow and checked/wrapping operations;
- division by zero and minimum-integer divided by minus one;
- pointer provenance, bounds and lifetime;
- poison-producing operations and propagation;
- immediate undefined behavior versus deferred poison;
- floating-point reassociation, contraction, NaN and denormal behavior;
- atomic ordering, width and target fallback;
- optimization-level changes and semantic preservation.

Use a version-pinned source-to-IR corpus and an explicit mapping from each source operation to the LLVM construct and required preconditions. No source behavior should be inferred from a backend default.

## 7. Exit criteria

- Every evidence record names its exact proposition, subject, assumptions and trust boundary.
- Reuse fails closed on changed semantic inputs, source, target, tool, configuration or dependency closure.
- The reference semantics is fixed for the tested fragment before backend comparison.
- At least two independently implemented paths agree on all accepted fixtures or produce minimized counterexamples.
- Ordered effects, payloads, errors, resources and rejected programs are checked.
- LLVM-specific unsupported or undefined cases are explicit and never silently treated as ordinary values.
- Claims are limited to the tested subset and pinned environment.

Do not select an interpreter, VM, LLVM or native backend in this study.
