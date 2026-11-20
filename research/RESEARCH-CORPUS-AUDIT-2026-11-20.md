# Research Corpus Audit — 2026-11-20

**Research item:** PLAN.md §0.1, Reconcile the research corpus  
**Status:** Partial; complete tracked-path inventory and limited link checks recorded, semantic reconciliation still open  
**Primary snapshot revision:** `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f` (inventory excludes its own manifest file)  
**Normative boundary:** This report records documentation and inventory findings only. It makes no language, architecture, identity, or implementation decisions.

## 1. Executive summary

The recursive Git tree at the primary snapshot revision contains **462 tracked research artifacts** (excluding the inventory manifest itself):

- 234 Markdown/MDX files (231 `.md` and 3 `.mdx`);
- 194 Python files;
- 22 Lean source files and one Lean toolchain pin;
- 3 JSON files;
- 1 C file, 1 Rust file, 1 TOML file, 1 Protocol Buffers schema, and 4 text files;
- 240 files under `research/PROTOTYPES/`;
- 24 files under `research/preparation/` and `research/references/`.

A machine-readable inventory snapshot records all 462 paths, Git blob SHAs, byte sizes, coarse categories, and qualified path-based traceability metadata: [RESEARCH-CORPUS-INVENTORY-2026-11-20.json](RESEARCH-CORPUS-INVENTORY-2026-11-20.json).

The main index's relative links and the preparation index's brief links resolve. Exact Git-blob comparison found one repeated blob: the same Apache-2.0 licence text is stored alongside both OCI and REAPI snapshots. This is expected shared licence content, not evidence of duplicated research.

The audit remains **partial**. The current `main` tree at the recorded baseline contains 22 Lean source modules and tests, including the paired-observation modules from PR #85 and the QF_LIA term-profile/admissibility modules added by PR #86. SCW-24/25 and SCW-29 are represented in source and CI; later Scenario 34 gates remain open. The inventory classifies paths and records tentative mappings; it does not verify every artifact's semantic contents, determine every supersession relationship, prove index completeness, or reproduce all experiments.

## 2. Evidence and checks performed

### 2.1 Repository inventory

- Retrieved the recursive Git tree for `main` at current `main` HEAD revision `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f`; excluded the inventory manifest itself to avoid self-reference.
- Enumerated all 462 tracked research artifacts whose paths begin with `research/`, excluding the inventory manifest itself.
- Recorded path, Git blob SHA, byte size, coarse artifact category, and traceability metadata for every file in the inventory JSON.
- Distinguished scenario-named reports, prototype implementations, tests, prototype readmes/reports, preparation briefs, external snapshots/licences, structured fixtures, and research documents.
- Recorded direct RT/scenario identifiers as high-confidence path evidence. Prototype-family mappings are explicitly marked medium confidence; files without reliable path identifiers remain unassigned rather than receiving guessed mappings.

The inventory is pinned to the exact current `main` tree revision `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f`. The inventory is a reproducible path-level snapshot. It is not a claim that every file's contents have been read or validated.

### 2.2 Markdown relative-link scan

