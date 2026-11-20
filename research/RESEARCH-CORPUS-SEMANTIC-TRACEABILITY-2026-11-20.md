# Research Corpus Semantic Traceability — First Pass (2026-11-20)

**Research item:** `PLAN.md` §0.1 — Reconcile the research corpus  
**Status:** Partial first-pass triage; not a completed semantic audit  
**First-pass content-triage revision:** `e6b5f4a0c9f4365a3fef19283fa0894b7cc82716`  
**Taxonomy crosswalk revision:** `59a65f29f082b848ffd27b199c89bc2ae97c50ea`  
**Inventory snapshot:** `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f` (462 tracked research artifacts; inventory manifest excluded)  
**Normative boundary:** This report classifies research artifacts and proposes traceability metadata only. It does not accept any language, architecture, hash, compatibility, or implementation decision.

## 1. Purpose and method

The corpus inventory contained 36 low-confidence entries whose filenames did not expose a reliable RT or Scenario identifier. A first-pass content triage inspected their titles, scope/status declarations, section structure, explicit research-area declarations, and related-document references. The resulting primary and secondary research-area mappings and candidate plan-stage mappings are recorded in the inventory JSON.

This is a triage, not a claim that every paragraph, claim, experiment, or citation in these documents has been independently validated. Broad synthesis documents are mapped to multiple areas only where their stated scope crosses those areas. Administrative indexes and corpus-management documents are assigned to Stage 0 rather than being presented as substantive research results.

## 2. Stage mapping convention

| Stage | Plan area |
|---|---|
| 0 | Research inventory and evidence hygiene |
| 1 | Semantic foundation and identity |
| 2 | Formal semantics and verification foundation |
| 3 | Dependency graph, incremental computation, and cache |
| 4 | Semantic storage, versioning, and Git integration |
| 5 | Types, execution model, runtime, and POSIX |
| 6 | Translation, backends, and optimization |
| 7 | Scale, ecosystem, collaboration, and adoption |

An artifact may map to multiple stages when its stated scope genuinely spans them. A stage mapping is a navigation aid, not evidence that the stage's exit criteria have passed.

## 3. First-pass mapping of the 36 low-confidence entries

