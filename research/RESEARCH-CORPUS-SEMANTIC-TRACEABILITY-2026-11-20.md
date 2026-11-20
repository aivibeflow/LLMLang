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

The first-pass individual role review covers **240 artifacts across eight prototype families and the Scenario 34 Lean extension**. Family READMEs, file lists, implementation entry points, and test roles were inspected. **All 240 prototype-tree files now have first-pass individual role mappings** (3 CLI, 103 dependency-graph, 3 LLVM, 7 package-identity, 15 package-index, 104 RT-04-01, 2 RT-16 authorization, and 3 Toolchain Server). These are traceability mappings, not full claim-level or execution validation:

| Prototype family | Files | First-pass finding | Plan stages |
|---|---:|---|---:|
| CLI-WORKLOADS-01 | 3 | Individual roles mapped to RT-01/17; no RT-14 ownership retained | 7 |
| DEPENDENCY-GRAPH-01 | 103 | Individual file roles mapped across prototype result reports, Python modules/tests, Lean source-query modules, and SCW task audits; family spans requirements/intent, identity/dependency, formal core/proof, package/build, and RT-20 patch-planning | 1, 2, 3, 5, 7 |
| LLVM-PRESERVATION-01 | 3 | Individual fixture/probe roles mapped to RT-03/09/13 | 1, 6 |
| PACKAGE-IDENTITY-01 | 7 | All individual files mapped to package identity, language version, and cache-index areas RT-05/11/12 | 1, 3, 7 |
| PACKAGE-INDEX-01 | 15 | All individual files mapped to logical indexes, archive/closure/provider/content-store and benchmarks; RT-19 is adjacency only (adapter not integrated into Toolchain Server) | 3, 7 |
| RT-04-01 | 104 | Individual content-based RT traceability: 39 RT-03-only, 59 RT-04-only, and 6 shared cross-profile artifacts; see §5.1 | 1, 5 |

All 240 prototype-tree files have individual first-pass role mappings; no prototype files remain without an individual role review. The mappings were derived from README sections, source/module docstrings, scenario crosswalks, and paired test imports/names; they do not establish that the implementation is correct or that every experiment is reproducible. Family-level stage lists are navigation ranges, not claims that every file participates in every listed stage.


### 5.1 RT-04-01: content-based RT-03 / RT-04 classification

The 104 files under `research/PROTOTYPES/RT-04-01/` were reviewed individually using module purpose/docstrings, imports, paired tests, README descriptions, and cross-references. Their RT mapping is no longer inferred from the directory name:

| Classification | Files | Basis |
|---|---:|---|
| RT-03 only | 39 | RT-03 semantic evaluators, path/solver/actor/resource models, their focused tests, and the solver requirements file |
| RT-04 only | 59 | RT-04 declaration checker, ownership/call-boundary models, concurrency/memory/wire models, SQLite probes, and their focused tests |
| RT-03 and RT-04 | 6 | Artifacts explicitly spanning the semantic/checker boundary or documenting/testing both prototype areas |
| **Total** | **104** | Every file in the directory is assigned from inspected content |

The six shared files are:

| Artifact | Why both mappings apply |
|---|---|
| `README.md` | Directory guide documents both RT-04 checker work and the RT-03 evaluator, path, typed-call, and cross-profile experiments. |
| `rt03_typed_calls.py` | Executes RT-03 A/B/D typed-call semantics and derives call-site/type inputs for the RT-04 declaration checker. |
| `test_rt03_typed_calls.py` | Exercises RT-03 semantic variants and the RT-04 checker projection on the shared typed-call workload. |
| `test_rt03_rt04_cross_profile.py` | Compares RT-03 observable traces with RT-04 checker vectors. |
| `test_rt03_reference.py` | Primarily tests the RT-03 reference evaluator and includes an explicit RT-04 effect-summary boundary comparison. |
| `test_rt04_owned_call.py` | Tests the RT-04 caller ownership checker and compares its result with the RT-03 return-cleanup trace. |

