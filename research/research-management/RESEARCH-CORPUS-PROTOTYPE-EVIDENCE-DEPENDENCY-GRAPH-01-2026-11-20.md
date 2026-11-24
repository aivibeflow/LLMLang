# Prototype Evidence Graph Review — Dependency Graph and Logos Binding — 2026-11-20

**Status:** first-pass semantic and provenance reconciliation for the Lean source-to-query proof family  
**Baseline:** current main before this review, `e2aa15b8006659f6d256aa61fd294911aa73c21f`  
**Scope:** `research/PROTOTYPES/DEPENDENCY-GRAPH-01/`, its Lean `logos_binding` subproject, Scenario 27/34 evidence, SCW-04/05 task records, and the Logos-binding CI workflow  
**Decision boundary:** current-state and traceability audit only; no architecture choice is made

## 1. Family structure

The Dependency Graph prototype family contains 103 files. The `logos_binding` subproject contains 21 Lean modules, `lakefile.lean`, `lean-toolchain`, and two SCW task/audit documents. The inventory's count of 22 Lean files includes the 21 source modules plus `lakefile.lean`.

The family README is an overview, not a complete file manifest: a basename scan finds many implementation/test files not named directly in that README. This is not sufficient to classify them as orphans. The inventory and Scenario 34 report provide additional file-role and proof crosswalks. A complete import/test/fixture graph for all 103 family files remains open.

## 2. Current Lean module graph

The current source graph separates the relational semantics from the external Logos/CPC integration layer:

| Layer | Files | Responsibility and evidence boundary |
|---|---|---|
| Source IR and declarations | `SourceQuerySemantics.lean`, `SourceSyntax.lean` | Independent source/query terms, stable variable identity, declaration role/sort, and finite declaration context. `SourceSyntax` does not import the external Logos/CPC parser. |
| Checked source semantics | `CheckedSourceSemantics.lean`, `SourceCoreTests.lean` | Checked declarations and core identity/context tests. |
| Command semantics | `SourceCommandSemantics.lean`, `SourceCommandTests.lean`, `SymbolicCommandSemantics.lean`, `SymbolicCommandTests.lean` | Concrete and symbolic command execution for the checked fragment. |
| Observation semantics | `ProgramObservationSemantics.lean`, `ProgramObservationTests.lean`, `PairedObservationSemantics.lean`, `PairedObservationTests.lean` | Single-program and paired-program observations used by relational reasoning. |
| Relational IR and query construction | `RelationalSourceQuerySemantics.lean`, `CanonicalQuerySymbols.lean`, `ProgramRelationalQuery.lean`, `ProgramRelationalQueryTests.lean` | Independent relational formula construction and canonical query symbols. `RelationalSourceQuerySemantics` imports `SourceQuerySemantics` only. |
| QF_LIA and adapter boundary | `QfLiaQuery.lean`, `LogosQueryAdapter.lean`, `QfLiaAdmissibility.lean` | A separate query AST and adapter. `LogosQueryAdapter` converts the independent query term and proves `toLogosQueryTerm_preserves_eval`; admissibility is checked separately. |
| External parser/renderer integration | `LLMLangLogosBinding.lean` | Imports `QfLiaQuery`, Lean, and `Cpc.Parser`; owns the Logos/CPC term renderer, JSON decoder, and parser-state bridge. |
| Integration and test entrypoint | `Main.lean` | Integrates the modules and runs bounded semantic correspondence/identity checks. |
| Build definition | `lakefile.lean`, `lean-toolchain` | Declares the build targets and pinned Lean toolchain. |

This graph is based on the current imports and declarations, not on directory placement. The source modules and their test modules remain distinct evidence artifacts.

## 3. SCW-04: historical audit finding and current disposition

The [SCW-04 module-boundary audit](../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SCW-04-MODULE-BOUNDARY-AUDIT.md) was written before the SCW-15 decoupling work. Its original observation—that relational proofs directly depended on `LogosBinding.QueryTerm` and the external parser integration—was accurate for the source state it audited.