| Artifact | Research item mapping | Plan stage(s) | Content basis |
|---|---|---:|---|
| `COMPILATION-CACHE-SPEEDUP-ESTIMATE.md` | RT-11 | 3 | Analytical cache cost model; explicitly not a benchmark |
| `CORE-LANGUAGE-SEMANTICS.md` | RT-03 | 1 | Explicit RT-03 research-area declaration and semantic decision vectors |
| `GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md` | RT-05, RT-15, RT-20, RT-22, RT-23 | 1, 4, 7 | Semantic identity, Git representation/merge, and worktree/toolchain integration |
| `GIT-SEMANTIC-REPOSITORY.md` | RT-05, RT-15, RT-20, RT-22, RT-23 | 1, 4, 7 | Semantic graph persistence, diff/merge, repository and worktree integration |
| `GLOBAL-SEMANTIC-ARTIFACT-STORE.md` | RT-05, RT-12, RT-13 | 1, 6, 7 | Reusable semantic artifacts, packages/libraries, target profiles and POSIX wrappers |
| `LANGUAGE-VERSIONING.md` | RT-05, RT-11, RT-12, RT-18 | 1, 3, 7 | Append-only component registry, composite language version, package binding and cache |
| `LIBRARIES-AND-TEMPLATES.md` | RT-12 | 7 | Package, library, public interface, dependency, and template model |
| `LLMLang-CONCEPT.md` | RT-01, RT-03, RT-04, RT-05, RT-14 | 1, 5, 7 | Vision/non-goals, SPG, semantic/type boundaries, and AI-native authoring |
| `LLMLang-FORMAL-VERIFICATION.md` | RT-03, RT-07, RT-08, RT-09 | 1, 2, 6 | Canonical semantics, formal projections, proof boundary, executable/formal correspondence |
| `LLVM-BACKEND-ARCHITECTURE.md` | RT-09, RT-13 | 6 | LLVM backend, lowering, trust boundary, and semantic preservation |
| `PACKAGE-INDEX-LOGICAL-SCHEMA.md` | RT-12 | 7 | Explicit RT-12 logical package-index schema |
| `PACKAGE-MANIFEST-AND-IDENTITY.md` | RT-05, RT-12 | 1, 7 | Package manifest and content identity |
| `PACKAGE-SYSTEM.md` | RT-12 | 7 | Package distribution, indexes, identity, dependency closure and reproducibility |
| `POSIX-RUNTIME-ARCHITECTURE.md` | RT-04, RT-10, RT-13, RT-16 | 5, 6, 7 | POSIX runtime, ownership/resources, target implementation, and trust boundary |
| `PREFERRED-FUNCTION-RELATIONAL-SCHEMA.json` | RT-05, RT-07, RT-12 | 1, 2, 7 | Immutable ImplHash identity, ContractId verification, and function/package model |
| `PROTOTYPE-01-RESULTS.md` | RT-05, RT-06, RT-07 | 1, 2, 3 | Content-addressed semantic graph, dependency tracking, selective evolution, provenance |
| `README.md` | PLAN.md §0.1 | 0 | Research navigation and artifact discovery |
| `REPOSITORY-AUDIT-2026-11-17.md` | PLAN.md §0.1 | 0 | Repository consistency, proof-status, and prototype regression audit |
| `RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md` | RT-03, RT-04 | 1, 5 | Explicit RT-03/RT-04 typed call and ownership-transfer boundary |
| `RESEARCH-CORPUS-AUDIT-2026-11-20.md` | PLAN.md §0.1 | 0 | Corpus inventory and reconciliation output |
| `RESEARCH-DEEP-COMPARISON.md` | RT-01, RT-14, RT-17 | 7 | Comparative landscape of agent-native development platforms and DX |
| `RESEARCH-DEPENDENCY-MAP.md` | PLAN.md §0.1 | 0 | Cross-aspect planning register, not a single substantive RT result |
| `RESEARCH-OPTION-MATRIX-01.md` | RT-03, RT-04, RT-05, RT-07, RT-09, RT-10, RT-13, RT-16, RT-18 | 1, 2, 5, 6, 7 | Integrated candidate-vector comparison across semantics, identity, verification, runtime, backend, security, evolution |
| `RESEARCH-PROGRAM-OPEN-QUESTIONS-2026-11-19.md` | PLAN.md §0.1 | 0 | Research programme inventory, sequencing and completion gates |
| `RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md` | PLAN.md §0.2 | 0 | Explicit Stage 0.2 research-methodology output |
| `RESEARCH-RELATED-PROJECTS.md` | RT-01, RT-14, RT-17 | 7 | Adjacent projects and implications for goals, AI authoring and DX |
| `RESEARCH-STATE-2026-11-19.md` | PLAN.md §0.1 | 0 | Cross-corpus evidence/state snapshot and next-work register |
| `RESEARCH-SYNTHESIS-01-CROSS-SCENARIO.md` | RT-05, RT-06, RT-07, RT-14, RT-15 | 1, 2, 3, 4, 7 | Identity, change sets, impact analysis, verification reuse and collaboration |
| `RESEARCH-TAXONOMY.md` | PLAN.md §0.1 | 0 | Research-area taxonomy and coverage-gap register |
| `RFC-DEVELOPMENT-ENGINE.md` | RT-14, RT-17, RT-19, RT-20, RT-21, RT-22, RT-23 | 1, 3, 4, 7 | Context planning, change orchestration, Toolchain Server, verified commit and worktrees |
| `RFC-REQUEST-CHANGE.md` | RT-02, RT-14, RT-15, RT-20 | 1, 4, 7 | Intent/request capture, reviewable changes, provenance and change lifecycle |
| `SEMANTIC-COMPILATION-CACHE.md` | RT-05, RT-06, RT-11 | 1, 3 | Semantic identities, dependency closure, action graph and invalidation |
| `SEMANTIC-DEPENDENCY-INDEX.md` | RT-05, RT-06, RT-19, RT-20, RT-23 | 1, 3, 7 | Dependency semantics/completeness and toolchain/patch-planning consumers |
| `TOKEN_EFFICIENCY.md` | RT-14, RT-17 | 7 | Context selection, output reduction, iteration count and model/task matching |
| `TRANSLATION-AND-TARGET-BACKENDS.md` | RT-09, RT-13 | 6 | Translation pipeline and target-backend semantic preservation |
| `examples/package/manifest.toml` | RT-12 | 7 | Illustrative package-manifest fixture |

Paths above are relative to `research/`.

## 4. Scenario-to-RT crosswalk

All **136 of 136 scenario report files** now have candidate RT-area mappings and numeric plan-stage mappings in the inventory JSON. These files represent **135 unique scenario identifiers**: Scenario 95 has a main study plus an explicitly linked execution follow-up; there is no Scenario 16 report in the current corpus, and its absence is not silently renumbered:

- **63 reports** are cross-walked from explicit scenario links and bounded ranges in `RESEARCH-TAXONOMY.md`.
- **73 reports** were mapped in a first-pass content/header review. Scenarios 1–14 required scope-based triage; the remaining 59 have explicit `Research area(s)` or `Aspect` declarations in their report headers.
- A report may map to multiple RT areas. Counts below are file-to-area assignments, not unique reports by area.

| RT area | Scenario reports mapped |
|---|---:|
| RT-02 | 6 |
| RT-03 | 73 |
| RT-04 | 71 |
| RT-05 | 18 |
| RT-06 | 25 |
| RT-07 | 20 |
| RT-08 | 21 |
| RT-09 | 14 |
| RT-10 | 23 |
| RT-11 | 12 |
| RT-12 | 7 |
| RT-13 | 13 |
| RT-14 | 1 |
| RT-15 | 3 |
| RT-16 | 1 |
| RT-17 | 4 |
| RT-18 | 4 |
| RT-20 | 1 |
| RT-21 | 1 |

### 4.1 Additional 73 scenario mappings

| Scenario | Candidate RT areas | Basis |
|---:|---|---|
| 1 | RT-05 | content/scope triage |
| 2 | RT-14, RT-15 | content/scope triage |
| 3 | RT-02, RT-06 | content/scope triage |
| 4 | RT-07, RT-08, RT-11 | content/scope triage |
| 5 | RT-03, RT-05 | content/scope triage |
| 6 | RT-05 | content/scope triage |
| 7 | RT-05 | content/scope triage |
| 8 | RT-05 | content/scope triage |
| 9 | RT-05, RT-06 | content/scope triage |
| 10 | RT-04, RT-05, RT-12 | content/scope triage |
| 11 | RT-05, RT-12, RT-15 | content/scope triage |
| 12 | RT-11, RT-12, RT-13 | content/scope triage |
| 13 | RT-02, RT-05, RT-12 | content/scope triage |
| 14 | RT-02, RT-07, RT-08, RT-12 | content/scope triage |
| 35 | RT-03, RT-04, RT-05, RT-10 | declared research area/aspect |
| 58 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 59 | RT-03, RT-04, RT-09 | declared research area/aspect |
| 60 | RT-03, RT-04, RT-09 | declared research area/aspect |
| 61 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 62 | RT-03, RT-04, RT-13 | declared research area/aspect |
| 63 | RT-03, RT-04, RT-12 | declared research area/aspect |
| 64 | RT-03 | declared research area/aspect |
| 65 | RT-03 | declared research area/aspect |
| 66 | RT-03, RT-04, RT-09, RT-13 | declared research area/aspect |
| 67 | RT-03, RT-04, RT-06, RT-17 | declared research area/aspect |
| 68 | RT-03, RT-04, RT-09, RT-18 | declared research area/aspect |
| 69 | RT-03, RT-04, RT-09 | declared research area/aspect |
| 70 | RT-03, RT-04, RT-09 | declared research area/aspect |
| 80 | RT-03, RT-09, RT-17 | declared research area/aspect |
| 81 | RT-03, RT-04, RT-11 | declared research area/aspect |
| 82 | RT-03, RT-04, RT-11 | declared research area/aspect |
| 83 | RT-03, RT-04, RT-11 | declared research area/aspect |
| 84 | RT-03, RT-04, RT-11 | declared research area/aspect |
| 85 | RT-03, RT-04, RT-11 | declared research area/aspect |
| 86 | RT-03, RT-04, RT-11 | declared research area/aspect |
| 87 | RT-03, RT-04, RT-11 | declared research area/aspect |
| 88 | RT-03, RT-04, RT-05, RT-18 | declared research area/aspect |
| 89 | RT-03, RT-09 | declared research area/aspect |
| 90 | RT-03, RT-05, RT-06, RT-18 | declared research area/aspect |
| 91 | RT-05, RT-06, RT-11, RT-15, RT-18 | declared research area/aspect |
| 92 | RT-03, RT-04, RT-05, RT-07, RT-11, RT-12, RT-20 | declared research area/aspect |
| 93 | RT-11 | declared research area/aspect |
| 94 | RT-03 | declared research area/aspect |
| 98 | RT-03, RT-04 | declared research area/aspect |
| 99 | RT-03, RT-04 | declared research area/aspect |
| 100 | RT-03, RT-04 | declared research area/aspect |
| 101 | RT-03, RT-04 | declared research area/aspect |
| 109 | RT-03, RT-04, RT-13 | declared research area/aspect |
| 110 | RT-04, RT-05, RT-13 | declared research area/aspect |
| 111 | RT-04, RT-05, RT-13 | declared research area/aspect |
| 112 | RT-03, RT-04, RT-08 | declared research area/aspect |
| 113 | RT-04, RT-10 | declared research area/aspect |
| 114 | RT-04, RT-10 | declared research area/aspect |
| 115 | RT-04, RT-09, RT-10 | declared research area/aspect |
| 116 | RT-04, RT-09, RT-10, RT-13 | declared research area/aspect |
| 117 | RT-04, RT-10, RT-13 | declared research area/aspect |
| 118 | RT-04, RT-09, RT-10, RT-13 | declared research area/aspect |
| 119 | RT-03, RT-04, RT-05 | declared research area/aspect |
| 120 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 121 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 122 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 123 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 124 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 125 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 126 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 127 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 128 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 129 | RT-03, RT-04, RT-06, RT-10 | declared research area/aspect |
| 130 | RT-04, RT-06, RT-10 | declared research area/aspect |
| 131 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 132 | RT-03, RT-04, RT-10 | declared research area/aspect |
| 133 | RT-03, RT-04, RT-10, RT-21 | declared research area/aspect |
| 134 | RT-03, RT-04, RT-05, RT-13 | declared research area/aspect |