- Scanned inline Markdown links in the **233-file historical baseline** under `research/` at the PR #79 baseline; later changes in PRs #80/#82 affected three distinct Markdown files, whose 30 local relative links were rechecked against the refreshed inventory tree.
- Checked **1,330 relative-link occurrences** across the 233-file historical baseline against the tracked repository tree (1,323 in the initial full scan; three Markdown files changed by PRs #80/#82 were rechecked after their latest edits (30 local links total), with a net increase of seven link occurrences). External HTTP(S)/mailto links, fragment-only links, and root-absolute paths from copied upstream documentation were excluded from local path resolution.
- Found one broken relative link in the LLMLang-authored `research/RT-04-PROTOTYPE-01-SCENARIOS.md`; corrected it to point to the sibling `RT-04-RT-03-CROSS-PROFILE-TRACES.md` file. A repeat check of the corrected file resolves.
- Found **38 unresolved relative-link occurrences inside verbatim external snapshots only**: six in the Alive2 README (five image assets and `BugList.md`) and 32 in OCI snapshot documents (references to seven OCI source documents not included in the partial snapshot). These files were not rewritten because they are preserved upstream source snapshots.
- The MCP snapshot contains root-absolute links into the upstream documentation site; these are not repository-relative paths and were not treated as missing local files.
- The current main index has 98 unique relative targets (99 inline relative-link occurrences); all resolve against the full repository tree. The preparation index has 11 unique relative targets and the references index has two; all resolve.

**Result:** no broken inline relative links were found in the historical baseline of LLMLang-authored research documents. The full current-corpus scan remains open. The 38 missing targets in copied upstream snapshots reflect the deliberately partial vendored source sets. This scan does not validate external URL availability, heading anchors, reference-style Markdown links, or index completeness against every artifact.

### 2.3 Taxonomy and dependency map

- `research/RESEARCH-TAXONOMY.md` contains 24 research-area entries, RT-01 through RT-24.
- `research/RESEARCH-DEPENDENCY-MAP.md` contains 94 dependency IDs, DEP-001 through DEP-094, with no gaps in that ID range.
- The previous Stage 0.3 summary in `PLAN.md` reported 18 areas and 35 edges; this was stale.

**Correction:** PLAN.md §0.3 now reports the current counts (24 areas and 94 edges); RT-24 was added as a candidate research area with eight explicitly provisional dependency edges (DEP-086–DEP-093), while RT-14 retains DEP-078–DEP-085. The taxonomy and dependency map remain evolving research registers; the existence of an edge does not make it an accepted architecture rule.

### 2.4 Preparation pack and external references

- The preparation index links eight preparation briefs; all eight resolve.
- The briefs distinguish preparation instructions from executed research evidence and specify reproducibility expectations such as source revisions, tool versions, fixtures, commands, raw outputs, negative/UNKNOWN cases, limitations, and decision boundaries.
- The external-reference register identifies four pinned snapshot groups: MCP, OCI, Alive2, and Bazel Remote Execution API.
- The reference register states that 13 stored source/licence files were checked against upstream blob IDs. This audit did not independently retrieve and re-hash those upstream files.

### 2.5 First-pass semantic traceability

- Reviewed the 36 inventory entries previously marked low confidence using document titles, scope/status declarations, section structures, explicit research-area declarations, and related-document references.
- Assigned candidate RT-area mappings or explicit Stage 0 research-management ownership to all 36 entries; recorded the basis and candidate plan stages in [the semantic traceability report](RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md) and inventory JSON.
- Added `plan_stages` metadata to all 462 inventory records. A taxonomy/header/content crosswalk now maps all 136 Scenario reports to candidate RT areas: 63 from taxonomy links/ranges and 73 from first-pass report scope review. The first-pass individual role review now covers all 240 prototype artifacts across eight families and the Scenario 34 Lean extension; no prototype-tree artifacts remain without individual file-role mappings. The 104-file RT-04-01 family has received a separate content-based RT-03/RT-04 traceability review (39 RT-03-only, 59 RT-04-only, and 6 shared artifacts). The final five previously family-only files are now individually mapped: two RT-16 authorization artifacts and three RT-19 Toolchain Server artifacts. Content/claim and reproducibility validation remains open. Nine vendored technical source documents now have use-case mappings; seven reference/provenance files plus one prototype-family index remain Stage 0-only. RT-24 is registered in the taxonomy with candidate edges DEP-086–DEP-093; its candidate contract remains non-normative.
- The semantic review is explicitly first-pass triage, not full claim-level verification or acceptance of the proposals described by the documents.
- Scenario numbering review found 136 report files representing 135 unique IDs: Scenario 95 has a main study and an explicitly cross-referenced execution follow-up; Scenario 16 has no report in the current corpus. Its absence is recorded as unresolved (reserved number versus missing artifact), not silently renumbered.

**Result:** the previous 36 low-confidence records no longer have blank/unassigned path-only mappings. The RT-04-01 family no longer uses directory-name inference as its RT mapping basis; the corpus-wide semantic traceability gate remains open.

### 2.6 Initial section-level supersession review

Three explicit cases were recorded in the inventory; none supersedes its whole document:

- Scenario 31's first text-based query representation is superseded by the typed canonical query IR v2 in Scenario 32; the Scenario 31 profile analysis remains relevant.
- Scenario 32 §9's parser-state bridge sketch is superseded by the compiled Logos implementation in `PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`; the query IR document remains relevant.
- The embedded ADR-0001 external-KV-authoritative proposal in `GIT-SEMANTIC-REPOSITORY.md` is historical and superseded by Proposed ADR-014 and `GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md`; the surrounding research remains background.

**Result:** three section-level cases are explicit; no entire document was marked superseded. This is not a complete semantic duplicate/orphan/contradiction audit.

### 2.8 Reproducibility instructions and CI coverage

The prototype READMEs and workflow definitions provide reproducibility instructions for the principal executable slices:

| CI suite | Pinned environment | Executed scope |
|---|---|---|
| Logos binding | Lean 4.34.0 | Lake build and `Main.lean` parser/source-query tests |
| Package identity | Python 3.11 | Unit-test discovery and byte-compilation |
| Package index | Python 3.11 | Unit-test discovery, byte-compilation, and provider benchmark at sizes 1,000 and 5,000 |
| QF_LIA profile | Python 3.12 | Compile Dependency Graph source/tests and run `test_qf_lia_profile.py` |
| Repository structure | Python 3.12 plus pinned `mpmath==1.3.0` and `sympy==1.14.0` | Repository-structure checks and the RT-04-01 test suite |
| Semantic dependency index | Python 3.11 | Selected identity, impact-planning, semantic-index, call-site, validation, and diff tests |
| Toolchain workspace | Python 3.12 | Compile Toolchain Server prototype and run `test_toolchain.py` |

The CI configuration is a reproducibility aid, not proof that every research artifact is covered. In particular, the Semantic Dependency Index workflow selects a subset of the Dependency Graph tests; the CLI workload and LLVM preservation prototypes have no dedicated job in the current `ci-required` workflow. Scenario reports also describe additional one-off commands and native-tool observations that are not all repeated by CI.

PR #88's merged head `ad49cb161e9abbd1eb65ea0fac0bafca843a9ea3` passed both Required CI and Required CI policy. The `logos-binding / lean-build-and-test` and `qf-lia-profile / focused-tests` jobs completed successfully, as did the other required suites. This CI run compiles the configured Lean proof modules and exercises the bounded parser/semantic tests; it does not execute every experiment or validate every artifact in the corpus.

### 2.7 Exact blob comparison

Git blob SHA comparison across the 450 inventory entries found one repeated blob:

| Blob SHA | Paths | Assessment |
|---|---|---|
| `d645695673349e3947e8e5ae42332d0ac3164cd7` | `research/references/snapshots/OCI/LICENSE-APACHE-2.0.txt`; `research/references/snapshots/REAPI/LICENSE-APACHE-2.0.txt` | Expected shared Apache-2.0 licence text; retain both colocated copies for snapshot attribution. |

No other byte-identical files were found by this Git-blob comparison. This does not detect near-duplicates, overlapping research, or superseded documents with different contents.


### 2.9 First bounded evidence audit — RT-03/04 Scenarios 97–108

The first claim/evidence pass reviewed the scenario reports, linked implementation and test modules under PROTOTYPES/RT-04-01, the shared COR-13 corpus description, and the preparation brief. The review distinguishes finite fixture results from source-language or production claims.

| Scenario | Claim checked against code/tests | Evidence supported | Boundary or finding |
|---:|---|---|---|
| 97 | Cleanup outcome composition across six candidate policies; ownership/debt projection | Twelve discriminators × six policies (72 observations); the test exhausts 13,230 finite combinations. The obligation auditor is a separate module and imports neither the operational composer nor its helpers. | Both sides share the fixture vocabulary and consume the same observation schema; this is an independent implementation check of ownership projection, not an independent language specification. Cleanup dispositions are inputs, not inferred native resource states. |
| 98 | Structural path coverage for a generated depth-3 binary AST | Seven condition markers, 128 concrete assignments, eight predicted paths; both RT-03 evaluators are compared with the path model on traces and final resources. | Hand-generated AST only; evaluator agreement and path coverage do not establish parser/CFG completeness. |
| 99 | Repeated marker identity across sequential branches | Two concrete assignments produce only TT/FF paths; focused path-model suite includes the regression. | Marker identity is assigned by the fixture; source name resolution, mutation, and general predicate equivalence remain outside scope. |
| 100 | Feasibility in a finite pure Boolean predicate IR | Exhaustive four-assignment domain yields three route vectors and replayable witnesses; unsupported forms fail closed. | Immutable Boolean fragment only; exactness comes from finite enumeration, not general symbolic reasoning or source extraction. |
| 101 | SymPy 1.14.0 DPLL2 against the same finite predicate IR | Solver route sets are compared with the truth-table analyzer and replayed against concrete evaluators; the report records a local conjunction-family timing table. | Integration gap: rt03_sympy_predicate_paths.py directly omits routes when SymPy returns False. The conservative result mapper added in Scenario 102 is a separate module and is not called by this adapter. Treat Scenario 101 as a bounded differential experiment, not a safe may-analysis/pruning interface. |
| 102 | SAT/UNSAT/UNKNOWN result handling and pruning basis | Replayed complete SAT models establish feasibility; timeout, unsupported/error, malformed or incomplete models remain UNKNOWN; UNSAT is accepted only with an explicit basis. | The mapper does not authenticate the caller-supplied UNSAT basis; its docstring leaves that to the caller. The current test_rt03_feasibility_outcomes.py contains eight test methods, while the report says seven focused tests passed. Reconcile the count or pin the historical test revision. |
| 103 | Real wall-clock timeout using an isolated SymPy worker | Four focused tests include a real 12-pigeon/11-hole timeout; the worker is killed/reaped and timeout remains UNKNOWN. Request IDs and one-process-per-query scope are visible in the implementation. | No memory/CPU/descendant bound, persistent worker pool, or broad crash/startup/malformed-response matrix; measured timings are machine-specific. |
| 104 | Predicate identity across a Boolean mutation | Three tests exhaust the two-value fixture and distinguish name-conflation, independent versions, and versions plus transition relation. | Hand-authored finite oracle; no source parser, SSA extraction, heap aliasing, loops, or concurrent writes. |
| 105 | Call mutation summaries | Five tests compare pure, toggle, may-write/unknown, and unsafe name-conflated summaries over all four before/after Boolean pairs. | Summaries are supplied by the fixture; no source-derived effect/call graph or dynamic dispatch. |
| 106 | Field-sensitive call-site alias sets | Five tests compare exact, disjoint, may-alias, unknown, and incorrect no-alias assumptions over the two-field fixture. | Alias sets and mutator footprint are supplied; no points-to analysis, heap graph, or source completeness proof. |
| 107 | Source-derived call aliases in a Python-shaped AST subset | The adapter recognizes one direct toggle mutator, propagates bounded reference targets through assignments/branch joins, and rejects unsupported constructs; tests include omitted-target and unsupported-source counterexamples. | This is not LLMLang parsing or general Python analysis. Concrete execution and extraction share the Python AST grammar and bounded semantic contract. |
| 108 | Path-sensitive alias precision | Ten tests compare joined may-alias and path-sensitive enumeration over 16 finite input combinations, including correlated and independent aliases. | Both executors share the AST grammar and toggle contract; fixed finite enumeration, not a scalable relational points-to analysis or independent source-to-CFG oracle. |

**CI evidence:** Required CI run 44767733362, commit 30a064cf5f276a63c2110f8309f7f306af75f987, completed the repository-structure / structure job successfully. Its Test RT-04 prototype 01 step ran python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v after installing the pinned requirements-solver.txt; that step passed. At the time of this report, other Required CI jobs were still running, so the overall workflow was not yet complete.

**Audit result:** Scenarios 97–108 have traceable bounded implementation/test evidence, but none establishes general LLMLang source semantics or source-to-CFG completeness. The Scenario 101/102 solver-pruning boundary and Scenario 102 test-count discrepancy are recorded as open audit findings. The broader 104-file RT-04-01 suite passing CI is execution evidence for that checked-out test corpus, not proof of every research claim.

## 3. Findings and actions

| ID | Finding | Action / status |
|---|---|---|
| RCA-01 | The corpus has 462 tracked research artifacts in the refreshed inventory snapshot (excluding the manifest itself), but previously lacked a complete path inventory. | Added the machine-readable inventory snapshot. |
| RCA-02 | Artifact-to-item mapping is not uniformly explicit in filenames. | Added qualified path-based mappings; content-level verification remains open. |
| RCA-03 | The 233-file historical baseline was scanned for inline relative links (1,330 occurrences); the current corpus contains 234 Markdown/MDX files after adding the semantic-traceability report, so a full current-corpus scan remains open. One LLMLang-authored broken link was fixed; 38 unresolved occurrences remain only in partial Alive2/OCI snapshots. | Project-authored inline relative links resolve; external snapshot completeness, external URLs, anchors, and index completeness remain open. |
| RCA-04 | At the refreshed inventory revision, the main, preparation, and references indexes have 85, 11, and 2 unique relative targets; all resolve. | Index link existence checks complete; scientific readiness and index coverage remain open. |
| RCA-05 | PLAN.md §0.3 reported stale taxonomy/dependency counts. | Corrected to 24 research areas and 94 dependency edges; added RT-24 with candidate dependencies DEP-086–DEP-093 while retaining RT-14 edges DEP-078–DEP-085. |
| RCA-06 | One exact duplicate blob is shared by the OCI and REAPI Apache-2.0 licence files. | Classified as intentional shared licence content; no deletion proposed. |
| RCA-07 | External snapshot integrity and experiment reproducibility have not been independently re-established. | Preserve pinned revisions and existing manifest; verify source blobs and experiment environments in a later pass. |
| RCA-08 | Three section-level supersession cases are explicit; semantic near-duplicates, orphans, and contradictions are not exhaustively reviewed. | Record the three known cases without deleting whole documents; complete the corpus-wide semantic review in a later pass. |
| RCA-09 | All 104 files in `PROTOTYPES/RT-04-01/` previously inherited RT-04 traceability from the directory name, although their contents include RT-03-only and cross-profile artifacts. | Replaced path inference with individual content-based role mappings: 39 RT-03-only, 59 RT-04-only, and 6 shared; exact shared files and method are recorded in the semantic traceability report. |
| RCA-10 | Five prototype-tree files remained at family-level mapping only (two RT-16 authorization and three RT-19 Toolchain Server artifacts). | Individually reviewed their purpose and paired test/document relationships; all 240/240 prototype-tree files now have first-pass role mappings. |
| RCA-11 | Bounded path-feasibility experiments have a solver integration boundary: the raw SymPy adapter prunes UNSAT directly, while the conservative evidence mapper is separate; Scenario 102 also reports seven focused tests although its current test file contains eight methods. | Recorded both as open evidence-audit findings; do not treat the raw adapter as a safe may-analysis interface or the test count as reconciled until the code/report revision is pinned.

## 4. Reconciliation rules

1. Do not delete or rewrite historical research merely because a newer scenario exists.
2. Keep preparation briefs distinct from executed research results.
3. Keep copied primary-source snapshots distinct from LLMLang-authored analysis.
4. Treat the taxonomy and dependency map as detailed evolving registers; do not copy stale fixed counts into other documents.
5. Treat path-derived mappings as inventory hints, not as accepted semantic traceability.
6. Keep research exploratory; architectural or language decisions must be recorded separately in the appropriate decision/specification documents.

## 5. Remaining work for full completion of PLAN.md §0.1

- [ ] Read and validate the content-level mapping for every artifact, including prototypes, tests, fixtures, generated outputs, RFCs, and snapshots.
- [x] First-pass content/heading/reference triage of 36 low-confidence entries; see the semantic traceability report.
- [x] Cross-walk all 136 Scenario reports to candidate RT areas (63 taxonomy link/range mappings; 73 first-pass content/header mappings); record Scenario 134 prior-art-only applicability; Scenario 91's RT-24 reference now resolves.
- [x] First-pass individual file-role mapping for all 240 prototype artifacts across eight families and the Scenario 34 Lean extension; no prototype-tree artifacts remain without individual role mappings.
- [ ] Validate prototype claims, test evidence, generated outputs, exact tool versions, and reproducibility at content/experiment level. First bounded pass: Scenarios 97–108; see §2.9 and the semantic traceability report. The full 104-file RT-04-01 test suite passed its Required CI step, but broader claim validation remains open.
- [x] Map nine vendored technical source documents to the RT areas named by the reference register; keep seven provenance/navigation/licence files at Stage 0.
- [x] Register RT-24 and cross-link its three research documents; keep the technical contract and dependency edges explicitly provisional.
- [x] Reconcile scenario-number identity at first pass: record Scenario 95's main/follow-up relationship and the absent Scenario 16 report without renumbering.
- [ ] Identify semantically duplicate, superseded, orphaned, and contradictory documents.
- [ ] Decide whether missing relative targets in the partial Alive2/OCI source snapshots should remain documented as non-vendored upstream material or whether additional upstream files/assets should be added while preserving source provenance; validate external URLs and heading anchors if needed.
- [ ] Verify exact source revision, tool versions, commands, fixtures, expected outputs, and negative cases for each reproducibility-sensitive experiment.
- [ ] Independently re-verify external snapshot blob identities and licence provenance.
- [ ] Confirm that the research index exposes every relevant artifact or provides clear directory-level indexes for grouped artifacts.

## 6. Sources inspected

- Recursive Git tree at `a30ec074e08186f04a35535b9933bfa878713f31`; inventory excludes its own manifest file.
- `PLAN.md`
- `research/README.md`
- `research/RESEARCH-TAXONOMY.md`
- `research/RESEARCH-DEPENDENCY-MAP.md`
- `research/preparation/README.md` and its eight linked briefs
- `research/references/README.md` and `research/references/SNAPSHOT-MANIFEST.json`
- `draft/GLOSSARY.md`

---

**Conclusion:** the repository-wide path inventory, coarse artifact classification, Git-blob duplicate check, inline relative-link scan across all 233 research Markdown/MDX files, first-pass triage of 36 low-confidence entries, and individual role mapping for all 240 prototype-tree files are recorded. The first bounded claim/evidence audit covers Scenarios 97–108; it identifies an unintegrated raw-UNSAT pruning adapter and a Scenario 102 test-count discrepancy. The full corpus evidence audit remains open. One LLMLang-authored broken link was fixed; 38 unresolved occurrences are confined to partial verbatim external snapshots. PLAN.md §0.1 remains partially validated until content-level and reproducibility validation for all 240 individually role-mapped prototype artifacts, index completeness, explicitly preserve RT-24's non-normative candidate status, supersession/orphan/contradiction analysis, external snapshot provenance/completeness, and reproducibility verification are complete.