That observation is no longer a description of current main:

- `RelationalSourceQuerySemantics.lean` imports `SourceQuerySemantics` only.
- `LogosQueryAdapter.lean` is a separate adapter to `LogosBinding.QueryTerm`.
- The adapter contains `toLogosQueryTerm_preserves_eval`.
- `QfLiaAdmissibility.lean` consumes the relational program and adapter separately.
- `LLMLangLogosBinding.lean` owns the actual `Cpc.Parser` integration.

The SCW-15 decoupling and adapter work is recorded as complete in [Scenario 34](../formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md) and was implemented in PR #41, with subsequent build/test coverage in PR #43 and the later PR #94 Logos-binding CI run. The old SCW-04 finding is retained as historical evidence; its current status is clarified by the addendum to that audit.

This does **not** close the later source-derived CPC binding and parser-state identity obligations. Scenario 34 still leaves SCW-32 and related follow-up work open.

## 4. SCW-05 declaration-context breakdown

The [SCW-05 declaration-context breakdown](../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SCW-05-DECLARATION-CONTEXT-BREAKDOWN.md) still says `In progress` and leaves all seven tasks unchecked. This conflicts with Scenario 34 §7, which records SCW-05 as complete, and with the current source:

- `SourceSyntax.lean` defines stable `VariableId`, `DeclarationRole`, declaration sort, and `DeclarationContext` lookup.
- `SourceCoreTests.lean` checks identity-based lookup and declaration properties.
- `Main.lean` includes the integration checks.
- `lakefile.lean` includes the relevant build targets.

The stale status is a documentation inconsistency, not evidence that the implementation is absent. The SCW-05 breakdown is updated in this change to mark its seven scoped tasks complete and to point to Scenario 34 and the successful CI evidence. Broader context validation and scope uniqueness remain separate SCW-06 work and are not claimed complete by SCW-05.

## 5. CI evidence and current-source boundary

The latest relevant Logos-binding CI run is [44766546452](https://github.com/aivibeflow/LLMLang/actions/runs/44766546452), associated with PR #94. Its `logos-binding` job passed both:

- `Build parser-state bridge`;
- `Run parser-state binding and semantic correspondence tests`.

The PR #94 merge commit is `8286ce3cf8c7f77b6c4f927e747bd93211e2d943`. Comparing it with the reviewed current main revision shows no subsequent changes to `.lean` files, `lakefile.lean`, or `lean-toolchain`. Later changes in that interval are documentation, inventory, audit, or workflow files. The PR #94 run therefore validates the current Lean source tree, while the later Required CI aggregate is not misrepresented as a fresh Lean build.

The CI result proves that the configured build and test targets passed in that pinned environment. It does not prove the full source-language-to-CPC correspondence, complete JSON schema semantics, or all solver-facing declaration closure. Those remain explicit Scenario 34 limitations.

## 6. Navigation and unresolved relationship findings

1. The family README did not directly link to Scenario 34, SCW-04, or the SCW-05 breakdown. This review adds those links and a compact Lean-module map.
2. The SCW-05 breakdown had no inbound link from Scenario 34 or the family README. It is now linked from both; it was an orphan candidate by navigation, not by semantic purpose.
3. The family README did not directly link to `PROTOTYPE-27-RESULTS.md`; the repository root README already did. A family-local link is added for consistency.
4. The README's incomplete basename coverage is not proof that the remaining Python files are orphans. Their test/import/workflow relationships still require a complete graph pass.
5. Scenario 34 remains in progress: source-derived CPC binding, serialized-query correspondence, and parser-state identity are not promoted to completed claims by the SCW-15/SCW-05 updates.

**Conclusion:** the dated SCW-04 audit and SCW-05 task breakdown contained stale current-status statements. The source graph and Scenario 34 show that SCW-15 decoupling and SCW-05 declaration-context work are implemented; the latest Logos-binding CI run passes on the current Lean source tree. The later CPC/JSON correspondence work remains open. The family README now links the key proof modules and task records, but a complete semantic dependency graph for every file in the 103-file family is still required.