### 4.2 Cross-reference and applicability anomalies

- **Scenario 91:** references RT-24; this is now a valid taxonomy reference after RT-24 was registered as the 24th area. The inventory crosswalk includes RT-24.
- **Scenario 134:** mapped to RT-03/04/05/13 for discoverability, but the architecture decision makes it prior-art/reference only. It creates no active requirement for wire-schema evolution or Protobuf/Avro/CBOR runtime experiments.
- **Scenario numbering:** the two Scenario 95 files are a main study and supplemental execution report, not duplicate independent studies. No Scenario 16 file exists in the current corpus; whether that number was reserved or a report is missing remains unresolved.

These are candidate traceability mappings, not accepted design decisions or evidence that an RT research gate is complete.

## 5. Prototype-family traceability review

The first-pass individual role review covers **131 artifacts across five prototype families and the Scenario 34 Lean extension**. Family READMEs, file lists, implementation entry points, and test roles were inspected. **All 131 reviewed files now have first-pass individual role mappings** (3 CLI, 103 dependency-graph, 3 LLVM, 7 package-identity, and 15 package-index). These are traceability mappings, not full claim-level or execution validation:

| Prototype family | Files | First-pass finding | Plan stages |
|---|---:|---|---:|
| CLI-WORKLOADS-01 | 3 | Individual roles mapped to RT-01/17; no RT-14 ownership retained | 7 |
| DEPENDENCY-GRAPH-01 | 103 | Individual file roles mapped across prototype result reports, Python modules/tests, Lean source-query modules, and SCW task audits; family spans requirements/intent, identity/dependency, formal core/proof, package/build, and RT-20 patch-planning | 1, 2, 3, 5, 7 |
| LLVM-PRESERVATION-01 | 3 | Individual fixture/probe roles mapped to RT-03/09/13 | 1, 6 |
| PACKAGE-IDENTITY-01 | 7 | All individual files mapped to package identity, language version, and cache-index areas RT-05/11/12 | 1, 3, 7 |
| PACKAGE-INDEX-01 | 15 | All individual files mapped to logical indexes, archive/closure/provider/content-store and benchmarks; RT-19 is adjacency only (adapter not integrated into Toolchain Server) | 3, 7 |

All 131 reviewed prototype files have individual first-pass role mappings; the remaining 109 files under `research/PROTOTYPES/` have not received the same individual role review. The mappings were derived from README sections, source/module docstrings, scenario crosswalks, and paired test imports/names; they do not establish that the implementation is correct or that every experiment is reproducible. Family-level stage lists are navigation ranges, not claims that every file participates in every listed stage.

## 6. External-reference and taxonomy reconciliation

The reference register explicitly maps the vendored source material to research areas. Those use-case mappings have now been copied into the inventory:

| Source group | Snapshot files with domain mapping | RT areas |
|---|---:|---|
| Alive2 | 1 | RT-07, RT-09, RT-13 |
| MCP | 4 | RT-16, RT-19, RT-22 |
| OCI | 3 | RT-05, RT-11, RT-12 |
| Bazel REAPI | 1 | RT-11, RT-12 |

The four licence files plus the preparation index, reference index, and snapshot manifest remain Stage 0 provenance/navigation artifacts (**7 files**); the Dependency Graph prototype README is an additional Stage 0 family index (**1 file**). These indexes are not assigned substantive RT ownership.

