# RT-00 — Quality rules evidence-shape recheck

**Research item:** `PLAN.md` §0.2 — Establish research quality and decision rules  
**Date:** 2026-11-23  
**Current-main baseline:** `345f8b97683de91e31271e2055c44063d4dc1da9`  
**Status:** Comparative method recheck; no policy adopted  
**Scope:** Test whether the proposed common report/claim fields remain useful across three different evidence shapes—an executable build benchmark, a machine-checked Lean development, and a bounded memory-model study—and distinguish common fields from type-specific reproduction fields.

## Question and alternatives

The existing [Research Quality and Decision Rules](../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md) proposes a common report structure, per-claim evidence classification, and gates Q1–Q5. This recheck asks whether one required template can serve the three evidence shapes inspected here.

- **A — One fixed template:** require every report to fill each common section and claim-table field.
- **B — Shared minimum with evidence-specific attachments:** require traceability, scope, method/provenance, result class, limits, and decision boundary, while making reproduction and evidence pointers specific to the claim type.
- **C — Free-form reports plus indexes:** rely on author judgment and cross-document navigation, without a common minimum claim record.

The comparison evaluates discoverability and ability to reproduce/check the specific evidence. It does not establish reviewer usability or choose project policy.

## Method and environment

Inspected the current-main versions of:

1. [RT-11 Binding Invalidation Benchmark](../../toolchain-and-collaboration/RT-11/RT-11-BINDING-INVALIDATION-BENCHMARK.md), an executed synthetic C build/link/verification action-count benchmark.
2. `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`, a Lean/Lake development with source, theorems, tests, exact Lean toolchain, and pinned Logos dependency.
3. [Scenario 118](../../language-design/RT-04/RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md), a bounded model and independent sequential-interleaving comparison.

The RT-11 benchmark was freshly run from the exact current-main source with CPython 3.12.14, Debian GCC-compatible `cc` 14.2.0, and x86_64 Linux. Command, run output, and comparison are below. The Lean source/toolchain/dependency metadata and `logos-binding.yml` workflow were inspected; neither `lean` nor `lake` is installed in this local environment, so no local proof/build rerun is claimed. The latest Required CI build on current main `345f8b9` is the relevant independent build evidence; this recheck did not rerun that workflow. Scenario 118's report-level method, seven-test note, baseline commit, and stated limits were inspected; its historical tests were not rerun here.

## Evidence-shape comparison

| Evidence shape | Useful common fields | Required evidence-specific fields | Current observation |
|---|---|---|---|
| **Executable benchmark — RT-11** | Question, alternatives, exact source revision, scope/assumptions, method, result class, limitations, decision boundary, downstream links. | OS/architecture, compiler and version, command/options, generated fixture/action model, raw structured output, expected invariants, clean-build oracle, timing versus action-count distinction. | Reproduced on Linux/GCC: all 12 linkage/phase combinations completed. Separate linkage reduced caller compiles on implementation change from 12 to 4, while 12 targets still linked and re-verified. Compile inputs stayed identical while outputs changed from `(10,11,10,11)` to `(11,12,11,12)`, falsifying a compile-input-only verification key in this fixture. This is action-count evidence, not a wall-time or LLMLang compiler measurement. |
| **Lean formal development — Logos binding** | Question/claim, formal scope and assumptions, exact revision, result class, correspondence limit, decision boundary. | Theorem/definition names, Lean version, Lake manifest and dependency commit, build/test command, checker/build result, axioms/admitted goals if any, exact target file/module. | The repository pins Lean `v4.36.0` and Logos commit `cf18742973861b3718d04c5f25775448098ff474`; current CI invokes `lake build --fail-fast LLMLangLogosBinding`. Local rerun was unavailable because `lean` and `lake` are not installed. A generic experiment-style `seed/raw-output` field would not fit; theorem target and formal context are the correct evidence pointer. Build success still does not establish source/compiler correspondence. |
| **Bounded memory-model comparison — Scenario 118** | Research question, candidate relations, model result, scope, falsifier/counterexample, implementation decision boundary. | Operation grammar, relation axioms, enumeration bounds, independent oracle, exact script/test entry point, generated case counts, toolchain when executed. | The report states a fixed load/store fragment and 4,096 generated programs, with seven focused tests and explicit exclusions (RMW, fences, mixed sequential consistency, target lowering). These bounds and exclusions are material claim scope; a broad document-level “Proof” label would be misleading. |

## Current-main benchmark reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python3 -B -m src.binding_build_benchmark --cc cc
```

The process returned exit code 0 and emitted a JSON result with 12 cases. All cold/warm, implementation, contract, history, and compiler-flag phases matched the benchmark's clean-build output checks in both exact and separate linkage modes. The key comparison was:

| Implementation edit | Caller compiles | Links | Verification runs |
|---|---:|---:|---:|
| Exact linkage | 12 | 12 | 12 |
| Separate linkage | 4 | 12 | 12 |

Both the projected and whole-snapshot verification keys reran the 12 affected executables. The result preserves the main study's limits: the workload is synthetic, the local compiler/SDK are fixed, action counts are not timings, and production dependency discovery, remote trust, and LLMLang implementation behavior are not measured.

## Comparison result

**B — shared minimum with evidence-specific attachments** has the strongest provisional balance. Across all three shapes, a stable question/scope, revision, assumptions, result class, limitations, downstream links, and explicit decision boundary make the claim interpretable. The reproduction payload must vary by evidence type: a benchmark needs a runnable fixture plus environment and output invariants; a proof needs exact theorem/build target, formal context, toolchain, and checker result; a bounded model needs its grammar, bounds, oracle, and excluded cases. Prior-art claims need authoritative source/version provenance, not an executable command.

The proposed rules already allow reports to combine sections and distinguish model results, experiments, and proofs. The evidence-shape review sharpens one implementation choice: keep Q1–Q5 as review questions, but use a short common metadata block plus type-specific evidence pointer rather than requiring every report to duplicate the full claim table. A claim table is most useful for mixed reports or conclusions that drive a specification choice; short scenario notes can use a compact claim/evidence sentence when all fields remain explicit.

Vector A offers strong uniform fields but risks a duplicated claim register, especially where the report itself is the proof/model. Vector C has the least authoring overhead but makes cross-type reproduction hard to locate consistently. These are document-level observations, not measured reviewer outcomes.

## Recommendation, not a decision

Pilot Vector B on one new executable experiment, one proof-producing report, and one mixed prior-art/model report. Measure time-to-find claim evidence, missing-field rate, duplicate prose, reviewer disagreement, false-positive rate for any automated checks, and maintenance time. Do not promote a template or CI gate to accepted policy until maintainers review this evidence.

## Remaining dependencies and limits

- Maintainer adoption of evidence vocabulary, minimum fields, template, and gates remains external to this study.
- This three-shape comparison is purposive, not a representative sample of all research documents; no reviewer usability or authoring-cost study was conducted.
- The Lean build was not locally repeated. Current Required CI is the only build evidence referenced here; exact source-to-LLMLang/compiler correspondence remains separately open.
- Scenario 118's historical test run was not repeated; this report checks its documented evidence shape, not the correctness of its result.
- Corpus-wide claim-level coverage and clean-environment reproduction of foundational claims remain Stage 0.2/0.1 work.

**Conclusion:** a common quality floor is applicable, but evidence pointers and reproduction payloads must remain type-specific. This study provides comparative input for choosing a rollout approach; it does not close §0.2 or accept project policy.
