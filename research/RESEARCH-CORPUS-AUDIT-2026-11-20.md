# Research Corpus Audit — 2026-11-20

**Research item:** PLAN.md §0.1, Reconcile the research corpus  
**Status:** Partial; complete tracked-path inventory and limited link checks recorded, semantic reconciliation still open  
**Primary snapshot revision:** `a30ec074e08186f04a35535b9933bfa878713f31` (inventory excludes its own manifest file)  
**Normative boundary:** This report records documentation and inventory findings only. It makes no language, architecture, identity, or implementation decisions.

## 1. Executive summary

The recursive Git tree at the primary snapshot revision contains **457 tracked research artifacts** (excluding the inventory manifest itself):

- 233 Markdown/MDX files (230 `.md` and 3 `.mdx`);
- 194 Python files;
- 17 Lean source files and one Lean toolchain pin;
- 3 JSON files;
- 1 C file, 1 Rust file, 1 TOML file, 1 Protocol Buffers schema, and 4 text files;
- 235 files under `research/PROTOTYPES/`;
- 24 files under `research/preparation/` and `research/references/`.

A machine-readable inventory snapshot records all 456 paths, Git blob SHAs, byte sizes, coarse categories, and qualified path-based traceability metadata: [RESEARCH-CORPUS-INVENTORY-2026-11-20.json](RESEARCH-CORPUS-INVENTORY-2026-11-20.json).

The main index's relative links and the preparation index's brief links resolve. Exact Git-blob comparison found one repeated blob: the same Apache-2.0 licence text is stored alongside both OCI and REAPI snapshots. This is expected shared licence content, not evidence of duplicated research.

The audit remains **partial**. The current `main` tree adds six Lean source/test modules since the PR #81 inventory baseline, including the paired-observation proof and tests from PR #85. SCW-24/25 are present and included in the refreshed inventory; they are not missing artifacts. The inventory classifies paths and records tentative mappings; it does not verify every artifact's semantic contents, determine every supersession relationship, prove index completeness, or reproduce all experiments.

## 2. Evidence and checks performed

### 2.1 Repository inventory

- Retrieved the recursive Git tree for `main` at revision `c105766eee22f25532712be115e62beb4d42faf5`; excluded the inventory manifest itself to avoid self-reference.
- Enumerated all 457 tracked research artifacts whose paths begin with `research/`, excluding the inventory manifest itself.
- Recorded path, Git blob SHA, byte size, coarse artifact category, and traceability metadata for every file in the inventory JSON.
- Distinguished scenario-named reports, prototype implementations, tests, prototype readmes/reports, preparation briefs, external snapshots/licences, structured fixtures, and research documents.
- Recorded direct RT/scenario identifiers as high-confidence path evidence. Prototype-family mappings are explicitly marked medium confidence; files without reliable path identifiers remain unassigned rather than receiving guessed mappings.

The inventory is a reproducible path-level snapshot. It is not a claim that every file's contents have been read or validated.

### 2.2 Markdown relative-link scan