Three documents explicitly identify themselves as **RT-24**. The taxonomy now includes RT-24 as its 24th research area, with links to all three documents. The dependency map adds eight candidate edges, DEP-078–DEP-085, to the existing RT-03/05/06/15/19/20/22/23 areas. The row and edges are explicitly provisional: the RT-24 proposal does not select a canonical SPG schema, identity model, byte encoding, hash envelope, or merge policy. Scenario 91's RT-24 reference now resolves through the taxonomy.

## 7. Known section-level supersession cases

The initial semantic search found three explicit, scoped supersession cases. None requires deleting the whole source document:

1. **Scenario 31:** its first text-based query representation is superseded by the typed canonical query IR v2 documented in Scenario 32. Scenario 31's strict QF_LIA profile and prior-art comparison remain relevant.
2. **Scenario 32:** §9's parser-state bridge sketch is superseded by the compiled implementation under `PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`. The typed query IR specification remains relevant; the current tests are not exhaustive over the full accepted CPC grammar.
3. **GIT-SEMANTIC-REPOSITORY:** the embedded ADR-0001 proposal that made external KV the authoritative semantic store is historical and superseded by Proposed ADR-014 plus `GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md`. The surrounding research and alternatives remain useful background.

The inventory records these as section-level supersession metadata. No entire document was marked superseded in this pass. A corpus-wide near-duplicate, orphan, and contradiction review is still open.

## 8. Remaining traceability gaps

The mapping is intentionally incomplete in these areas:

1. Prototype mappings are first-pass file-role classifications; they do not validate every claim, test outcome, generated artifact, or experiment environment.
2. Explicit RT identifiers in paths and scenario headers are strong traceability evidence, not proof that every claim, experiment, or conclusion is valid or current.
3. RT-24 remains a candidate research proposal; registration does not accept its schema, identity model, canonical encoding, hash envelope, or merge policy.
4. Seven reference/provenance files plus one prototype-family README remain Stage 0-only by design; their purpose is corpus navigation and source attribution, not a missing domain classification.
5. Scenario 58's header and inventory mapping consistently identify RT-10 as the runtime area; no taxonomy/source mismatch remains.
6. Three explicit section-level supersession cases are now recorded; no whole document was marked superseded. The corpus-wide semantic duplicate/orphan/contradiction and per-experiment reproducibility audits remain incomplete.

## 9. Conclusion

The first-pass triage resolves all 36 previous low-confidence root-level mappings. The refreshed inventory now covers 462 research artifacts at `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f`, including 22 Lean source modules and 240 files under `research/PROTOTYPES/`. All 136 scenario reports have candidate RT mappings. The first-pass individual role review covers 131 prototype artifacts across five families and the Scenario 34 Lean extension; 109 further prototype-tree files remain outside that individual role review. Nine vendored technical source documents are mapped to the areas named by the reference register. Seven reference/provenance files plus one prototype-family README remain Stage 0-only. RT-24 is registered with dependency edges DEP-086–DEP-093 after preserving the RT-14 DEP-078–DEP-085 register; its candidate technical contract remains non-normative. Candidate plan-stage metadata is present on all 462 inventory records. This does **not** close PLAN.md §0.1: claim-level and reproducibility validation, semantic duplicate/orphan/contradiction analysis, and full supersession review remain open.


## 10. Post-baseline evidence update — Scenario 34

PR #85 added `PairedObservationSemantics.lean` and `PairedObservationTests.lean` to the Logos binding prototype. Both files are present in the current `main` tree and included in the Lake build roots. The Lean CI check passed for PR #85. SCW-24 (paired input environments) and SCW-25 (paired observation preservation) are therefore supported by committed formal source and kernel-checked examples. This confirms the bounded formal claim only; later SCW-26–29 evidence is recorded below, while SCW-30–34 and the broader adversarial acceptance gates remain open.


## 11. Post-baseline evidence update — Scenario 34 SCW-26–29

The current `main` tree at `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f` contains `CanonicalQuerySymbols.lean`, `ProgramRelationalQuery.lean`, `ProgramRelationalQueryTests.lean`, `QfLiaQuery.lean`, and `QfLiaAdmissibility.lean`. The modules define canonical declaration bindings, compile the complete `FactorDiff ∧ ObservationDiff` proposition, prove relational-query correctness/satisfiability correspondence for the checked fragment, and prove strict QF_LIA admissibility. Scenario 34 marks SCW-26–29 complete. PR #88's Required CI passed the Lean build/test job and the focused QF_LIA profile job. This evidence is conditional on the deterministic Int/Bool fragment and its explicit input/observation assumptions; SCW-30–34 (solver declaration closure, JSON/CPC source correspondence, exact assumptions, trust boundary) and SCW-35–41 (adversarial fixtures, axiom audit, dedicated proof gate, acceptance evidence) remain open.