The inventory records `traceability.method = "individual content review (module purpose, imports, paired tests, and README cross-references)"` and high confidence for all 104 entries. The family spans plan stages 1 and 5. This classification records artifact purpose and evidence relationships; it does not claim that the models are normative semantics, that their bounded tests prove general correctness, or that every native probe has been reproduced on current main.



### 5.2 Final five prototype artifacts: RT-16 and RT-19

The five remaining prototype-tree files were inspected individually. Their content and paired-document relationships support the following mappings:

| Artifact | Mapping | Content basis and boundary |
|---|---|---|
| `RT-16-AUTHORIZATION-01/policy.py` | RT-16 | Models principal/repository/action/base-revision capability checks, human-bound approvals, nonce reservation/consumption, and verification-evidence context/trust checks. The in-memory ledger and unkeyed digest are explicitly not production security or authenticated evidence. |
| `RT-16-AUTHORIZATION-01/test_policy.py` | RT-16 | Paired tests cover authorization scope, approval binding/expiry/replay, nonce lifecycle, and fail-closed evidence decisions. RT-16 documents 24 cases and a manual reproduction command; its text explicitly says no required CI workflow currently runs this suite, so this review does not claim a fresh execution. |
| `TOOLCHAIN-SERVER-01/README.md` | RT-19 | Defines the prototype's narrow lifecycle scope, implementation/test entry points, implemented/deferred features, run command, and limitations. |
| `TOOLCHAIN-SERVER-01/toolchain.py` | RT-19 | Implements the in-memory immutable Entity/Snapshot and isolated Workspace/Change lifecycle, optimistic preconditions, acceptance, and single-file JSON import/export. It is not a persistent backend, MCP server, or canonical SPG/API contract. |
| `TOOLCHAIN-SERVER-01/test_toolchain.py` | RT-19 | Tests round-trip, atomic rejection, stale revisions, workspace isolation, duplicate targets, external edits, invalid entities, acceptance boundary, and tampered imports. README records the focused CI job and its nine tests; that evidence is distinct from this content-role mapping. |

The inventory now records high-confidence individual content-review mappings for all five files. This closes the **prototype file-role inventory** only; it does not close RT-16 security validation, RT-19 lifecycle/recovery research, or the corpus-wide claim/reproducibility audit.

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

The first-pass triage resolves all 36 previous low-confidence root-level mappings. The refreshed inventory now covers 462 research artifacts at `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f`, including 22 Lean source modules and 240 files under `research/PROTOTYPES/`. All 136 scenario reports have candidate RT mappings. The first-pass individual role review covers all 240 prototype-tree artifacts across eight families and the Scenario 34 Lean extension. Nine vendored technical source documents are mapped to the areas named by the reference register. Seven reference/provenance files plus one prototype-family README remain Stage 0-only. RT-24 is registered with dependency edges DEP-086–DEP-093 while preserving RT-14's DEP-078–DEP-085 register; its candidate technical contract remains non-normative. Candidate plan-stage metadata is present on all 462 inventory records. This does **not** close PLAN.md §0.1: claim-level and reproducibility validation, semantic duplicate/orphan/contradiction analysis, and full supersession review remain open.


## 10. Post-baseline evidence update — Scenario 34

PR #85 added `PairedObservationSemantics.lean` and `PairedObservationTests.lean` to the Logos binding prototype. Both files are present in the current `main` tree and included in the Lake build roots. The Lean CI check passed for PR #85. SCW-24 (paired input environments) and SCW-25 (paired observation preservation) are therefore supported by committed formal source and kernel-checked examples. This confirms the bounded formal claim only; later SCW-26–29 evidence is recorded below, while SCW-30–34 and the broader adversarial acceptance gates remain open.


## 11. Post-baseline evidence update — Scenario 34 SCW-26–29

