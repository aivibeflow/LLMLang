# Cross-Cutting Research Document Alignment Review — 2026-11-20

**Status:** first-pass consistency review  
**Baseline:** current main before this review, `c35ba93c031684100dcdbc06a34b0e14696c37ab`  
**Scope:** research taxonomy, dependency map, option matrix, semantic dependency index, draft glossary, PLAN.md, and repository indexes  
**Decision boundary:** terminology and document alignment only; no identity, hash, semantic-index, or architecture choice is accepted

## 1. Taxonomy and dependency-map integrity

The cross-cutting counts agree:

| Source | Verified count | Result |
|---|---:|---|
| Research taxonomy | 24 unique research-area rows, RT-01 through RT-24 | Matches inventory |
| Research dependency map | 94 unique dependency rows, DEP-001 through DEP-094 | Matches inventory |
| Dependency-map graph | 24 RT nodes, 94 directed edges | No missing or duplicate DEP IDs; no self-loops |

The dependency map's feedback relationships are documented rather than hidden:

- RT-05 identity and RT-12 package identity form a feedback relationship; the map also records the influence of RT-13 target context.
- RT-14 Knowledge/Task Context, RT-19 Toolchain Server, and RT-20 Change Impact Planning form a documented operational feedback cycle. The edges are detailed in DEP-045, DEP-055, DEP-058/059, and DEP-082–085.
- The SCCs found in the directed graph correspond to these documented feedback relationships. No additional undocumented strongly connected component was found in this first pass.

The taxonomy, dependency map, and option matrix have distinct roles. The taxonomy defines research areas; the map records conditional cross-area relationships; the option matrix compares candidate vectors. They are related management artifacts, not semantic duplicates.

## 2. Glossary and hash terminology

The [draft glossary](../draft/GLOSSARY.md) defines the proposed terms:

- generic `ContractHash`;
- `OpHash` for an operation;
- `ImplHash` for an implementation;
- `CCHash` for a conformance class;
- optional `CandidateSetHash` for a time/scope-specific candidate set.

The plan uses `ImpHash` in several identity tasks while the glossary uses `ImplHash`. This is **already explicitly recorded as unresolved** in PLAN.md §0.1: the spelling must be reconciled before either is treated as normative. The discrepancy is not silently normalized in this review, and no hash payload, envelope, domain-separation, or lifecycle decision is made.

The glossary remains a proposal. Its open points and the plan's terminology prerequisite are consistent; neither source establishes an accepted canonical identity schema.

## 3. Semantic Dependency Index boundary

[`SEMANTIC-DEPENDENCY-INDEX.md`](SEMANTIC-DEPENDENCY-INDEX.md) is a candidate design for immutable dependency edges, discovery evidence, completeness records, and consumer-specific projections. It is not the cross-aspect RT dependency map and is not a canonical SPG schema.

The index's status is consistent with PLAN.md and RT-24: the executable subset and call-site binding experiments are evidence, while canonical identity, wire representation, completeness semantics, and merge policy remain open.

The document had a duplicate section number: a later `Snapshot-scoped reverse-query completeness binding` heading was numbered §9 after an earlier §9, and the final RT-24 relationship heading was unnumbered. This review renumbers those headings to §13 and §14. No content or semantic claim is changed.

The hash terminology in the index remains provisional and is subject to the explicit `ImpHash`/`ImplHash` reconciliation prerequisite. A link to the draft glossary is added to the index's hashing section.

## 4. Option matrix and decision status

The [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md) defines common evaluation criteria and a discriminating research programme. Its readiness section explicitly leaves source correspondence, cross-profile type/resource validation, identity envelopes, program proofs, the two-backend slice, threat-model evidence, and workload weights open.

This is consistent with PLAN.md's status that no semantic profile or complete type/effect/ownership architecture has been accepted. “Readiness assessment” does not mean a candidate vector has been selected. Unknown criteria are not scored as zero; the matrix requires them to remain unknown until evidence exists.

## 5. RT-24 and ADR status

RT-24 remains a proposal. The taxonomy and dependency map describe its candidate scope; the plan records the candidate technical contract as non-normative. ADR-014 remains Proposed. The historical embedded ADR-0001 proposal is superseded as a proposal by ADR-014 and the Git representation/semantic merge research, but this does not accept ADR-014 or settle the canonical semantic representation.

## 6. Index and navigation alignment

The repository root README already links the draft glossary and semantic dependency index. The research index did not provide direct links to those cross-cutting references; this review adds them so research readers can find the candidate index and the terminology prerequisite without relying on the root README.

The taxonomy and dependency map are already linked from the research index and cross-reference each other. No missing inbound reference was found for these two documents.

## 7. Findings and limits

1. Taxonomy count (24 RT areas), dependency-map count (94 DEP edges), and inventory counts agree.
2. The map's directed feedback cycles are represented in its prose and detailed edge register; no hidden SCC was found in the first pass.
3. The `ImpHash`/`ImplHash` discrepancy is a known unresolved terminology issue, explicitly flagged by PLAN.md. It is not resolved here.
4. The semantic dependency index is a candidate model, not a canonical SPG or accepted architecture.
5. The option matrix is a comparative programme, not a decision record.
6. The duplicate section numbering in the semantic dependency index is an editorial defect and is corrected.
7. The draft glossary remains a draft; no new glossary terms are introduced.

This review does not validate the technical soundness of every DEP rationale, prove the completeness of the option space, or decide any identity/hash boundary. It only checks cross-document consistency and navigation.

**Conclusion:** the taxonomy and dependency map are structurally consistent with the inventory (24 RT areas and 94 DEP edges). The major terminology discrepancy is already explicitly unresolved, and the candidate/non-normative status of the glossary, option matrix, semantic dependency index, and RT-24 proposal is consistent across the reviewed documents. The only confirmed editorial defect was duplicate section numbering in the semantic dependency index; it is corrected without changing content.


## 8. Inventory delta discovered during count reconciliation

The reviewed main tree also contains two package-index diagnostics added after the prior 471-record inventory snapshot:

- [`run_tests_with_timings.py`](PROTOTYPES/PACKAGE-INDEX-01/run_tests_with_timings.py), added by PR #105. It is invoked on every `package-index` workflow run. It discovers the package-index unittest suite, records per-test wall-clock durations, and emits the 20 slowest tests plus total suite duration.
- [`profile_package_provider.py`](PROTOTYPES/PACKAGE-INDEX-01/profile_package_provider.py), added by PR #109. It is compiled by the workflow and invoked only when `run_benchmark=true`; it uses `cProfile` around a bounded disk-backed Provider build.

Both files are prototype diagnostics, not normative package-index semantics. Both are referenced by the workflow; the timing runner is also used by the package-index README's Run instructions. They are not orphan files. Their roles are recorded individually in the refreshed inventory, and the README file index now links both.

Including these two Python files and this review report, the inventory snapshot contains 474 research files: 241 Markdown/MDX, 199 Python, 22 Lean source files, and 245 prototype-tree files. The earlier 471-record inventory was stale by two package-index diagnostics before this report was added.