- Scanned inline Markdown links in all **233 Markdown/MDX files** under `research/` at the PR #79 baseline; later changes in PRs #80/#82 affected three distinct Markdown files, whose 30 local relative links were rechecked against the refreshed inventory tree.
- Checked **1,330 relative-link occurrences** across the 233 Markdown/MDX files against the tracked repository tree (1,323 in the initial full scan; three Markdown files changed by PRs #80/#82 were rechecked after their latest edits (30 local links total), with a net increase of seven link occurrences). External HTTP(S)/mailto links, fragment-only links, and root-absolute paths from copied upstream documentation were excluded from local path resolution.
- Found one broken relative link in the LLMLang-authored `research/RT-04-PROTOTYPE-01-SCENARIOS.md`; corrected it to point to the sibling `RT-04-RT-03-CROSS-PROFILE-TRACES.md` file. A repeat check of the corrected file resolves.
- Found **38 unresolved relative-link occurrences inside verbatim external snapshots only**: six in the Alive2 README (five image assets and `BugList.md`) and 32 in OCI snapshot documents (references to seven OCI source documents not included in the partial snapshot). These files were not rewritten because they are preserved upstream source snapshots.
- The MCP snapshot contains root-absolute links into the upstream documentation site; these are not repository-relative paths and were not treated as missing local files.
- The main index has 85 unique relative targets at the refreshed inventory revision; all resolve. The PR branch index now has 98 unique targets; all resolve, including the semantic-traceability report and prototype-family navigation links. The preparation index has 11 unique relative targets and the references index has two; all resolve.

**Result:** no broken inline relative links remain in LLMLang-authored research documents. The 38 missing targets in copied upstream snapshots reflect the deliberately partial vendored source sets. This scan does not validate external URL availability, heading anchors, reference-style Markdown links, or index completeness against every artifact.

### 2.3 Taxonomy and dependency map

- `research/RESEARCH-TAXONOMY.md` contains 24 research-area entries, RT-01 through RT-24.
- `research/RESEARCH-DEPENDENCY-MAP.md` contains 85 dependency IDs, DEP-001 through DEP-085, with no gaps in that ID range.
- The previous Stage 0.3 summary in `PLAN.md` reported 18 areas and 35 edges; this was stale.

**Correction:** PLAN.md §0.3 now reports the current counts (24 areas and 85 edges); RT-24 was added as a candidate research area with eight explicitly provisional dependency edges (DEP-078–DEP-085). The taxonomy and dependency map remain evolving research registers; the existence of an edge does not make it an accepted architecture rule.

### 2.4 Preparation pack and external references

- The preparation index links eight preparation briefs; all eight resolve.
- The briefs distinguish preparation instructions from executed research evidence and specify reproducibility expectations such as source revisions, tool versions, fixtures, commands, raw outputs, negative/UNKNOWN cases, limitations, and decision boundaries.
- The external-reference register identifies four pinned snapshot groups: MCP, OCI, Alive2, and Bazel Remote Execution API.
- The reference register states that 13 stored source/licence files were checked against upstream blob IDs. This audit did not independently retrieve and re-hash those upstream files.

### 2.5 First-pass semantic traceability

- Reviewed the 36 inventory entries previously marked low confidence using document titles, scope/status declarations, section structures, explicit research-area declarations, and related-document references.
- Assigned candidate RT-area mappings or explicit Stage 0 research-management ownership to all 36 entries; recorded the basis and candidate plan stages in [the semantic traceability report](RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md) and inventory JSON.
- Added `plan_stages` metadata to all 456 inventory records. A taxonomy/header/content crosswalk now maps all 136 Scenario reports to candidate RT areas: 63 from taxonomy links/ranges and 73 from first-pass report scope review. All 120 prototype-family records now have first-pass individual file-role mappings across five families; content/claim and reproducibility validation remains open. Nine vendored technical source documents now have use-case mappings; seven reference/provenance files plus one prototype-family index remain Stage 0-only. RT-24 is registered in the taxonomy; its candidate contract remains non-normative.
- The semantic review is explicitly first-pass triage, not full claim-level verification or acceptance of the proposals described by the documents.
- Scenario numbering review found 136 report files representing 135 unique IDs: Scenario 95 has a main study and an explicitly cross-referenced execution follow-up; Scenario 16 has no report in the current corpus. Its absence is recorded as unresolved (reserved number versus missing artifact), not silently renumbered.

**Result:** the previous 36 low-confidence records no longer have blank/unassigned path-only mappings, but the corpus-wide semantic traceability gate remains open.

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

At the time of this audit update, the current PR's required CI run is still in progress; only completed job results should be treated as execution evidence. No claim is made here that all 120 individually mapped prototype-family artifacts, all 235 files under `research/PROTOTYPES/`, or all scenario experiments have been executed in this run.

### 2.7 Exact blob comparison

Git blob SHA comparison across the 450 inventory entries found one repeated blob:

| Blob SHA | Paths | Assessment |
|---|---|---|
| `d645695673349e3947e8e5ae42332d0ac3164cd7` | `research/references/snapshots/OCI/LICENSE-APACHE-2.0.txt`; `research/references/snapshots/REAPI/LICENSE-APACHE-2.0.txt` | Expected shared Apache-2.0 licence text; retain both colocated copies for snapshot attribution. |

No other byte-identical files were found by this Git-blob comparison. This does not detect near-duplicates, overlapping research, or superseded documents with different contents.

## 3. Findings and actions

| ID | Finding | Action / status |
|---|---|---|
| RCA-01 | The corpus has 457 tracked research artifacts in the refreshed inventory snapshot (excluding the manifest itself), but previously lacked a complete path inventory. | Added the machine-readable inventory snapshot. |
| RCA-02 | Artifact-to-item mapping is not uniformly explicit in filenames. | Added qualified path-based mappings; content-level verification remains open. |
| RCA-03 | All 233 research Markdown/MDX files were scanned for inline relative links (1,330 occurrences across the refreshed inventory revision). One LLMLang-authored broken link was fixed; 38 unresolved occurrences remain only in partial Alive2/OCI snapshots. | Project-authored inline relative links resolve; external snapshot completeness, external URLs, anchors, and index completeness remain open. |
| RCA-04 | At the refreshed inventory revision, the main, preparation, and references indexes have 85, 11, and 2 unique relative targets; all resolve. | Index link existence checks complete; scientific readiness and index coverage remain open. |
| RCA-05 | PLAN.md §0.3 reported stale taxonomy/dependency counts. | Corrected to 24 research areas and 85 dependency edges; added RT-24 with candidate dependencies. |
| RCA-06 | One exact duplicate blob is shared by the OCI and REAPI Apache-2.0 licence files. | Classified as intentional shared licence content; no deletion proposed. |
| RCA-07 | External snapshot integrity and experiment reproducibility have not been independently re-established. | Preserve pinned revisions and existing manifest; verify source blobs and experiment environments in a later pass. |
| RCA-08 | Three section-level supersession cases are explicit; semantic near-duplicates, orphans, and contradictions are not exhaustively reviewed. | Record the three known cases without deleting whole documents; complete the corpus-wide semantic review in a later pass. |

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
- [x] First-pass individual file-role mapping for all 120 prototype-family artifacts.
- [ ] Validate prototype claims, test evidence, generated outputs, exact tool versions, and reproducibility at content/experiment level.
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

**Conclusion:** the repository-wide path inventory, coarse artifact classification, Git-blob duplicate check, inline relative-link scan across all 233 research Markdown/MDX files, and first-pass triage of 36 low-confidence entries are recorded. One LLMLang-authored broken link was fixed; 38 unresolved occurrences are confined to partial verbatim external snapshots. PLAN.md §0.1 remains partially validated until content-level and reproducibility validation for all 120 prototype-family artifacts, index completeness, explicitly preserve RT-24's non-normative candidate status, supersession/orphan/contradiction analysis, external snapshot provenance/completeness, and reproducibility verification are complete.