The current `main` tree at `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f` contains `CanonicalQuerySymbols.lean`, `ProgramRelationalQuery.lean`, `ProgramRelationalQueryTests.lean`, `QfLiaQuery.lean`, and `QfLiaAdmissibility.lean`. The modules define canonical declaration bindings, compile the complete `FactorDiff ∧ ObservationDiff` proposition, prove relational-query correctness/satisfiability correspondence for the checked fragment, and prove strict QF_LIA admissibility. Scenario 34 marks SCW-26–29 complete. PR #88's Required CI passed the Lean build/test job and the focused QF_LIA profile job. This evidence is conditional on the deterministic Int/Bool fragment and its explicit input/observation assumptions; SCW-30–34 (solver declaration closure, JSON/CPC source correspondence, exact assumptions, trust boundary) and SCW-35–41 (adversarial fixtures, axiom audit, dedicated proof gate, acceptance evidence) remain open.


## 12. First bounded claim/evidence audit — Scenarios 97–108

This pass follows the RT-03/04 preparation brief and the shared semantics corpus. It checked each scenario's stated result against its named prototype and tests, and records only the bounded fragment actually exercised. It does not promote any profile, ownership rule, solver, alias policy, or language semantics to an accepted decision.

| Scenario | Implementation/test evidence | Supported claim | Unresolved boundary |
|---:|---|---|---|
| 97 | rt03_cleanup_composition.py, rt03_cleanup_composition_audit.py, test_rt03_cleanup_composition.py | Six cleanup composition vectors preserve distinct cause carriers over 72 named observations; the test exhausts 13,230 combinations and checks owner/debt projection. | Auditor is separately implemented but shares the observation vocabulary and fixture inputs; no native cleanup execution or independent language contract. |
| 98 | rt03_path_model.py, test_rt03_path_model.py | Seven unique unknown conditions yield eight structural paths, witnessed by all 128 Boolean assignments and cross-checked against recursive and small-step evaluator traces. | Hand-built AST; no LLMLang parser or source/CFG completeness evidence. |
| 99 | test_rt03_path_model.py repeated-marker case | Repeated identical fixture markers retain only TT/FF routes and match the two concrete assignments. | Marker identity is a fixture convention; source resolution and mutation boundaries are not modeled. |
| 100 | rt03_predicate_paths.py, test_rt03_predicate_paths.py | Exhaustive truth-table evaluation of the finite Boolean IR finds exactly three feasible routes and replayable witnesses. | Four-input finite domain only; no source extraction or general solver claim. |
| 101 | rt03_sympy_predicate_paths.py, test_rt03_sympy_predicate_paths.py | SymPy 1.14.0 DPLL2 agrees with the finite oracle on the reported fixtures and produces replayable witnesses; local timing is recorded for one conjunction family. | Raw adapter skips routes on solver UNSAT directly and does not call the conservative Scenario 102 classifier. Keep it as a differential experiment only; do not reuse as a may-analysis pruning API without a trusted/checked UNSAT basis. |
| 102 | rt03_feasibility_outcomes.py, test_rt03_feasibility_outcomes.py | SAT/UNKNOWN candidate models are locally replayed; incomplete or invalid answers remain UNKNOWN; UNSAT is accepted only with an explicit basis. | The basis is caller-supplied and not authenticated by this module. The current test file has eight test methods, while the report says seven focused tests passed; reconcile historical revision/count. |
| 103 | rt03_bounded_solver_worker.py, test_rt03_bounded_solver_worker.py | One-process-per-query worker enforces a real wall-clock deadline, kills/reaps the worker, and maps timeout to UNKNOWN; four focused tests cover SAT, untrusted UNSAT, timeout, and invalid timeout. | POSIX-only pipe handling, no memory/CPU/descendant bound, and no full startup/crash/malformed-response or persistent-pool test matrix. |
| 104 | rt03_mutable_predicate_identity.py, test_rt03_mutable_predicate_identity.py | Exhaustive two-value fixture demonstrates that reusing a variable name across a write can remove reachable routes; version plus transition relation restores the exact route set. | Hand-authored finite oracle; no SSA/source extraction, aliasing, loops, or concurrency. |
| 105 | rt03_call_mutation_summaries.py, test_rt03_call_mutation_summaries.py | Pure, toggle, and may-write/unknown summaries produce the expected finite route sets; unsafe name-conflation drops possible routes. | Summary is supplied, not derived from a source call graph or effect analysis. |
| 106 | rt03_alias_sensitive_call_paths.py, test_rt03_alias_sensitive_call_paths.py | Exact, disjoint, may-alias, unknown, and incorrect no-alias sets distinguish precision from soundness in a two-field fixture. | Points-to sets are supplied; no heap model or source-level alias extraction. |
| 107 | rt03_source_alias_extraction.py, test_rt03_source_alias_extraction.py | A restricted Python AST adapter derives a direct toggle summary and bounded call-site target union; unsupported mutators/fields fail closed. | Not LLMLang parsing; source executor and adapter share AST grammar and a hand-authored contract. |
| 108 | execute_path_sensitive_summary and the same source-alias tests | Finite path-state enumeration recovers correlated-alias precision while preserving independent/unknown routes in 16 fixture valuations. | Not a scalable relational points-to analysis; no independent source-to-CFG oracle. |

