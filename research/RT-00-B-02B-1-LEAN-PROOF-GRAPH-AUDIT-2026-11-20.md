# RT-00 B-02b.1 — Lean proof graph audit

**Audit snapshot:** `c35ba93c031684100dcdbc06a34b0e14696c37ab`  
**Date:** 2026-11-20  
**Scope:** `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`, Scenario 34, family README, and the Required CI workflow.  
**Method:** read-only source and workflow inspection through the GitHub repository tree and file contents. No local Lean build was run during this audit; build/test evidence is the CI run cited below.

## 1. Executive result

The Lean prototype contains a real kernel-checked correspondence chain for the restricted deterministic Int/Bool source fragment:

1. typed source expressions;
2. deterministic command execution;
3. symbolic command translation;
4. program observations;
5. paired executions;
6. a canonical relational formula;
7. strict QF_LIA admissibility.

The chain is implemented across separate modules. It is **not** yet an end-to-end proof that the serialized version-2 query or the CPC assumptions parsed by Logos are exactly the formula derived from a source program. Scenario 34 correctly remains **In progress**.

## 2. Audited source graph

The directory contains 21 Lean files, including `lakefile.lean`. The semantic/library and test-module import graph is:

```text
SourceQuerySemantics
├── SourceSyntax
│   └── CheckedSourceSemantics
│       └── SourceCommandSemantics
│           └── SymbolicCommandSemantics
│               └── ProgramObservationSemantics
│                   └── PairedObservationSemantics
│                       └── CanonicalQuerySymbols
│                           └── ProgramRelationalQuery
│                               └── QfLiaAdmissibility
├── RelationalSourceQuerySemantics
│   └── CanonicalQuerySymbols
└── QfLiaQuery
    └── LogosQueryAdapter
        └── QfLiaAdmissibility

LLMLangLogosBinding
  imports QfLiaQuery, Lean, and Cpc.Parser

Main
  imports LLMLangLogosBinding, SourceSyntax,
  RelationalSourceQuerySemantics, and LogosQueryAdapter
```

Test modules import the semantic module they exercise. `ProgramRelationalQueryTests` imports `QfLiaAdmissibility`. There is no import cycle in the inspected graph.

The architecture is meaningfully layered: the source/query semantic core is independent of the CPC parser. The parser bridge is in `LLMLangLogosBinding.lean`; the executable integration checks are in `Main.lean`.

## 3. SC-1 through SC-7 traceability

| Scenario 34 claim | Kernel-checked declaration | Module |
|---|---|---|
| SC-1 — expression typing preservation | `translateExpr_preserves_typing` | `CheckedSourceSemantics.lean` |
| SC-2 — expression evaluation preservation | `translateExpr_preserves_eval` | `SourceQuerySemantics.lean` |
| SC-3 — command-sequence preservation | `translateCommands_preserves` | `SymbolicCommandSemantics.lean` |
| SC-4 — program observation preservation | `translateProgramObservations_preserves` | `ProgramObservationSemantics.lean` |
| SC-5 — paired-execution preservation | `pairedObservations_preserved` | `PairedObservationSemantics.lean` |
| SC-6 — relational-query correctness | `compileRelationalQuery_correct`, `compileRelationalQuery_satisfiable_iff` | `ProgramRelationalQuery.lean` |
| SC-7 — QF_LIA admissibility | `compileRelationalQuery_qfLia` | `QfLiaAdmissibility.lean` |

The proofs are distributed across the implementation modules. Scenario 34's proposed `Correspondence.lean` is an architectural proposal, not a file present in this snapshot.

The theorem chain is for the explicitly restricted source fragment in Scenario 34: mathematical Int and Bool, finite declarations, deterministic commands, a single final return, explicit initial state, and selected observations. It does not establish semantics for arbitrary LLMLang programs or excluded language features.

## 4. Lean examples and executable integration checks

The six Lean example modules contain the following numbers of `example` declarations, each checked when the module is compiled:

| Module | Lean examples |
|---|---:|
| `SourceCoreTests.lean` | 29 |
| `SourceCommandTests.lean` | 22 |
| `SymbolicCommandTests.lean` | 17 |
| `ProgramObservationTests.lean` | 18 |
| `PairedObservationTests.lean` | 16 |
| `ProgramRelationalQueryTests.lean` | 23 |
| **Total** | **125** |

These are kernel-checked examples, not 125 end-to-end tests. `Main.lean` additionally runs executable checks for declaration-context lookup and parser-state binding, including rejection cases.

## 5. Toolchain and CI evidence

- `logos_binding/lean-toolchain` pins `leanprover/lean4:v4.36.0`.
- `lakefile.lean` pins the Logos/CPC dependency to commit `cf18742973861b3718d04c5f25775448098ff474`.
- The package sets `warningAsError := true`.
- The Logos-binding workflow installs Lean 4.36.0, resolves the pinned Lake dependency, runs `lake build --fail-fast LLMLangLogosBinding`, then runs `lake env lean -DwarningAsError=true --run Main.lean`.
- Required CI run [#44801357527](https://github.com/aivibeflow/LLMLang/actions/runs/44801357527) passed on the exact audited HEAD `c35ba93c031684100dcdbc06a34b0e14696c37ab`. The Logos build and Main execution steps both passed.

This is current CI evidence, not a local reproduction performed as part of this audit.

## 6. Axiom and trust-boundary findings

A static scan of the 21 Lean files found no explicit `sorry`, `admit`, project-local `axiom`, or `opaque` declaration. This scan is not a substitute for an axiom-dependency report generated by Lean.

Scenario 34 records standard Lean axioms (`propext`, `Classical.choice`, and `Quot.sound`) for selected theorem groups. The project-wide CI-enforced axiom audit is still open as SCW-39. Therefore this audit does not claim that the full theorem dependency closure has been independently enumerated or policy-checked.

The trust boundary remains incomplete beyond the canonical Lean query:
- SCW-30: solver-facing declaration closure;
- SCW-31: canonical JSON / version-2 wire correspondence;
- SCW-32: connection of the proved formula to Logos terms and parser-state identity;
- SCW-33: exact CPC assumptions bound to the source-derived formula;
- SCW-34: explicit solver/checker trusted-computing-base statement.

SCW-35–38 adversarial acceptance fixtures, SCW-39 automated axiom audit, SCW-40 dedicated proof CI gate, and SCW-41 milestone evidence are also marked open in Scenario 34. The existing Required CI is useful evidence, but it does not by itself close those acceptance tasks.

## 7. Documentation inconsistencies

The implementation and CI pin Lean 4.36.0, but:
- `research/PROTOTYPES/DEPENDENCY-GRAPH-01/README.md` still says Lean 4.34.0 and cites the older run #44766546452 as the latest relevant Logos-binding run;
- `research/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md` still describes the SCW-06–09 build as Lean 4.34.0.

These are documentation freshness issues; they do not invalidate the successful current build. SCW-05's dedicated breakdown is now marked Complete and explicitly limits its scope to the declaration-context data model.

## 8. Conclusion and disposition

**Disposition: B-02b.1 source inspection complete, with explicit open proof-boundary items.**

The Lean proof chain SC-1–SC-7 is present and the exact audited revision passes Required CI. The appropriate claim is a kernel-checked correspondence result for the restricted formal fragment through the canonical QF_LIA query IR. It is not yet a verified source-to-JSON-to-CPC pipeline and must not be presented as such.

No source code or existing research result was modified by this audit. Documentation freshness and the open SCW-30–41 work remain visible follow-up items.