The Required CI run 44767733362 on commit 30a064cf5f276a63c2110f8309f7f306af75f987 passed the repository-structure job's full RT-04-01 test-discovery step after installing the pinned solver requirements. This establishes that the checked-out test suite passed in that CI environment. It does not validate source completeness or prove the general claims stated by the scenarios.

The pass therefore finds strong, reproducible bounded fixture evidence for the specific path, cleanup, solver-result, and alias discriminators. The two cross-cutting follow-ups are (1) integrate the conservative UNSAT evidence policy at the actual solver adapter boundary, or clearly keep the raw adapter test-only; and (2) reconcile the Scenario 102 focused-test count with the current eight-method test file. Broader source/CFG extraction, independent contract review, general alias/effect analysis, solver trust/certificates, and production resource bounds remain open.


## 13. COR-13 evidence chain and native execution boundary — Scenarios 119–133

The second evidence slice checks the COR-13 sequence from owned-result shape inference through SQLite dependency observations, source-role correlation, invocation receipts, caller recovery, and generated Rust.

| Scenario | Evidence and test mapping | What remains unproven |
|---:|---|---|
| 119 | rt04_owned_call_match.py and test_rt04_owned_call_match.py compare AST-derived result shapes with the disposition model; 450 callee-contract combinations and 4,096 concrete inputs are reported; ten focused tests are present. | Hand-built single-call AST and shared COR-13 disposition assumptions; no source parser or native resource. |
| 120 | sqlite_cleanup_probe.py exercises close BUSY, finalize error with consumption, and close_v2 deferred destruction against SQLite 3.46.1. | Standalone native probe, not run by CI; one thread and prepared-statement cases. |
| 121–123 | Recovery, evidence freshness, and shared close-boundary models have Python tests; separate native probes report 356 admitted plans and 114 native policy/input pairs. | Native probes are not in CI; complete source/FFI coverage and concurrency are bounded by fixture assumptions. |
| 124–125 | Interleaving and callback-reentry tests plus native SQLite probes cover 11 schedules, 12 callback cases, statements, BLOBs, and backup dependencies. | One SQLite version and controlled wrapper; probes are manual, and general alias/reentry authority remains open. |
| 126–128 | Role, source-correlation, and foreign-outcome tests check finite resource identities, 147,456 source-role inputs, and 1,728 outcome inputs per policy; selected SQLite backup paths are probed natively. | Native evidence covers selected consuming outcomes; retained/indeterminate paths remain model contracts. No general points-to or FFI contract extraction. |
| 129–130 | Cancellation receipt tests use scheduled threads; durable receipt tests use process interruption and SQLite journal recovery. | CancelIoEx is cited API documentation, not a native Windows execution; local SQLite crash recovery is not distributed transaction evidence. |
| 131–132 | Shared owned-result and typed caller recovery tests compare composed/direct transitions and a separate bounded oracle across 5,184 and 20,736 input spaces. | Fixture parsers and disposition inputs are shared; no complete language semantics or general lowering. |
| 133 | rt04_rust_owned_probe.py generates Rust; test_rt04_rust_owned_probe.py has three generator tests. The report separately records 62,976 native comparisons per optimization level using Rust 1.85.1. | Python CI does not compile or execute generated Rust. Native run and toolchain reproduction remain separate manual evidence. |

The current Required CI repository-structure job runs all RT-04-01 test_*.py modules and passed. It does not invoke the standalone SQLite probes or the native Rust runner. Accordingly, the repository currently has a successful automated test layer plus separately reported native observations; this review has not independently rerun the latter.

This evidence chain supports bounded statements about the tested SQLite API paths and generated COR-13 fixture. It does not establish general ownership/typestate semantics, source-derived dependency completeness, all FFI contracts, or a production concurrency model. The next evidence task is controlled reproduction of native probes and preservation of their exact outputs/toolchain provenance.


## 14. Native reproduction harness — first run passed

The RT-04 native evidence boundary now has a dedicated manual workflow, `.github/workflows/rt04-native-reproduction.yml`, and orchestrator `PROTOTYPES/RT-04-01/run_native_probes.py`, with a focused command-inventory test `test_rt04_native_probe_runner.py`. The harness selects the SQLite 3.46.1 distribution shared library and passes its exact path through `LLMLANG_SQLITE_LIBRARY`; the loader override avoids accidental selection of the host's default SQLite library. The first run showed why the source-ID gate matters: upstream 3.46.1 reported a source ID ending `a1e33`, while the scenarios record the distro build ending `alt1`. All eight C-API probes were skipped rather than silently accepting the version-only match. The runner checks the Scenario 120–128 SQLite version and source ID, and the generated-Rust runner enforces Rust 1.85.1.

The workflow covers the base cleanup, recovery matrix, snapshot freshness, close call boundary, interleavings, callback reentry/dependent coverage, backup roles/outcomes, durable invocation receipts, and generated Rust comparison. It records the repository revision, Python/platform metadata, both C-library and Python sqlite3 versions, rustc verbose metadata, exact commands, exit statuses, and separate stdout/stderr files in a JSON manifest and a 30-day Actions artifact.

The Python `sqlite3` runtime used by Scenario 130 is now isolated from the C-API probes: the workflow builds SQLite 3.53.1 and the runner launches the durable-receipt subprocess with that library first on `LD_LIBRARY_PATH`. It verifies the Python module's runtime version and records `sqlite_source_id()` before running the probe. This is a version match to the historical report; the original report did not record a Python SQLite source ID, so byte-identical library provenance is not claimed.

**Status:** the corrected run [44770566744](https://github.com/aivibeflow/LLMLang/actions/runs/44770566744) passed all ten commands with zero failures/skips. It used the exact SQLite 3.46.1 distro source ID and Rust 1.85.1. Artifact [14647056715](https://github.com/aivibeflow/LLMLang/actions/runs/44770566744/artifacts/14647056715) preserves the manifest and all outputs. The C-API and generated-Rust native commands have now executed successfully. The first successful run used Python sqlite3 3.46.1, not Scenario 130's historical 3.53.1; the workflow has now been extended to build and preflight 3.53.1 for the durable-receipt subprocess. This version-specific correction needs a fresh run. Per-case outputs for the other probes have been checked against the corresponding scenario results. Required CI remains Python-test evidence only.


## 15. Per-case native output comparison — first successful run

The stdout from [native run 44770910183](https://github.com/aivibeflow/LLMLang/actions/runs/44770910183) was compared directly with Scenarios 120–128 and 133. All eight SQLite C-API probes and the generated-Rust comparison agree with their reported counts and observations: 356/154 admitted/rejected recovery plans; 114 admitted close boundaries with 30 source-proof rejections; 11 interleavings; 12 callback cases plus 8 dependent-coverage cases; 12 shared-source backup traces; and 125,952 Rust observations (62,976 at each optimization level), including the three pairs of reported start counts. The base close, stale-snapshot, finalize-error, deferred-destruction, and writable/read-only backup return codes also match the scenario tables.

Scenario 130's ten durable-receipt cases passed on this run, but Python's sqlite3 runtime was 3.46.1 rather than the report's 3.53.1. The workflow now builds 3.53.1 and uses it in a dedicated subprocess for this probe; exact-version reproduction remains pending that rerun. Artifact [14648440097](https://github.com/aivibeflow/LLMLang/actions/runs/44770910183/artifacts/14648440097) preserves the logs and manifest.
