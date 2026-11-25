# LLMLang Research and Development Plan

**Status:** living plan  
**Updated:** 2026-11-23
**Restored baseline:** detailed plan from [`aa39c8f`](https://github.com/aivibeflow/LLMLang/commit/aa39c8fc2a611ae72ff85acff3de3c16fcc4eb39), reconciled with the current project plan and repository evidence  
**PR #47 consolidation:** §5 maps the research in the merged snapshot at `73d37723e6a759159b354c2cd74327517c4036c4` to the current plan. PR #50 restored the text of `PLAN.md`. PR #51 incorporated the research from PR #47 into the plan. [Restoration commit `2c7f3d1`](https://github.com/aivibeflow/LLMLang/commit/2c7f3d1) · [Consolidation commit `7fd8eac`](https://github.com/aivibeflow/LLMLang/commit/7fd8eace9210dffdbdcd98302e19bf6bc18be756)<br>
**Repository:** `aivibeflow/LLMLang`  
**Research corpus at plan creation:** 102 files under `research/`  
**Normative boundary:** this plan schedules research and validation. Research results are not normative language rules until explicitly reviewed and transferred to `draft/`.

## 1. Purpose

This plan consolidates the LLMLang research programme, including topics already investigated, topics with active prototypes, and topics that remain open. Its purpose is to:

- establish a dependency-aware order for research;
- preserve completed work instead of treating it as future work;
- distinguish an existing research document from a validated result or an accepted architectural decision;
- identify the evidence and exit criteria required before moving to the next stage;
- keep the research corpus in `research/` and the candidate specification in `draft/`.

The stages are ordered. Work inside a stage may proceed in parallel when its dependencies are satisfied. A later stage may be explored early, but it must not be treated as architecturally settled before its prerequisites pass their exit criteria.

## 2. Status vocabulary

Use these statuses for each item:

- **Researched** — a research document or substantial analysis exists. This does not mean the question is conclusively resolved.
- **Prototyped** — an executable prototype or focused experiment exists.
- **Partially validated** — some claims have supporting evidence, but acceptance criteria remain unmet.
- **In progress** — active work or an explicit next experiment exists.
- **Not started** — no substantial research has been recorded yet.
- **Decision pending** — alternatives have been investigated, but an explicit design decision remains open.
- **Accepted** — an explicit project decision has been recorded in a durable design document. A recommendation alone is not acceptance.

Status applies to the current evidence, not to how important the topic is. Where the repository contains related research but not a direct answer to the exact question, mark the item as partially researched rather than complete.

## 3. Stage overview

| Stage | Name | Main outcome | Gate |
|---|---|---|---|
| 0 | Research inventory and evidence hygiene | A reconciled map of existing work, claims, prototypes, gaps, and decisions | Every existing research area is mapped; evidence and decision status are explicit |
| 1 | Semantic foundation and identity | A coherent model of SPG, semantic objects, contracts, and immutable identities | Canonical semantic objects, identity boundaries, and contract relations are sufficiently defined |
| 2 | Formal semantics and verification foundation | A small formal core with independently checkable claims and explicit proof boundaries | A reference semantics and a sound, reproducible verification slice exist |
| 3 | Dependency graph, incremental computation, and cache | Sound impact analysis and cache reuse/invalidation model | Dependency completeness and cache-key soundness are demonstrated on representative changes |
| 4 | Semantic storage, versioning, and Git integration | Durable repository representation and semantic merge workflow | Clone, history, diff, merge, conflict handling, and recovery are demonstrated |
| 5 | Types, execution model, runtime, and POSIX | A small executable language/runtime slice with explicit platform boundaries | A vertical slice preserves its declared semantics on a selected target |
| 6 | Translation, backends, and optimization | Multiple target realizations and evidence-backed implementation selection | Two backends agree with reference semantics for the selected subset |
| 5–6 (cross-cutting) | RT-37 embedded firmware and RT-38 OS kernels | Freestanding profile and bootable bounded pilots | Explicit runtime closure, independent target evidence and trust boundaries; firmware precedes kernel |
| 7 | Scale, ecosystem, collaboration, and adoption | Measured feasibility and operational model for real projects | Performance, storage, collaboration, trust, and usability criteria are measured |

---

# Stage 0 — Research inventory and evidence hygiene

**Order:** first; can run alongside maintenance of existing prototypes.  
**Purpose:** establish what the current research corpus actually proves and what remains open.

### 0.1 Reconcile the research corpus

**Estimated research complexity:** **2/10** — repository-wide inventory, duplicate/orphan audit, traceability, and reproducibility checks.

- [x] Enumerate every tracked file under `research/` from the recursive Git tree; record its path, Git blob SHA, byte size, coarse artifact category, and path-based research-item traceability in [the corpus inventory snapshot](research/research-management/RESEARCH-CORPUS-INVENTORY-2026-11-20.json).
- [x] Perform first-pass content/heading/reference triage of all 36 previously low-confidence root-level entries; add explicit RT/Stage 0 mappings, candidate plan-stage metadata, and review basis in the inventory and [semantic traceability report](research/research-management/RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md). This is triage, not full claim-level validation.
- [x] Map 63 Scenario reports from explicit links/ranges in `RESEARCH-TAXONOMY.md`.
- [x] Complete first-pass crosswalk for all 136 strict `RESEARCH-SCENARIO-<number>` report files: the remaining 73 use report header/scope review. Record Scenario 91's RT-24 cross-reference (now registered), Scenario 134's prior-art-only applicability, Scenario 95's supplemental execution report, and the absent Scenario 16 number without renumbering; Scenario 58 is consistently mapped to RT-10. The 137 broad filename count included the RT-00 Scenario 130 claim-traceability pilot, not an omitted report; see [Scenario crosswalk reconciliation](research/research-management/RT-00/RT-00-A-SCENARIO-CROSSWALK-RECONCILIATION-2026-11-23.md). Scenario 16 intent remains unresolved.
- [x] Complete per-path prototype-family role review. The 2026-11-23 content review maps all 289 current prototype paths individually, including the 36 paths outside the previous 253-file total. This is file-role/traceability triage only; it does not establish claim validation, test execution, or reproduction. See [RT-00 A prototype role review](research/research-management/RT-00/RT-00-A-PROTOTYPE-ROLE-REVIEW-2026-11-23.md).
- [ ] Validate prototype claims, test evidence, generated outputs, exact tool versions, and reproducibility at content/experiment level.
- [x] Recheck the exact current-main verification-key prototype against the three focused suites and compare exact execution identity with subject-only and policy/applicability separation; 26/26 tests passed. See [RT-00 C verification reuse identity recheck](research/research-management/RT-00/RT-00-C-VERIFICATION-REUSE-IDENTITY-RECHECK-2026-11-24.md). This is a bounded prototype evidence audit, not proof of production dependency/environment completeness.
- [x] Record three explicit section-level supersession cases (Scenario 31 query representation; Scenario 32 parser-state bridge sketch; embedded ADR-0001 proposal); no whole document is marked superseded.
- [ ] Complete the corpus-wide semantic duplicate, superseded-version, orphan, and contradiction review. Exact-blob comparison at main `41bd03e` still finds only the expected shared OCI/REAPI Apache-2.0 licence pair, but content-level comparison of remaining new/modified research families and cross-cutting contradiction reconciliation remain open. See [RT-00 B9](research/research-management/RT-00/RT-00-B-09-CURRENT-MAIN-CORPUS-RELATIONSHIP-DELTA-2026-11-24.md).
- [x] Scan inline relative Markdown links in the 233-file historical baseline (1,330 relative-link occurrences; PR #80 and PR #82 Markdown changes were rechecked). The current corpus has 234 Markdown/MDX files after adding the semantic-traceability report; a full current-corpus link scan remains open. The 38 unresolved occurrences from the baseline are confined to partial verbatim external snapshots (Alive2 and OCI).
- [x] Run the offline Markdown/MDX local-path and available-anchor scan against current main plus the refreshed E report in PR #160. The exact PR merge checkout contains 253 Markdown and 3 MDX files (256 total); 2,891 link occurrences (1,318 unique) produced 1,641 accepted, 82 unresolved, and 1,168 excluded. All 82 unresolved occurrences are confined to copied upstream MCP/OCI/Alive2 snapshots; no LLMLang-authored local link or available-target anchor was reported. Lychee returned exit code 2 and the evidence-gathering workflow job succeeded. Final validation run #44942704138 preserves artifact #14721739745 (merge checkout `3643ea099bdd89c64e9fa468bddbc3ad29e80155`). PR #160 remains branch-only until merged. External URL availability and fragments on missing snapshot targets remain unverified.
- [x] Preserve historical findings; the inventory classifies historical scenarios and prototypes without deleting or rewriting them.
- [x] Review the 23 zero-inbound candidates at the B8 baseline and the newly surfaced current-main Russian concept companion as a 24th candidate; classify it as an intentional translation companion, add reciprocal navigation, and keep translation parity unverified. See [RT-00 B8](research/research-management/RT-00/RT-00-B-08-ZERO-INBOUND-CANDIDATE-REVIEW-2026-11-23.md) and [RT-00 B9 current-main relationship delta](research/research-management/RT-00/RT-00-B-09-CURRENT-MAIN-CORPUS-RELATIONSHIP-DELTA-2026-11-24.md). The 58 documents without a designated-index link remain review candidates, not proven orphans.
- [x] Classify every tracked file into a coarse artifact category (research document, scenario result, prototype implementation/test/report, preparation material, reference snapshot, structured fixture, index, or other).
- [x] Refresh the exact path/blob/size inventory and first-pass content-role mappings against main `a396e2709c811ffb1810e2e62d93849c890d8ca6`. Main contains 904 artifacts: 20 paths absent from the 884-record manifest and nine existing records with stale Git metadata. The new RT-07 scalar-preservation, valuation-binding, program-assumptions, upstream-model, single-kernel composition and model-extension paths have individual role entries; changed files were individually reviewed. The refreshed manifest recorded all 904 paths on that baseline; the RT-11 PR branch adds its report and raw timing evidence and refreshes the exact PR-tree metadata. See [RT-00 A current-main reconciliation](research/research-management/RT-00/RT-00-A-POST-THEMATIC-INVENTORY-REFRESH-2026-11-24.md).
- [ ] Record and verify exact commit/revision, tool versions, and environment for every reproducibility-sensitive result. The inventory records exact tree identities; merged experiment results retain their pinned tools and sources, but this refresh environment cannot rerun every toolchain. The RT-05 pilot's hashes and reported Lean kernel result are preserved. Original-run attestation, independent review, claim-level reproduction and source-to-fixture correspondence remain explicit gates. The freshness workflow checks path/blob/size consistency only.

**Post-evidence current-main inventory refresh (2026-11-24):** The exact recheck at main `a396e2709c811ffb1810e2e62d93849c890d8ca6` found 904 research artifacts, 20 paths absent from the 884-record manifest and nine stale blob/size entries. The additions and changed files received individual role review. The refreshed manifest records all paths on that baseline; the RT-11 direct-child timing PR updates the manifest for its two additional report/evidence files and carries forward the three individually role-reviewed RT-07/32 proof artifacts merged in #480 on current main `7dd68a30fd720c750f052ab745e4478d42bd76f0`. Historical navigation scan at that baseline: 435 research Markdown/MDX and 3,113 local links, with 18 zero-inbound candidates, 52 without a direct designated-index link, and 38 unresolved local snapshot targets. The RT-11 PR-tree rerun on main `7dd68a30fd720c750f052ab745e4478d42bd76f0` scanned 437 research Markdown/MDX and 3,126 local links; it found the same 18/52 candidates and 38 unresolved targets (775 existing non-Markdown targets). See [RT-00 A current-main reconciliation](research/research-management/RT-00/RT-00-A-POST-THEMATIC-INVENTORY-REFRESH-2026-11-24.md). External URL reachability and partial snapshot completeness remain unverified. The RT-00 B10 reachability report establishes zero unreachable artifacts under its linked-directory model at its pinned baseline. B12's selected lexical candidates were reviewed, but four known controls escaped its filter; semantic supersession, contradiction and cross-document claim review remain open. Scenario 16 remains unresolved pending author/archive evidence. Historical run provenance and fresh reproduction remain experiment-specific.

**Post-relocation inventory audit (2026-11-24):** The [exact-tree migration comparison](research/research-management/RT-00/RT-00-A-CORPUS-RELOCATION-2026-11-24.md) reconciles 318 path moves in merged PR #444 and checks 522 exact-blob moves in the intermediate commit of PR #446. After both mappings, main `1a59724` has 47 unrepresented paths and 227 stale blob or size records against the archived 786-record inventory. Role and identity reconciliation, claim-level reproducibility, and review of changed content remain open.

**Thematic inventory refresh (2026-11-24):** The [current-tree reconciliation](research/research-management/RT-00/RT-00-A-THEMATIC-INVENTORY-REFRESH-2026-11-24.md) maps all 786 archived records through three moves and reviews the roles of all newly inventoried paths and the 24 previously pending role records. The result pins exact research path, blob and size metadata. Review the remaining changes and experiment evidence before using them for specification synthesis.

**Research navigation reachability (2026-11-24):** The [RT-00 B10 audit](research/research-management/RT-00/RT-00-B-10-INDEX-REACHABILITY-2026-11-24.md) reaches all 849 tracked research files from the research index or this plan through local links and explicitly linked directory listings. The prior tree had 65 unreachable paths under the same model. Structural discoverability is verified for this tree. External snapshot completeness, semantic review and underlying claims remain open.

**Changed-artifact role review (2026-11-24):** The [RT-00 B11 ledger](research/research-management/RT-00/RT-00-B-11-CHANGED-ARTIFACT-ROLES-2026-11-24.md) classifies all 95 deltas left by the first navigation projection. Thirty additional records are equal under the broader command-path projection. The report records the RT-36 translation coverage gap and the remaining semantic, experimental and independent review obligations.

**Corpus text-overlap screen (2026-11-24):** The [RT-00 B12 screen](research/research-management/RT-00/RT-00-B-12-TEXT-OVERLAP-2026-11-24.md) checks all 87,990 Markdown/MDX pairs and reviews the 18 selected candidates. Four known translation or supersession controls escape the filter. Retain explicit claim lineage and manual semantic review. The Scenario 16 numbering gap needs author or archive evidence.

**Previous inventory snapshot:** 462 tracked research artifacts (excluding the inventory manifest itself) at revision `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f`: 234 Markdown/MDX files, 194 Python files, 22 Lean source files, 240 files under `PROTOTYPES/`, and 136 scenario-named documents. This historical snapshot has been superseded by the refreshed inventory at the current main revision below. The taxonomy contains 24 research areas (RT-01–RT-24); the dependency map contains 94 registered edges (DEP-001–DEP-094).

**Current-main inventory refresh:** PR #100 refreshed the inventory against a reviewed tree based on main `47ec6e26ca12e615283d02393656bc0b3e9f656f` and merged as `422f77d5340ffbfeb1f00d301f8ba1bc86760070`; PR #102 added the scenario relationship review, and PR #104 added the RT-04-01 evidence graph review. PR #107 adds the Dependency Graph/Logos evidence review and refreshes the inventory to 471 research artifacts: 240 Markdown/MDX files, 197 Python files, 22 Lean source files, 243 prototype-tree files, and 136 scenario-named documents. PR #105 and PR #109 also added the package-index test-timing and Provider-profiling diagnostics after the 471-record inventory snapshot. This cross-cutting alignment review indexes both diagnostics and adds one further report, refreshing the inventory to 474 artifacts: 241 Markdown/MDX files, 199 Python files, 22 Lean source files, and 245 prototype-tree files. The earlier inventory refresh found 17 changed existing blobs and six added research files; no previous paths were deleted. The three new prototype files received individual role mappings. The [Dependency Graph evidence review](research/research-management/RESEARCH-CORPUS-PROTOTYPE-EVIDENCE-DEPENDENCY-GRAPH-01-2026-11-20.md) reconciles SCW-04's historical finding and marks the scoped SCW-05 declaration-context work complete; SCW-32 source-derived CPC binding and subsequent JSON/parser-state correspondence remain open. The [cross-cutting alignment review](research/research-management/RESEARCH-CORPUS-CROSS-CUTTING-ALIGNMENT-REVIEW-2026-11-20.md) confirms 24 RT areas/94 DEP edges, preserves the explicit `ImpHash`/`ImplHash` terminology issue as unresolved, corrects semantic-index section numbering, and records the two package-index diagnostic scripts added by PRs #105 and #109.

**Status:** partially validated. Historical inventory and link checks remain pinned to their recorded revisions; current-main artifacts and metadata are reconciled at `f1401e8` in the post-evidence refresh above. Structural discoverability has since been checked with a directory-link graph and corpus lexical candidates were adjudicated, but B12 missed four known relationship controls. The full semantic duplicate/supersession/orphan/contradiction review, translation parity, external URL validation, source snapshot completeness, exact run provenance for some historic experiments, and independent claim review remain open. RT-24 and other architectural proposals remain proposals; no architecture decision is implied.


**Public-interface evidence reconciliation (2026-11-24):** The [RT-00 B audit](research/research-management/RT-00/RT-00-B-PUBLIC-INTERFACE-EVIDENCE-AUDIT-2026-11-24.md) compares the integrated proposal against 63 reproduced prototype tests. A binding declaration admits an observed out-of-contract trace, and positive-only resolution keys produce false reuse in the scoped fixture. Public-interface refinement, name identity policy and source/backend correspondence remain open.

**Evidence-audit progress (2026-11-20; refreshed 2026-11-23):** the first bounded claim/evidence passes cover Scenarios 1–15 and 17–134 (Scenario 16 is absent), with linked prototypes/tests, specification-level prior art, historical LLVM preservation experiments, and native-probe boundaries checked. It records finite-fixture support and explicit limitations, confirms the full RT-04-01 test-discovery step passed in Required CI run 44767733362, and identifies an integration boundary: the exploratory SymPy path adapter prunes raw UNSAT results directly, while the separate conservative result mapper requires an explicit accepted evidence basis. These components are not yet integrated. The current eight-test result-policy file passed a fresh CPython 3.12.14 run with exact hashes; the file is the same blob present in Required CI commit `b808c3a8f984bbc5c175ecf45d61e0e8db7a00bb`. See [RT-00 C Scenario 102 reproduction](research/research-management/RT-00/RT-00-C-SCENARIO-102-RESULT-POLICY-REPRO-2026-11-23.md). The historical seven-test focused run's exact source revision remains unknown; do not equate it with either current result-policy or DPLL test files.

**Post-relocation backend preservation replay (2026-11-24):** The [RT-00 C replay](research/research-management/RT-00/RT-00-C-BACKEND-PRESERVATION-REPLAY-2026-11-24.md) reproduced the exact LLVM integer and view input identities, O0/O3 native outcomes and negative controls, and the published LLVM-to-Wasm module and handwritten WAT hashes. The Wasm observations matched on two Node releases. Broader source correspondence and cross-engine evidence remain open.

**Package Provider evidence replay (2026-11-24):** The [paired queue comparison](research/research-management/RT-00/RT-00-C-PROVIDER-QUEUE-REPLAY-2026-11-24.md) reproduced 130 focused tests and verified identical archive hashes in 20 pairs. At 1,000 synthetic objects the indexed queue lowered median build time on four shapes, with overlapping observed times. Controlled hardware and representative storage workloads remain required for §7.2 decisions.

**Exact-current RT-04 native lifecycle replay (2026-11-24):** The [RT-00 C replay](research/research-management/RT-00/RT-00-C-NATIVE-LIFECYCLE-REPLAY-2026-11-24.md) passed all ten native commands and 364 model tests. All ten stdout sections match the prior CI job log, including 125,952 generated-Rust observations. The recorded SQLite build identities cover these reruns. Original Scenario 130 provenance and general foreign/provider correspondence remain open.

**Native reproduction preparation (2026-11-20):** the manual and focused-PR [RT-04 Native Reproduction workflow](.github/workflows/rt04-native-reproduction.yml) and [reproduction protocol](research/language-design/RT-04/RT-04-NATIVE-REPRODUCTION.md) execute the SQLite C-API probes, durable-receipt recovery, and generated-Rust comparison while preserving machine-readable environment metadata and per-command output. Successful run 44771268838 passed all ten commands with zero failures/skips: C SQLite 3.46.1 with the exact scenario distro source ID, Python 3.12.14 with SQLite 3.53.1 for Scenario 130, and Rust 1.85.1. Per-case outputs for Scenarios 120–128, 130, and 133 match the reports; the 364-test Required CI run also covers the finite models in Scenarios 109–118. Scenario 134 is prior-art/reference material under the accepted same-build compatibility decision. Scenarios 96A/96B were freshly reproduced by LLVM job 44773422416 with matching package hash, toolchain versions, input IR hashes, comparison counts, and negative controls; artifact 14647744441. See audit §§2.13–2.16 and §2.20 and the linked reproduction artifacts/protocols. The final PR validation run 44774296240 also passed all ten RT-04 native commands and both LLVM preservation probes (artifacts 14650095720 and 14650040345); Required CI on main merge commit b808c3a8 passed in run 44774552406. The historical Scenario 130 report did not preserve its SQLite source ID, so only version-level equivalence is established. The [RT-04-01 prototype evidence graph review](research/research-management/RESEARCH-CORPUS-PROTOTYPE-EVIDENCE-RT04-01-2026-11-20.md) records the runner/test/workflow links, current 45-module/364-test suite, artifact hashes, and remaining provenance limits. This is a reproduced bounded slice, not completion of prototype validation.

**Current-main reconciliation (2026-11-21):** The inventory manifest revision b118346ecd499d7962a6ac546fb1031bc7e2bc26 records 488 research artifacts and 248 prototype files, but it is stale relative to current main at b0142c27f5632a859c379b78a10cb22f500ebfd8. The recursive inventory audit in PR #146 scanned main at 017e64b87c87371309197a392165258b8b088dd1 and measured 490 research artifacts excluding the manifest, 250 Markdown files, 3 MDX files, 202 Python files, 23 Lean files, 249 prototype files, and 136 Scenario-named documents. Exact comparison to b52ba2f adds the two RT-23 report/test paths; comparison from b52ba2f to b0142c2 adds the B4 report. This yields 493 research artifacts, 252 Markdown, 3 MDX, 203 Python, 23 Lean, and 250 prototype files. The manifest at current main has five missing paths (RT-24 report/test, RT-23 report/test, and B4 audit report), zero extra paths, and five stale SHA/size records (Dependency Graph README, research README, dependency map, RT-24 canonical report, and RT-23 worktree contract). PR #149 proposes the correction and remains unmerged. PR #160 scanned 253 Markdown and 3 MDX files (256 total) on current main plus the E report: 2,891 occurrences, 1,318 unique, 1,641 accepted, 82 upstream-snapshot errors, 1,168 excluded. Final validation run #44942704138 and artifact #14721739745 preserve the evidence (merge checkout `3643ea099bdd89c64e9fa468bddbc3ad29e80155`).

The 26/108 taxonomy/dependency register was structurally checked: all 108 DEP IDs are unique, all endpoints resolve to one of the 26 RT IDs, there are no self-loops, and the two non-trivial strongly connected components are RT-05/RT-12 and RT-14/RT-19/RT-20, both documented in the dependency-map prose. The high-level Mermaid diagram is explicitly simplified and does not depict RT-21–RT-26; the detailed register does contain them. The current research README already labels the 24/94 figures in the older alignment review as superseded.

Prototype role-review counts are not reconciled: the inventory aggregate says 242; the previous PLAN statement says 245; the previous inventory per-file traceability covers 248 paths; current main has 250 prototype paths. Current family path counts are 3/108/4/7/17/106/2/3. Do not infer equivalent content-review depth for every current file from path or traceability metadata.


**Current-main inventory freshness addendum (2026-11-22):** A fresh recursive-tree comparison at `fc717d9c5a69085d7a524fd6dfc27145f0c35a1c` found 578 research files excluding the manifest: 297 Markdown, 3 MDX, 226 Python, 33 Lean, 289 prototype-tree paths, and 137 Scenario-named documents. The manifest has 554 records, 24 missing paths, 20 stale blob SHA/size records, and no extra paths. 11 prototype paths are absent from the manifest; represented-path traceability metadata is not equivalent to content review or reproduced evidence. The manifest records a historical aggregate of 242 individually role-triaged prototype files in `semantic_traceability_review.prototype_family_review`; this is 47 below the current 289 prototype paths. The per-family review ledger must be reconciled against exact current paths before assigning review status to individual files. See [RT-00 A current-main inventory freshness reconciliation](research/research-management/RT-00/RT-00-A-CURRENT-MAIN-INVENTORY-FRESHNESS-RECONCILIATION-2026-11-22.md). Stage 0.1 remains open: the manifest refresh and content-role triage of the 24 previously absent paths are complete on PR #234's branch, while 36 prototype paths remain outside individual role review and claim-level/reproducibility validation remains open. This exact-tree count supersedes older numeric snapshots for the named commit only.

**Content-role triage follow-up (2026-11-22):** The 24 paths absent from the previous manifest were individually reviewed by content, paired tests/imports, and explicit scope. Eleven prototype files received individual role mappings: eight in DEPENDENCY-GRAPH-01, two in LLVM-PRESERVATION-01, and one in ALLOCATOR-COMPAT-01. The historical prototype role-review total is now 253/289 current prototype paths; 36 remain outside the individually reviewed total. This is role triage only, not execution or claim validation. See [RT-00 A content-role triage](research/research-management/RT-00/RT-00-A-CONTENT-ROLE-TRIAGE-2026-11-22.md). The inventory manifest has been refreshed against the exact PR tree and validated by the inventory freshness workflow.

**Current-main A refresh (2026-11-23):** PR #234 is merged. PR #237 subsequently changed only one research-tree file, RT-19, while adding the scoped accepted ADR-017 outside `research/`. The follow-up review individually classified the 36 prototype paths outside the prior total and refined three related Lean source-role records. The resulting PR branch records 289/289 prototype paths with individual content-role triage and refreshes the RT-19 blob metadata. It adds this A report, so the branch inventory target is 581 research artifacts excluding the inventory manifest. The final exact recursive-tree check is pending; do not treat the branch count as verified until that workflow passes. The 137-versus-136 filename-count discrepancy is reconciled in [the Scenario crosswalk report](research/research-management/RT-00/RT-00-A-SCENARIO-CROSSWALK-RECONCILIATION-2026-11-23.md); Scenario 16 intent and claim-level/reproducibility validation remain open. See [RT-00 A prototype role review](research/research-management/RT-00/RT-00-A-PROTOTYPE-ROLE-REVIEW-2026-11-23.md).

**Current-main freshness reconciliation (2026-11-23):** At main `5662fab189d357cd88037726f05d9ec1dcbb13d8`, the exact tree contains 589 research artifacts excluding the manifest. The prior 587 records omit the Git binary-storage study and quality-rules rollout comparison; the taxonomy record also has a stale SHA/size pair. The refreshed PR inventory adds those records, refreshes taxonomy and README metadata, and is checked against the exact PR tree. RT-27 taxonomy/dependency-map registration was completed in PR #251; the post-merge exact inventory reconciliation is recorded in [RT-00 A RT-28 inventory freshness](research/research-management/RT-00/RT-00-A-RT28-INVENTORY-FRESHNESS-2026-11-23.md). This closes only the named-tree inventory freshness delta. Stage 0.1 remains open for claim/reproducibility validation, full semantic duplicate/supersession/orphan/contradiction review, Scenario 16 intent, and external snapshot/index completeness.

**Current-main duplicate/index recheck (2026-11-23):** [RT-00 B7](research/research-management/RT-00/RT-00-B-07-CURRENT-MAIN-EXACT-CONTENT-AND-INDEX-RECHECK-2026-11-23.md) re-enumerates main `02d0c3d065e160277b498e106646e8a02f2a43fd`: 607 research paths, 606 unique blobs, and only the intentional shared OCI/REAPI license duplicate. The index auditor found and the report corrects one broken LLMLang-authored RT-24 taxonomy link. After correction, 38 unresolved local targets are all in partial upstream OCI/Alive2 snapshots; 23 documents have no inbound links and 57 lack designated-index inbound links. These remain candidates for full content review, not automatic orphan findings. Claim/toolchain reproduction, semantic paragraph-level overlap review, those candidate files, Scenario 16, and external snapshot completeness remain open dependencies.

### 0.2 Establish research quality and decision rules

**Research output (2026-11-20):** [Research Quality and Decision Rules](research/research-management/RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md) proposes a claim-level evidence vocabulary, report structure, traceability fields, and five review gates. This is a partial result; conventions are not yet accepted and existing artifacts have not been fully audited.

**Research output (2026-11-23):** [Quality Rules Rollout Options](research/research-management/RT-00/RT-00-QUALITY-RULES-ROLLOUT-OPTIONS-2026-11-23.md) compares corpus-wide retrofit, priority-ordered manual audit, and staged hybrid rollout against three current-main reports. It provisionally recommends a warning-first hybrid, but does not measure reviewer outcomes or migration cost. Maintainer adoption, corpus-wide audit, reproducibility reruns, and any CI pilot remain external dependencies; §0.2 remains open.

**Research output (2026-11-23):** [Quality Rules Evidence-Shape Recheck](research/research-management/RT-00/RT-00-QUALITY-RULES-EVIDENCE-SHAPE-RECHECK-2026-11-23.md) compares an exact-main rerun of RT-11's synthetic C benchmark, the pinned Lean/Lake Logos proof project, and Scenario 118's bounded model report. It provisionally favors a shared metadata/scope/decision-boundary minimum with evidence-type-specific reproduction pointers; the local benchmark reproduced its 12 cases, while this environment lacks Lean/Lake and the current Required CI build is referenced. No policy is adopted; maintainer approval, corpus audit, pilot, and reviewer-effort measurements remain external dependencies.

**Implementation pilot (2026-11-23, issue #285):** The [proposed Quality Review Protocol](research/research-management/QUALITY-REVIEW-PROTOCOL.md) consolidates claim classes, report structure, reproducibility variants, negative-result handling, decision gating, and an exact claim-to-draft crosswalk. A [report template](research/templates/REPORT-TEMPLATE.md), [claim register](research/templates/CLAIM-REGISTER-TEMPLATE.md), [bounded checker test report](research/research-management/RT-00/RT-00-QUALITY-RULES-PILOT-2026-11-23.md), and [warning-only pilot workflow](.github/workflows/research-quality-pilot.yml) provide concrete implementations. Six synthetic unit tests passed locally (CPython 3.13.5); no corpus-wide validation, reviewer trial, maintained policy adoption, clean foundational reproduction, or normative specification change is claimed. The six checkboxes remain open pending project-wide adoption and validation.

**Real-report pilot (2026-11-23, issue #285):** [Ten-report quality audit](research/research-management/RT-00/RT-00-QUALITY-RULES-REAL-REPORT-PILOT-2026-11-23.md) checks 10 pinned existing report blobs. The original checker produced 65 structural warnings; 3 metadata punctuation warnings were corrected, leaving 62. A manual, line-grounded review identified 29 more layout-only warnings; the other 33 are not adjudicated as defects. None of the 10 triggered executable-evidence checks due to the absent exact evidence-type field. A [machine-readable sample](research/quality-audit/2026-11-23-sample.json) and warning-only replay workflow are provided. This is not a representative corpus audit, does not reproduce the reports’ experiments, and does not adopt the research policy. All §0.2 completion checks remain open.

**Adjudication follow-up (2026-11-23):** [33-warning review](research/research-management/RT-00/RT-00-QUALITY-RULES-ADJUDICATION-2026-11-23.md) now classifies all 33 previously unadjudicated warnings from the exact ten-report pilot: 16 further layout-only cases and 17 documentation/traceability gaps, including eight missing complete baseline-revision records. The [machine-readable register](research/quality-audit/2026-11-23-adjudication.json) maps each warning to source lines, rationale and next action; the [validator](.github/scripts/validate_research_quality_adjudication.py) tests completeness and line-range bounds, not the correctness of scientific claims. Three scoped claim/evidence/proof examples preserve negative and unproved source-correspondence boundaries. This closes only the bounded warning-triage queue, **not** the full research-quality acceptance criteria; §0.2 remains open pending explicit adoption, broad claim-level auditing, and clean foundational reruns.

**Historical source provenance (2026-11-23, issue #285):** [Eight-report publication snapshot audit](research/research-management/RT-00/RT-00-QUALITY-RULES-PROVENANCE-RECHECK-2026-11-23.md) pins earliest report commits and corresponding committed source blobs. [Five bounded historical reruns](.github/workflows/research-historical-rechecks.yml) test publication snapshots, not necessarily the original author workspace. An archived Git tree does not establish historical experiment provenance; the associated §0.2 evidence gates remain open until original run inputs are attested, critical results reproduced, corpus claims reviewed, and maintainers approve conventions.

**Nine evidence-navigation corrections (2026-11-23):** [Stage 0.2 supplementary report](research/research-management/RT-00/RT-00-QUALITY-RULES-NAVIGATION-REMEDIATION-2026-11-23.md) documents completed *metadata/traceability* crosswalks on Scenarios 98/103/118/29 and DEP-007. The previous eight original-execution attestations, independent claim review and maintainer policy adoption remain open. The frozen 10-report sample now replays exact historic Git bytes instead of assuming current reports have not been edited.

**Stage 0.2 second claim audit (2026-11-23):** [24 source-bound claims across 12 further reports](research/research-management/RT-00/RT-00-QUALITY-RULES-CLAIM-COHORT2-2026-11-23.md) are documented with exact Git object IDs, evidence types, statement/limitation line bounds and downstream decision caveats. [Machine-readable register](research/quality-audit/2026-11-23-claim-cohort2.json) plus optional [CI source validator](.github/workflows/research-claim-cohort-audit.yml) test link integrity and bookkeeping, **not** underlying scientific correctness. This remains a purposive small cohort, not full corpus coverage or formal process adoption; section 0.2 exit gates remain open.

**Stage 0.2 reproducibility continuation (2026-11-23):** [Three archived-source second-cohort rerun cases](research/research-management/RT-00/RT-00-QUALITY-RULES-CLAIM-COHORT2-RERUN-2026-11-23.md) now pin the Scenario 110/112 and RT-24 merge test inputs, provide Python 3.12.14 Ubuntu execution commands and preserve exact output/environment through [GitHub Actions](.github/workflows/research-claim-cohort2-reruns.yml). Passing these tests would corroborate those bounded fixtures, **not** the general language, scheduler or production semantic merge policy. Issue #285 exit criteria remain open.

**Additional Stage 0.2 falsification control (2026-11-23):** [Orthogonal finite-model oracle experiment](research/research-management/RT-00/RT-00-QUALITY-RULES-ORTHOGONAL-ORACLES-2026-11-23.md) compares the archived JSON-decoder and fairness models to separately authored reference tables, plus a Git-source-inventory negative fixture. This goes beyond re-running the author tests but remains bounded model evidence, not an independently peer-reviewed protocol or accepted `draft/` rule. Reviewer/maintainer adoption and broad corpus/attestation obligations remain open.

**Source-pinned second-oracle observations (2026-11-23):** [CI #45261537559](https://github.com/aivibeflow/LLMLang/actions/runs/45261537559) passed seven fresh checks: 3,456 JSON-policy combinations (504 accepted/2,952 rejected), 21,840 fairness-action words (138 valid cycles, 114 weak-but-not-strong), and a clean-Git-merge/absent-declared-file counterexample. [Result register](research/quality-audit/2026-11-23-orthogonal-oracle-results.json) stores exact model/test blobs, CI, host and limits; [independent human-review handoff](research/quality-audit/2026-11-23-independent-review-handoff.md) is **pending (0/8)**, not a completed scientific review. Historical execution attestations, representative corpus validation and maintainer rule adoption remain open.

**Root research structural census (2026-11-23):** [Stage 0.2 corpus census report](research/research-management/RT-00/RT-00-QUALITY-RULES-ROOT-CORPUS-CENSUS-2026-11-23.md) defines an immutable 309-document root Markdown/MDX scope, a warning-only checker sweep and a 24-document SHA-256-selected review queue across Scenario, RT and other root reports. This is structural *coverage*, not an audited 309-document claim register or a representative statistical validity estimate; individual review, original-run provenance and process adoption are still open.

**Source-bound symbolic proof evidence replay (2026-11-24):** The [RT-33 source-bound quality check](research/research-management/RT-00/RT-00-QUALITY-RULES-PROOF-CHAIN-REPLAY-2026-11-24.md) rebuilt the pinned LLMLang Lean binding, reproduced 16 exact SMT and CPC outputs, passed 14 focused tests, and confirmed that a final-only certificate cannot establish an all-boundary claim. General source correspondence, independent scientific review and maintainer rules approval remain open.

**Finite three-backend reproduction (2026-11-24):** The [RT-00 evidence composition replay](research/research-management/RT-00/RT-00-QUALITY-RULES-THREE-BACKEND-REPLAY-2026-11-24.md) regenerated cvc5, Lean and TLC artifacts for 798 fixed claims and reproduced all 2,394 scoped receipts, with 712 bounded agreements and 86 refutations. Shared source assumptions, general correspondence and independent review remain open.

**Verified root census result (2026-11-23):** [Pinned CI #45263179285](https://github.com/aivibeflow/LLMLang/actions/runs/45263179285) inspected all 309 root research Markdown/MDX documents at commit `627c708`; 2,035 **surface-only** warnings occurred across 308 files, and only 7 exact evidence-type metadata fields were found (67 unvalidated executable-status hints). The [24-item SHA-256 selected review queue](research/quality-audit/2026-11-23-root-census-observations.json) remains entirely **NOT REVIEWED** by a second person. This does not fulfill corpus-wide claim validation or justify blocking CI; no method-policy adoption is recorded.

**Stage 0.2 proof-source provenance continuation (2026-11-23):** [Lean 4.36.0 archival proof recheck](research/research-management/RT-00/RT-00-QUALITY-RULES-PINNED-LEAN-PROOF-2026-11-23.md) proposes exact Git/SHA-256 source identity validation, source-pinned kernel checking and saved actual `#print axioms` output. This improves the boundary between *formal bounded proof* and *reported executable test*, but does not prove source-to-SPG/backend semantics, validate all corpus claims, reconstruct eight historical runs, or adopt Stage 0.2 policy.

**Pinned formal proof recheck observed (2026-11-23):** [Lean CI #45264153180](https://github.com/aivibeflow/LLMLang/actions/runs/45264153180) checked the exact archived `ObservableRewrite.lean` SHA-256 with Lean 4.36.0 and preserved the actual axioms `propext`, `Classical.choice`, `Quot.sound`. See [proof source/host outcome ledger](research/quality-audit/2026-11-23-pinned-lean-proof-observations.json). This establishes a *bounded model theorem check*, not production optimizer correctness, comprehensive research claim review, or maintainer acceptance of §0.2 rules.

**Stage 0.2 review after report relocation (2026-11-24):** The [source-bound queue comparison](research/research-management/RT-00/RT-00-QUALITY-RULES-QUEUE-RELOCATION-2026-11-24.md) reproduces the historical census and 24-document review queue and finds 13 exact historical blobs in the pinned post-PR-#444 tree. Current links locate 24 candidates, including 11 with revised bytes. Preserve the archived claim inputs for review. External dependencies are independent human adjudication of the 24-document queue and the separate eight-claim handoff, original-run attestations where recoverable, and maintainer approval of Stage 0.2 rules. Broader claim verification remains open.

**Historical citation replay after both moves (2026-11-24):** The [adjudication follow-up](research/research-management/RT-00/RT-00-QUALITY-RULES-ADJUDICATION-2026-11-23.md#archival-citation-check-after-directory-moves-2026-11-24) reproduces all 33 archived warning adjudications by checking their citation ranges on the original Git blobs. Independent adjudication, technical claim review and maintainer adoption remain open.

**Estimated research complexity:** **3/10** — mostly methodological analysis and consistency checks.

- [ ] Use a consistent research structure: problem, hypotheses, prior art, alternatives, formal model, experiments, results, limitations, decision, and draft impact.
  - [x] Compare five recent RT-19/25/32/13 reports to the proposed minimum structure by content rather than heading names. Core information is present under varied headings; metadata and claim-level traceability remain uneven. [Report structure recheck (2026-11-24)](research/research-management/RT-00/RT-00-REPORT-STRUCTURE-RECHECK-2026-11-24.md)
  - Remaining external dependencies: corpus-wide audit of older reports/prototypes, claim-level IDs and falsifier/impact records, independent human review, and maintainer approval.
- [ ] Distinguish observations, assumptions, conjectures, experimental results, proofs, and accepted decisions.
  - [x] Recheck this distinction across four recent implementation-relevant reports (RT-19 transaction and publication boundaries, RT-25 workload fit, RT-32 Lean observation binding). All preserve scope and decision boundaries; stable claim IDs and per-claim confidence/falsifier/impact fields are not yet uniform. [Recent evidence-class recheck (2026-11-24)](research/research-management/RT-00/RT-00-RECENT-EVIDENCE-CLASS-RECHECK-2026-11-24.md)
  - Remaining external dependencies: independent human adjudication of the quality-review queue, maintainer approval of the proposed evidence vocabulary/gates, and corpus-wide claim provenance/reproduction/source-correspondence review.
- [ ] Require reproducible commands, fixtures, tool versions, and expected outputs for executable experiments.
  - [x] Cross-check reproduction routes for recent RT-19/25/32 implementation studies and rerun the RT-19 Toolchain suite (9/9, Python 3.12.14); added its missing command and expected output to the publication report. [Reproduction boundary recheck (2026-11-24)](research/research-management/RT-00/RT-00-REPRODUCTION-BOUNDARY-RECHECK-2026-11-24.md)
  - Remaining external dependencies: pinned Rust plus TCMalloc/mimalloc runner for allocator replay; Lean 4.36.0 and LLVM tools for RT-32/RT-13 reproductions; persistent RT-19 publication/coordinator implementations for design-level recovery and concurrency tests; corpus-wide claim reproduction.
  - [x] Cross-check reproduction routes for the same four recent reports and rerun the RT-19 Toolchain suite to verify the command; corrected the publication report's missing command/expected result. Archived RT-25 summary recomputation is not a fresh benchmark, and broader candidate environments remain external. [Recent evidence-class recheck, reproduction boundary](research/research-management/RT-00/RT-00-RECENT-EVIDENCE-CLASS-RECHECK-2026-11-24.md#reproduction-boundary-crosswalk)
  - Remaining external dependencies: independent reproduction of the RT-19 crash/publication design, a pinned Rust plus TCMalloc/mimalloc runner for fresh allocator runs, and tool/source compatibility validation beyond the RT-32 fixture.
- [ ] Record negative results and rejected alternatives.
  - [x] Recheck five recent RT-19/25/32/13 studies: distinguish model counterexamples/unsupported inputs, recommendation-scoped exclusions, neutral measurements, and unavailable candidates. No negative result is treated as an accepted project decision. [Negative-result boundary recheck (2026-11-24)](research/research-management/RT-00/RT-00-NEGATIVE-RESULT-BOUNDARY-RECHECK-2026-11-24.md)
  - Remaining external dependencies: uniform claim-level result labels and independent review/reproduction across the corpus; maintainer adoption of the Stage 0.2 quality vocabulary.
- [ ] Link every proposed specification change to its supporting research and evidence.
- [ ] Ensure that `research/` remains exploratory and `draft/` remains the candidate specification.
  - [x] Cross-check the draft index, accepted compatibility decision, proposed review protocol, and three recent evidence reports. The selected files keep scoped research recommendations separate from accepted rules; no empirical report silently amends the accepted decision. [Research-to-draft boundary recheck (2026-11-24)](research/research-management/RT-00/RT-00-RESEARCH-DRAFT-BOUNDARY-RECHECK-2026-11-24.md)
  - Remaining external dependencies: corpus-wide application of the boundary check; independent review of the claim cohort and proposed quality protocol; maintainer adoption; and exact source-bound claim links for any future draft change.

**Exit criteria:** every existing research artifact is discoverable from an index; every major claim has an explicit evidence level; unresolved questions are linked to `TODO.md` or a clearly identified research item. See the [external evidence and approval dependencies](#external-evidence-and-approval-dependencies).

---

# Stage 1 — Semantic foundation and identity

**Order:** after Stage 0 inventory; foundational for all later stages.  
**Purpose:** define what a LLMLang program is and what exactly its identities commit to.

### 0.3 Research taxonomy and cross-aspect dependency map

- [x] Define the research taxonomy and identify the major LLMLang research areas.
- [x] Establish an initial directed dependency map with relationship types and confidence levels.
- [x] Identify feedback loops, foundational topics, and opportunities for parallel research.
- [ ] Validate and revise dependency edges as research produces evidence; the current map is an initial hypothesis, not a settled architecture. [DEP-005 was rechecked on current main](research/research-management/RT-00/RT-00-DEP-005-EVIDENCE-RECHECK-2026-11-23.md): the typed-SPG fixture falsifies unordered treatment of the tested observable effects, while leaving several valid order-preserving representations open. [DEP-006 was also rechecked](research/research-management/RT-00/RT-00-DEP-006-TYPE-IDENTITY-EVIDENCE-RECHECK-2026-11-23.md): scalar signature and ownership-obligation changes affect represented contract/dependency identity in bounded fixtures; inline versus referenced type identity remains open. [DEP-007 has a checked proof on the current proof blob](research/research-management/RT-00/RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md): an observation model with ordered traces distinguishes rewrites that value-only checks accept; full-language source/backend correspondence remains open. [DEP-009 was rechecked on current main](research/research-management/RT-00/RT-00-DEP-009-SPG-ADMISSION-RECHECK-2026-11-23.md): rehashed missing-edge graphs pass persistence but fail independent typed admission; source completeness remains a separate dependency. [DEP-012 was also rechecked](research/research-management/RT-00/RT-00-DEP-012-CACHE-IDENTITY-RECHECK-2026-11-23.md): caller-only caching is falsified for a rebound operation call; exact dependency closure is supported, but the production granularity/performance trade-off remains open. [DEP-008 was rechecked](research/research-management/RT-00/RT-00-DEP-008-TYPED-PROOF-BOUNDARY-RECHECK-2026-11-23.md): typed trace proofs and ownership models support a layered fail-closed boundary, but their composition and source binding remain unproved.

**Evidence:** [Research taxonomy](research/research-management/RESEARCH-TAXONOMY.md) currently enumerates 24 research areas (RT-01–RT-24); [cross-aspect dependency map](research/research-management/RESEARCH-DEPENDENCY-MAP.md) currently records 94 dependency edges (DEP-001–DEP-094), research waves, and feedback loops. These are live register counts, not fixed architectural limits.

**Status:** initial taxonomy and dependency map completed; ongoing validation remains part of each research task.

## 1.0 Intent, requirements, and human-validated formalization (RT-02)

**Estimated research complexity:** **7/10** — the core workflow is represented in Scenarios 15, 17, and 18, but faithful reconstruction, semantic-difference detection, human review effectiveness, and end-to-end evidence remain to be researched.

**Existing evidence:** [Scenario 15 — Business Intent to Formal Contracts](research/language-design/RT-02/RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md), [Scenario 17 — Typed Requirement IR](research/language-design/RT-02/RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md), [Scenario 18 — Requirement Evolution and Semantic Impact](research/language-design/RT-02/RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md), and the [Requirement Reconstruction and Human Semantic Validation research proposal](research/language-design/RT-02/RT-02-REQUIREMENT-RECONSTRUCTION-AND-HUMAN-VALIDATION.md). Existing prototypes demonstrate bounded intent/clarification/provenance and typed-IR analysis; they do not implement a complete conversational elicitation or reconstruction workflow.

Research the complete path from a user's request to an accepted, traceable business contract and then to implementation evidence. The reconstructed explanation must be generated from the typed/formal model, not simply paraphrased from the original prompt.

- [ ] Define the end-to-end lifecycle and artifact boundaries: immutable Human Intent, elicitation questions, clarification decisions, typed Requirement IR, formal candidates, analysis results, reconstructed explanation, human approval, accepted contract, component contracts, tests, implementation, and verification evidence.
- [ ] Define clause-level provenance from every IR/formal clause and reconstructed statement to original source fragments and authorized clarification decisions; detect dangling, unsupported, or conflicting provenance.
- [ ] Compare deterministic, LLM-assisted, independent-pass, and hybrid reconstruction strategies. In primary fidelity experiments, prevent the reconstruction generator from seeing the original prompt; use the source separately for semantic-difference analysis.
- [ ] Define reconstruction outputs: human-readable contract, business-rule table, temporal/scenario explanations, counterexamples, semantic differences, unresolved questions, and provenance links.
- [ ] Define how to detect omitted, added, weakened, strengthened, polarity-flipped, temporally shifted, or scope-shifted semantics, including exceptions and negative obligations.
- [ ] Define fail-closed handling for unsupported constructs, unresolved assumptions, missing provenance, incomplete source coverage, analyzer UNKNOWN, and reconstruction failure.
- [x] Check assignment-budget `UNKNOWN` in the finite requirement analyzer against both completed consistency and contradiction. Twelve cases separate exhausted budgets from complete enumeration, and the scenario helper returns no rows on exhaustion. [Finite requirement assignment bound](research/language-design/RT-02/RT-02-REQUIREMENT-ASSIGNMENT-BOUND-2026-11-24.md).
- [ ] Compare [FRET/FRETISH](https://github.com/NASA-SW-VnV/fret) and other formal backends for supported requirement classes; do not make FRET mandatory or assume that a FRET explanation proves intent correctness.
- [ ] Define the human review protocol and exact approval binding: ACCEPT, REVISE, CLARIFY, or REJECT against a specific immutable semantic revision and evidence package.
- [ ] Define revision/impact behavior: semantic changes regenerate affected reconstructions and invalidate affected approvals; provenance-only changes must remain distinguishable from semantic changes.
- [ ] Build clause-level round-trip and seeded-mutation experiments; measure semantic fidelity, provenance coverage, false acceptance, and unknown handling.
- [ ] Run controlled human-review studies comparing prompt-only, formal-only, reconstruction-only, and reconstruction-plus-scenarios/provenance; include domain stakeholders and predeclare thresholds.
- [ ] Keep intent correctness, formal-contract correctness, and implementation correctness as separate claims with separate evidence and acceptance gates.
- [ ] Validate the workflow on representative requirement classes and risk levels; record limits before transferring any result into `draft/`.

**Status:** partially researched. The existing Scenario 15/17/18 work supplies important building blocks, but reconstruction fidelity, semantic-difference detection, and human-review effectiveness have not yet been experimentally validated. The linked research proposal includes a worked order-confirmation example and an experiment plan; it is not a normative architecture decision.

**Exit criteria:** every accepted normative clause is traceable to source/decision evidence; reconstruction faithfully exposes the supported formal semantics and marks unknowns; seeded semantic mutations are detected; human reviewers can identify seeded interpretation defects at predeclared thresholds; approval is bound to the exact semantic revision; implementation verification remains separate.

## 1.1 Semantic Program Graph and program representation

**Estimated research complexity:** **10/10** — the complete SPG model must reconcile graph structure, object lifecycle, identity, evolution, and downstream consumers.

- [ ] Define the Semantic Program Graph (SPG) as a typed semantic representation.
- [ ] Define the relationship between Specification Graph, Design Graph, and Implementation Graph.
  - [x] Compare pinned active requirements, per-edge witnesses and composed refinement. A finite sweep finds 462 locally witnessed designs with no common allowed outcome. Lean checks coverage composition and the missing-requirement counterexample. Production applicability, feasibility and authorization remain open. [Multiple requirement coverage](research/semantic-representation/RT-05/RT-05-MULTI-REQUIREMENT-COVERAGE-2026-11-24.md).
  - [x] Compare exact cross-layer hashing and scoped checked judgments on a closed approval rule. Scoped evidence preserves two values and one judgment on a compatible requirement edit. Stale or missing evidence blocks release, and a trace-only control admits three incompatible cases. Multi-requirement coverage and production release policy remain open. [Layered refinement evidence](research/semantic-representation/RT-05/RT-05-LAYERED-REFINEMENT-EVIDENCE-2026-11-24.md).
- [ ] Define semantic nodes, edges, ownership, references, and graph boundaries.
  - Compare native fallible record construction and later field transfer over 4,608 Rust observations. Separate acquisition, rollback and completed ownership orders preserve every vector. Declaration-order rollback changes 144 early-exit vectors. Reusing the initializer order for completed drops changes 168 completed vectors. User-defined destructors, aliasing and cross-language coverage remain open. [Partial record ownership](research/semantic-representation/RT-05/RT-05-PARTIAL-RECORD-OWNERSHIP-2026-11-25.md)
  - Compare mutable reference topology on 184 closed graph classes. The shared canonical table preserves all 11,688 of its recipe vectors per runtime across relabeling and cycles. Separate-root reconstruction changes 4,758 vectors and physical identifiers change all 1,948 renamed keys. General alias analysis and persistent identity remain open. [Mutable reference topology](research/semantic-representation/RT-05/RT-05-MUTABLE-REFERENCE-TOPOLOGY-2026-11-25.md)
  - Compare receiver binding identity over 108 mutable contexts and 8,640 native C and Rust vectors. Code alone collapses all 5,778 distinct context pairs. Receiver values without shared references collapse 27 pairs and change 135 recipe vectors. The explicit shared table preserves every observed trace. General lifetime and source correspondence remain open. [Stateful bound method](research/semantic-representation/RT-05/RT-05-STATEFUL-BOUND-METHOD-2026-11-25.md)
- [ ] Separate syntax trees, source text, semantic representation, provenance, and generated artifacts.
  - Compare source, expanded syntax, and compiler-resolved bindings on 48 native Rust macro programs. Expanded tokens without definitions collapse eight pairs with distinct effects. The scoped SPG projection preserves all 144 observations and groups the 264 equivalent pairs. General macro provenance and source reconstruction remain open. [Macro binding identity](research/semantic-representation/RT-05/RT-05-MACRO-BINDING-IDENTITY-2026-11-25.md)
  - Compare Unicode names and captured values across 52 native Python, Rust and JavaScript observations. A source-profile-aware graph preserves all results. A shared cell alters six Rust observations per configuration despite correct name normalization. Literal bytes and source provenance remain separate. [Unicode source binding](research/semantic-representation/RT-05/RT-05-UNICODE-SOURCE-BINDING-2026-11-25.md)
- [ ] Determine whether multiple source syntaxes can represent the same semantic graph.
  - [x] Compare three expression profiles on one typed SPG fragment. Within each of 32 configurations all nine conversions preserve canonical graph bytes, including call binding and observable evaluation order. Whole-program frontends remain open. [Cross-profile SPG](research/language-design/RT-31/RT-31-CROSS-PROFILE-SPG-2026-11-24.md).
  - [x] Resolve qualified, named and open source imports to exact SPG operation references. Five source forms share one baseline caller. Across 972 catalog transitions, successful-only lookups give 248 unsafe reuses and complete scoped reads give zero. Production namespace and visibility rules remain open. [Scoped import resolution](research/semantic-representation/RT-05/RT-05-IMPORT-RESOLUTION-INVALIDATION-2026-11-24.md).
- [ ] Define canonicalization and normalization rules.
  - Compare full source order, ordered observable operands and field-map-only hashing for named records in Rust and Python. All 3,888 native observations support preserving an explicit order for trace and failure effects while omitting sequencing for closed total literals. The field map alone collapses 228 distinct case pairs. General effects, defaults, partial initialization and frontend correspondence remain open. [Named record evaluation](research/semantic-representation/RT-05/RT-05-NAMED-RECORD-EVALUATION-2026-11-25.md)
  - [x] Compare canonical ownership and cleanup in a two-scope COR-13 fragment. The 900 input pairs preserve exact roots and 8,192 result/trace observations. Erasing transfer timing, branch order or close-contract roles hides semantic differences. Broader aliasing, effects and full frontend extraction remain open. [Owned SPG normalization](research/semantic-representation/RT-05/RT-05-OWNED-SPG-NORMALIZATION-2026-11-24.md).
- [ ] Define semantic graph evolution, node replacement, splitting, merging, and lineage.
  - [x] Compare review reuse over 12 native Git selection histories with exact commit-bound lineage. Endpoint IDs and unrestricted reachability overgrant across splits, merges and restored scopes even when the final tree equals the baseline. Exact one-to-one continuation preserves the four declared grants and keeps two incomplete histories unknown. Issuer authority and Git multi-parent lineage remain open. [Composed lineage](research/semantic-representation/RT-05/RT-05-COMPOSED-LINEAGE-AUTHORITY-2026-11-24.md).
  - [x] Compare review transfer at a real two-parent Git merge. Two pairs share exact merge commits and require different decisions under the selected-parent policy. Exact Ed25519 fixture receipts preserve the three authorized continuations and leave six missing, stale or unverifiable cases pending. Production resolution issuers and general ancestry remain open. [Multi-parent lineage](research/semantic-representation/RT-05/RT-05-MULTI-PARENT-LINEAGE-2026-11-24.md).
- [ ] Decide artifact granularity: operations, interfaces, contracts, types, implementation components, tests, models, and proofs.
  - [x] Compare snapshot, value and expression storage layouts on the same acyclic SPG. All 54 archives restore exact graph bytes and agree with 5,832 result and trace observations. At 64 entries a local edit writes 27,076 per-value bytes, 27,153 expression-layout bytes or 139,101 whole-snapshot bytes. Context-free expression reuse is refuted, and workload and other artifact choices remain open. [SPG object granularity](research/semantic-representation/RT-05/RT-05-SPG-OBJECT-GRANULARITY-2026-11-24.md).
  - [x] Compare whole, flat and blocked storage of an exact keyed recursive group. At 256 members, a local edit writes 44,495, 17,692 or 2,688 new bytes while changing the same 257 semantic addresses. Exact admission and a body-only cache control distinguish physical reuse from executable identity. [Recursive group storage](research/semantic-representation/RT-05/RT-05-RECURSIVE-GROUP-STORAGE-2026-11-25.md)
- [ ] Define how recursive and mutually dependent structures are represented.
  - [x] Compare structural unfolding equality with finite declaration graph equality and nominal identity on guarded recursive types. A direct paired-path oracle matches all 8,256 comparisons over 128 rooted fixtures, and invalid by-value cycles fail admission. Nominal wrappers and immutable shape versions stay distinct. Broader type semantics and a canonical format remain open. [Guarded recursive types](research/semantic-representation/RT-05/RT-05-GUARDED-RECURSIVE-TYPE-IDENTITY-2026-11-24.md).
  - [x] Compare root traversal, exhaustive permutation and explicit keys on ordered recursive definitions. The traversal matches 52 small isomorphism classes and scales to the tested 128 members. An 11-member witness rules out assuming byte compatibility with exhaustive ordering. Recursive types, unordered edges and the canonical format remain open. [Ordered SCC canonical traversal](research/semantic-representation/RT-05/RT-05-ORDERED-SCC-CANONICAL-TRAVERSAL-2026-11-24.md).
  - [x] Compare stable refinement with exact canonicalization for symmetric unordered components. Exact search matches the exhaustive classification of 772 small graphs, while two connected graph pairs collide under refinement. Directed edge roles and production bounds remain open. [Unordered recursive canonicalization](research/semantic-representation/RT-05/RT-05-UNORDERED-RECURSIVE-CANONICALIZATION-2026-11-24.md).
  - [x] Compare exact directed, role-labeled recursive component identity on 2,496 components and 14,976 relabelings. Erasing direction, roles or multiplicity collapses distinct classes. Typed refinement still admits a symmetric collision. Keep ordered occurrence semantics, larger bounds and canonical bytes open. [Directed recursive roles](research/semantic-representation/RT-05/RT-05-DIRECTED-RECURSIVE-ROLES-2026-11-24.md).
  - [x] Compare ordered executable occurrences with role-local order, unique steps and unordered call operands in a closed recursive fragment. Exact lowering preserves all 6,048 source observations and all 2,016 renamed or reordered surface keys. Every projection collapses behaviorally distinct sources. Keep general frontend correspondence, recursion policy and production bytes open. [Ordered recursive occurrences](research/semantic-representation/RT-05/RT-05-ORDERED-RECURSIVE-OCCURRENCES-2026-11-24.md).

**Existing evidence:** `research/LLMLang-CONCEPT.md` describes the SPG and the three logical graph layers; dependency-graph scenarios 18–28 explore requirement evolution, dependency discovery, and formal dependency analysis.

**Research output (2026-11-21)** · The typed SPG study proposes nodes, edges, layer boundaries, lifecycle and granularity. In a closed fixture, 32 pairs of source bodies produce byte-identical graphs and match an independent trace oracle on 224 paired inputs. The experiment also distinguishes exact calls from operation bindings, validates typed recursion in two group encodings, and checks lineage across equal-value selections. [Typed Semantic Program Graph](research/semantic-representation/RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md)

**Research output (2026-11-21)** · Independent graph admission distinguishes persistence integrity from typed executable structure. Nine rehashed invalid graphs pass persistence and fail the new checker. [Typed SPG import validation](research/semantic-representation/RT-05/RT-05-TYPED-SPG-IMPORT-VALIDATION.md)

**Repository representation evidence (2026-11-24)** · The closed declaration fixture preserves semantic roots and exact selections under 24 physical layouts. Packed and per-slot canonical export give different blob and byte costs for scoped updates. [Canonical Git layouts](research/toolchain-and-collaboration/RT-24/RT-24-CANONICAL-GIT-LAYOUTS-2026-11-24.md).

**Status** · Partially validated for the closed scalar and ordered-event fixture. The canonical schema, wider language and repository correspondence, and identity rules remain open.

## 1.2 Semantic identity, hashes, and canonical encoding

**Estimated research complexity:** **8/10** — foundational identity and hash boundaries affect caching, dependencies, proofs, merge, and artifact storage.

**Terminology prerequisite:** Review [`draft/GLOSSARY.md`](draft/GLOSSARY.md) before changing this section or related RT-20/RT-24/package identity work. Preserve the distinct proposed identities `OpHash`, `ImplHash`, `CCHash`, optional `CandidateSetHash`, and conformance-evidence identity; reconcile the plan's existing `ImpHash` spelling with the glossary's `ImplHash` before treating either as normative. The glossary is a proposal, not an accepted schema or hash-envelope decision.

- [ ] Define the distinct roles of logical/stable IDs, semantic hashes, operation identity, implementation identity, action keys, artifact hashes, and evidence identity.
  - [x] Compare guarded execution keys across 19,200 scope and edit pairs. The exact possible-provider set still allows 1,708 stale reuses when the selection relation changes. A per-state projection preserves all scoped observations in the fixture and permits 3,187 safe reuses. General guards and identity envelopes remain open. [Guarded dispatch identity](research/semantic-representation/RT-05/RT-05-GUARDED-DISPATCH-IDENTITY-2026-11-25.md).
- [ ] Specify the exact semantic payload committed by `OpHash`.
- [ ] Specify `ImpHash` and the identity of a concrete implementation.
- [ ] Define the contract identity and the identity of a class of compatible implementations.
- [ ] Define canonical typed serialization, domain separation, digest encoding, and hash algorithm agility.
  - Compare five native adapters for 181 I64 literals. Ordinary JavaScript Number changes 56 accepted values and collapses 46 distinct pairs before hashing. Exact numeric lexemes, decimal text and fixed-width hexadecimal preserve every input and the complete typed graph root. General canonical formats and other scalar types remain open. [Cross-runtime I64 encoding](research/semantic-representation/RT-05/RT-05-CROSS-RUNTIME-I64-ENCODING-2026-11-25.md)
- [ ] Define hash-relevant versus descriptive, provenance, and evidentiary graph edges.
- [ ] Define cycle handling in hash dependencies.
- [ ] Define which target, ABI, runtime, toolchain, and configuration properties affect implementation identity.
- [ ] Define stable-ID lifecycle, including rename, split, merge, deprecation, and replacement.
- [ ] Define collision handling and migration policy.
- [ ] Specify the invariant that a semantic change affecting an implementation changes its `ImpHash`; determine the exact dependency propagation rules that make this automatic.

**Existing evidence:** `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`, `research/LLMLang-CONCEPT.md`, and the open questions LL-001–LL-008 in `TODO.md`.

**Status:** researched; decision pending on canonical envelopes, dependency boundaries, stable-ID lifecycle, and exact `OpHash`/`ImpHash` payloads. The current project plan explicitly defers locking identity choices until cross-aspect synthesis.

**Research output (2026-11-21)** · Python and Node agree on a typed UTF-8 identity fixture across 127 cases. The corpus distinguishes exact integers, Unicode, map order and identity domains. [Portable identity bytes](research/semantic-representation/RT-05/RT-05-PORTABLE-IDENTITY-BYTES.md)

## 1.3 Contracts and compatible implementations

**Estimated research complexity:** **6/10** — requires formal compatibility/refinement criteria and evidence rules, integrated with identity and call binding.

- [ ] Define contract structure and semantics: preconditions, postconditions, invariants, effects, errors, state transitions, and assumptions.
- [ ] Define the difference between exact contract equality, refinement, substitutability, and behavioral equivalence.
- [ ] Define how one operation can have many implementations and how one implementation can satisfy multiple contracts.
- [ ] Define contract-based analogue discovery separately from call identity and dispatch.
- [ ] Define the evidence required before substituting an implementation for a specific `OpHash`.
- [ ] Define verified adapters for compatible but non-identical contracts.
- [ ] Define what may be inferred automatically and what requires proof or explicit approval.
- [ ] Define evidence binding to exact semantic inputs, assumptions, target profile, and tool versions.

**Existing evidence:** global semantic artifact store research; operation identity and analogue-discovery questions LL-001–LL-003; requirement/contract work in scenarios 15–19.

**Status:** researched; decision pending on formal compatibility, refinement/substitution criteria, and the evidence needed for implementation selection.

**Research output (2026-11-23):** [Contract versus implementation identity recheck](research/language-design/RT-04/RT-04-CONTRACT-VS-IMPLEMENTATION-IDENTITY-RECHECK-2026-11-23.md) reran the synthetic binding fixture on current main. It demonstrates two observably different implementations satisfying the same bounded contract, while caller compilation remains reusable only across a stable separately linked boundary. This supports separating OpHash from ImplHash and using explicit BindingHash when exact execution must be pinned; it does not prove general refinement/substitutability or settle the OpHash envelope.

### 1.3.1 Public interfaces and verified provider binding (RT-05/20; proposed)

- [ ] Specify stable qualified public names, scoped export catalogs, aliases/lineage and exact immutable interface revisions; reconcile OpHash rather than assume a new hash.
- [ ] Define operation/group signatures, public contracts, provider-owned contracts and explicit bindings; distinguish direct and operation calls, external symbol/ABI mappings and runtime dispatch.
- [ ] Generate separate body-correctness and contract-refinement obligations, including state/protocol, effect, authority, ownership, progress and resource guarantees; reject vacuity and unsupported proof claims.
- [ ] Specify reproducible resolution, authorized publication, absence/ambiguity handling, exact evidence, conditional caller proofs and independent verification.
- [ ] Test compatible evolution, breaking revisions, explicit migration, scoped invalidation, package export/index consistency, merge and cache soundness.
- [ ] Implement finite oracle and independent backend/source correspondence benchmarks before selecting normative semantics.

**Bounded refinement pilot (2026-11-24):** The [finite Python/Lean comparison](research/semantic-representation/RT-05/PUBLIC-INTERFACE-FINITE-REFINEMENT-PILOT-2026-11-24.md) checks 15 fixtures and distinguishes a direct public-body judgment from separate body and refinement obligations. The finite case theorem is kernel checked. Source-to-observation correspondence, independent review and the broader profiles remain open.

**Observed scalar provider calls (2026-11-24):** The [typed-SPG observation pilot](research/semantic-representation/RT-05/PUBLIC-INTERFACE-SPG-OBSERVATION-PILOT-2026-11-24.md) compares two fixture source surfaces across 42 observations and checks 21 Python/Lean verdicts. Exact rebinds, stale provider promises, reordered effects and budget exhaustion discriminate the admission methods. Full source-to-contract correspondence and owned-runtime integration remain open.
**Comparison result:** The finite pilot narrows admission-policy choices: signature-only admission is insufficient for the observed effect, error and ownership cases; direct checking against the public contract and separate checking of a provider-owned contract plus refinement each catch fixture violations, but the latter adds a distinct provider-claim obligation and rejects narrower or overbroad claims. Both preserve `unknown` for missing observations. Distinct conforming bodies may still produce different allowed outputs, so admission does not prove substitutability or justify cache reuse. Remaining external dependencies are actual-source lowering into the finite observations, a pinned Lean 4.36.0 fresh rerun, independent checker review, richer protocol/liveness/resource semantics, authorization and package-publication integration, ABI/runtime conformance, and workload-based comparison. No implementation choice is selected.

**Exact receipt applicability after rebinding (2026-11-24):** The [rebind pilot](research/semantic-representation/RT-05/PUBLIC-INTERFACE-VERIFICATION-REBIND-2026-11-24.md) composes the reproduced scalar observations in six evidence submissions. A stable caller claim has a new exact verification key when its provider premise changes. Fresh evidence for only one obligation leaves the aggregate insufficient, and a failed provider promise refutes the aggregate. Production receipt authorization remains open.

**Modular scalar caller theorem (2026-11-24):** The [Lean pilot](research/semantic-representation/RT-05/PUBLIC-INTERFACE-MODULAR-CALLER-2026-11-24.md) proves a caller contract from the abstract provider contract for every integer in a handwritten model. Two provider witnesses discharge the same theorem and three controls fail conformance. The 100 typed-SPG observations check finite source correspondence. General source correspondence, failure and ownership semantics, and authorization remain open.

**Status:** proposed; [public-interface research](research/semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). **Exit gate:** independent review and positive/negative evidence across relevant semantic profiles; no change to accepted single-toolchain compatibility decision.

## 1.4 Core language semantics (RT-03)

**Estimated research complexity:** **7/10** — substantial remaining work on source correspondence, effects, paths, calls, cancellation, resources, and independent review.

- [x] Survey the principal semantic dimensions: value/computation model, evaluation strategy, purity and state, errors and cancellation, determinism, effects and observations, concurrency, termination/resources, and module composition.
- [x] Compare four coherent candidate profiles: pure functional (A), imperative/linear (B), concurrent/actor (C), and effectful functional (D).
- [x] Record major compatibility tensions and cross-aspect implications for types, SPG/identity, dependency analysis, proofs, compiler/IR, runtime, cache, semantic merge, security, and conformance.
- [x] Define an initial shared observable-behavior vocabulary and finite representative corpus for pure results, explicit errors, ordered effects, handler outcomes, and final fixture state; broader language coverage remains open.
- [x] Implement a bounded executable reference-semantics slice for RT-03 candidates A and D over the shared fragment; it is an exploratory interpreter, not a complete semantics or profile selection.
- [x] Implement a second RT-03 evaluator using an independent small-step control/value-stack algorithm and differentially compare complete traces/results/final fixture state against the recursive evaluator, including nine generated two-write cases. This is algorithmic independence, not independent specification review.
- [x] Add an explicit `result_sequence` construct to both RT-03 evaluators: propagate the first Result error unchanged, skip later expressions, return the final success when all items succeed, and reject non-Result items. Differential tests also prove ordinary `sequence` remains strict and unchanged. This is an explicit prototype construct, not implicit call propagation, exceptions, cancellation, or cleanup semantics.
- [x] Add a distinct terminal `cancel` outcome to both RT-03 evaluators. Cancellation discards pending continuations, preserves already completed effects, and is observably distinct from a Result error even with the same reason payload. Differential tests cover cancellation inside nested Result/ordinary sequences. This is a synchronous control-flow slice only; async/concurrent cancellation, call boundaries, resource unwinding, and cleanup remain open.
- [x] Add a structured `with_resource` scope to both RT-03 evaluators. It records acquisition/use/release, releases after success and Result error, unwinds nested scopes LIFO on cancellation, preserves primary plus cleanup failures, and exposes unreleased resources when release fails. Differential tests cover acquisition failure, cleanup after errors/cancellation, nested unwind order, and cleanup failure aggregation. This is a fixture-level structured resource protocol, not an ownership/borrow checker; branching, transfer/return, async behavior, and source-to-scope completeness remain open.
- [x] Add a bounded boolean `if` expression to both RT-03 evaluators. Only the selected branch executes; malformed non-boolean conditions fail closed. Differential scenarios verify that enclosing resource scopes release after branch Result errors and cancellation. This covers concrete execution paths only; symbolic/path-sensitive completeness and independent path-model review remain open.
- [x] Add a third RT-03 structural path model that imports neither evaluator and independently enumerates bounded branch/resource paths. It forks non-literal conditions, respects literal booleans, models cancellation during condition evaluation, LIFO cleanup, cleanup failures, active-resource leftovers, and explicit Result-sequence short-circuiting. Tests compare predicted resource event sequences and final active-resource sets against both evaluators over a finite corpus. This is not a source-level CFG extractor or proof of branch completeness; symbolic path feasibility, source-to-expression completeness, and independent human/formal review remain open. Extend the cross-check with an exhaustive 72-case matrix over branch choice, two nested release success/failure flags, and selected/unselected normal, Result-error, and cancellation expressions. Tighten the analysis vocabulary so unknown conditions require an explicit `unknown_bool` marker, reject literal non-boolean conditions, and traverse nested addition/Result wrappers without missing cancellation paths. Add a fourth, independently derived resource outcome-algebra model that computes exact acquire/release traces, cleanup-error precedence, cancellation cleanup aggregation, and retained resources. Compare its exact outputs against both evaluators and projections against the path model over 144 generated cases (scope depths 1–3, all release flags, normal/Result-error/cancellation outcomes, and each acquisition-failure position). This validates only the bounded fixture protocol; it does not settle ownership/borrowing/transfer semantics.
- [x] Extend the bounded reference corpus with Result propagation, resource acquire/use/release, cleanup, cancellation, branching, an independent structural path model, and an independent resource outcome-algebra model. The latter compares exact traces/results/final resources against both evaluators over a 144-case generated matrix. These are finite executable cross-checks, not a formal proof or external review; broader observations and independent review remain open.
- [ ] Validate RT-03 dependency-map edges through concrete downstream research and experiments.
- [x] Extend the bounded experiment set with typed calls, owned-resource return and cleanup alternatives, recursion/fuel, and actor blocking/progress; record the limits in Scenarios 35–41 and the RT-03/04 shared corpus. These are comparative probes, not selected language rules.
- [x] Execute Scenario 97's six cleanup-error composition candidates over its 12 discriminators and a 13,230-case valid outcome/ownership product; cross-check resource obligations with a separate audit projection. This distinguishes cause carriers while leaving policy choice and source-level completeness open.
- [x] Exhaust all 128 concrete assignments of a seven-condition RT-03 AST fixture and compare them with eight structural paths and both evaluators; record the parser/source-extraction limits in Scenario 98. This is finite AST-path evidence, not source-language completeness.
- [x] Constrain repeated occurrences of the same `unknown_bool` marker to reuse their earlier path choice; compare both concrete assignments against the two feasible paths in Scenario 99. This is marker-identity correlation only, not general symbolic feasibility or source value-identity evidence.
- [x] Exhaust all four assignments in a two-variable Boolean predicate IR for sequential `x` and `x or y` branches; compare the three feasible path vectors and concrete witnesses with both evaluators and resource traces in Scenario 100. This is an exponential finite truth-table model, not a solver or source-CFG completeness result.
- [x] Cross-check Scenario 100 route sets and replayable witnesses with pinned SymPy 1.14.0 DPLL2; compare truth-table and solver medians on a conjunction family through 18 Boolean inputs in Scenario 101. The performance result covers one easy family only; solver trust, hard formulas, a real timeout boundary, and source correspondence remain open.
- [x] Compare exact finite, tri-state, bounded-hybrid, and proof-carrying path-pruning policies in Scenario 102. Eight result-policy fixtures verify that replayable witnesses establish feasibility and that timeout/UNKNOWN/errors or untrusted UNSAT do not prune a possible path; 128 fixed-seed formulas cross-check route sets and witnesses against exhaustive enumeration. This does not exercise a real solver timeout or establish source correspondence.
- [x] Exercise one real solver wall-clock limit through a per-query worker; a hard pigeonhole query is killed/reaped and remains UNKNOWN in Scenario 103. This is one pinned-backend case, not a performance distribution or general worker architecture validation.
- [x] Exhaust a two-state mutable Boolean fixture across name-conflated, unlinked versions, and transition-constrained versions in Scenario 104; name reuse across a write loses both reachable routes, while correct transition constraints recover the concrete route set. Aliasing and source/IR extraction remain open.
- [x] Compare pure, known-toggle, and unknown/may-write call summaries over the exhaustive Boolean state-pair domain in Scenario 105; incomplete summaries must havoc caller-visible state in the bounded model or they can drop reachable routes. Source-derived effect and alias summaries remain open.
- [x] Exhaust the two-field call-site alias domain for exact, disjoint, may-alias, and unknown points-to cases in Scenario 106; field-sensitive precise aliases preserve routes while incomplete alias sets broaden them conservatively. General source-derived points-to analysis remains open; Scenario 107 covers only a tiny AST subset.
- [x] Derive a toggle summary and branch-joined call alias sets from a bounded Python-shaped AST subset in Scenario 107; eight cases preserve all concrete routes, while non-relational joins can add infeasible routes. General parsing, source/CFG completeness, and path-sensitive alias analysis remain open.
- [x] Compare joined may-alias analysis with finite path-sensitive summary execution in Scenario 108; enumerating 16 fixture valuations removes two infeasible routes from a correlated-alias case and preserves all routes for independent alias choices. This is a bounded exact enumerator, not a scalable symbolic analysis.
- [ ] Exercise broader resource limits and difficult formula families; authenticate or check negative-result evidence before solver-based path pruning; bind immutable predicate versions and source CFG extraction to route constraints.
  - A restricted source-derived CFG reproduces 128 CPython executions over effectful guards, nested cleanup, pending handle return and error causes. Executions cover all 84 source call spans in the generated corpus. LLMLang source typing, asynchronous unwinding and general source correspondence remain open. [Source cleanup CFG](research/language-design/RT-03/RT-03-SOURCE-CLEANUP-CFG-2026-11-25.md)
- [ ] Normalize the surviving vectors for whole-specification synthesis; do not select a profile or transfer it into `draft/` by implication.

**Evidence:** [RT-03 — Core Language Semantics](research/language-design/RT-03/CORE-LANGUAGE-SEMANTICS.md).

**Status:** researched at the candidate-survey level; partially validated only as a map of options and trade-offs. No semantic profile, evaluation strategy, effect model, or complete observation model has been accepted. The existing QF_LIA/Lean/Logos work covers a narrow relational fragment and is not a complete language semantics.

**Next work:** integrate the typed-call, owned-result return, cleanup-disposition/composition, bounded-recursion/fuel, actor-progress, and AST-path probes into a grammar-bound source-to-model account. Compare varied satisfiable/unsatisfiable formula families and timeout/unknown behavior; model mutation/version boundaries; bind a parser/IR extractor to branch-node coverage; make effect order/payload observable in cross-profile summaries; and obtain independent human/formal review. Cover call-boundary unwinding, ownership transfer/return, asynchronous cancellation, cleanup divergence, and termination-budget exhaustion before expanding the expression fragment. Keep profile A–D alternatives open.

### 1.4.1 Type, effect, ownership, and capability alternatives (RT-04)

**Estimated research complexity:** **8/10** — several mutually constraining systems must form one coherent static and runtime model.

- [x] Survey type identity/compatibility, refinement and typestate, inference, effect representations/handlers, ownership/borrowing/lifetimes, capabilities, concurrency/memory models, and error/resource outcomes.
- [x] Cross-map candidate RT-04 mechanisms against RT-03 profiles A–D without selecting a profile.
- [x] Record candidate hash-boundary questions for operation contracts, implementations, conformance classes, and verification evidence.
- [x] Implement the first executable RT-04 declaration-level comparison for refinement, transitive effect summaries, capabilities, and affine resource consumption; add 12 focused unit tests and record the limits. This is one exploratory checker model, not two complete reference semantics.
- [x] Extend Profile B with a finite CFG resource-flow experiment and tests for branch-consistent joins, inconsistent joins, repeated consumption, loops, and malformed CFG references. This validates only the supplied CFG model, not source-to-CFG completeness.
- [x] Add direct/transitive effect-bound validation and fixtures requiring UNKNOWN for missing call-graph completeness or unresolved callees; retain definite rejection when a known effect already exceeds the bound. The completeness list is fixture-level asserted metadata, not authenticated source-analysis evidence.
- [x] Extend the executable corpus with typed call-site arity, argument-type, and expected-result checks plus a structural `Result<Ok, Err>` type-constructor experiment. Typed call-site targets must also occur in the coarse call graph; missing callee signatures yield UNKNOWN. This remains a declaration-level experiment, not source type inference or a selected ADT semantics.
- [x] Add a Profile B scoped-capability grant experiment: hierarchical POSIX path scopes, parent-child attenuation, explicit call-site grant delegation, recipient acceptance, and ancestor revocation propagation. Missing delegation yields UNKNOWN; malformed or over-broad grants fail closed. This is fixture-level static checking, not runtime token authentication or revocation.
- [ ] Replace fixture-level call-graph completeness assertions with source/snapshot-bound evidence; extend resource analysis with symbolic path conditions, transfer/return, and cleanup; define runtime capability issuer/trust and concurrent revocation semantics.
  - SQLite WAL checks grant ancestry across concurrent revoke, reissue and effect publication in 45 process-pair runs. Leaf-only validation admits two stale effects, and a global epoch refuses one unaffected operation. An exact-chain writer transaction and checked snapshot retry agree in this local effect scope. [Concurrent grant revocation](research/language-design/RT-04/RT-04-CONCURRENT-GRANT-REVOCATION-2026-11-25.md)
  - The Cortex-M3 ISR fixture derives direct call and tail-branch coverage from the exact linked artifact and pins primitive effects to body bytes. It preserves `UNKNOWN` for indirect targets and stale effects. Source-level completeness remains open. [Transitive ISR effects](research/runtime-and-systems/RT-37/RT-37-CORTEX-M3-TRANSITIVE-ISR-EFFECTS-2026-11-24.md).
- [x] Add a first shared observable-trace fixture oracle for RT-03 profiles A and D and cross-check it against RT-04 checker vectors A and B; cover pure return, declared filesystem read, ordered writes, and undeclared effects. This is a finite compatibility oracle, not a second complete reference semantics. See [cross-profile trace report](research/language-design/RT-04/RT-04-RT-03-CROSS-PROFILE-TRACES.md).
- [x] Implement a second independently derived resource outcome-algebra model and compare its exact resource traces/results/final maps against both RT-03 evaluators, plus the structural path model's resource projections, over 144 generated cases. This is independent corroboration only for the bounded resource-scope outcome rules; it is not a second complete cross-aspect semantics model.
- [x] Derive ownership obligations at a named call from a bounded callee AST and declared close contracts. Across 4,096 concrete inputs, the inferred result shapes match the disposition model. The checker detects dropped obligations and caller matches that become incomplete after a close contract changes. [Scenario 119](research/language-design/RT-04/RESEARCH-SCENARIO-119-OWNED-RESULT-MATCHING.md)
- [x] Probe errors with retention, errors with consumption, and successful deferred destruction on a versioned SQLite library. An outstanding statement changes the valid recovery path. [Scenario 120](research/language-design/RT-04/RESEARCH-SCENARIO-120-SQLITE-CLEANUP-DEPENDENCIES.md)
- [x] Compare a close precondition, busy recovery, and deferred destruction on 510 bounded plans. SQLite agrees with all 356 admitted traces. Local recovery and forwarding differ when an outside owner retains a dependent statement. [Scenario 121](research/language-design/RT-04/RESEARCH-SCENARIO-121-SQLITE-LOCAL-CLOSE-RECOVERY.md)
- [x] Derive close preconditions from a source fragment and compare complete source proof with snapshot freshness over 4,116 executions. A native SQLite probe confirms that an intervening prepare invalidates an empty observation. [Scenario 122](research/language-design/RT-04/RESEARCH-SCENARIO-122-CLOSE-EVIDENCE-FRESHNESS.md)
- [x] Compare four close policies on a shared workload with local cleanup, an outside owner, and a foreign call. SQLite agrees at 114 call boundaries. Guard refusal and busy retain the connection, while deferred close can return before destruction. [Scenario 123](research/language-design/RT-04/RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md)
- [x] Compare version validation and guarded close across 11 schedules on serialized SQLite. A shared lock excludes an intervening prepare when the producer uses that lock. A producer through an alias with a different lock can still make close busy. [Scenario 124](research/language-design/RT-04/RESEARCH-SCENARIO-124-CLOSE-SYNCHRONIZATION.md)
- [x] Check reentry under a recursive guard and compare statement enumeration against distinct dependent kinds. SQLite matches 12 callback cases and 8 close calls. A source backup can make close busy with an empty statement list. [Scenario 125](research/language-design/RT-04/RESEARCH-SCENARIO-125-CLOSE-REENTRY-AND-COVERAGE.md)
- [x] Compare identity-aware roles and reservation policies for an FFI operation with two resources. Across 432 plans, acquisition in role order admits deadlock, while identity order and all-or-none reservation avoid it in the fixture. SQLite checks source sharing, rejection, and retry after failed initialization. [Scenario 126](research/compiler-and-translation/RT-13/RESEARCH-SCENARIO-126-MULTI-RESOURCE-FFI-ROLES.md)
- [x] Derive correlated resource identities and a conditional release across two FFI calls. An independent oracle checks 147,456 inputs. Complete routes certify 232 programs, versus 214 with independent call pairs and 156 with separate role sets. [Scenario 127](research/language-design/RT-04/RESEARCH-SCENARIO-127-SOURCE-ROLE-CORRELATION.md)
- [x] Compare outcome types after admitted multi-resource FFI calls. Release on every error admits 288 conflicts in 1,728 inputs. Bounded reconciliation obligations preserve compatible shared roles. SQLite confirms that `backup_finish` consumes the backup when reporting a prior step error. [Scenario 128](research/compiler-and-translation/RT-13/RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md)
- [x] Compare cancellation evidence keyed to an invocation with an acknowledgment policy and a role-pair key. Each weaker policy admits 96 conflicts in 5,376 inputs. A scheduled worker reproduces acknowledgment before completion. [Scenario 129](research/runtime-and-systems/RT-10/RESEARCH-SCENARIO-129-CANCELLATION-AND-INVOCATION-EVIDENCE.md)
- [x] Recover terminal evidence after process interruption on a durable journal. Ten SQLite traces distinguish an atomic effect and result from two commits. A committed generation survives fresh allocator processes and fences delayed old results. [Scenario 130](research/runtime-and-systems/RT-10/RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md)
- [x] Run the COR-13 ownership and cleanup workload through two execution models. They agree on 5,184 inputs including aliased later calls, and the observed result shapes match static inference. [Scenario 131](research/language-design/RT-04/RESEARCH-SCENARIO-131-SHARED-OWNED-RESULT-WORKLOAD.md)
- [x] Compare typed forwarding and recovery at the COR-13 caller. The model and oracle agree on 20,736 inputs per fixture. Recovery enables 1,380 additional starts, with release effects and diagnostics recorded separately. [Scenario 132](research/language-design/RT-04/RESEARCH-SCENARIO-132-TYPED-CALLER-RECOVERY.md)
- [x] Run the checked COR-13 caller through generated Rust under both transfer rules. Two optimization levels match the reference on 62,976 traces each, including a changed alias binding. [Scenario 133](research/compiler-and-translation/RT-13/RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md)
- [ ] Compare reconciliation across independent providers, concurrent delivery, and restored snapshots. Validate guard coverage across alias escape, reentry, and wider effects.
  - The Linux descriptor-transfer comparison finds false admission after successful send and sender close, before any receive receipt. A replay that tracks queued and received references matches 696 lock observations. General source binding, aliased endpoints and authenticated release remain open. [Queued foreign ownership](research/language-design/RT-04/RT-04-QUEUED-FOREIGN-OWNERSHIP-2026-11-25.md)
- [ ] Independently review the comparative report and validate RT-03↔RT-04 dependency assumptions.
- [ ] Reconcile RT-04 semantic distinctions with RT-05 identity and RT-07 proof boundaries before selecting hash-bearing fields.

**Evidence:** [RT-04 alternatives report](research/language-design/RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md); [Prototype 01 implementation and tests](research/PROTOTYPES/RT-04-01/README.md); [Prototype 01 results](research/language-design/RT-04/RT-04-PROTOTYPE-01-RESULTS.md); [scenario matrix](research/language-design/RT-04/RT-04-PROTOTYPE-01-SCENARIOS.md).

**Status:** comparative survey and bounded prototypes are in place, but no type/effect/ownership/capability architecture is selected. The corpus now includes typed calls, owned-resource returns, cleanup dispositions/composition, effect-bound and capability checks, shared RT-03/RT-04 trace fixtures, and independent resource outcome/obligation projections. New studies include [COR-13](research/language-design/RT-04/RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md), [Scenario 35](research/language-design/RT-04/RESEARCH-SCENARIO-35-RESOURCE-RETURN-AND-CLEANUP.md), and [Scenario 97](research/language-design/RT-04/RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md). The call-graph completeness metadata remains fixture asserted rather than source/snapshot-bound; source-to-CFG and path-condition completeness, ordered effect summaries, row unification/handler coverage, trusted capability evidence, and concurrent revocation remain open. Independent review and reconciliation with RT-05 identity and RT-07 proof boundaries are required before hash-boundary or architecture decisions.

**Research output (2026-11-21)** · Valuation-indexed ordered effect summaries match 128 executions. Combining independent callee summaries introduces 28 impossible traces across 16 programs. [Ordered call effects](research/language-design/RT-04/RT-04-ORDERED-CALL-EFFECT-SUMMARIES.md)

**Owned-return contract discriminator (2026-11-24):** The [RT-04 native comparison](research/language-design/RT-04/RT-04-OWNED-PROVIDER-CONTRACT-REPLAY-2026-11-24.md) reproduces 256 traces and separates early and staged transfer in 24 failed-cleanup pairs. An error flag alone loses the ownership and subsequent-admission distinctions. General source, foreign-resource and public-binding integration remain open.

**Foreign cleanup and descriptor aliases (2026-11-24):** The [Linux FFI probe](research/language-design/RT-04/RT-04-LINUX-OWNED-CLEANUP-2026-11-24.md) checks 64 native traces with a real `fclose` error and an independently opened lock contender. A surviving duplicate can preserve the underlying lock after staged cleanup closes the original descriptor. General source correspondence, cross-platform behavior and concurrent alias reconciliation remain open.

## 1.5 Prior-art study for semantic representation and identity

- [x] Compare Unison's content-addressed code identity and codebase model.
- [x] Compare Git's object model and DAG with semantic object identity.
- [x] Compare LLVM IR identity and canonicalization limits.
- [x] Compare content-addressed artifact stores and package registries.
- [x] Identify which ideas can be reused without making a target IR or source syntax the semantic authority.

**Research output (2026-11-23):** [RT-15 prior-art identity and storage comparison](research/toolchain-and-collaboration/RT-15/RT-15-PRIOR-ART-IDENTITY-AND-STORAGE-COMPARISON-2026-11-23.md) reviews primary sources for Unison, Git, LLVM, Nix, Bazel, OCI, and Maven. Candidate synthesis keeps semantic objects, Git history, ActionKeys, artifact bytes, package references, and authenticated evidence as distinct layers. This closes the comparative survey only; the semantic object model, canonical identity payloads, dependency closure, compatibility rules, and trust policy remain open under §§1.1–1.3, 3.1–3.3, and 7.4.

**Exit criteria:** a reviewed semantic object model; explicit identity table and canonicalization proposal; contract compatibility vocabulary and evidence model; remaining foundational decisions registered in `TODO.md`.

---

# Stage 2 — Formal semantics and verification foundation

**RT-36 — Formal verification assumptions, trust boundaries and conditional proof management (P0; research proposed).** [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](research/formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md); [Issue #436](https://github.com/aivibeflow/LLMLang/issues/436). Exit: typed premise and authorization model, status/closure semantics, independently checked conditional/discharge pilot, exact binding and revocation tests, adversarial benchmark, reproducible evidence and independent review. Keep local theorem checks, system closure and policy admission distinct.

**RT-33 — Proof backend selection and verification orchestration (P0; comparative experiments in progress).** Investigate a backend-independent Contract IR / proof-obligation pipeline that classifies obligations and selects or combines Lean, SMT, TLA+, or other engines using explicit capability profiles. Define conservative abstention, translation correspondence, trust boundaries, cross-backend evidence composition, result states, provenance, and incremental invalidation. Evaluate using the contract formalization corpus plus state-transition/concurrency cases. This generalizes RT-32; it does not make Lean the universal verifier or select any backend as normative. See [RT-33](research/formal-verification/RT-33/RT-33-PROOF-BACKEND-SELECTION-AND-ORCHESTRATION.md) and [issue #390](https://github.com/aivibeflow/LLMLang/issues/390). The [kernel-checked symbolic correspondence](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/SYMBOLIC-TRANSITION-CORRESPONDENCE.md) covers every register-state boundary in the Lean transition model for arbitrary integer inputs. The [Lean-owned SMT query experiment](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/SYMBOLIC-SMT-QUERY.md) emitted the proved typed mismatch predicate as SMT-LIB for three controls and replayed the solver model. Source representation, general SMT-LIB denotation, and checked certificates remain open.

The [RT-33 bounded Lean comparison](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/LEAN-TRANSITION-STATE.md) checked all 798 finite state claims against cvc5 on matching fixture scope. Lean checked 712 equalities and 86 inequalities. TLC, translation correspondence outside the sampled cases and evidence composition remain open.

The [RT-33 evidence composition experiment](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/EVIDENCE-COMPOSITION.md) admitted 2,394 pinned receipts for 798 exact finite obligations. Its controls reject stale premise closure and weakened observation scope, and preserve conflicts and conditional results. Production artifact trust and persistent dependency invalidation remain open under [#397](https://github.com/aivibeflow/LLMLang/issues/397).

**RT-33 benchmark expansion:** establish a multi-label Proof Obligation Benchmark that separates obligation forms from semantic domains, covers boundary/negative/conditional/composed cases, and evaluates obligation generation, backend planning, translation correspondence, verification, evidence aggregation, and abstention independently. Start with a small representative seed set; the up-to-80-case matrix is a coverage target, not a fixed quota. See [benchmark](research/formal-verification/RT-33/PROOF-OBLIGATION-BENCHMARK.md) and [case template](research/formal-verification/RT-33/PROOF-OBLIGATION-BENCHMARK-TEMPLATE.md). Proposed [executable seed corpus](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/README.md) and follow-up experiments are tracked under LL-029.

**RT-33 research output:** the [cvc5 state experiment](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/SMT-TRANSITION-STATE.md) recorded 86 replayed counterexamples across 798 fixed transition cases. The [three-backend comparison](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/TLC-TRANSITION-STATE.md) also checked 2,778 distinct trace-prefix states in TLC and reproduced its counterexample. A final-state-only control missed a transient mismatch. General translation correspondence, symbolic inputs, effects, temporal obligations, and SMT certificates remain open under [#395](https://github.com/aivibeflow/LLMLang/issues/395).

The [symbolic CPC experiment](research/formal-verification/PROOF-OBLIGATION-BENCHMARK/SYMBOLIC-CPC-CERTIFICATES.md) checked two cvc5 certificates against their exact archived source assertions in Logos. The final-boundary certificate was rejected for the all-boundary query. Complete checker soundness verification and general correspondence across the text boundary remain open.



**Order:** after the semantic objects and contract boundaries from Stage 1 are stable enough to formalize.  
**Purpose:** make language meaning precise and ensure that verification claims are independently checkable.

## 2.0 Automatic complexity inference and resource verification (RT-34)

**Priority:** P0 foundations/pilot, P1 advanced domains. **Status:** Research brief and benchmark plan established. The nested-loop pilot checks a scoped cost model; general inference and other benchmark cases remain open. [RT-34](research/formal-verification/RT-34/RT-34-AUTOMATIC-COMPLEXITY-INFERENCE.md) · [Benchmark plan](research/formal-verification/RT-34/RT-34-COMPLEXITY-BENCHMARK.md) · [Issue #412](https://github.com/aivibeflow/LLMLang/issues/412).

- [ ] Define cost profiles, size domains, resource Contract IR and proof/evidence identity (CX-01–03).
  - A scoped affine call proof binds the selected provider, event weights, size domain and exact budget. Reusing a functional contract certifies five false budgets in 11 snapshots, while exact rebinding resolves seven and leaves four unknown. General resource Contract IR and authenticated provider evidence remain open. [Call-cost proof binding](research/formal-verification/RT-34/RT-34-CALL-COST-BINDING-2026-11-25.md)
- [ ] Pilot loop, recursion and call analysis, source correspondence and independent checking (CX-04–07).
  - The nested-loop pilot proves exact abstract event counts and sound dependent and rectangular envelopes over natural sizes. It checks 536 generated-C observations and detects guard omission and added work. General extraction, recursion, foreign cost and independent adjudication remain open. [Nested-loop cost](research/formal-verification/RT-34/RT-34-NESTED-LOOP-COST-2026-11-25.md)
- [ ] Independently adjudicate benchmark cases and compare inference vectors (CX-19).
- [ ] Study problem lower bounds, optimality, amortization, memory, parallel/probabilistic and multivariate complexity (CX-08–14).
- [ ] Investigate resource-preserving lowering, synthesis, incremental invalidation, regression gates and external calls (CX-15–18, CX-20).

Dependencies: RT-03/04 semantics/types, RT-07/08 evidence, RT-05/11 identities/cache, RT-26 resource enforcement, RT-32/33 proof generation and orchestration. Exit: reproducible scoped experiment, checked cost proofs and source correspondence, explicit assumptions and abstention, comparative evidence and no normative selection without review.

The [binary-search cost pilot](research/formal-verification/RT-34/RT-34-BINARY-SEARCH-PROBE-BOUNDS-2026-11-25.md) proves the exact positive-size probe bound for the halving model and checks 13,354 sorted input pairs per native profile. A singleton stall falsifies a retained-midpoint update. Membership correctness and arbitrary compiler/source correspondence remain separate.

The [balanced recursion pilot](research/formal-verification/RT-34/RT-34-MERGE-RECURRENCE-2026-11-25.md) checks tight abstract comparison recurrences and exact writes at power-of-two sizes. The native corpus distinguishes input-dependent comparisons, an incorrect equal-floor recurrence and a split without progress. General recursion extraction and independent review remain open.

## 2.1 Formal semantics of the language

**Estimated research complexity:** **8/10** — requires a precise executable semantics and correspondence with source programs.

- [ ] Compare operational, denotational, and axiomatic semantics for the initial LLMLang core.
- [ ] Define an executable reference semantics for a deliberately small subset.
- [ ] Define observable behavior: return values, errors, state changes, I/O, resource behavior, concurrency, and declared effects.
- [ ] Define semantic equivalence and refinement.
- [ ] Define evaluation order, effects, error propagation, and state transitions.
- [ ] Define semantics of contracts and their composition.
- [ ] Define semantics-preserving transformations and compiler correctness boundaries.- [ ] Define assumptions and environmental boundaries explicitly.

**Existing evidence:** `research/LLMLang-FORMAL-VERIFICATION.md`, `research/LLMLang-CONCEPT.md`, typed requirement IR and formal dependency scenarios 25–33.

**Status:** partially researched; a complete language semantics is not yet established.

## 2.2 Proof architecture and proof boundary

**Estimated research complexity:** **8/10** — includes trusted computing base, assumptions, evidence scope, and compositional proof boundaries.

- [ ] Determine which claims belong in Lean, SMT, specialized checkers, testing, or trusted runtime code.
- [ ] Define the trusted computing base for each proof claim.
- [ ] Define proof object formats, proof checking, provenance, and evidence reuse.
- [ ] Separate solver answers from independently checked proofs.
- [ ] Define exact binding between source-level assumptions, typed IR, serialized queries, and proof obligations.
- [ ] Define fail-closed behavior for unsupported or ambiguous constructs.
- [ ] Define how proof status is represented: candidate, unknown, checked, rejected, or proven.
- [ ] Define the relationship between proof validity and specification adequacy; a proof cannot establish that the specification captures user intent.

**Existing evidence:** scenarios 28–33, prototype 29, Lean CPC parser-state binding prototype, Logos integration, and `research/LLMLang-FORMAL-VERIFICATION.md`.

**Status** — Partially validated. The pinned Lean 4.34.0 and Logos CI run validated the parser-state bridge, typed renderer and JSON decoder. Scenario 34 proves source-to-query preservation in the independent Lean IR for the finite Int/Bool fragment, including paired command executions. The connection from the proved formula to serialized queries and CPC assumptions remains open. [CI run 44175854422](https://github.com/aivibeflow/LLMLang/actions/runs/44175854422) · [Scenario 34](research/formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md)

## 2.3 Lean, Logos, SMT, and solver integration

**Estimated research complexity:** **8/10** — solver behavior, proof evidence, timeout/UNKNOWN handling, and source binding must be validated.

- [x] Complete explicit Lean build and test validation for the pinned Lean 4.34.0 environment and pinned Logos revision; CI run [44175854422](https://github.com/aivibeflow/LLMLang/actions/runs/44175854422) passed all build and test steps.
- [x] Implement the CPC parser-state bridge and exact symbol identity binding; obtain a successful pinned CI build and adversarial validation (CI run 44175854422 passed the existing parser-state tests).
- [x] Implement construction of expected `Eo.Term` values from the canonical typed Relational Query IR; the pinned CI renderer and AST-equivalence tests pass. Full end-to-end validation against source-derived CPC assumptions remains open.
- [x] Implement strict versioned JSON decoding and rejection of malformed or unsupported input; the full pinned CI test step, including adversarial decoder tests, passes.
- [x] Kernel-check expression-level source-to-query preservation for the typed Int/Bool expression fragment. [CI run 44175854422](https://github.com/aivibeflow/LLMLang/actions/runs/44175854422)
- [x] Verify the CPC parser-state bridge and exact assumption-list binding adversarially for the version-2 relational-query envelope; pinned Lean CI run [44185102839](https://github.com/aivibeflow/LLMLang/actions/runs/44185102839) passed parser-state binding and factor-pair fixtures. This binds the CPC assumptions to the decoded query; it does not prove the decoded query is semantically derived from source.
- [x] Prove that the canonical Lean formula is satisfiable exactly when admissible paired executions differ at the selected input and in the return or selected state. Bind every formula symbol to its source declaration and sort (SCW-26–28). [Scenario 34](research/formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#75-paired-execution-and-relational-query)
- [x] Prove that lowering the formula from each admitted program, contract and factor produces a term in the strict QF_LIA profile (SCW-29). [Scenario 34](research/formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#76-qf_lia-admissibility-and-external-wirechecker-boundary)
- [x] Prove that every symbol in the lowered solver term has exactly one declaration of the right sort and resolves to its original source binding (SCW-30). [Scenario 34](research/formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#76-qf_lia-admissibility-and-external-wirechecker-boundary)
- [x] Prove that an accepted version-2 JSON envelope carries the exact Lean-generated declarations and typed terms, and check Int and Bool fixtures (SCW-31). [Typed JSON correspondence](research/formal-verification/RT-07/RT-07-TYPED-JSON-CORRESPONDENCE.md)
- [x] Carry the supported Lean formula and exact declarations through Logos rendering and CPC assumptions, and document the checked boundary (SCW-32–34). [Scenario 34](research/formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#76-qf_lia-admissibility-and-external-wirechecker-boundary)
- [ ] Keep QF_LIA as a conservative profile; reject unsupported strings, nonlinear arithmetic, and constructs outside the profile.
- [ ] Test SAT/UNSAT/UNKNOWN handling and solver protocol failures.
- [ ] Record what is checked by Lean, what is trusted in Logos, and what remains outside the proof boundary.

**SCW-32 sort and finite denotation evidence:** [Logos sort preservation](research/formal-verification/RT-07/RT-07-LOGOS-RENDERED-SORTS.md) proves the pinned Logos type function agrees with every successfully rendered typed query term. The [finite denotation comparison](research/formal-verification/RT-07/RT-07-LOGOS-SCALAR-DENOTATION-2026-11-24.md) agrees on 1,536 expression evaluations and both assumptions for each of 96 concrete pairs through the actual Logos SMT translation. Same-sort controls distinguish type checking from interpretation. General interpretation preservation remains open.

**SCW-32 scalar preservation:** The [kernel theorem](research/formal-verification/RT-07/RT-07-LOGOS-SCALAR-PRESERVATION-2026-11-24.md) proves preservation for arbitrary typed source expressions under related constant valuations through the actual Logos SMT translation into the restricted evaluator. Establishing the relation for arbitrary wire/parser program bindings and connecting the evaluator to upstream model semantics remain open.

**SCW-32 exact constant valuations:** The [valuation proof](research/formal-verification/RT-07/RT-07-LOGOS-VALUATION-BINDING-2026-11-24.md) proves that successful table construction realizes the typed values of every resolved parser constant. The same check rejects identity aliases before evaluation. Relating arbitrary paired program inputs to the wire valuation and connecting the restricted evaluator to upstream semantics remain open.

**SCW-32–33 program assumption meaning:** The [program bridge theorem](research/formal-verification/RT-07/RT-07-LOGOS-PROGRAM-ASSUMPTIONS-2026-11-24.md) relates the two exact parsed assumptions at any successfully constructed wire valuation to dependence in the corresponding pair of source executions. Existing example envelopes retain their exact bytes. The [concrete-pair lifting theorem](research/formal-verification/RT-07/RT-07-LOGOS-CONCRETE-PAIR-LIFTING-2026-11-24.md) proves the reverse direction after a successful validation of the parser table shape.

**SCW-32/34 upstream scalar model semantics:** The [upstream model proof](research/formal-verification/RT-07/RT-07-LOGOS-UPSTREAM-SCALAR-MODEL-2026-11-24.md) proves agreement with the pinned `Cpc.SmtModel` for every successfully evaluated restricted term when constant valuations agree. The two verification toolchains compile the same evaluator source. Existence of a well-formed upstream model for each accepted valuation, compatibility of proof artifacts and complete checker soundness composition remain open.

**SCW-34 single-kernel program composition:** The [Lean 4.34 composition](research/formal-verification/RT-07/RT-07-LOGOS-SINGLE-KERNEL-PROGRAM-2026-11-24.md) compiles the LLMLang source theorem and upstream model proof in the same verification kernel, then proves the meaning of the ordered CPC assumptions for related models. The usual Lean 4.36 path still passes. Concrete-pair lifting and application of complete checker soundness remain open.

**SCW-34 well-formed model extension:** The [model extension proof](research/formal-verification/RT-07/RT-07-LOGOS-MODEL-EXTENSION-2026-11-24.md) extends each scalar valuation by overriding exact constant names and sorts. The overlay preserves a provided well-formed model with standard Lean axioms. Unconditional existence uses one additional upstream `native_decide` axiom. The trust disposition and complete checker composition remain open.

**SCW-34 kernel model witness:** The [isolated Logos rebuild](research/formal-verification/RT-07/RT-07-LOGOS-KERNEL-MODEL-WITNESS-2026-11-24.md) replaces the empty-language canonicity proof with `rfl` and checks unconditional model existence using standard Lean axioms. The pinned dependency retains the published axiom until a dependency decision. The completed verdict proof audit below establishes its wider native computation boundary.

**SCW-34 conditional source refutation:** The [composition theorem](research/formal-verification/RT-07/RT-07-LOGOS-SOURCE-REFUTATION-COMPOSITION-2026-11-24.md) proves equal observations for any admitted source pair with distinct selected inputs from the exact runtime certificate, a validated binding table, a well-formed base model and the typed Logos verdict soundness premise. The full upstream proof is supplied in the following audit. The native computation trust decision remains open.

**SCW-34 pinned verdict proof audit:** The [complete rule build and source composition](research/formal-verification/RT-07/RT-07-LOGOS-VERDICT-PROOF-2026-11-25.md) checks the conditional source claim with the actual upstream verdict theorem in Lean 4.34. The four verdict and composed claims have the same 2,118 native computation axioms. Explicit acceptance of that boundary or an admissible replacement remains external.

**Existing evidence:** scenarios 29–33; `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/`; Lean QF_LIA profile/admissibility modules and focused tests; CI workflow.

**Restricted affine proof route:** The [Lean certificate checker](research/formal-verification/RT-07/RT-07-RESTRICTED-AFFINE-CERTIFICATES-2026-11-25.md) refutes two exact archived QF_LIA assertions and a weighted control using standard Lean axioms. It checks coverage of all branches and abstains on a satisfiable control and an integer-only contradiction. General SMT-LIB correspondence, stronger proof rules and routing policy remain open.

**Direct CPC evidence (2026-11-21)** · A source-derived flat CPC refutation passes the assumption and verdict gates. A refutation of a substituted query passes standalone Logos and fails source binding. [Source-bound CPC refutation](research/formal-verification/RT-07/RT-07-SOURCE-BOUND-CPC-REFUTATION.md)

**CPC alias evidence (2026-11-21)** · A closed proof profile can admit disjoint nullary abbreviations while checking actual top-level constant declarations separately. [CPC alias binding](research/formal-verification/RT-07/RT-07-CPC-NULLARY-ALIAS-BINDING.md)

**SCW-33 acceptance evidence:** [Exact CPC binding and verdict](research/formal-verification/RT-07/RT-07-BOUND-CPC-VERDICT.md) ties every accepted source-wire query to the ordinary parser's ordered assumptions and exact command stream used by Logos. Interpretation of rendered terms and the wider checker trust boundary remain open.

**Status** — Partially validated. Pinned CI passed the version-2 CPC parser-state and factor-pair tests in run 44185102839. SCW-06–31 connect the checked Int/Bool AST to the typed JSON query. The source-wire checker binds parsed assumptions and commands to the exact query at runtime. The supported source implication composes with the full pinned upstream verdict proof relative to its audited axioms. Wider source correspondence, certificate profile admission and upstream trust disposition remain open. [Scenario 34 proof boundary](research/formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#76-qf_lia-admissibility-and-external-wirechecker-boundary)

**SCW-34 trust boundary:** [Logos runtime verdicts and soundness](research/formal-verification/RT-07/RT-07-LOGOS-CHECKER-TRUST-BOUNDARY.md) records the kernel-checked runtime conditions under Lean 4.36 and the separate upstream verification build under Lean 4.34. The [full rule build and verdict proof audit](research/formal-verification/RT-07/RT-07-LOGOS-VERDICT-PROOF-2026-11-25.md) records the completed single-kernel proof path and the native computation assumptions still required.

## 2.4 Verified SPG-to-Lean pipeline (RT-32)

**Estimated research complexity:** **9/10** — requires a sound connection between authoritative LLMLang semantics, typed SPG, generated Lean terms, proof obligations, and independently checked evidence.

- [ ] Compare shallow, deep, and hybrid Lean embeddings; identify which claims each can establish and where semantic correspondence is required.
- [ ] Define the admitted SPG/verification-IR subset and deterministic mapping from versioned LLMLang functions, contracts, invariants, calls, and effects to Lean definitions and theorem statements.
  - Lean kernel-checks all 128 observations of eight source-derived RT-03 cleanup graphs, a separate resource completion property, and four mutation witnesses. The claims depend on the pinned source extraction and CPython oracle; general LLMLang SPG/source correspondence remains open. [Source cleanup kernel replay](research/formal-verification/RT-32/RT-32-SOURCE-CLEANUP-KERNEL-2026-11-25.md)
  - Lean proves the equivalence between admitted signed I64 values and ordered eight-octet words. All 181 exact native hexadecimal archive observations match the Lean model. JSON admission and production SPG extraction remain open. [Signed I64 byte proof](research/formal-verification/RT-32/RT-32-SIGNED-I64-BYTE-KERNEL-2026-11-25.md)
  - Lean proves that bijective mutable location renaming preserves observations and relates the final heaps for arbitrary admitted action lists. All 184 native class equations match across 4,416 selected vectors. General importer and source correspondence remain open. [Mutable renaming kernel](research/formal-verification/RT-32/RT-32-MUTABLE-RENAMING-KERNEL-2026-11-25.md)
  - Lean proves that six fixed observation sequences determine the exact two-receiver context and all admitted traces. Check 108 exact archive equations and 2,592 fresh C/Rust probe vectors, with nine observed signature collapses after omitting the sixth probe. Wider method and source correspondence remain open. [Bound-method observation completeness](research/formal-verification/RT-32/RT-32-BOUND-METHOD-OBSERVATION-COMPLETENESS-2026-11-25.md)
- [ ] Generate proof obligations from contracts and control flow: preconditions, postconditions, branch conditions, loop invariant initialization/preservation/exit, recursive obligations, and termination measures.
  - [x] Generate and kernel-check initialization, preservation, exit and termination for two stride variants of a typed natural-number countdown with an ordered trace. Six controls distinguish missing invariants, early exit, failed decrease, value and event-order violations. General SPG source binding and broader control flow remain open. [Countdown loop obligations](research/formal-verification/RT-32/RT-32-COUNTDOWN-LOOP-OBLIGATIONS-2026-11-24.md).
  - [x] Generate mutual termination measures and a checked parity recurrence from two exact SPG group encodings. Both members agree with Lean on 64 observations across the encodings. Zero decrease and a changed base result fail separate checks. Signed inputs outside the natural-number proof and general source correspondence remain open. [Generated mutual termination](research/formal-verification/RT-32/RT-32-GENERATED-MUTUAL-TERMINATION-2026-11-24.md).
  - [x] Generate and check natural-number termination, ordered traces and length for two mutually recursive SPG members. Both group encodings agree with Lean and a separate oracle on 80 observations. Event reorder, failed decrease and changed finite contract fail at distinct gates. General recursive admission and source correspondence remain open. [Mutual recursive effects](research/formal-verification/RT-32/RT-32-MUTUAL-RECURSIVE-EFFECTS-2026-11-24.md).
- [ ] Define compositional caller proofs from version-bound callee contracts, preserving exact function, contract, assumption, and dependency identities; allow explicitly conditional proofs when callee proof evidence is absent, but never report them as proven.
  - [x] Generate actual conditional and closed Lean proofs from unary typed SPG calls. Seven closed cases agree with 35 SPG observations. Late rebinding reuses the caller proof; an edited direct pin changes its identity. A stale provider identity, reversed effects and a broadened assumption are rejected. General source extraction and trusted closure admission remain open. [Generated call contracts](research/formal-verification/RT-32/RT-32-GENERATED-CALL-CONTRACTS-2026-11-24.md).
- [ ] Define a typed Proof Dependency Graph (PDG), distinct from and linked to SPG, for proof artifacts, contract theorems, assumptions, call-site dependencies, transitive proof closure, and provenance.
  - [x] Compare transitive closure of exact claim receipts with immediate-edge admission. The traversal agrees with a least-fixed-point oracle on 12,288 root cases, while immediate-edge admission produces 2,577 false closures. Provider rebinding reuses the modular theorem and refreshes exact closure evidence. Source-derived inventory completeness and genuine receipt admission remain open. [Transitive proof closure](research/formal-verification/RT-32/RT-32-TRANSITIVE-PROOF-CLOSURE-2026-11-24.md).
- [ ] Define assumption-discharge and proof-state transitions: conditional/pending dependencies → closed/proven only after compatible checked callee evidence and all other obligations are bound.
- [ ] Validate incremental reuse/invalidation: callee body change with unchanged contract, contract change, caller change, stale proof artifact, changed assumptions/toolchain, and transitive dependency closure.
- [ ] Prove or explicitly bound source-to-Lean correspondence for the admitted subset; a theorem about generated Lean code alone is not a proof about LLMLang source.
  - Kernel-check unbounded prefix and transfer conservation for record ownership, and 72 exact archive equations covering 2,304 Rust vectors. Release uniqueness needs distinct roles and completed declaration/acquisition correspondence needs an exact permutation. Incorrect owner and transfer proof applications are rejected. General source extraction and independent review remain open. [Record ownership proof](research/formal-verification/RT-32/RT-32-RECORD-OWNERSHIP-PROOF-2026-11-25.md)
  - [x] Compare typed deep interpretation with generated shallow mutual recursion over the same effectful SPG bodies. Lean proves the exact fuel threshold for natural inputs and exhaustion at every finite budget for signed negative inputs. Compare 1,088 SPG observations across both encodings and reject trace-order and budget mutations. A verified decoder and wider correspondence remain open. [Deep recursive fuel](research/formal-verification/RT-32/RT-32-DEEP-RECURSION-FUEL-2026-11-24.md).
- [x] Compare shallow, deep and hybrid checks on two exact call-free scalar SPG bodies. Check canonical body and trace-contract bytes, prove preservation of whole observations across the Lean lowering and check both generated trace contracts. Four observation paths agree at 14 points. Keep SPG extraction and Python-to-Lean semantic correspondence explicit. [Exact SPG observation binding](research/formal-verification/RT-32/RT-32-SPG-LEAN-OBSERVATION-BINDING-2026-11-24.md).
- [ ] Evaluate Lean tactics, SMT-assisted discharge, reusable lemmas, and optional LLM-generated proof candidates, while requiring independent Lean-kernel checking.
- [ ] Define the TCB, axiom/import policy, unsupported/unknown behavior, proof provenance, evidence states, and fail-closed rules.
  - Check native worker cancellation with ten general Lean properties, two policy counterexamples and eight exact guarded schedule equations. At most one close and no post-revocation write hold over arbitrary command lists in the model. The 56 observed handoffs and 16 terminal outcomes match the archived projection. Source correspondence, uncontrolled scheduling and independent review remain open. [Worker kernel replay](research/formal-verification/RT-32/RT-32-WORKER-CANCEL-KERNEL-2026-11-25.md)
  - [x] Compare local and imported Lean 4.36.0 dependency views. Public imports retain exact axiom summaries while hiding proof terms. A private relay changes the dependency graph and provider sidecar without changing the public provider artifact or any caller artifact. Bind direct proof-path evidence to the exact provider bundle. [Compiled Lean dependencies](research/formal-verification/RT-32/RT-32-LEAN-COMPILED-DEPENDENCIES-2026-11-24.md).
  - [x] Check signed compiled Lean claims against exact SPG subjects, the expected proposition and transitive axioms. Two valid bundles pass and eight controls fail. An authorized signature alone admits a wrong theorem, a foreign premise and a mismatched compiled context. Production issuer governance and general proof admission remain open. [Compiled claim admission](research/formal-verification/RT-32/RT-32-COMPILED-CLAIM-ADMISSION-2026-11-24.md).
- [ ] Define incremental proof caching and invalidation for SPG, contracts, dependencies, assumptions, generator/compiler versions, and Lean toolchain changes.
- [ ] Build positive and adversarial fixtures, including incorrect implementations, weakened contracts, missing invariants, invalid termination measures, mismatched translations, stale callee proofs, and unsupported effects.

**Research brief:** [RT-32 — Verified SPG-to-Lean Pipeline](research/formal-verification/RT-32/RT-32-VERIFIED-SPG-TO-LEAN-PIPELINE.md). Coordinate with RT-03/05/07/08/09/11/24. This is a Toolchain/formal-verification research goal, not a new LLMLang surface-language feature or a decision to make Lean the runtime.

**Exit criteria:** a non-trivial function is translated from SPG without a separately authored Lean implementation; generated obligations cover its declared contract and termination; the Lean kernel checks the proof; source-to-Lean correspondence covers the admitted subset; adversarial fixtures reject incorrect or stale evidence; provenance binds proofs to exact semantic and toolchain identities; conditional caller proofs remain visibly unproven until every dependency is discharged through compatible checked evidence.

## 2.5 Correctness of optimization and translation

**Estimated research complexity:** **9/10** — semantic preservation across lowering and optimization needs version-pinned corpora and independent validation.

- [ ] Define proof obligations for semantic graph rewrites, including correspondence with authoritative LLMLang semantics when Lean or another verifier is used as a target representation.
- [ ] Define proof obligations for compiler optimizations.
- [ ] Study translation validation versus proving the optimizer correct.
- [ ] Evaluate Alive2 and related LLVM validation techniques.
  - [x] Cross-check five LLVM 19 modules in the structural verifier, Alive2 and the extracted Vellvm interpreter. Alive2 confirms identity and refutes incorrect signed-overflow metadata and a store reorder. Unsupported atomic and fence cases need separate concurrent evidence. [LLVM validation coverage](research/compiler-and-translation/RT-13/RT-13-ALIVE2-VELLVM-COVERAGE-2026-11-24.md). [Stock replay](research/compiler-and-translation/RT-13/RT-13-STOCK-ALIVE2-LLVM-EH-2026-11-24.md) confirms the same verdicts using unmodified Alive2 and exception-enabled LLVM 19.1.7.
- [x] Check whole-domain status, output stores and ordered callbacks for the exact Scenario 96A checked signed-add LLVM IR at O0 and O3. Two solvers reject mismatch formulas and find three verifier-accepted counterexamples, each replayed natively. Unsupported flags stay outside the claim. [Checked-add observation validation](research/compiler-and-translation/RT-13/RT-13-LLVM-CHECKED-ADD-OBSERVATIONS-2026-11-24.md).
- [x] Bind two cvc5 CPC refutations to those exact checked-add formulas and replay both in Logos. Check declaration names and sorts before aligning parser IDs, then check the ordered assumptions and actual proof commands. Swapped or renamed certificates fail binding. [Checked-add certificate binding](research/compiler-and-translation/RT-13/RT-13-LLVM-CHECKED-ADD-CPC-BINDING-2026-11-24.md).
- [x] Replay the exact checked-add formulas in Lean for O0 and O3, with 12 LRAT certificates and eight normalization proofs. Each LRAT theorem has one native reflection axiom; the offline route rejects a certificate for a different goal. General LLVM/source correspondence remains open. [Lean bit-vector replay](research/compiler-and-translation/RT-13/RT-13-LLVM-CHECKED-ADD-LEAN-2026-11-25.md)
- [x] Prove the same checked-add claims with symbolic signed arithmetic and normalization in Lean. All 20 claims and three arithmetic lemmas use only standard axioms, and three false preservation claims are refused. This covers the exact fixture without changing the general LRAT assumption. [Symbolic checked-add proof](research/compiler-and-translation/RT-13/RT-13-LLVM-CHECKED-ADD-SYMBOLIC-2026-11-25.md)
- [ ] Define differential and property-based testing against reference semantics.
- [ ] Define when testing is sufficient evidence and when formal proof is required.

**Prior art:** Lean, SMT solvers, TLAPS, Dafny, K Framework, Vellvm, Alive2.

**Research output (2026-11-21)** · Lean checks preservation of result, error and ordered trace by a bottom-up rewrite over a typed scalar expression grammar. [RT-07 observable rewrites](research/formal-verification/RT-07/RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md)

**Status:** partially validated for the expression model. Source, graph and backend correspondence remain open.

**Exit criteria:** a small, executable reference semantics; at least one end-to-end, independently checked proof path with explicit assumptions; a documented trusted computing base; reproducible CI validation.

---

# Stage 3 — Dependency graph, incremental computation, and cache

**Order:** after Stage 1 identity and Stage 2 semantic/proof boundaries are sufficiently defined.  
**Purpose:** compute only what has actually been invalidated while preserving soundness.

## 3.1 Semantic dependency model

**Estimated research complexity:** **8/10** — completeness across static, dynamic, external, generated, aliased, and recursive dependencies is foundational.

- [x] Synthesize Scenarios 19, 20, 25 and RT-19/20/23 into a candidate Semantic Dependency Index contract; keep it explicitly non-canonical pending SPG schema decisions.
- [x] Define and implement an executable candidate SPG subset and typed dependency extractor; this is a research prototype, not the canonical language schema.
- [x] Specify candidate stable call-site identity, conditional target representation, and source/target relation constraints; validate them with focused tests.
- [x] Add a snapshot-scoped dependency-index projection so RT-20 reverse lookup excludes historical caller versions and remains pinned to one exact Semantic Snapshot.
- [x] Bind snapshot-scoped reverse lookup to explicit completeness evidence, exact snapshot/target/scope, extractor/schema identity, and the digest of the returned edge set; fail closed to UNKNOWN or NOT_CHECKED when evidence is absent or mismatched.
- [x] Connect the reverse-query result to impact-planning completeness audits; require Snapshot-bound evidence by default, preserve every evidence binding in the plan identity, and force full revalidation on missing or mismatched bindings. The research prototype does not authenticate the producer or prove its observation model complete.
- [x] Add a differential Snapshot payload-scan audit for reverse-index edge coverage and bind its evidence to the exact query.
- [x] Represent caller compatibility per exact call-site/target edge; require explicit evidence-backed migrate/preserve/adapt/fork decisions and resulting caller hashes; block plans with missing or unresolved decisions. Prototype coverage includes mixed old/new behavior and shared-caller version selection.
- [x] Bind each call-site/target alternative to its exact caller-required Contract hash; keep the provided Contract reference solely on the callee and resolve it through the existing caller-to-callee edge in RT-20 planning, validation, and semantic diff. Do not duplicate provided-contract hashes in call edges, reverse-index edges, or CIP decisions (declaration schema v2; dependency-index schema v3; not yet normatively equated with glossary CCHash).
- [ ] Reconcile the candidate subset with the canonical SPG schema and formal semantics before normative adoption.
- [ ] Define semantic dependencies separately from provenance, audit observations, and traceability.
- [ ] Define hash-relevant dependency edges and dependency closure.
- [ ] Define how dependencies are discovered from static analysis, typed IR, runtime observations, tests, and formal semantics.
- [ ] Define confidence/evidence classes for dependency edges.
- [ ] Define sound conservative may-depend graphs.
  - [x] Compare finite guard-sensitive may-dependency closure against 16,384 explicit queries. Location-only traversal misses targets in 3,408 queries. State-aware closure matches the known-table oracle, and local unknown expansion avoids misses with measurable loss of precision. Exhausted queries return unknown. Source extraction, wider effects and snapshot binding remain open. [Conditional dependency closure](research/semantic-representation/RT-06/RT-06-CONDITIONAL-DEPENDENCY-CLOSURE-2026-11-25.md).
- [ ] Define how missing or incomplete dependency evidence affects reuse.
- [ ] Define cycles and strongly connected components for analysis and scheduling.
- [ ] Define change-impact analysis for requirement, contract, design, implementation, and target changes.

**Existing evidence:** scenarios 18–28 and prototypes 18–28 in `research/PROTOTYPES/DEPENDENCY-GRAPH-01/`.

**Status:** extensively researched and prototyped in Scenarios 18–28 and dependency-graph prototypes 18–28. A candidate index contract and executable typed extractor now exist in `research/SEMANTIC-DEPENDENCY-INDEX.md` and `research/PROTOTYPES/DEPENDENCY-GRAPH-01/`. The candidate schema is not canonical; reconciliation with the accepted SPG model, formal soundness, and Toolchain integration remain open.

**Research output (2026-11-21)** · A closed scoped-lookup fixture distinguishes absent and present binding reads. Per-key projection reuses 216 results with zero observed false reuse, conditional on whole-layer admission. [Negative binding reads](research/semantic-representation/RT-06/RT-06-SCOPED-BINDING-READ-DEPENDENCIES.md)

## 3.2 Incremental analysis and invalidation

**Estimated research complexity:** **5/10** — focused binding/invalidation experiments are tractable, though production completeness remains difficult.

- [ ] Define invalidation for type checking, contract checking, optimization, code generation, tests, and proofs.
- [ ] Define the difference between semantic impact and evidence staleness.
- [ ] Define how an `ImpHash` change propagates through dependent semantic nodes and action results.
- [ ] Define safe reuse when only non-semantic metadata changes.
- [ ] Define conservative fallback when dependency completeness cannot be established.
- [ ] Define impact planning and non-interference gates.
- [ ] Benchmark small local edits, shared component edits, and broad semantic changes.

**Existing evidence:** `research/SEMANTIC-COMPILATION-CACHE.md`, scenarios 18–28, and dependency graph prototypes.

**Status:** researched and prototyped in parts; full compiler integration and empirical validation are not implemented.

**Research output (2026-11-23):** [RT-32 incremental invalidation recheck](research/formal-verification/RT-32/RT-32-INCREMENTAL-INVALIDATION-RECHECK-2026-11-23.md) compares global invalidation, complete-dependency ActionKeys, timestamp/dirty hints, and fail-closed behavior for unknown closure. A focused suite passed 72 tests on CPython 3.12.14. The result supports content-addressed reuse conditionally on complete dependencies and distinct evidence freshness; it does not establish compiler integration or workload performance. Integration across real stages, metadata projection, source-derived completeness/non-interference, representative benchmarks, and production identity/trust decisions remain open.

## 3.3 Semantic build and cache graph

**Estimated research complexity:** **6/10** — requires sound action keys, dependency closure, and demonstrated invalidation/reuse.
- [ ] Define optional package-distributed cache-index files for validation, compilation, analysis, tests, and proofs; decide whether indexes and result payloads are embedded or separately fetched.
- [x] Establish the version-identity split for cache records: composite `LanguageVersion`, append-only component-registry digest, and separate `ToolchainIdentity`; record the candidate design in `research/LANGUAGE-VERSIONING.md`.
- [x] Add an experimental version-bound cache-record validator and tests covering language-version, registry-digest, and toolchain changes to Action Key inputs. This remains a prototype, not a normative cache-index format.
- [ ] Bind every cached result to exact Action Key inputs and complete dependency closure; define compatibility evidence for reuse across different language or toolchain identities.
- [ ] Define cache-index merge, conflict handling, artifact availability/eviction, and trust/evidence checks.

- [ ] Define typed build actions and their inputs/outputs.
  - Compare the generated RT-01 CLI with a separately linked native division object. The scoped action key plans nine compilations across six edits, versus 18 under whole-input invalidation. Entry and semantic snapshot keys retain stale artifacts and hide two failures of a requested replacement. General closure extraction and controlled timing remain open. [CLI action keys](research/language-design/RT-01/RT-01-CLI-ACTION-KEYS-2026-11-25.md)
- [ ] Keep Semantic Hash, Action Key, and Artifact Hash distinct.
- [ ] Include tool identity, tool version, configuration, target, environment, runtime, and policy inputs whenever they can affect a result.
- [ ] Define deterministic versus nondeterministic action handling.
- [ ] Define local, workspace, remote, and global cache layers.
- [ ] Define cache integrity, trust, provenance, and eviction.
- [ ] Define test and proof evidence caching with exact subject and assumption binding.
- [ ] Define behavior for incomplete dependency closure: invalidate conservatively or disable caching.
- [ ] Define reproducibility requirements and cache poisoning defenses.

**Existing evidence:** `research/SEMANTIC-COMPILATION-CACHE.md`, `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`, `research/COMPILATION-CACHE-SPEEDUP-ESTIMATE.md`, [Language Versioning](research/packages-and-ecosystem/RT-18/LANGUAGE-VERSIONING.md), and the exploratory [Package Identity Prototype 01](research/packages-and-ecosystem/PROTOTYPES/PACKAGE-IDENTITY-01/README.md).

**Status:** researched; the version-binding design and a first experimental cache-record validator now exist. The initial component registry is `language-components.toml` and is append-only. The candidate validator keeps LanguageVersion, registry digest, and ToolchainIdentity distinct and includes them in Action Key construction. The cache-index wire format, compatibility declarations, complete dependency-closure model, merge/conflict policy, and broader implementation validation remain open.

**Research output (2026-11-23):** [RT-33 build graph/cache options recheck](research/formal-verification/RT-33/RT-33-BUILD-GRAPH-CACHE-OPTIONS-RECHECK-2026-11-23.md) compares package-embedded cache data, optional package index references with separate CAS payloads, local/workspace cache, and team/remote cache. A 36-test focused suite passed. Current evidence favors local-first experimentation and optional cache metadata outside package semantic identity; remote trust, result-fetch lifecycle, cache-index merge/eviction and production dependency completeness remain external dependencies. No production format or layer is selected.

## 3.4 Quantify compilation speedup

**Estimated research complexity:** **5/10** — controlled benchmark design and measurement; conclusions depend on representative workloads and hardware.

- [ ] Validate the analytical model in `COMPILATION-CACHE-SPEEDUP-ESTIMATE.md`.
- [ ] Implement reproducible benchmarks for cold, warm, local-edit, component-edit, and broad-change builds.
- [ ] Measure cache hit rates by action type.
- [ ] Measure hashing, dependency discovery, scheduling, storage, and verification overhead.
- [ ] Compare against clean and conventional incremental builds in representative Rust, Go, and C++ projects.
- [ ] Report speedup distributions and workload assumptions rather than a single headline number.
- [ ] Identify workloads where caching is neutral or slower.

**Status:** analytical estimate researched in `research/COMPILATION-CACHE-SPEEDUP-ESTIMATE.md`; empirical benchmark results still required.

**Research output (2026-11-23):** [RT-11 cache speedup model recheck](research/toolchain-and-collaboration/RT-11/RT-11-CACHE-SPEEDUP-MODEL-RECHECK-2026-11-23.md) reran the synthetic binding experiment on CPython 3.12.14 / Debian GCC 14.2.0. Clean-build outputs matched; action-count reuse patterns were reproduced, including a counterexample showing caller compile identity is not a safe executable-verification key. No durations or representative workloads were measured, so the analytical speedup ratios remain hypotheses and every empirical-performance checkbox above remains open.

**Research output (2026-11-23):** [RT-11 benchmark measurement boundary recheck](research/toolchain-and-collaboration/RT-11/RT-11-BENCHMARK-MEASUREMENT-BOUNDARY-RECHECK-2026-11-23.md) recorded that one current-main run executes 467 incremental cache actions plus 12 clean oracles and compared instrumentation-only, larger synthetic workload, real Rust/Go/C++ workload, and premature product-prototype options. It recommends instrumentation-only as the lowest-dependency next experiment; a repeated timing attempt was stopped without retaining partial values. No latency or speedup claim is made; all §3.4 empirical-performance checkboxes remain open.

**Research output (2026-11-24):** [RT-11 instrumented binding action timing](research/toolchain-and-collaboration/RT-11/RT-11-ACTION-TIMING-INSTRUMENTATION-2026-11-24.md) adds opt-in per-miss wall/child-CPU/output samples and records two paired runs with raw JSON. A separate-link implementation edit executed 45 misses versus 53 for exact linkage in this synthetic fixture. The measurement wrapper itself added about 935 ms on those 45 actions while measured child wall sums were 234 ms, so the current instrumentation is too intrusive for absolute speedup claims. Replace it with lower-overhead measurement before timing broader workloads; representative LLMLang and real-project comparisons remain open.

**Research output (2026-11-24):** [RT-11 direct-child timing recheck](research/toolchain-and-collaboration/RT-11/RT-11-DIRECT-CHILD-TIMING-RECHECK-2026-11-24.md) replaces the per-command Python helper with direct parent-side subprocess/RUSAGE_CHILDREN timing. Two paired synthetic runs retain clean-oracle agreement and repeat 53 exact-link versus 45 separate-link implementation misses; two whole-experiment timings (16.291 s without timing, 16.534 s with timing) are too few and unpinned for performance conclusions. A post-rebase current-source rerun at main `264c97b` again passed the clean oracles and reproduced the 53/45 action counts; its direct child sums were 297.08/290.52 ms exact and 189.82/182.66 ms separate, kept as a distinct recheck rather than pooled with the archived run. This compares direct timing with the former helper instrumentation but does not estimate a controlled overhead effect. Representative projects, separately measured hashing/dependency/scheduling cost, and controlled repetitions remain open.

**Exit criteria:** a dependency-completeness policy; sound action-key model; tests showing that relevant changes invalidate all affected results and irrelevant changes preserve valid results; reproducible benchmark data.

---

# Stage 4 — Semantic storage, versioning, and Git integration

**Order:** after identity and dependency boundaries are stable enough to persist.  
**Purpose:** make semantic programs durable, portable, reviewable, and mergeable in ordinary repositories.

**Current workstream status:** Git representation and semantic merge research is completed at concept level. The full report is [Git semantic repository research](research/toolchain-and-collaboration/RT-15/GIT-SEMANTIC-REPOSITORY.md); [ADR-014](docs/adr/014-git-semantic-merge.md) records a **Proposed** direction, not an irreversible accepted architecture. Implementation and benchmarking are deferred until cross-aspect synthesis.

## 4.1 Semantic object storage

**Estimated research complexity:** **6/10** — storage, immutable snapshots, recovery, and identity integration.

- [ ] Compare KV databases, content-addressed object stores, relational indexes, and filesystem layouts.
- [ ] Define canonical object encoding and immutable object lifecycle.
- [ ] Define indexes for graph traversal, reverse dependencies, contracts, and implementation discovery.
- [ ] Define transactions and atomic publication of graph revisions.
- [ ] Define garbage collection and reachability.
- [ ] Define crash recovery, corruption detection, backup, and replication.
- [ ] Define local repository storage versus shared/global artifact storage.
- [ ] Define portability without requiring a live external database.

**Existing evidence:** `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md` and the current Git representation research.

**Status:** researched at architectural level; storage prototype and recovery tests remain open.

## 4.2 Git representation and repository model

**Estimated research complexity:** **6/10** — repository mapping and semantic versioning need consistency with SPG identity.

- [ ] Define the canonical Git-visible representation of a semantic program.
- [ ] Compare storing canonical serialized semantic objects directly in Git with storing KV-backed objects plus repository manifests.
- [ ] Define the mapping between Git commits/trees and semantic graph snapshots.
- [ ] Preserve ordinary Git clone, fetch, push, branch, tag, and history behavior.
- [ ] Define readable textual representation, diff strategy, and generated metadata.
- [ ] Define how large objects and binary artifacts are handled.
  - Native Git LFS 3.6.1 distinguishes the committed pointer, local media and filtered checkout or archive. Across fourteen settings, exact manifest, pointer, size and SHA-256 checks reconstruct seven available artifacts and refuse seven others. Path-based reuse accepts six wrong snapshots. External media retention and production transport remain open. [Git LFS object admission](research/toolchain-and-collaboration/RT-24/RT-24-LFS-OBJECT-ADMISSION-2026-11-25.md)
- [ ] Satisfy the mandatory RT-27 repository constraints: reconstruct the complete committed SPG state from Git alone (including required metadata/indexes), and avoid one tracked file per SPG object ([R-STORE-001](research/toolchain-and-collaboration/RT-27/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-001--complete-reconstruction-from-git), [R-STORE-002](research/toolchain-and-collaboration/RT-27/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-002--no-one-file-per-object-layout)).
- [ ] Specify and test cache-first record metadata, including integrity/trust checks and a cache-hit path that skips payload reads/deserialization; require deterministic serialization ([R-STORE-003](research/toolchain-and-collaboration/RT-27/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-003--cache-lookup-before-payload-deserialization), [R-STORE-004](research/toolchain-and-collaboration/RT-27/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-004--deterministic-physical-serialization)).
  - [x] Compare cache-first reads for a sequential container, indexed independent records and ZIP from a clean Git clone. All layouts skip payload on a full hit. At half coverage, indexed and ZIP readers decode 128 records while the sequential reader decodes all 256. Exact Git metadata and content checks reject misplaced or mismatched values. Broader format workloads remain open. [Metadata-first cache reads](research/toolchain-and-collaboration/RT-27/RT-27-METADATA-FIRST-CACHE-READS-2026-11-24.md).
- [ ] Prohibit ordinary text merge as a correctness mechanism for SPG containers; integrate only through complete-state semantic merge and whole-graph validation ([R-STORE-005](research/toolchain-and-collaboration/RT-27/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#r-store-005--no-ordinary-text-merge-of-spg-containers)).
- [ ] Define explicit add/update/delete semantics, keep physical placement separate from semantic identity, bound active storage/compaction growth, and make indexes recoverable from Git ([R-STORE-009–012](research/toolchain-and-collaboration/RT-27/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md#4-semantic-and-operational-constraints)).
- [ ] Measure Git packfile delta-compression efficiency for immutable SPG object containers under add/remove-only workloads; compare bounded stable shards, immutable segments, and chunking before selecting a layout.
  - [x] Compare four physical layouts over 24 native Git histories at 0.01%, 1% and 10% replacement. Module shards preserve concentrated locality while hash shards spread the two larger edits. Segments minimize new payload bytes, and a compaction reduces the active checkout while retaining a larger Git pack. Clean clones reconstruct both roots. Longer and representative histories remain open. [Sharded Git history](research/toolchain-and-collaboration/RT-27/RT-27-SHARDED-GIT-HISTORY-2026-11-24.md).
  - [x] Compare fixed and content-defined chunk boundaries in ten native Git histories. Content anchors localize the unaligned insertion and deletion. Fixed boundaries write fewer new bytes in the aligned insertion and same-rank replacement. Neither layout reuses chunks on the anchor-free insertion. Clean clones restore both revisions. Long histories and resource measurements remain open. [Chunk boundaries](research/toolchain-and-collaboration/RT-27/RT-27-CHUNK-BOUNDARIES-2026-11-25.md).
- [ ] Define repository portability and reproducibility from a clean clone.
  - Compare 22 native full, shallow, sparse and partial Git settings in SHA-1 and SHA-256 repositories. Exact tree and verified blob-cache admission reconstructs all 12 available graphs, distinctly refusing ten unavailable, corrupt or invalid cases. A path cache accepts eight incorrect snapshots. General remote recovery and repository closure remain open. [Partial and sparse Git reconstruction](research/toolchain-and-collaboration/RT-24/RT-24-PARTIAL-SPARSE-RECONSTRUCTION-2026-11-25.md)

**Existing evidence:** `research/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md`.

**Status:** researched at architectural level; binary-container efficiency is under investigation. The benchmark and physical-layout decision remain open.


**Binary storage efficiency research (2026-11-23)** · The SPG storage workload adds/removes immutable payloads. The five-run reference microbenchmark (30,000 × 192-byte high-entropy records; 1% changes; Git 2.47.3) found only negligible pack-plus-index differences between mutable-container and immutable-segment variants: 240 bytes on append and under 0.012% on deletion. It does not select a layout. The earlier exploratory measurements remain unverified and are not acceptance evidence. [Research report](research/toolchain-and-collaboration/RT-27/GIT-BINARY-SPG-STORAGE-EFFICIENCY.md) · [Harness and instructions](research/toolchain-and-collaboration/benchmarks/git_binary_spg/README.md) · [Five-run results](research/toolchain-and-collaboration/benchmarks/git_binary_spg/results-2026-11-23.json)

- [x] Execute and preserve a five-run fixed-size baseline for append, compact deletion, and tombstone deletion across mutable-container and immutable-segment layouts; validate retained repositories with `git fsck --full`.
- [ ] Extend the benchmark to realistic variable-size SPG payloads and references, bounded multi-shard placement, long histories, branch divergence, compaction, clone/fetch, and KV-independent reconstruction.
- [ ] Compare bounded stable shards, immutable segments, and chunked containers; measure packfile size, delta depth/size, CPU, memory, read/checkout/reconstruction time, and history growth.
- [ ] Select no physical format or shard key until benchmark results are reviewed against the unresolved SPG identity/lineage model.

**Research output (2026-11-23):** [RT-27 SPG Repository Storage Format Requirements](research/toolchain-and-collaboration/RT-27/RT-27-SPG-REPOSITORY-STORAGE-FORMAT-REQUIREMENTS.md) records mandatory reconstruction, cache-first metadata, determinism, merge-safety, and workload-evaluation requirements without selecting a format. RT-27 is now registered as a standalone research area in the taxonomy and dependency map. RT-28 also depends on RT-27's storage requirements; this dependency does not select a physical storage format. Format comparison/benchmarks also depend on stabilized SPG identity, import/export, semantic merge, and representative workloads.

## 4.3 Semantic diff, merge, and conflict resolution

**Estimated research complexity:** **6/10** — substantial integration and conflict semantics, dependent on canonical representation and identity.

- [ ] Define semantic diff independently of textual diff and AST diff.
- [ ] Define three-way merge over semantic graph snapshots.
- [ ] Define conflict classes: same-node edits, contract/implementation divergence, identity collisions, dependency conflicts, split/merge conflicts, and metadata-only conflicts.
- [ ] Define automatic merge when changes are provably independent.
- [ ] Define conservative conflict behavior when independence cannot be established.
- [ ] Define interactive conflict resolution and preservation of both alternatives.
- [ ] Define post-merge validation: graph integrity, type checking, contract checking, dependency completeness, tests, and proofs.
- [ ] Define merge reproducibility and audit history.

**Mapping reconciliation evidence (2026-11-21)** · Disjoint interface keys can claim the same export. Revision and catalog checks reject stale publication even when logical entries repeat. [RT-23/24 mapping merge](research/toolchain-and-collaboration/RT-23/RT-23-INTERFACE-MAPPING-MERGE.md)

## 4.4 Git integration workflow

- [ ] Prototype a Git merge driver that invokes the LLMLang semantic merge tool.
  - [x] Compare a native file driver, explicit-context refusal and textual fallback across 12 temporary-repository cases. Merge, cherry-pick and rebase each report success for a pair with identical driver observations and different graph closure. Only the full pinned trees expose all three missing exact callees. [Native merge driver experiment](research/toolchain-and-collaboration/RT-24/RT-24-NATIVE-GIT-MERGE-DRIVER-2026-11-24.md).
- [ ] Prototype a Git mergetool integration for interactive conflicts.
  - [x] Compare native Git mergetool exit status with a repository-context adapter in 12 cases. Exact inputs and staged semantic reconstruction preserve an ordinary conflict and reject a stale index, a wrong input blob and two semantic conflicts. Native Git can leave no conflict stages despite a broken call. Missing tools and unsupported replay operations preserve the stages. General interactive resolution and publication still require their own gates. [Native mergetool experiment](research/toolchain-and-collaboration/RT-24/RT-24-NATIVE-GIT-MERGETOOL-2026-11-24.md).
- [ ] Define clean fallback behavior when the tool is unavailable.
- [ ] Test merges in normal Git workflows and across operating systems.
  - Sixteen native Git histories isolate two ordinary conflicts and eight declared profile collisions in otherwise clean Linux merges. Checking all prefixes catches the eight profile collisions while two Git configuration values still restore all fourteen clean trees on Linux. Native filesystem coverage on other profiles remains open. [Profile-bound Git paths](research/toolchain-and-collaboration/RT-24/RT-24-PROFILE-BOUND-GIT-PATHS-2026-11-25.md)
- [ ] Verify that merge drivers do not silently discard unresolved semantic conflicts.
- [ ] Document repository setup and team workflows.

### 4.5 End-to-end semantic merge and synchronized commit lifecycle

**Estimated research complexity:** **10/10** — spans graph validation, merge, Git synchronization, failure recovery, and exact-state guarantees.

**Study these documents as one set before changing this workstream:**
- [Git Representation and Semantic Merge](research/toolchain-and-collaboration/RT-15/GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md) — primary research source for repository representation and semantic merge rules.
- [ADR-014](docs/adr/014-git-semantic-merge.md) — proposed architecture direction; not Accepted.
- [RT-20](research/toolchain-and-collaboration/RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) — caller impact, per-call-site migration/preservation, hash propagation, and verified completion.
- [RT-22](research/toolchain-and-collaboration/RT-22/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md) — repository/worktree operations, merge reconciliation boundary, commit preparation, and recovery.
- [RT-23](research/toolchain-and-collaboration/RT-23/RT-23-SINGLE-INSTANCE-TOOLCHAIN-AND-INCREMENTAL-MULTI-WORKTREE.md) — shared semantic state, versioned interface mappings, incremental worktree views, and synchronized semantic/filesystem commit.
- [RT-19](research/toolchain-and-collaboration/RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) — semantic Change Set/Snapshot lifecycle and transport-neutral API.

The documents have explicit ownership boundaries and reciprocal links. Re-read the complete set together whenever merge, rebase, cherry-pick, semantic export/import, or commit behavior changes.

**Detailed candidate contract:** [RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge](research/toolchain-and-collaboration/RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md). RT-24 is a research proposal, not an accepted format or merge decision. Its identity/SPG reconciliation is recorded in [RT-24 Identity and SPG Reconciliation](research/toolchain-and-collaboration/RT-24/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md), with the scenario comparison in [RT-24 Identity Architecture Decision Matrix](research/toolchain-and-collaboration/RT-24/RT-24-IDENTITY-DECISION-MATRIX.md). There is no standalone RT-05 specification in the current repository; the relevant evidence is distributed across Studies 05–08, RT-03, Semantic Dependency Index research, and the executable prototypes.

**Refined execution order:**
- [x] Reconcile RT-24 against the current identity/SPG research and executable subset; record the competing Stable Entity ID versus content-addressed-value models, occurrence/selection and lineage boundary, current prototype fields/limitations, hash-layer distinctions, and dependency-completeness gap in RT-24 Identity and SPG Reconciliation. No identity architecture or canonical SPG schema was selected.
- [x] Compare Studies 05–08 against rename, identical-value/different-occurrence, split/merge, move, call-site, and branch-merge scenarios in RT-24 Identity Architecture Decision Matrix. This completes the comparison, not the architecture decision.
- [ ] Decide Stable Entity ID + Content Hash versus content-addressed values with explicit lineage/selection after completing RT-03/RT-04 semantic reconciliation and the decision gates recorded in the matrix.
- [ ] Reconcile the selected identity model with RT-03 language semantics and RT-04 type/effect research before freezing hash-relevant fields and canonical SPG object/edge schemas.
- [ ] Integrate the existing ReverseLookupEvidence/query_snapshot_incoming completeness gate with RT-20 CIP and the semantic merge coordinator; define the independent audit producer, observation coverage, evidence trust policy, and end-to-end fail-closed tests. The prototype already binds evidence to snapshot, target, scope, extractor/schema, and exact edge-set digest, but does not authenticate the producer or prove its observation model complete.
  - Compare 32 native builds across a header edit, eight feature profiles and two optimization levels. Source and flags alone omit 24 call edges, and a profile union adds 80 excess edges. Exact profile binding supplies all active caller obligations and rejects all 64 stale receipt swaps. General frontend coverage and audit governance remain open. [Configuration-bound caller coverage](research/toolchain-and-collaboration/RT-24/RT-24-CONFIG-CALLER-COVERAGE-2026-11-25.md)
  - [x] Compare exact query binding, Ed25519 audit authorization and independent source reconciliation in twelve explicit-call cases. A signed empty projection suppresses RT-20 full revalidation unless reconciled against source. Production observation coverage and authority policy remain open. [Reverse audit authority](research/toolchain-and-collaboration/RT-24/RT-24-REVERSE-AUDIT-AUTHORITY-2026-11-24.md).
- [ ] Select the smallest supported SPG subset and specify its textual source inventory/manifest fixture. Keep the repository source textual; treat local stores, caches, and indexes as reconstructible derived state.
- [x] Compare two canonical Git exports for the existing closed-inventory fixture. Twenty-four physical input trees reach one semantic root and one exact artifact per layout. Verify round-trip identity, ordered payload changes and five rejected inputs. [Canonical Git layouts](research/toolchain-and-collaboration/RT-24/RT-24-CANONICAL-GIT-LAYOUTS-2026-11-24.md).
- [ ] Extend the importer/exporter experiment to the selected SPG and repository schema, including its broader syntax, dependencies and portability contracts.
- [ ] Implement typed SemanticDiff with exact snapshot binding, per-call-site reference changes, root/dependency changes, lineage records, and deterministic output.
  - Closed-inventory evidence covers exact retargets, conditions, physical moves and missing input. [Typed tree diff](research/toolchain-and-collaboration/RT-24/RT-24-TYPED-TREE-DIFF.md)
  - [x] Compare equal-root histories against occurrence continuity on native Git. Twelve cases distinguish value evidence, retained linear history, a real shallow clone and a squash that erases the intervening deletion. Authorized lifetime records and general merge lineage remain open. [Git selection lifetimes](research/toolchain-and-collaboration/RT-24/RT-24-GIT-SELECTION-LIFETIMES-2026-11-24.md).
- [ ] Implement a pure three-way merge core over pinned base/ours/theirs snapshots. Apply only unambiguous rules; emit structured conflicts for update/update, delete/update, identity/lineage, retarget, dependency, root, and unsupported-context cases.
- [ ] Validate the entire merged graph, not just merged files/entities; prove that incomplete source inventory or reverse-reference context cannot yield a clean result.
- [ ] Integrate RT-20 CIP as a mandatory gate: preserve/migrate/adapt/fork per call site, support mixed old/new callers and shared-caller splits, and rebuild the candidate whenever planned changes alter it.
  - The exact-tree fixture connects one source-audited caller migration to Git publication and receipt recovery. [Tree-bound CIP](research/toolchain-and-collaboration/RT-24/RT-24-TREE-BOUND-CIP-PUBLICATION.md)
  - [x] Compare local CIP checks and source-derived consumer paths for a shared-caller split through native two-parent merges. Exact tree and edge checks accept four incorrect path plans. The rooted check rejects all four and preserves aligned publication, retry and clean-clone recovery. General path coverage and migration authority remain open. [Split caller paths](research/toolchain-and-collaboration/RT-24/RT-24-SPLIT-CALLER-PATHS-2026-11-24.md).
- [ ] Integrate Interface Mapping Revision merge separately under RT-23 parent-revision/CAS/scope rules; test disjoint keys, same-key conflicts, delete/update, and stale baselines.
  - Compare 18 native clean merges of independently valid binding, name and export changes. Reference or contract-only checking accepts 16. Checking the selected operation, contract, provider, ABI and input scope publishes six and distinguishes unresolved evidence from incompatible data. Production authority, real ABI semantics and concurrent integration remain open. [Cross-map export proof](research/toolchain-and-collaboration/RT-24/RT-24-CROSS-MAP-EXPORT-PROOF-2026-11-25.md)
- [ ] Only after the pure core passes, build a Git repository coordinator with explicit base/ours/theirs trees; then test merge, rebase, and cherry-pick against real temporary repositories. Keep per-file merge driver as an adapter, not a whole-graph correctness boundary.
- [ ] Finally integrate RT-23 exact-tree synchronized commit and idempotent crash/timeout recovery; test clone reconstruction without the original local semantic database.
  - A coordinated Git generation detects an intervening change even when the branch returns to the same OID. [Ref generation experiment](research/toolchain-and-collaboration/RT-23/RT-23-COORDINATED-REF-GENERATION.md)

**Research output (2026-11-21)** · A three-way selector composes independent declarations across a textual conflict. Rebuilding the candidate from selected rows detects an exact callee lost across disjoint slot edits. The positive export reconstructs the same selections. [RT-24 closed-inventory merge](research/toolchain-and-collaboration/RT-24/RT-24-CLOSED-THREE-WAY-MERGE.md)

**Required sequence:**
- [ ] Reconcile the canonical textual repository representation, manifests/roots, external dependency pins, and deterministic import/export; prove clean-clone reconstruction and round-trip equivalence.
  - Compare 13 native submodule cases with independent manifest, gitlink, origin and object checks. Exact admission reconstructs all seven available dependencies and refuses six others. Working file, nested HEAD and origin tip can diverge with the same committed root. Production origin governance and object retention remain open. [Pinned gitlink reconstruction](research/toolchain-and-collaboration/RT-24/RT-24-PINNED-GITLINK-RECONSTRUCTION-2026-11-25.md)
  - Rebuild an exact typed CLI from four independent clean Git clones in packed and per-entry layouts. Both restore the same semantic roots and native binaries across 272 observations and refuse ten invalid clones. A local Echo edit adds 1,397 or 1,017 uncompressed blob bytes respectively. General dependency and package closure remain open. [Executable clean clone](research/toolchain-and-collaboration/RT-24/RT-24-CLEAN-CLONE-CLI-2026-11-25.md)
  - Compare four admission policies across twelve mixed-version native Git histories. Exact dual read with parent-root checks reconstructs all six valid merges and refuses the other six. JavaScript number consumption produces four invalid candidates, and exact reads without root checks produce two. Production schema evolution and general graph closure remain open. [Versioned I64 Git merge](research/toolchain-and-collaboration/RT-24/RT-24-VERSIONED-I64-GIT-MERGE-2026-11-25.md)
- [ ] Define semantic diff over stable semantic identities, separating Git object identity, semantic identity, and action/evidence identity.
- [ ] Specify deterministic three-way SPG merge over exact base/ours/theirs snapshots, including independent add/add, same-entity update/update, delete/update, rename/move, split/merge, replacement, and dependency/lock changes.
  - The closed fixture composes independent exact call retargets under a fixed selector policy and rejects a missing upstream branch-version pin. [Call-target merge](research/toolchain-and-collaboration/RT-24/RT-24-CALL-TARGET-MERGE.md)
- [ ] Define a structured conflict/result model with provenance, exact input roots, merge policy/tool versions, resolution decisions, and explicit clean/conflict/invalid/insufficient-context outcomes.
  - [x] Compare slot, caller-scope, semantic-root, tree and commit-bound conflict decision replay. Eight native Git cases include a changed affected caller in a still-closed candidate, a metadata-only edit and equal trees reached through different commits. Production review and publication policy remain open. [Conflict resolution replay](research/toolchain-and-collaboration/RT-24/RT-24-CONFLICT-RESOLUTION-REPLAY-2026-11-24.md).
- [ ] Specify merge rules for versioned Interface Mapping Revisions separately from immutable semantic objects; use revision/CAS baselines and fail on same-key or otherwise ambiguous conflicts.
  - Compare 48 native Git ref schedules over separately mutable bindings and exports. Own-ref CAS publishes six ineligible combinations. Fresh validation without verifying the peer publishes two. A fresh exact tuple check with transactional peer verification publishes all six valid proposals and rejects the rest. Production concurrency, recovery and authorization remain open. [Cross-map ref revalidation](research/toolchain-and-collaboration/RT-24/RT-24-CROSS-MAP-REFS-2026-11-25.md)
  - A Git publication fixture binds the materialized mapping bytes to the exact semantic catalog and branch commit. [Mapping tree publication](research/toolchain-and-collaboration/RT-23/RT-23-MAPPING-TREE-PUBLICATION.md)
  - Compare native conflict-cache reuse across 20 recreated merges. Git reapplies one cached text resolution in every case. Eight select the wrong exact caller target after a policy or parent-role change. An exact scoped approval preserves eight reuses and requires a new decision for 12. General impact closure, issuer trust and publication remain open. [Scoped rerere reuse](research/toolchain-and-collaboration/RT-24/RT-24-RERERE-SCOPED-RESOLUTION-2026-11-25.md)
- [ ] Design a repository-level merge coordinator with complete tree context. Do not treat independent per-file merge-driver success as proof of whole-SPG consistency.
  - A closed replay fixture detects a missing semantic patch even when the candidate tree imports and its parent matches. [Semantic patch reconciliation](research/toolchain-and-collaboration/RT-24/RT-24-SEMANTIC-PATCH-RECONCILIATION.md)
- [ ] Integrate the semantic engine with ordinary Git merge/rebase/cherry-pick. Prototype the custom merge driver and interactive mergetool, explicit local setup/doctor behavior, and fail-closed behavior when the coordinator or required context is unavailable.
  - [x] Compare local Git hook coverage across eight workflow variants with valid and invalid exact staged graphs. Five reject the invalid candidate before its branch changes. Cherry-pick, merge-backend rebase and merge with verification disabled install it despite post-hook failure. An apply-backend rejection leaves the branch unchanged and HEAD detached at the onto commit. [Native Git hook boundary](research/toolchain-and-collaboration/RT-24/RT-24-NATIVE-GIT-HOOKS-2026-11-24.md).
  - Native one-commit replay demonstrates that textual success and correct ancestry still need source closure and typed patch correspondence. [Git replay closure](research/toolchain-and-collaboration/RT-24/RT-24-GIT-REPLAY-SOURCE-CLOSURE.md)
  - [x] Compare multi-commit rebase, cherry-pick and explicit squash. Nine candidates share one terminal tree. Two retained chains contain an unclosed prefix and two have closed but unapproved prefix roots. One terminal check cannot certify retained history. [Multi-commit replay prefixes](research/toolchain-and-collaboration/RT-24/RT-24-MULTI-COMMIT-REPLAY-PREFIXES-2026-11-24.md).
  - Compare 14 native histories with recreated merges. All close, but two expected final roots hide an intermediate merge-only caller change. Checking the caller before and after reconstructs six exact replays and refuses four conflicting or unsupported changes. Originally conflicted merges and production publish policy remain open. [Merge-only changes after rebase](research/toolchain-and-collaboration/RT-24/RT-24-REBASE-MERGE-RESIDUALS-2026-11-25.md)
- [ ] After Git creates a candidate merged tree, import/reconcile the complete LLMLang representation into the shared semantic state; run repository-wide graph/reference/contract checks and RT-20 caller-impact, per-call-site migration, hash-propagation, and evidence checks.
  - Compare five publication policies over nine native Git histories with independently passing parent builds. Parent-only checks publish three invalid candidates, and provider-name reuse publishes one. Fresh exact checking publishes all five valid candidates and rebuilds each from a clean clone. General authority, concurrency and whole-SPG closure remain open. [Configured native merge](research/toolchain-and-collaboration/RT-24/RT-24-CONFIGURED-MERGE-PUBLICATION-2026-11-25.md)
  - [x] Compare state-bound and provider-only evidence across native merges of a guarded routing edit and a provider edit. Both branches pass in all three cases. Provider-only coverage misses the invalid combination, while state-bound coverage identifies two gaps that fresh validation resolves. General source/authority and production integration remain open. [Guarded merge evidence](research/toolchain-and-collaboration/RT-24/RT-24-GUARDED-MERGE-EVIDENCE-2026-11-25.md).
  - [x] Compare native Git per-ref, transaction-tip and newly reachable history gates in ten local receives. The tip gate accepts a closed tip with an unclosed ancestor. The incremental history gate rejects it when newly reachable and depends on the receiver baseline for existing history. Per-ref rejection can still update a different branch on a non-atomic push. [Receive gate evidence](research/toolchain-and-collaboration/RT-24/RT-24-NATIVE-RECEIVE-GATE-2026-11-24.md).
- [ ] Finalize only through RT-23's synchronized commit protocol: pin the exact semantic snapshot, mapping revision, worktree generation, selected regular-file changes, expected Git ref, and validation evidence; materialize canonical LLMLang representation and selected files into the actual worktree; commit them together.
  - [x] Interleave two native Git receives across dependent program and catalog refs. Both pass against the old peer even with a validator lock and separate atomic pushes. A lock spanning receive and commit rejects the second writer until it can revalidate the changed peer. An atomic compatible batch succeeds. Enforcement against all ref writers remains required. [Concurrent receive validation](research/toolchain-and-collaboration/RT-23/RT-23-CONCURRENT-RECEIVE-VALIDATION-2026-11-24.md).
  - [x] Exercise dependent Git ref verification inside exact native transactions on files and reftable. Both reject a stale peer when the dependency is verified. Files also adds the peer lock explicitly while reftable serializes the compared prepared cases. A verified retry fails after the original baseline changes. [Dependent ref verification](research/toolchain-and-collaboration/RT-23/RT-23-DEPENDENT-REF-VERIFICATION-2026-11-24.md).
  - [x] Compare exact-tree publication and checkout synchronization across linked worktrees. Eight cases show scoped preflight catches existing edits and a shared lock defers a cooperating writer. An ordinary edit during ref prepare can still change the checkout while the correct commit and receipt are published. Enforceable writer boundaries and filesystem synchronization remain open. [Linked-worktree publication](research/toolchain-and-collaboration/RT-23/RT-23-LINKED-WORKTREE-PUBLICATION-2026-11-24.md).
  - [x] Compare native multi-file readers across pointer switches, Git ref updates, mutation and reclamation. Three mixed reads pass closed import and reconstruct a third root. Pinned Git and retained immutable directories preserve the original view, and a pinned manifest rejects mixed bytes. Acquisition races, writer enforcement and storage durability remain open. [Pinned generation reads](research/toolchain-and-collaboration/RT-23/RT-23-NATIVE-GENERATION-READS-2026-11-25.md).
- [ ] Specify idempotent recovery for interruption before/after Git ref update, timeout with unknown outcome, stale HEAD/tree, partial export, and repeated completion requests. Never report semantic state as committed merely because it exists in the Toolchain store.
  - Compare 42 native recovery calls when an append and its SQLite receipt are separated by process termination. The exact framed-operation policy gives eight correct successes and six refusals. Blind retry and latest payload report 11 and nine wrong successes. Stable namespace, write interruption, durable storage and production integration remain open. [Mutable log recovery](research/toolchain-and-collaboration/RT-19/RT-19-MUTABLE-LOG-RECOVERY-2026-11-25.md)
  - [x] Interrupt native Git after ref prepare on files and reftable. Both preserve the old branch and absent receipt, but abandoned locks block immediate retry. The reftable lock also blocks an unrelated ref write. Production lock ownership, commit-phase observation and power-loss durability remain open. [Prepared ref crash](research/toolchain-and-collaboration/RT-23/RT-23-GIT-PREPARED-REF-CRASH-2026-11-24.md).
  - [x] Compare commit-phase observation in the files and reftable backends. A stopped files writer exposes the new branch without its receipt, even to one Git enumeration. A reftable table-list switch exposes both in the tested cut. Multi-call readers, recovery policy and power-loss durability remain open. [Ref commit visibility](research/toolchain-and-collaboration/RT-23/RT-23-REF-COMMIT-VISIBILITY-2026-11-24.md).
  - [x] Compare paired ref recovery with one protected journal ref and delayed branch projection at native Git process stops. Both backends recover the exact journal decision and idempotent projection. A conflicting branch move is preserved, and default clones need an explicit fetch of the journal. Trust, remote visibility, lock recovery, worktree state and power-loss durability remain open. [Single-ref journal recovery](research/toolchain-and-collaboration/RT-23/RT-23-SINGLE-JOURNAL-REF-2026-11-24.md).
  - [x] Compare Git snapshot retention after a branch rewrite on files and reftable. OID-only reads lose the old root after collection. Reader refs and journal ancestry retain it, and explicit fetch recovers it in clean clones. Verified current-read acquisition rejects a moved branch. Lease ownership, expiry, maintenance and remote policy remain open. [Pinned Git retention](research/toolchain-and-collaboration/RT-23/RT-23-PINNED-GIT-RETENTION-2026-11-25.md).
- [ ] Add real temporary-repository end-to-end tests for clone/reconstruction, parallel branches, merge/rebase/cherry-pick, cross-file conflicts, mapping conflicts, RT-20 caller splits, clean and failed validation, crash recovery, and no-duplicate commit retry.
  - [x] Compare explicit and virtual bases in 28 native criss-cross repositories. Six clean default merges per backend lack agreed real-base observations. A candidate all-base gate publishes four convergent cases and preserves the old ref in every refusal. General ancestry, authorization and synthesis policy remain open. [Multiple merge bases](research/toolchain-and-collaboration/RT-24/RT-24-MULTIPLE-MERGE-BASES-2026-11-25.md)
- [ ] Benchmark repository-level merge, semantic import/export, incremental worktree synchronization, and cache/store reconstruction; record platform and repository-size assumptions.

**Status:** architecture research exists and is cross-linked; RT-24 records a candidate technical contract, and its bounded source-closure/merge-tree fixture is reproduced on Git 2.52.0/CPython 3.12.14 (workflow #45072410771, 11/11 tests). Canonical representation, identity/schema reconciliation, a general semantic diff/merge implementation, multi-commit replay/conflict handling, and concurrent Git publication remain open. ADR-014 remains Proposed.

**Dependency:** canonical SPG/identity and import/export decisions from Stages 1 and 3; RT-20 impact-plan correctness; RT-19 semantic API; RT-22 repository/worktree contract; RT-23 shared-state and synchronized-commit runtime.

**Exit criteria:** clean clone reconstructs the exact declared semantic state; commits map deterministically to semantic snapshots and mapping revisions; repository-level semantic merge works for independent and conflicting changes; merged graphs pass RT-20 impact/hash/caller checks; the exact validated semantic state and selected regular files are synchronized into one recoverable Git commit; merge/rebase/cherry-pick, fallback, interactive resolution, and crash recovery are tested.

---

# Stage 5 — Types, execution model, runtime, and POSIX

**Order:** after the semantic core and initial proof boundary; a small vertical slice should be chosen early.  
**Purpose:** define what programs mean when executed and how LLMLang interacts with systems.

## 5.1 Type system and data model

**Estimated research complexity:** **8/10** — overlaps the unresolved RT-04 type, ownership, effect, and capability architecture.

- [ ] Define primitive and algebraic data types.
- [ ] Compare structural and nominal typing.
- [ ] Research generic and polymorphic types.
  - Compare inlined and separately linked static specializations, Rust trait objects and explicit dictionaries across 18 native links and 18,432 results. Cross-linking stale caller objects changes 1,024 inlined results while the other three routes use the linked provider throughout. A nondependent edit changes the provider archive but preserves the caller object bytes. Generic SPG lowering, ABI policy and representative measurements remain open. [Generic provider binding](research/semantic-representation/RT-05/RT-05-GENERIC-PROVIDER-BINDING-2026-11-25.md)
- [ ] Evaluate refinement types and dependent types.
- [ ] Define typed states, state transitions, and constrained values.
- [ ] Define ownership, borrowing, lifetimes, references, and aliasing.
- [ ] Define mutability and resource management.
  - Compare 9,216 Rust and C++ runs of staged record construction and transfer. Implicit teardown agrees on 1,008 early-exit pairs but differs on all 144 completed pairs. An explicit release sequence yields equal graphs for all 36 paired sources and equal behavior in every tested input. Destructors that fail, ABI, other profiles and independent review remain open. [Cross-profile record cleanup](research/semantic-representation/RT-05/RT-05-CROSS-PROFILE-RECORD-CLEANUP-2026-11-25.md)
- [ ] Define effects, capabilities, and error types.
- [ ] Define type inference and explicit annotations.
- [ ] Define compatibility between types exposed by different implementations.
- [ ] Determine which guarantees are enforced by types, contracts, or proofs.

**Existing evidence:** concept and formal-verification research; typed requirement and typed relational IR prototypes.

**Status:** partially researched; complete language type-system design remains open.

## 5.2 Execution semantics and runtime architecture

**Estimated research complexity:** **9/10** — combines execution, resource lifecycle, cancellation, scheduling, concurrency, and observable behavior.

- [ ] Define interpreter/reference execution.
- [ ] Define VM requirements, if a VM is needed.
- [ ] Define runtime representation of values and semantic calls.
- [ ] Define explicit call binding to immutable operation identity.
- [ ] Define error propagation, cancellation, and resource cleanup.
  - Compare a two-client native worker in CPython and Rust O0/O3 across 72 controlled runs. Checking only at admission permits three revoked write attempts. Immediate terminal cancellation reports six apparently completed results while a handle is open. A fresh effect gate and post-close terminal settlement preserve all expected outcomes. Uncontrolled scheduling and runtime integration remain open. [Native worker settlement](research/language-design/RT-01/RT-01-RESOURCE-WORKER-SETTLEMENT-2026-11-25.md)
  - [x] Compare a native blocked Linux pipe read with cooperative eventfd cancellation. Closing and reusing a descriptor leaves an existing read pinned to the original pipe. Six cases distinguish EOF, cancellation and delivery, including two-ready outcome priority and terminal byte settlement. Foreign I/O, portability and controlled timing remain open. [Linux read cancellation](research/runtime-and-systems/RT-26/RT-26-LINUX-READ-CANCELLATION-2026-11-24.md).
- [ ] Research first-class resource accounting and enforcement for task scopes and task hierarchies: memory, CPU, disk I/O, network I/O, coroutine/task switches, and hardware/software performance counters.
  - [x] Check task CPU attribution across two native pthread workers, including cleanup after cancellation. Per-dispatch sums follow the migrating task. Origin-thread spans undercount without a peer and overcount with a peer, while cross-clock subtraction can be negative. Production overhead and enforcement remain open. [Migrating task CPU](research/runtime-and-systems/RT-26/RT-26-MIGRATING-TASK-CPU-2026-11-24.md).
  - [x] Compare delivered and dequeued bytes on native TCP and UDP. A four-byte buffer preserves the stream tail but consumes a full 16-byte datagram. A second receiver can invalidate a previously admitted datagram length. Wire counters, portable settlement and coordinated socket access remain open. [Linux socket byte settlement](research/runtime-and-systems/RT-26/RT-26-LINUX-SOCKET-BYTE-SETTLEMENT-2026-11-24.md).
  - [x] Compare Linux address-space admission with native residency sampling. Discarding all 768 touched pages leaves an additional mapping denied until unmap, and two locally admitted workers exceed the corresponding shared virtual-length bound. Physical charging, cgroups and portable group accounting remain open. [Linux mapping residency](research/runtime-and-systems/RT-26/RT-26-LINUX-MAPPING-RESIDENCY-2026-11-24.md).
  - [x] Compare spanning and dispatch-based CPU attribution on one asyncio thread. The spanning totals double-charge a 60 ms sibling interval; three dispatch segments include the reader’s cleanup even on cancellation. Production scheduler, migration and hardware counters remain open. [Coroutine CPU attribution](research/runtime-and-systems/RT-26/RT-26-COROUTINE-CPU-ATTRIBUTION-2026-11-24.md).
  - [x] Compare summed RSS and PSS for two processes mapping shared and copy-on-write pages. Summed RSS stays at 4 MiB after writing half the mapping in either profile, while PSS rises from 2 to 3 MiB only in the copy-on-write case. Outside-owner charging and cgroups remain open. [Linux shared-memory attribution](research/runtime-and-systems/RT-26/RT-26-LINUX-SHARED-MEMORY-ATTRIBUTION-2026-11-24.md).
  - [x] Check Linux perf availability for two hardware and three software events on the current thread. All five return EPERM in the measured environment. Native thread CPU and getrusage counters pass independent controls. PMU and cross-target evidence need a supported environment. [Linux performance counters](research/runtime-and-systems/RT-26/RT-26-LINUX-PERFORMANCE-COUNTER-BOUNDARY-2026-11-24.md).
- [ ] Define real-time resource limits, quotas, budgets, rate limits, and throttlers, including hierarchical aggregation, inheritance, delegation, and contention between parent/child tasks.
  - [x] Compare native Linux process CPU limits with cumulative child usage. Soft and hard limits yield distinct termination evidence. Two individually admitted workers exceed a one-second group budget, and reaping preserves both charges. Live group enforcement and portable accounting remain open. [Linux CPU budgets](research/runtime-and-systems/RT-26/RT-26-LINUX-PROCESS-CPU-BUDGET-2026-11-24.md).
- [ ] Define limit-exceeded events and typed handlers/policies that can decide whether to continue, throttle, pause, cancel, retry, degrade, shed work, escalate, or terminate; specify overshoot, race, and handler-failure behavior.
  - In a closed task tree, cancellation can stop new admissions immediately. Releasing existing capacity requires terminal settlement. [Cancellation accounting](research/runtime-and-systems/RT-26/RT-26-CANCELLATION-ACCOUNTING.md)
  - [x] Compare Linux file-size enforcement and a shared live-byte reservation. Two files can exceed a 4,096-byte group limit by 2,048 even when each child obeys its file limit. Serialized admission and terminal file-length settlement respect the fixture cap and retain charges for surviving files. [Linux file budget settlement](research/runtime-and-systems/RT-26/RT-26-LINUX-FILE-BUDGET-SETTLEMENT-2026-11-24.md).
- [ ] Determine which resource controls belong in high-level language semantics and APIs versus runtime, OS/container, and deployment integrations; preserve explicit capability and portability boundaries.
- [ ] Define memory model and concurrency semantics.
- [ ] Define threads, synchronization, atomics, signals, blocking I/O, and scheduling boundaries.
- [ ] Define capability and security model.
- [ ] Define trusted low-level primitives and their contracts.
- [ ] Define runtime versioning and its contribution to implementation identity.

**Status:** partially validated in bounded execution models. The atomic load and store fragment derives read-from and happens-before and checks all four coherence rules. An independent interleaving oracle agrees on global-order witnesses for 4,096 layouts. RMW predecessors, release sequences and three fence linkages were checked with complete finite outcome comparisons and two solvers. Broader mixed-order semantics, source correspondence and backend validation remain open. [RMW and fences](research/language-design/RT-04/RT-04-RMW-RELEASE-SEQUENCES-AND-FENCES-2026-11-24.md). [Coherence fixtures](research/language-design/RT-04/RESEARCH-SCENARIO-117-ATOMIC-WRITE-READ-COHERENCE.md) · [Execution relations](research/language-design/RT-04/RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md)

**Resource accounting evidence (2026-11-21)** · A bounded RT-26 model compares separate checks with serialized hierarchical reservation. Separate checks overshoot in four of six schedules. The serialized ledger matches direct subtree accounting across 4,320 transitions. Runtime and OS enforcement measurements remain open. [Cooperative budget reservation](research/runtime-and-systems/RT-26/RT-26-COOPERATIVE-BUDGET-RESERVATION.md)

**Research output (2026-11-21)** · Across 1,260 orderings of nested task events, a transitive join matches the lifetime oracle. Publishing after direct task bodies leaves live loans in 198 schedules. [RT-10 structured scope join](research/runtime-and-systems/RT-10/RT-10-STRUCTURED-SCOPE-JOIN.md)

## 5.3 POSIX architecture and conformance

**Estimated research complexity:** **9/10** — platform profiles, API semantics, conformance evidence, and runtime boundaries.

- [ ] Select initial POSIX edition and explicit conformance profile.
- [ ] Define LLMLang-facing API: close POSIX mapping versus safer typed facade.
- [ ] Define a shared contract for multiple POSIX implementations.
- [ ] Separate portable runtime implementation from native Linux syscall implementation.
- [ ] Define conformance evidence, optional features, and implementation-defined behavior.
- [ ] Define error, resource, process, file, and descriptor semantics.
- [ ] Define concurrency and environment-dependent behavior.
  - A blocking pipe probe distinguishes returned EINTR from a handled signal followed by a restarted read. [POSIX read interruption](research/runtime-and-systems/RT-10/RT-10-POSIX-READ-INTERRUPTION.md)
- [ ] Define initial vertical slice, such as process startup, basic file I/O, and errors.
- [ ] Select initial Linux architecture and isolate syscall ABI details.
- [ ] Define how existing C libraries and external ABI boundaries are called.
- [ ] Define the trusted low-level runtime boundary.
- [ ] Compare behavior using conformance, differential, and contract-derived tests.
- [ ] Define precisely what POSIX compatibility and formal verification claims cover.

**Existing evidence:** `research/POSIX-RUNTIME-ARCHITECTURE.md`; related open questions LL-013–LL-019 in `TODO.md`.

**Research output (2026-11-21)** · Libc and raw Linux x86-64 adapters match 112 expected nonblocking pipe observations, including short transfer, would-block, EOF and SIGPIPE. [RT-10 pipe I/O](research/runtime-and-systems/RT-10/RT-10-POSIX-NONBLOCKING-PIPE-IO.md)

**Status:** partially validated for the bounded POSIX pipe fixture. The overall profile, wider conformance, and runtime integration remain open.

**Exit criteria:** a small typed executable subset; reference execution; one POSIX vertical slice with explicit contracts and conformance scope; tests for observable behavior and error cases.

## 5.4 Freestanding embedded and real-time firmware (RT-37)

**Status:** Bounded Cortex-M3 startup and timer/GPIO slices validated in QEMU. **Priority:** P0 shared foundation; P1 pilot. [Research brief](research/runtime-and-systems/RT-37/README.md) · [Issue #440](https://github.com/aivibeflow/LLMLang/issues/440).

- [ ] Compare OS-independent target profiles, explicit runtime closure, startup/linking, memory layouts, static-only and explicit allocator policies.
- [x] Compare statically sized slots and a checked linear cursor in a linked 64-byte Cortex-M3 arena. Four LLVM/Rust images reproduce 2,704 reservation observations. Fixed slots admit four small requests where the linear policy admits sixteen, and an omitted-size-guard control wraps the cursor. [Cortex-M3 bounded allocator](research/runtime-and-systems/RT-37/RT-37-CORTEX-M3-BOUNDED-ALLOCATOR-2026-11-24.md).
- [x] Compare Cortex-M3 reset, data/BSS initialization, fixed-width controller execution and ELF runtime closure on direct LLVM and freestanding Rust. Five images reproduce 14 UART steps each. A bootable image with an undefined unwind symbol and two other unresolved-runtime controls distinguish closure from functional replay. [Cortex-M3 closure](research/runtime-and-systems/RT-37/RT-37-CORTEX-M3-FREESTANDING-CLOSURE-2026-11-24.md).
- [ ] Specify typed MMIO/volatile, peripheral protocols, SVD ingestion, interrupts, DMA, transitive effects and capabilities.
- [x] Compare DMA handback under endpoint-only, wrapping, retiring and natural-number lease identities. Lean checks ownership, device bounds, matching completion/quiescence and synchronized acquire. A 5,628-transition replay and stale-reuse controls distinguish the policies. Concrete descriptor, queue drain and cache evidence remain open. [DMA lease ownership](research/runtime-and-systems/RT-37/RT-37-DMA-LEASE-OWNERSHIP-2026-11-24.md).
- [x] Compare layout-only, direction-only and protocol-aware admission on 33 Cortex-M3 MMIO requests. Exact SVD and header import supply structural data, while explicit clear/read effects, masked aliases and a checked device profile distinguish 14 over-admissions from access direction alone. Keep physical LM3S metadata and general volatile lowering open. [MMIO metadata and capabilities](research/runtime-and-systems/RT-37/RT-37-MMIO-METADATA-AND-CAPABILITIES-2026-11-24.md).
- [x] Check read-to-clear SysTick access preservation in seven Cortex-M3 builds. LLVM and Rust volatile paths retain two word loads and observe `10`. Ordinary LLVM O0 retains both IR loads and executes one linked load, observing `11`. A nonzero write to `VAL` confirms the reset effect. [Cortex-M3 volatile COUNTFLAG](research/runtime-and-systems/RT-37/RT-37-CORTEX-M3-VOLATILE-COUNTFLAG-2026-11-24.md).
- [x] Compare root-only, supplied and linked call graphs for transitive ISR effects. Exact Cortex-M3 vector and leaf binding admits two acknowledgement paths, rejects three blocking/allocation artifacts, and retains `UNKNOWN` for unresolved or stale evidence. [Transitive ISR effects](research/runtime-and-systems/RT-37/RT-37-CORTEX-M3-TRANSITIVE-ISR-EFFECTS-2026-11-24.md).
- [ ] Investigate stack/flash/RAM bounds, target-specific WCET, deadlines, interrupt latency, RTOS integration, and hardware assumptions.
- [x] Compare stack bounds for the bounded Cortex-M3 timer workload. Twelve QEMU images match the static direct-control model with 8 B for polling, 32 B for aligned SysTick and 40 B for the alignment control. A phase-independent bound is 40 B for either interrupt image under the single basic exception assumption. [Cortex-M3 stack](research/runtime-and-systems/RT-37/RT-37-CORTEX-M3-STACK-BOUND-2026-11-24.md).
- [x] Produce a pinned Cortex-M bootable timer/GPIO firmware pilot with independent reference traces, negative controls and separately scoped functional/static resource evidence. Four LLVM and Rust images reproduce 14 duty and GPIO steps each. SysTick pending-state and GPIO masking controls distinguish outcomes hidden by the application trace. [Cortex-M3 timer and GPIO](research/runtime-and-systems/RT-37/RT-37-CORTEX-M3-SYSTICK-GPIO-2026-11-24.md).

**Dependencies:** RT-03/04/07/08/09/10/13/16/32/33/34/36; Stage 6 native lowering. **Exit:** reproducible profile comparison and firmware execution evidence, explicit unsupported operations and trust boundaries. No language rule selected.

---

# Stage 6 — Translation, backends, implementation selection, and optimization

**Order:** after a reference semantics and a stable semantic subset exist.  
**Purpose:** realize the same source semantics on multiple targets without making any target language the source of truth.

## 6.1 Translation architecture

**Estimated research complexity:** **9/10** — source semantics and preservation obligations must survive multiple translation stages.

- [ ] Decide whether backends consume typed SPG directly or a normalized target-independent semantic IR.
- [ ] Define the lowering pipeline and preservation obligations.
- [ ] Define target capability declarations and unsupported constructs.
- [ ] Define explicit translation outcomes: exact under assumptions, preserved with runtime support, restricted, unsupported, and unverified.
- [ ] Define runtime support as part of a target realization.
- [ ] Define generated artifact identity and reproducibility.
- [ ] Define verification independent of the code generator wherever practical.
- [ ] Define incremental translation and selective verification invalidation.

**Existing evidence:** `research/TRANSLATION-AND-TARGET-BACKENDS.md`, `research/LLVM-BACKEND-ARCHITECTURE.md`, and formal-verification research.

**Research output (2026-11-21)** · Direct SPG execution and a lowered instruction stream agree with an independent oracle over 140 observations. An operation-binding change alters the reachable artifact while leaving the caller address fixed. [Ordered SPG lowering](research/compiler-and-translation/RT-09/RT-09-ORDERED-SPG-LOWERING.md)

**Status:** partially validated for the scalar instruction fixture. External code generation, canonical IR and general preservation remain open.

### Required bidirectional translation study (RT-30)

- [ ] Research automated LLMLang → C, C++, Go, and Rust translation and C/C++/Go/Rust → LLMLang import as separate directions.
- [ ] Define a source/target matrix, semantic observation model, preservation contracts, and explicit exact/runtime-supported/restricted/partial/unverified/unsupported outcomes.
- [ ] Compare canonical semantic IR, direct SPG lowering, and hybrid representations; preserve source provenance without conflating it with semantic identity.
- [ ] Evaluate whether a dedicated C runtime can implement high-level LLMLang features while keeping LLMLang—not C—as the semantic source of truth; compare runtime requirements and costs for all four targets.
- [ ] Cover same-language round trips, cross-target migration, mixed-language modules, ABI/FFI, source-language undefined/implementation-defined behavior, and incremental regeneration.
- [ ] Build differential conformance fixtures for both directions and a bounded bidirectional vertical slice with pinned compilers, runtimes, and platform profiles.

**Research brief:** [RT-30 — Bidirectional Semantic Translation](research/compiler-and-translation/RT-30/RT-30-BIDIRECTIONAL-SEMANTIC-TRANSLATION.md). Coordinate with RT-13, RT-28, and RT-29. This is a research goal, not a claim that all programs in the four languages are translatable.

## 6.2 Backend selection and cross-backend validation

**Estimated research complexity:** **9/10** — requires at least two independently validated realizations of a shared semantic subset.

- [ ] Define the minimal common semantic subset for backend experiments.
- [ ] Evaluate Python as an experimental/reference target.
- [ ] Evaluate Go as the first serious compiled target.
  - [x] Generate Go for the same checked integer fixture and replay 197,440 observations in each of two hosted forms. The cgo library exposes all 64 C ABI entries and needs libc. The standalone executable has no ELF needed libraries. Broader hosted capabilities and target selection remain open. [Generated Go integer lowering](research/compiler-and-translation/RT-13/RT-13-GENERATED-GO-INTEGER-LOWERING-2026-11-24.md).
- [ ] Evaluate Rust for ownership and systems-language coverage.
  - [x] Link generated COR-13 Rust callers to a separately compiled C provider that uses Linux event descriptors. Two profiles match 125,952 traces and physical audits each. Indeterminate outcomes keep role obligations in both physical states, while collapsing foreign errors changes 9,680 rows in the control. Foreign provider contracts and concurrent reconciliation remain open. [Native owned-result ABI](research/compiler-and-translation/RT-13/RT-13-NATIVE-OWNED-ABI-2026-11-24.md).
  - [x] Compare two exact native provider bindings on one checked COR-13 recovery caller, in an independent C route and generated Rust. Across both routes all 167,936 source and descriptor observations match. Rebinding at the same caller and contract changes 5,720 rows per transfer order. The disposition decoding model is checked separately in Lean. General source correspondence, FFI policy and portability remain open. [Bound owned providers](research/compiler-and-translation/RT-13/RT-13-BOUND-OWNED-PROVIDERS-2026-11-25.md).
- [ ] Evaluate C++ for ABI and platform coverage.
  - [x] Compile the same 64 integer programs as C++20 with GCC and Clang at O0 and O3. All profiles match 197,440 status, slot and callback observations and link all C ABI entries without undefined object symbols. Further platform, ownership and native C++ API coverage remain open. [Generated C++ integer lowering](research/compiler-and-translation/RT-13/RT-13-GENERATED-CPP-INTEGER-LOWERING-2026-11-24.md).
- [ ] Consider Java as an alternative compiled target.
  - [x] Generate Java 21 class files from the shared integer fixture. Interpreted and compiled HotSpot profiles each match 197,440 observations. The compilation log confirms all 64 entry methods. JVM deployment, native ABI and resource lifetime coverage remain separate gates. [Generated Java integer lowering](research/compiler-and-translation/RT-13/RT-13-GENERATED-JAVA-INTEGER-LOWERING-2026-11-24.md).
- [ ] Implement two backends for the same subset.
- [ ] Compare each backend against the same reference semantics and scenario corpus.
  - [x] Compare generated Rust and direct LLVM over all 64 integer fixture programs at O0 and O3. Each profile matches 197,440 status, output and callback observations. Rust O0 with debug assertions needs a panic symbol absent from the four successful objects. Both routes use an LLVM compiler family, and broader backend evidence remains open. [Generated Rust integer lowering](research/compiler-and-translation/RT-13/RT-13-GENERATED-RUST-INTEGER-LOWERING-2026-11-24.md).
  - [x] Compare generated Go and Rust on the same checked COR-13 owned-result sources. Each of four compiled profiles matches 62,976 complete traces, including cleanup failure, caller release, aliased role checks and terminal obligations. General source lowering and native resource correspondence remain open. [Generated Go owned outcomes](research/compiler-and-translation/RT-13/RT-13-GENERATED-GO-OWNED-OUTCOMES-2026-11-24.md).
- [ ] Compare return values, errors, state changes, and declared observable effects.
- [ ] Reject silent semantic weakening; report restrictions explicitly.
  - Compare native record layouts over 2,048 C calls and 16 exact ELF artifacts. Symbol plus size/alignment admits 478 incorrect vectors. DWARF/ELF comparison detects inaccurate field locations and widths. Matching layout with changed behavior still fails the exact output check. Eight artifacts satisfy both within the fixture. By-value and cross-target ABI remain open. [Native record layout](research/compiler-and-translation/RT-13/RT-13-NATIVE-RECORD-LAYOUT-2026-11-25.md)

**Existing evidence:** target selection recommendation in `research/TRANSLATION-AND-TARGET-BACKENDS.md`.

**Research output (2026-11-21)** · Direct LLVM and C++ realizations of one checked mutable byte-view operation match a Python oracle over 470,400 comparisons. An invalid LLVM alias annotation changes an ordered observation under O3 while preserving the final slab. [RT-09/13 mutable byte views](research/compiler-and-translation/RT-09/RT-09-13-MUTABLE-BYTE-VIEW-PRESERVATION.md)

**Status:** partially validated for this sequential mutable byte-view fixture. Broader cross-backend validation and initial target selection remain open.

## 6.3 LLVM backend

**Estimated research complexity:** **9/10** — lowering, UB/poison, target behavior, and source-to-IR preservation.

- [ ] Preserve the LLMLang-owned semantic source of truth and replaceable backend boundary; do not make LLVM IR the canonical semantic IR.
- [ ] Define a conservative LLVM IR subset and source-to-LLVM lowering contract.
- [ ] Research poison, undef, overflow flags, pointer provenance, aliasing, floating-point flags, atomics, and memory ordering.
  - [x] Compare split and fused binary64 rounding over 6,859 triples in C, Rust and Java. GCC contraction emits FMA and changes 77 outcomes. Explicit FMA matches the value oracle in all six profiles, while raw NaN bits differ in 114 cases. IR flags, exception modes, other architectures and broad lowering remain open. [Binary64 contraction](research/compiler-and-translation/RT-13/RT-13-BINARY64-CONTRACTION-2026-11-25.md).
  - [x] Compare verifier-admitted LLVM `contract`, `nsz` and `nnan` on matched binary64 inputs. O3 contraction changes 77 outcomes, `nsz` changes the result for the negative-zero input, and `nnan` folds the classifier within its checked input domain. Strict and explicit fused operations match their oracles. Dynamic rounding, broader flags and source proofs remain open. [LLVM floating-point flags](research/compiler-and-translation/RT-13/RT-13-LLVM-FP-FLAGS-2026-11-25.md).
- [x] Compare byte and word atomic lowering at O0/O3 for RV64, AArch64 and x86-64. RV64 with and without Zabha passes the two-hart fixture, while RV64 without native atomic support requires runtime helpers. An x86-64 text comparison cannot distinguish the moved-fence control. [Atomic lowering comparison](research/compiler-and-translation/RT-13/RT-13-ATOMIC-BYTE-WORD-LOWERING-2026-11-24.md).
- [ ] Define how LLVM optimization passes and target code generation are validated against LLMLang semantics.
  - [x] Compare dynamic binary64 rounding and sticky exception flags under ordinary, literal constrained and parameterized LLVM operations. Two LLVM 19.1.7 optimizer builds fold constrained literal cancellation to positive zero under downward rounding. The parameterized route matches all 80 cases per pipeline. Version fixes, LTO and broader semantics remain open. [Dynamic rounding](research/compiler-and-translation/RT-13/RT-13-LLVM-DYNAMIC-ROUNDING-2026-11-25.md).
  - [x] Compare native, full LTO and ThinLTO links across three pinned LLVM versions. Both LTO modes fold the inlined literal cancellation to positive zero. Retaining the call or loading operands dynamically preserves the downward negative zero in all nine profiles. Broader operations, portability and costs remain open. [Dynamic rounding through LTO](research/compiler-and-translation/RT-13/RT-13-LLVM-DYNAMIC-ROUNDING-LTO-2026-11-25.md).
  - The signed-add fixture checks the exact optimized IR under a source observation model, including no store on overflow and ordered callbacks. Native evidence confirms the selected counterexamples. [Checked-add observation validation](research/compiler-and-translation/RT-13/RT-13-LLVM-CHECKED-ADD-OBSERVATIONS-2026-11-24.md).
- [ ] Evaluate Alive2 and Vellvm and their applicability/limitations.
  - [x] Record bounded applicability on scalar, poison, alias, local atomics and fences. Vellvm passes 18 concrete checks and fails a false assertion. Alive2 explicitly reports unsupported atomics and fences. Stock Alive2 with exception-enabled LLVM reproduces the results with packaged or upstream LLVM verification tools. Broader concurrency and source-to-LLVM semantics remain open. [LLVM validation coverage](research/compiler-and-translation/RT-13/RT-13-ALIVE2-VELLVM-COVERAGE-2026-11-24.md) · [Stock replay](research/compiler-and-translation/RT-13/RT-13-STOCK-ALIVE2-LLVM-EH-2026-11-24.md).
- [ ] Define supported LLVM versions and reproducible toolchain identity.
  - [x] Reproduce the constrained downward cancellation discrepancy on exact LLVM 19.1.7, 22.1.4 and 23.1.1 drivers. Forced inlining changes negative zero even at O0. Retaining the call preserves all four cancellation modes in the witness. LTO, wider targets and the version policy remain open. [Dynamic rounding across LLVM versions](research/compiler-and-translation/RT-13/RT-13-LLVM-DYNAMIC-ROUNDING-VERSIONS-2026-11-25.md).
  - Debian LLVM/lld 19.1.7 emits working Wasm at O0 and O3 for the read-only view corpus. [LLVM to Wasm byte views](research/compiler-and-translation/RT-13/RT-13-LLVM-WASM-BYTE-VIEW-LOWERING.md)
- [ ] Build a target support matrix: architecture/CPU features, OS, ABI/calling convention, object format, linker, sysroot/system libraries, runtime, and required toolchain components.
  - Compare aggregate-by-value System V and Microsoft x64 conventions on Linux. Equal record layout and symbol names admit four incompatible direct proposals. Explicit declarations and a fixed pointer bridge each preserve all 1,024 native results in their route. Windows, other aggregates and production ABI evidence remain open. [By-value call conventions](research/compiler-and-translation/RT-13/RT-13-BY-VALUE-CALL-ABI-2026-11-25.md)
- [ ] Evaluate Cranelift as a candidate for fast Debug compilation and/or JIT; compare its supported targets, ABI/runtime integration, debug information, optimization behavior, and maintenance burden. Do not presume it should replace LLVM.
  - [x] Compare one ABI-bound checked-add fixture with Cranelift JIT and LLVM O0/O3. Across four profiles, 4,596 vectors each match the source evaluator. Record the target byte counts and six rejected mutants. Compilation latency, debug support and broader target coverage remain open. [Cranelift checked-add comparison](research/compiler-and-translation/RT-13/RT-13-CRANELIFT-CHECKED-ADD-2026-11-24.md).
- [ ] Define the evidence threshold for considering a direct native backend; first identify a concrete unmet requirement and estimate the full implementation/maintenance cost.
- [ ] Evaluate WebAssembly target profiles and whether LLVM or a dedicated toolchain provides the better fit.
  - A native-engine memory32 experiment verifies full-width arithmetic and logical view guards across 12,800 observations. [Wasm memory32 views](research/compiler-and-translation/RT-13/RT-13-WASM-MEMORY32-VIEWS.md)
- [ ] Specify a reproducible comparative benchmark protocol and shared workload corpus for LLVM, Cranelift, and any justified prototype backend.
- [ ] Measure cold and incremental compile latency/throughput, Debug and Release runtime performance, output size, peak memory, debug/diagnostic quality, target coverage, and toolchain/build complexity. Report distributions and workload-specific results; do not hide trade-offs in one aggregate score.
  - [x] Compare linked callback source origins using direct LLVM DWARF and generated Rust DWARF with a line map. Both O0/O3 routes recover the two exact source locations. Two attribution controls leave native behavior intact and fail the origin comparison. Debugger stepping and broader Debug coverage remain open. [DWARF callback origins](research/compiler-and-translation/RT-13/RT-13-DWARF-CALLBACK-SOURCE-ORIGINS-2026-11-24.md).
  - [x] Compare first and repeated in-process JIT materialization on one checked-add workload. With other builds paused, median Cranelift `none` is 277.0/101.5 µs and LLVM ORC O0 is 2,405.3/840.5 µs. Four profiles report distributions and independently checked results. Process startup, incremental and representative workload measurements remain open. [JIT materialization latency](research/compiler-and-translation/RT-13/RT-13-JIT-MATERIALIZATION-LATENCY-2026-11-24.md).
- [ ] Validate every candidate against the same reference semantics and adversarial conformance corpus; performance results do not waive semantic-correctness gates.
- [ ] Decide whether one backend or mode-specific backends (Debug/Release/JIT) are justified by the combined correctness, performance, portability, and maintenance evidence.
- [ ] Record the selected initial configuration, explicit non-goals, unsupported target combinations, fallback behavior, and criteria for revisiting the decision.

**Existing evidence:** `research/LLVM-BACKEND-ARCHITECTURE.md`; Scenarios 96, 96A, and 96B provide bounded source-to-LLVM preservation evidence, not a general backend validation.

**Status:** architectural recommendation exists; backend selection, comparative measurements, full target matrix, lowering validation, and target-specific correctness evidence remain open.

## 6.4 Implementation discovery, selection, and optimization

- [ ] Separate discovery of contract-compatible implementations from selection of a concrete implementation.
- [ ] Define selection constraints: target, ABI, capabilities, runtime, security, performance, and deployment environment.
- [ ] Define static binding versus runtime dispatch.
- [ ] Define specialization and multi-versioning.
- [ ] Define cost models and profile-guided selection.
- [ ] Define safe fallback when no compatible implementation is available.
- [ ] Define whether and how implementation choice can change without changing operation semantics.
- [ ] Measure dispatch and adaptation overhead.
- [ ] Define optimization across semantic nodes while preserving contracts.

**Existing evidence:** global semantic artifact store and POSIX runtime architecture.

**Status:** partially researched; selection semantics and policy remain open.

**Exit criteria:** two backends preserve the same reference semantics for a defined subset; target limitations are explicit; implementation selection never bypasses operation identity or compatibility evidence.

## 6.5 OS kernels and verified microkernel feasibility (RT-38)

**Status:** Bounded RV64 boot, scheduling, local Sv39 visibility and isolated IPC checked in QEMU. **Priority:** P1. [Research brief](research/runtime-and-systems/RT-38/README.md) · [Issue #441](https://github.com/aivibeflow/LLMLang/issues/441).

- [ ] Reuse RT-37 freestanding profile; specify privileged target capabilities, physical/virtual memory, MMU/TLB, trap/syscall ABI and context switching.
- [x] Compare RV64 bare PMP and Sv39 protections in five exact single-hart QEMU images. The same U-mode code distinguishes a protected read, a store to an RX page and trap recovery. Split PMP and correct Sv39 deny both accesses. An exposed Sv39 leaf restores the protected read. [RV64 PMP and Sv39 isolation](research/runtime-and-systems/RT-38/RT-38-RV64-PMP-SV39-TRAP-ISOLATION-2026-11-24.md).
- [x] Compare Sv39 remap and revoke with full, correct-address, wrong-address and missing translation fences. Ordinary memory ordering leaves stale reads in QEMU. Pinned QEMU overinvalidates, so exact linked operand checking distinguishes the wrong-address control. Selective hardware behavior and remote shootdown remain open. [Sv39 remap and revocation](research/runtime-and-systems/RT-38/RT-38-SV39-REMAP-REVOKE-2026-11-24.md).
- [x] Compare zero-on-allocation and zero-on-release using a three-frame RV64 Sv39 fixture, a separate ownership proof model and an independent operation trace. Dirty publication, leaked reservation and aliased mapping controls diverge. The checked allocation transactions run before translation is enabled. [RV64 frame ownership and rollback](research/runtime-and-systems/RT-38/RT-38-RV64-FRAME-ALLOCATOR-2026-11-24.md).
- [x] Compare cooperative round-robin and run-to-completion across four two-task RV64 workloads. Linked integer context checks and three QEMU controls distinguish a broken saved-register restore, a wrong stack and a repeated trap PC. [RV64 cooperative scheduling](research/runtime-and-systems/RT-38/RT-38-RV64-COOPERATIVE-SCHEDULER-2026-11-24.md).
- [x] Compare slot-only and generation-checked capability admission for one RV64 IPC endpoint. The slot-only control admits stale sends after regrant, while a bounded generation with retirement denies use after exhaustion. [RV64 IPC capability revocation](research/runtime-and-systems/RT-38/RT-38-RV64-IPC-REVOCATION-2026-11-24.md).
- [ ] Extend allocator and address-space contracts to live mappings, blocking and preemptive scheduling, and concurrent IPC and capability lifecycle, with global invariants and conditional hardware proofs.
- [ ] Replay selected seL4 proofs and evaluate implementing an LLMLang fragment against the original l4v specification. Assess Isabelle/HOL modeling, proof automation, counterexample search and reproducible replay. [Research plan](research/runtime-and-systems/RT-38/README.md#8-research-plan-for-implementing-against-an-existing-specification)
  - [x] Replayed upstream RISCV64 ASpec and ExecSpec, then checked one separately exported capability lookup wrapper and a behavior-preserving refactor against the original design in Isabelle/HOL. Three checked generic refutations distinguish wrong fault, slot and state effects. Reachable control witnesses, automatic counterexample search and checked LLMLang source binding remain open. [Capability lookup proof and replay](research/runtime-and-systems/RT-38/RT-38-SEL4-CAPABILITY-LOOKUP-ISABELLE-2026-11-24.md).
  - [x] Replayed upstream RISCV64 AInvs with one proof thread and checked four abstract lookup wrapper propositions, including capability, slot and fault validity under the original premises. Generated-source binding and the C link remain open. [Abstract lookup invariants](research/runtime-and-systems/RT-38/RT-38-SEL4-ABSTRACT-LOOKUP-INVARIANTS-2026-11-24.md).
  - [x] Replay official RISCV64 BaseRefine and Refine, then transfer the checked capability-lookup correspondence to both exported and refactored design wrappers. Both retain the original state, input, result and failure relations. Checked LLMLang source binding, reachable negative cases, automatic counterexample search and the C/binary link remain open. [Refined capability lookup](research/runtime-and-systems/RT-38/RT-38-SEL4-REFINED-LOOKUP-2026-11-24.md).
  - [x] Check the exact byte grammar of a bounded lookup wrapper and transfer the Isabelle correspondence to every admitted input. Two stored variants pass and five invalid inputs fail admission. The checked profile delegates the lookup primitives. General LLMLang grammar, a checked frontend, reachable semantic counterexamples and C/binary correspondence remain open. [Lookup source decoder](research/runtime-and-systems/RT-38/RT-38-SEL4-LOOKUP-SOURCE-DECODER-2026-11-25.md).
- [ ] Compare minimal HAL/assembly assumptions with checked intrinsics; validate source-to-binary preservation and no hosted imports.
- [x] Run the bounded RV64 QEMU single-core pilot with two Sv39 address spaces and a generation-checked endpoint. Independent IPC traces and stack/page-fault controls detect two incorrect mappings. The missing shared-ASID fence passes in QEMU and is identified by exact linked inspection. [RV64 isolated IPC pilot](research/runtime-and-systems/RT-38/RT-38-RV64-ISOLATED-IPC-PILOT-2026-11-24.md).
- [ ] Compose live allocation, mapping, scheduling and IPC invariants and extend the hardware premises before enabling SMP/DMA.

**Dependencies:** RT-37 profile/pilot, RT-03/04/07/08/09/10/13/16/32/33/34/36 and Stage 6 lowering. **Exit:** reproducible feasible or falsified kernel profile and bounded pilot evidence, explicit proof/TCB gaps. No full-kernel verification or production readiness claim.

---

# Stage 7 — Scale, ecosystem, collaboration, and adoption

**Order:** after the core vertical slice; some prior-art research can start earlier.  
**Purpose:** determine whether LLMLang remains practical for large codebases and real teams.

## 7.1 Performance and scalability

- [ ] Benchmark semantic graph size and traversal.
- [ ] Benchmark canonicalization and hashing.
- [ ] Benchmark dependency discovery and impact planning.
- [ ] Benchmark compilation and cache performance.
- [ ] Benchmark proof and test execution costs.
- [ ] Benchmark storage, indexing, and garbage collection.
- [ ] Benchmark large repositories and highly connected graphs.
- [ ] Benchmark concurrent edits and merge operations.
- [ ] Compare with Rust, Go, and C++ workflows on representative projects.
- [ ] Report memory, latency, throughput, cache hit rates, and confidence intervals.
- [ ] Identify pathological workloads and fallback strategies.
- [ ] **Mandatory research RT-25:** evaluate whether LLMLang's Rust-based runtime/toolchain should support alternative memory allocators, and whether allocator selection should be configurable per executable, process, or component. Complete the comparative study and its reproducible benchmark before selecting or rejecting an allocator. See [RT-25 — Memory Allocator Compatibility, Selection, and Benchmarking](research/runtime-and-systems/RT-25/RT-25-MEMORY-ALLOCATOR-COMPATIBILITY-AND-BENCHMARKING.md).
  - The first graph-shaped Rust workload compares glibc and jemalloc on one pinned configuration. [Allocator benchmark](research/runtime-and-systems/RT-25/RT-25-DEPENDENCY-GRAPH-ALLOCATOR-BENCHMARK.md)
  - [x] Cross-check existing results against RT-01 workload coverage and RT-25 acceptance gates; the bounded comparison does not select an allocator. [Workload-fit recheck (2026-11-24)](research/runtime-and-systems/RT-25/RT-25-WORKLOAD-FIT-RECHECK-2026-11-24.md)
  - Remaining external dependencies: Rust toolchain and TCMalloc/mimalloc on a pinned runner; executable package/archive and cache workloads plus persistent concurrent Toolchain workload; supported RT-10/RT-13 target, linking, and FFI matrix; controlled concurrent/memory-pressure and tail-distribution measurements. Keep RT-25 open until these are resolved or explicitly scoped out with evidence.
- [ ] **Mandatory research RT-26:** investigate high-level, hierarchical resource accounting and real-time enforcement for LLMLang tasks, including memory, CPU, disk/network I/O, coroutine/task switches, performance counters, limits, quotas, throttlers, and limit-exceeded handlers. Define the language/runtime/OS boundary and validate accounting accuracy, enforcement latency, overhead, and portability. See [RT-26 — Hierarchical Resource Accounting, Limits, Throttlers, and Handlers](research/runtime-and-systems/RT-26/RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md).
- [ ] **Mandatory research RT-28:** investigate incremental polyglot migration and semantic mirroring of actively developed upstream projects, including source frontends/identity, Migration Units and Mirror Bindings, incremental reconciliation, equivalence evidence, mixed-language interop, defect attribution, upstream contributions, and safe cutover/rollback. See [RT-28 — Incremental Polyglot Migration and Semantic Mirroring](research/compiler-and-translation/RT-28/RT-28-INCREMENTAL-POLYGLOT-MIGRATION-AND-SEMANTIC-MIRRORING.md). Coordinate with RT-27 storage research and RT-19/20/22/23/24.

## 7.2 Libraries, packages, templates, and artifact ecosystem

**Estimated research complexity:** **6/10** — identity, indexes, providers, publication, provenance, and operational policy.

### Package indexes and dynamic package delivery
- [ ] Define optional derived-result cache indexes in package archives and their integration with the semantic action cache; indexes must be independently omittable and must not affect logical package identity.

- [ ] Define the logical package-content model: roots, included objects, typed dependency edges, exports, modules, evidence, and provenance.
- [ ] Define compact canonical binary index tables and their key ordering; require binary-search and deterministic streaming-merge semantics.
- [ ] Compare whole-index compression with independently compressed blocks; measure codec, block-size, lookup, scan, and memory trade-offs.
- [ ] Evaluate optional sparse and hierarchical sparse indexes; establish when their lookup benefit justifies their storage and maintenance cost.
- [ ] Define index integrity, corruption detection, sparse-index reconstruction, and logical-versus-physical index identity.
- [x] Draft a human-readable TOML manifest schema candidate and an illustrative manifest fixture; keep binary encoding for machine indexes and object payloads where their formats require it.
- [x] Draft the Package Content Root Hash projection, identity exclusions, and validation invariants independently of raw TOML bytes and physical archive encoding.
- [x] Implement an exploratory executable package-identity model and focused fixtures for PMI-001–PMI-014; record its limits and test evidence.
- [ ] Review and validate the manifest schema, canonical typed hash encoding, and digest algorithm with independent implementations and adversarial fixtures before treating them as stable.
- [ ] Define static package archive and optional generated human-readable index (for example, `INDEX.md`) derived from the machine index.
- [ ] Define Dynamic Package requests by exact root Content Hash values and explicit dependency policies.
- [ ] Define exact-hash transitive dependency closure, optional/target/feature dependency semantics, and fail-closed missing-dependency behavior.
- [ ] Define provider snapshot consistency, deterministic logical package roots, and separation of content from delivery metadata.
- [ ] Define multi-provider index merge, availability metadata, selective retrieval, and trust/provenance boundaries.
- [x] Add a reproducible Provider benchmark harness for chain, diamond, high-fan-out, and many-dependency graphs; report time, throughput, Python allocation peak, process RSS, temporary-directory disk high-water, and archive size.
- [x] Add CI stress coverage for 1,200-object chain and high-fan-out dependency closures.
- [ ] Run and retain representative small/medium/large benchmark baselines on controlled hardware; CI measurements are exploratory and are not acceptance thresholds.
- [ ] Define a public immutable snapshot read API that can expose exact object metadata, dependency edges, and streaming payloads without private storage access; then implement a Provider adapter for a persistent backend.

**Existing evidence:** [Package System: Static and Dynamic Packages](research/packages-and-ecosystem/RT-12/PACKAGE-SYSTEM.md), extending the earlier [Libraries and Templates](research/packages-and-ecosystem/RT-12/LIBRARIES-AND-TEMPLATES.md) and [Global Semantic Artifact Store](research/packages-and-ecosystem/RT-12/GLOBAL-SEMANTIC-ARTIFACT-STORE.md) proposals.

**Status:** researched and prototyped at an exploratory level. A candidate TOML manifest schema, example fixture, Package Content Root Hash projection, identity exclusions, and PMI invariants are documented. The logical index, external-memory validation, streaming archive writer/verifier, exact dependency-policy resolver, and disk-backed Provider-to-archive pipeline have executable prototypes and CI coverage. The Provider uses SQLite for graph traversal state and streams sorted index rows plus one object payload at a time. A reproducible benchmark harness and 1,200-object chain/high-fan-out stress tests are implemented; CI records exploratory measurements, but controlled-hardware baselines and large-scale acceptance criteria remain open. The Toolchain Server Prototype 01 currently has only an in-memory lifecycle model and does not expose the public snapshot enumeration, dependency-edge, or streaming-payload API needed by Provider; no adapter is added against its private state. A persistent immutable-object backend and public snapshot read contract remain open. No normative wire format, codec policy, provider protocol, cache-index schema, final manifest schema, canonical hash encoding, or digest algorithm has been accepted.


- [ ] Define Package versus Library boundaries.
- [ ] Define library identity and public machine-readable contracts.
- [ ] Define dependency resolution and versioning.
- [ ] Define template instantiation, customization, detachment, and migration.
- [ ] Define global semantic artifact store and registry interfaces.
- [ ] Define artifact publication, signing, mirroring, licensing, revocation, retention, and garbage collection.
- [ ] Separate content integrity from publisher trust and licensing rights.
- [ ] Define opaque implementation evidence and verification limitations.

**Existing evidence:** `research/LIBRARIES-AND-TEMPLATES.md` and `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`; related TODO items LL-006–LL-012.

**Status:** researched in `research/LIBRARIES-AND-TEMPLATES.md`, `research/GLOBAL-SEMANTIC-ARTIFACT-STORE.md`, and `research/PACKAGE-SYSTEM.md`; package/index/provider design is proposed but not accepted, and operational policy, benchmarks, and trust implementation remain open.

## 7.3 Parallel development and collaboration

- [ ] Define concurrent graph edits and optimistic update rules.
- [ ] Define stable identity under rename, split, and merge.
- [ ] Define independent changes to contracts and implementations.
- [ ] Define conflict detection and safe automatic resolution.
- [ ] Define reviewable semantic change sets.
- [ ] Define provenance, authorship, approval, and audit trails.
- [ ] Define collaboration across branches, forks, and shared artifact registries.
- [ ] Test large multi-contributor scenarios.

**Existing evidence:** requirement evolution and semantic impact scenarios 18–19; Git semantic merge research.

**Status:** partially researched; end-to-end team workflow remains open.

## 7.4 Security, trust, and reproducibility

**Estimated research complexity:** **5/10** — current threat model and fixture prototype narrow the next experiments, but full operational security remains larger.

- [ ] Define trust boundaries among LLM authors, compiler, runtime, plugins, external tools, and artifact registries.
- [ ] Define deterministic validation independent of LLM claims.
- [ ] Define supply-chain provenance and signed evidence.
- [ ] Define sandboxing and capability restrictions for generated code.
  - A native cross-store experiment separates stale grant admission, scope-aware serialization and external-effect recovery. In a 45-case matrix the SQLite writer gate has no stale rename, while a process stop after rename leaves a file without a receipt under every tested policy. General external and issuer guarantees remain open. [External-effect revocation](research/language-design/RT-04/RT-04-EXTERNAL-EFFECT-REVOCATION-2026-11-25.md)
- [ ] Define cache poisoning and malicious artifact defenses.
- [ ] Define secret handling and isolation of build/test environments.
- [ ] Define reproducible builds and attestations.
- [ ] Define recovery and revocation when a tool, proof checker, or implementation is compromised.

**Status:** an initial threat model and tested authorization-policy experiment now exist in [RT-16 Threat Model 01](research/security/RT-16/RT-16-THREAT-MODEL-01.md). They cover scope binding, human approval, replay, evidence identity, and fail-closed checks at fixture level. A complete security architecture remains open; persistent multi-client authorization, concurrency/crash injection, sandbox testing, signed/authenticated evidence, and operational approval policy are high-priority gaps.

**Research output (2026-11-23):** [RT-16 authorization and evidence-policy recheck](research/security/RT-16/RT-16-POLICY-RECHECK-2026-11-23.md) reran the current-main policy suite: 24/24 passed on CPython 3.12.14 with source hashes recorded. This closes the fixture reproducibility gap, not production security. Exact scope binding is supported by the model; digest-only evidence does not authenticate its producer, and persistent nonce handling, signatures/trust roots, sandboxing, maintainers' approval policy, and Toolchain integration remain external dependencies.

## 7.5 Developer experience and adoption

**Estimated research complexity:** **10/10** — controlled comparative evaluation with real users/agents, correctness, repair effort, cost, and performance.

- [ ] Define human-readable source and semantic review workflows.
- [ ] Define diagnostics that explain semantic impact and failed contracts.
  - [x] Exercise versioned two-document repairs over LSP in 35 sessions. A stale version rejects the entire batch, but an unopened provider can change after server preflight and alter repair behavior. Scoped checking at application avoids the stale outcome and preserves unrelated edits in the fixture. General editor and Toolchain transaction integration remain open. [LSP repair application](research/toolchain-and-collaboration/RT-17/RT-17-LSP-REPAIR-APPLICATION-2026-11-24.md).
  - [x] Compare negotiated UTF-8, UTF-16 and UTF-32 positions and exact occurrence checks in 252 LSP sessions. Range-only application accepts 26 wrong edits. Token checks leave 12 wrong occurrences, and exact occurrence checks preserve all correct edits while rejecting those alternatives. Production editor and user evidence remain open. [LSP position encodings](research/toolchain-and-collaboration/RT-17/RT-17-LSP-POSITION-ENCODINGS-2026-11-25.md).
- [ ] Define editor, language-server, and debugging requirements.
  - [x] Exercise LSP push, pull, refresh and watched-file messages in 18 client/server sessions. A document version and document-bound result ID preserve four wrong results in each delivery style. A complete read projection rejects all four and avoids one whole-workspace refresh after an unrelated edit. Editor behavior and participant evaluation remain open. [LSP diagnostic freshness](research/toolchain-and-collaboration/RT-17/RT-17-LSP-DIAGNOSTIC-FRESHNESS-2026-11-24.md).
- [ ] Define migration and interoperability with existing languages and build systems.
- [ ] Evaluate learning curve and review quality for human developers.
- [ ] Evaluate LLM authoring workflows without treating generated output as trusted.
- [ ] Build representative end-to-end examples.
  - Compare one exact three-entry CLI graph through interpretation and generated Rust O0/O3. Both paths and the existing C/Python baselines pass all 34 RT-01 cases. Separate mutations distinguish negative division, empty arguments and diagnostic channels. General language support, representative project scale and participant evaluation remain open. [Typed CLI vertical slice](research/language-design/RT-01/RT-01-TYPED-CLI-VERTICAL-SLICE-2026-11-25.md)
- [ ] Define practical adoption criteria and migration strategy.

**Status:** initial workload acceptance criteria and an executable CLI corpus with C and Python host references are recorded in [RT-01 Reference Workloads](research/language-design/RT-01/RT-01-REFERENCE-WORKLOADS.md). [Scenario 95 execution](research/toolchain-and-collaboration/RT-17/RESEARCH-SCENARIO-95-EXECUTION-2026-11-20.md) adds an evidence-linked diagnostic/repair contract candidate, 12 structural discriminators, and a controlled evaluation protocol. These are analytical outputs only: LLMLang implementation behavior, human/agent usability, review quality, context/token use, repair effort, scope violations, and adoption criteria still need implementation and controlled study.

**Publication evidence (2026-11-21)** · Across 50 schedules, a complete read projection matches the diagnostic oracle. Entry-only publication accepts stale reports after external changes, while workspace-wide validation also discards unchanged results. [Diagnostic publication](research/toolchain-and-collaboration/RT-17/RT-17-DIAGNOSTIC-PUBLICATION.md)

**Exit criteria:** representative large-project benchmarks; working collaboration and recovery workflows; documented trust/security model; practical developer workflow evaluated with real tasks.

## 7.6 Toolchain Server and semantic development API (RT-19)

**Estimated research complexity:** **5/10** — bounded API, persistence, synchronization, MCP, and recovery experiments.

- [x] Identify the architectural gap between the existing Development Engine RFC and an operational agent-facing Toolchain API.
- [x] Draft a research proposal for a transport-neutral domain API with MCP, CLI, IDE, and CI adapters.
- [x] Define candidate Workspace, Change Set, immutable Snapshot, and typed mutation-envelope responsibilities.
- [x] Draft ADR-015 as a Proposed decision record with explicit non-decisions and validation gates.
- [x] Implement Prototype 01 for in-memory immutable objects/snapshots, isolated workspaces, typed changes, optimistic checks, acceptance, and single-file import/export.
- [x] Add a focused Python test suite and GitHub Actions workflow for the prototype.
- [x] Record the Git-authoritative/reconstructible-store boundary from Proposed ADR-014; do not silently change the ADR.
- [x] Compare the bounded transaction/recovery protocol choices using existing implementations: single embedded DB coordinator, object store plus workspace journal/outbox, and Git commit as acceptance. The state-machine comparison favors separate logical object/workspace contracts coordinated by one embedded DB transaction, with a durable outbox and Git as reconstructible authority. This closes only the comparative-analysis checkbox; no crash recovery or backend has been implemented or selected. See [RT-19 transaction/recovery protocol comparison](research/toolchain-and-collaboration/RT-19/RT-19-TRANSACTION-RECOVERY-PROTOCOL-COMPARISON-2026-11-24.md).
- [x] Replay a bounded SQLite acceptance/outbox and exact Git tree publication across eight process crashes. Fresh processes recover the exact root and original outcome after divergence, preserve the live index, and adjudicate duplicate and competing requests. [RT-19 process crash recovery](research/toolchain-and-collaboration/RT-19/RT-19-SQLITE-GIT-PROCESS-RECOVERY-2026-11-24.md).
- [ ] Specify the complete transaction and recovery contract for multiple branches, authorized changes and production Git/filesystem failures.
  - Compare recovery rights in 48 native SQLite/file schedules. Observation permission can authorize reconciliation of an already visible exact record after append revocation. Resuming a missing or partial record requires current append rights. A fenced split prevents two late effect races and one disclosure missed by fresh checks alone. Remote delivery and production authority remain open. [Recovery authority](research/toolchain-and-collaboration/RT-19/RT-19-RECOVERY-AUTHORITY-2026-11-25.md)
  - A SQLite/filesystem fixture uses exact prepared operation bytes to recover an already visible immutable effect after process termination. Filename-only recovery produces three false receipts. The exact recovery path retains both correct interrupted outcomes and one receipt under concurrent retry. Production namespace, authority and crash durability remain open. [External receipt recovery](research/toolchain-and-collaboration/RT-19/RT-19-EXTERNAL-RECEIPT-RECOVERY-2026-11-25.md)
- [ ] Specify semantic import/export, external-edit detection, and atomic multi-file publication.
  - [x] Compare per-file replacement with generation-manifest, generation-pointer, and exact Git-tree/ref publication boundaries; the bounded result favors validating a private complete tree before publishing its Git ref, while keeping durable accepted-pending state distinct. [Multi-file publication boundary recheck (2026-11-24)](research/toolchain-and-collaboration/RT-19/RT-19-MULTIFILE-PUBLICATION-BOUNDARY-RECHECK-2026-11-24.md)
- [ ] Specify optimistic concurrency, multi-agent workspaces, idempotency, and conflict handling.
  - [x] Recheck current workspace revision CAS against two workspaces on one base and repeated Change Set IDs. Local CAS permits competing same-base acceptance; retries return `StaleRevision`, not a stored result. Shared-head arbitration and durable idempotency remain separate unresolved contracts. [Concurrent workspace CAS recheck (2026-11-24)](research/toolchain-and-collaboration/RT-19/RT-19-CONCURRENT-WORKSPACE-CAS-RECHECK-2026-11-24.md)
  - The shared-head fixture now has a persistent request/outcome and Git receipt record with process crash and race checks. Branch-based acceptance, complete semantic merge/conflict discovery and maintainer choice of acceptance semantics remain open.
- [x] Specify candidate MCP Tools, Resources and Prompts schemas for the in-memory lifecycle. The upstream SDK passed 42 assertions over MCP stdio, including scoped resources, rejected stale mutations and atomic Change Sets. Production authorization, payload schema and persistence integration remain open. [Independent MCP client experiment](research/toolchain-and-collaboration/RT-19/RT-19-MCP-STDIO-SCHEMA-INTEROPERABILITY-2026-11-24.md).
- [ ] Prototype deterministic import/change/validate/accept/export/re-import as one vertical slice.
- [ ] Add failure-injection, security, authorization, and comparative source-editing tests.

**Existing evidence:** [RT-19 research proposal](research/toolchain-and-collaboration/RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) builds on [Development Engine RFC](research/toolchain-and-collaboration/RT-14/RFC-DEVELOPMENT-ENGINE.md), [Git semantic repository research](research/toolchain-and-collaboration/RT-15/GIT-SEMANTIC-REPOSITORY.md), and [ADR-014](docs/adr/014-git-semantic-merge.md).

**Status:** proposal and Proposed ADR-015 drafted; a narrow in-memory lifecycle prototype and focused CI test workflow are present. No API contract, persistent storage backend, multi-file synchronization algorithm, MCP surface, or ADR has been accepted. The prototype is evidence for workflow mechanics only, not implementation completion.

**Research output (2026-11-23):** [RT-19 storage backend contract recheck](research/toolchain-and-collaboration/RT-19/RT-19-STORAGE-BACKEND-CONTRACT-RECHECK-2026-11-23.md) compared the in-memory workspace lifecycle with the SQLite Content Store. Their current APIs are not interchangeable: one owns atomic workspace Change Sets, the other exposes opaque immutable-object snapshot reads. The proposed next experiment separates object-store and workspace-transaction contracts; persistent acceptance/recovery and adapter integration remain open.

**Research output (2026-11-23):** [RT-19 workspace persistence transaction boundary recheck](research/toolchain-and-collaboration/RT-19/RT-19-WORKSPACE-PERSISTENCE-TRANSACTION-BOUNDARY-RECHECK-2026-11-23.md) reran both focused suites (9/9 each), confirmed that the SQLite schema has no workspace-head API, and compared one embedded transaction coordinator, a journal/outbox over a separate immutable object contract, and Git-commit-coupled acceptance. It provisionally recommends testing a journal/outbox coordinator first, with one embedded DB as the physical engine and Git remaining the reconstruction authority. Process crash injection, multi-file/Git reconciliation, and durable recovery remain open.

**Research output (2026-11-24):** [RT-19 transaction and recovery protocol comparison](research/toolchain-and-collaboration/RT-19/RT-19-TRANSACTION-RECOVERY-PROTOCOL-COMPARISON-2026-11-24.md) re-ran the in-memory lifecycle and SQLite Content Store suites (9/9 each) and compared eight failure points across the three protocol candidates. It distinguishes the single embedded DB as physical coordinator from object-store/workspace-journal logical contracts, and Git commit as a receipt/reconstruction oracle rather than sole pre-commit workspace state. The comparison favors that bounded next experiment; it does not test crashes or establish production durability. Crash injection, source/SPG binding, atomic multi-file/Git reconciliation, MCP/authorization, workload measurements, and maintainer approval remain open.

**Exit criteria:** deterministic round-trip identity; stale/conflicting mutations rejected; accepted snapshots immutable; multiple workspaces isolated; crash/restart and export interruption recover safely; external edits are detected; MCP adapter independently tested; authorization and benchmark results documented.

---

## 7.7 LLM patch planning, caller migration, hash propagation, and verified commit (RT-20)

**Estimated research complexity:** **6/10** — significant multi-step validation and identity/dependency integration.

- [x] Capture the requirement that the complete function-change plan must be established before implementation.
- [x] Separate upward contract propagation from hash/reference propagation through callers.
- [x] Record per-call-site compatibility decisions: migrate to a new callee version, preserve the old immutable version, adapt, fork, or remain unresolved.
- [x] Preserve the caller-required contract hash and exact callee identity in each call-site decision; resolve the callee-provided contract through the callee declaration rather than storing a duplicate reference. Require PROVEN compatibility status plus evidence identity for resolved decisions and verify the bindings against materialized baseline/candidate objects.
- [x] Require shared-caller version-split analysis when different consumers need old and new behavior.
- [x] Define a candidate Change Impact Plan (CIP), plan-completeness checks, and mandatory plan execution.
- [x] Specify the proposed completion gate: freeze candidate, verify plan coverage, validate and audit exact hashes, then create a Git commit only on success.
- [x] Prototype a candidate Snapshot materialization check for planned call-site decisions: bind exact baseline/candidate roots, verify selected caller/callee membership and stored hashes, and inspect the actual candidate call-site target.
- [x] Audit the complete candidate dependency closure: recompute Snapshot root, traverse transitive typed references, verify object hashes and target kinds, and compare payload-derived edges with stored dependency metadata.
- [ ] Reconcile the function hashId and call-reference assumptions with identity Studies 05–08 and the RT-24 Identity and SPG Reconciliation report; no standalone RT-05 specification currently exists.
- [ ] Specify reverse-reference completeness for direct, indirect, dynamic, external, and generated call sites.
- [ ] Prototype single-chain propagation, mixed old/new callers, shared-caller splits, multiple call sites, and branching/converging graphs.
- [ ] Extend the call-site plan identity to represent one shared caller forked into multiple consumer/path-specific caller versions; the current prototype assumes one resulting version per base caller hash.
- [x] Extend CIP-to-diff enforcement with versioned output slots, exact typed-reference/call-target edge deltas (including call-site Contract bindings), post-materialization output-hash bindings, and consumer-path-specific shared-caller forks. The current implementation tests declaration add/remove/replace, typed-reference additions/rewrites, call-target add/remove/rewrite/condition changes, required-Contract migration, caller deletion, and a branching/converging caller split. Action-kind/prerequisite/evidence sufficiency, dynamic dependency completeness, behavioral compatibility, and commit authorization remain open.
- [ ] Prototype failed-validation/no-commit, exact-tree commit, concurrency rejection, and idempotent retry behavior.
- [ ] Reconcile the completion transaction with RT-19 persistence, crash recovery, atomic export, and Git coordination.

**Evidence:** [RT-20 — LLM Patch Planning, Caller Migration, Hash Propagation, and Verified Commit](research/toolchain-and-collaboration/RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) records the proposed workflow and invariants. It is a research proposal, not an accepted identity or Toolchain decision.

**Executable caller refactor:** [Calculator call-site split](research/language-design/RT-01/RT-01-CLI-CALL-SITE-REFACTOR-2026-11-25.md) compares eight Git candidates and 192 native subprocess observations. Exact per-call preservation and migration admits six. A warm store produces correct outputs for both removed-source candidates, which fail source closure. General caller inventory, language integration and independent review remain open.

**Status:** RT-20 remains a research proposal. The dependency-graph prototype includes Snapshot-scoped reverse lookup, differential payload-scan auditing, per-call-site compatibility planning, candidate call-site materialization checks, and a complete explicit-declaration dependency-closure audit. The candidate declaration schema is v2: each call-site alternative pins its required Contract hash, each callable callee owns one provided-Contract reference, and RT-20 decisions preserve the caller requirement plus exact callee identity without duplicating the provided-Contract reference. The dependency-index edge projection is v3. The graph audit checks exact object hashes, transitive target resolution/kinds, and consistency between payload-derived edges and stored dependency metadata. CIP schema v2 adds exact output slots, typed-reference/call-target edge deltas, materialized output-hash bindings, and consumer-path-specific shared-caller forks. PR #24 is merged. Post-merge workflows on `cf51c15a34cee14a8b0390322be0a15d9ee85559` passed: semantic dependency 101 tests + compilation, repository structure 6 + 78 tests, and strict QF_LIA 30 tests + compileall. Action-kind/prerequisite/evidence sufficiency, dynamic dependency completeness, behavioral compatibility, and a validation-gated commit remain open.

**Evidence:** [RT-20 Candidate Call-Site Validation](research/toolchain-and-collaboration/RT-20/RT-20-CANDIDATE-CALL-SITE-VALIDATION.md), [RT-20 Candidate Graph Audit](research/toolchain-and-collaboration/RT-20/RT-20-CANDIDATE-GRAPH-AUDIT.md), and tests under `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/`.

**Exit criteria:** a complete server-validated plan precedes all mutations; every relevant call site has an evidence-backed compatibility decision; contract and hash propagation are independently correct; old/new behavior and shared-caller version splits work; every planned change is enforced and unplanned changes are rejected; commit is created only for the exact candidate that passed all mandatory checks.

## 7.8 Knowledge Context and Task Context (RT-14)

**Estimated research complexity:** Knowledge Context **7/10**; Task Context **6/10**; integrated workflow validation **8/10**. Knowledge Context depends on sound identity, dependency, provenance, and access boundaries. Task Context has a narrower object/lifecycle scope but must integrate with Change Sets, patch planning, delegation, and completion gates.

These are two separate research requirements. Do not collapse them into one generic Context object before their responsibilities and invariants are understood.

### Knowledge Context — LL-026

Research a bounded, versioned, provenance-preserving description of the information available to an LLM agent for a task.

- [ ] Define the boundary between Knowledge Context, free-form prompt text, runtime/execution context, semantic dependency closure, and Task Context.
- [ ] Inventory eligible sources: Specification, Design, and Implementation objects; contracts; requirements; dependency records; diagnostics; tests and proof evidence; project documentation; approved external references.
- [ ] Compare exact snapshot-pinned object references with derived summaries, retrieved excerpts, and relevance-ranked material. Distinguish mandatory entries from optional supporting information.
- [ ] Define provenance, source trust classes, revision freshness, conflict handling, unknown/missing sources, and evidence that a context is complete for a declared purpose.
- [ ] Study context-size/token budgets, deterministic selection, relevance/coverage trade-offs, omission reporting, redaction, data minimization, and permission-aware retrieval.
- [ ] Separate Knowledge Context identity from semantic object identity, dependency hashes, Action Keys, and rendered prompt identity; specify invalidation and safe reuse conditions.
- [ ] Define transport-neutral assembly, inspection, serialization, and agent-facing retrieval APIs for RT-19.
- [ ] Construct discriminating fixtures for stale, conflicting, inaccessible, duplicated, incomplete, and over-budget context inputs; evaluate context precision/recall and task outcomes on representative workloads.

### Task Context — LL-027

Research a typed, versioned object describing the task an agent is expected to perform and the obligations that govern completion.

- [ ] Define the boundary between Task Context, human intent/requirements, Change Impact Plan, Change Set, workspace, Knowledge Context, and authorization grants.
- [ ] Define task identity and revision semantics; objective, requirement links, in/out-of-scope objects, constraints, non-goals, assumptions, prerequisites, deliverables, and acceptance criteria.
- [ ] Compare lifecycle models for creation, clarification, planning, execution, blocked/failed states, cancellation, retry, delegation, decomposition, review, handoff, and completion.
- [ ] Define how a task pins its baseline snapshot, selected Knowledge Context, target objects, and related Change Set/CIP without duplicating their authoritative state.
- [ ] Specify machine-checkable completion obligations: required mutations, tests, proofs, audits, approvals, evidence bindings, and fail-closed behavior when obligations remain unknown or unsatisfied.
- [ ] Study multi-agent ownership, concurrent task revisions, subtask dependencies, idempotency, recovery, and the boundary between task completion and commit/push authorization.
- [ ] Keep authorization independent: a Task Context describes requested work and constraints but does not grant capabilities; RT-16 policy checks remain authoritative.
- [ ] Build lifecycle and adversarial fixtures for stale baselines, scope expansion, omitted obligations, conflicting delegated work, cancellation/retry, and partial completion.

### Joint integration and exit criteria

- [ ] Define the Knowledge Context ↔ Task Context relationship without making either the authority for the other's semantics.
- [ ] Map both models onto RT-05/06 identity and dependency evidence, RT-02 requirements, RT-16 permissions, RT-19 workspaces/Change Sets, and RT-20 plan execution.
- [ ] Validate that context manifests and task records are reproducible, inspectable, revision-bound, and fail closed on unknown completeness, stale baselines, or unauthorized reads/actions.
- [ ] Compare agent performance with full-context, bounded-context, and deliberately incomplete-context conditions; measure task success, missed constraints, scope violations, token/context cost, review effort, and recovery behavior.
- [ ] Record candidate schemas, lifecycle alternatives, invariants, falsifiers, compatibility dependencies, and a bounded prototype/test plan. Do not select language syntax or accept a normative architecture as a result of this planning entry.

**Research status:** Required research is now registered as LL-026 and LL-027. No Knowledge Context or Task Context schema, syntax, lifecycle, or architecture has been selected.


## 7.9 AI-oriented syntax experimentation and MCP session observability (RT-31)

**Estimated research complexity:** **9/10** — requires a stable semantic oracle, multiple equivalent syntax frontends, controlled model evaluations, reliable error attribution, and privacy-aware session recording.

- [ ] Define the boundary among the authoritative Semantic Model, Abstract Syntax Model, canonical Semantic IR, and independently versioned Concrete Syntax Profiles. Determine which structures are distinct and specify their mappings.
- [ ] Define frontend/generator contracts, profile versioning, source provenance, diagnostics locations, normalization, elaboration, and semantic validation boundaries.
- [ ] Compare textual, explicit/verbose, structured, and hybrid syntax profiles while preserving the same declared semantic capabilities.
- [ ] Build a profile-independent task corpus covering representative language features and multi-step authoring tasks; pin acceptance oracles and negative controls.
- [ ] Implement parser/generator and cross-profile conversion prototypes; verify semantic equivalence independently of textual round-trip identity.
  - [x] Implement three versioned expression parsers and generators and check all nine conversions against an independent value/trace oracle on 4,032 observations. Frontend, binding, typing and trace controls distinguish validation stages. Broader syntax coverage and human/model evaluation remain open. [Cross-profile SPG](research/language-design/RT-31/RT-31-CROSS-PROFILE-SPG-2026-11-24.md).
- [ ] Define controlled AI experiments with pinned model/provider metadata, model settings, task/context, instruction version, profile, Toolchain build, and execution environment.
- [ ] Measure parse/syntax errors separately from semantic, type/effect/ownership, contract/invariant, hallucination, MCP/tool-call, and task-completion errors; include first-pass and repair-assisted outcomes.
- [ ] Define an MCP session event model for sessions, turns, requests/responses, tool calls, validation runs, repair attempts, and final outcomes, with stable correlation and provenance.
- [ ] Prototype privacy-aware recording with metadata-only and redacted-content modes; define authorization, secret redaction, retention, deletion, export, and audit controls before any unrestricted content capture.
- [ ] Define error attribution that distinguishes model mistakes, ambiguous/incomplete task context, Toolchain defects, and external environment failures; preserve multi-cause and unknown classifications.
- [ ] Build analytics and held-out regression evaluation for syntax, instruction, diagnostic, and Toolchain changes; require reviewed promotion rather than automatic unreviewed mutation.
- [ ] Report sample sizes, uncertainty, reproducibility, token/cost, latency, human review effort, and semantic coverage; do not optimize parse success or token count at the expense of semantics.

**Research brief:** [RT-31 — AI-Oriented Syntax, Semantic Separation, and Toolchain Optimization](research/language-design/RT-31/RT-31-AI-ORIENTED-SYNTAX-AND-TOOLCHAIN-OPTIMIZATION.md).

**Coordination:** RT-03/05/07/08/09 establish semantic meaning, identity, compiler boundaries, and correctness oracles; RT-14/19/22 establish agent context, MCP/Toolchain and repository session provenance; RT-16 governs privacy and trust; RT-18 governs evolution; RT-24 and RT-30 inform canonical representation and cross-language preservation.

**Status:** research required; three-level semantic/abstract/concrete separation is the agreed research direction, but the exact IR/AST boundary, profile design, logging schema, retention policy, and optimization process remain open. No concrete syntax or unrestricted session-content capture is selected.

**Exit criteria:** at least three syntax profiles cover a common semantic subset; profile transformations pass independent semantic-equivalence checks; controlled model evaluations produce reproducible, uncertainty-aware comparisons; session recording supports privacy controls and reliable error attribution; improvement proposals are checked against held-out regression tasks.


## 7.10 Semantic Function Discovery and Retrieval (RT-35)

**Estimated research complexity:** **8/10** — requires a canonical semantic description, retrieval-quality benchmarks, sound compatibility checks, snapshot-consistent indexes, and safe ambiguity handling.

- [ ] Define the distinction among exact function identity/hash, canonical semantic description, derived semantic fingerprint, and rebuildable search index.
- [ ] Specify a candidate canonical description covering intent, input/output roles, preconditions, postconditions/behavior, effects/capabilities, errors, constraints, and optional cost characteristics.
- [ ] Compare single-vector, multi-aspect, structured, lexical, and hybrid fingerprints/retrieval channels; keep embedding and ANN choices replaceable.
- [ ] Define intent-only, structured-requirement, and hybrid query forms, including provenance for explicit hard constraints versus soft preferences.
- [ ] Prototype KNN/ANN candidate retrieval and structured metadata/contract filters; preserve retrieval-channel and score provenance.
- [ ] Define and test hard compatibility checks for types, ownership, preconditions, postconditions, effects, capabilities, and failure behavior. Similarity scores must never authorize compatibility.
- [ ] Specify unknown/incomplete evidence behavior, exclusion reasons, ranking, explanation, and ambiguity handling; do not silently bind an arbitrary top-1 result.
- [ ] Demonstrate exact hash resolution and call binding against an immutable semantic snapshot; runtime invocation must not repeat semantic search.
- [ ] Define fingerprint/index versioning, incremental updates, cache keys/invalidation, snapshot consistency, stale-result rejection, and rebuild behavior.
- [ ] Test access control, package/workspace scope, metadata visibility, tenant isolation, misleading descriptions, index poisoning, and adversarial near-neighbours.
- [ ] Build a benchmark corpus with differently named equivalent-purpose functions, semantically close but incompatible functions, overlapping signatures, hard-constraint violations, and unknown contracts.
- [ ] Compare structured-only, single-vector KNN, multi-aspect KNN, and hybrid retrieval using Recall@K, precision/MRR/nDCG, compatible-candidate recall, false-compatible/unsafe-selection rate, ambiguity quality, latency, storage, and update cost.
- [ ] Report uncertainty, model/index versions, failure cases, and reproducibility; establish evidence-based minimum safety and quality thresholds before automatic resolution.

**Research brief:** [RT-35 — Semantic Function Discovery and Retrieval](research/semantic-representation/RT-35/RT-35-SEMANTIC-FUNCTION-DISCOVERY-AND-RETRIEVAL.md).

**Bounded evidence:** [Scoped retrieval and exact function binding](research/semantic-representation/RT-35/RT-35-SCOPED-RETRIEVAL-2026-11-25.md) compares five ranking channels in 36 contexts. Lexical and multi-aspect recover 42/48 compatible pairs, yet shortlist-only checking falsely binds 18/36 contexts for either channel. Complete authorized selection gives 12 bound, 12 ambiguous and 12 pending decisions. Stale roots, mismatched rows, prior-root receipts and omitted compatible rows distinguish exact binding from derived-index retrieval. Real workload labels, production embedding and ANN comparisons, index lifecycle measurements and independent review remain open.

**Coordination:** RT-03/04 define function meaning and compatibility; RT-05/24 define canonical semantics and immutable identity; RT-06/11 constrain dependency-aware indexing and cache invalidation; RT-07/08 provide soundness and evaluation gates; RT-09/19 define compiler/Toolchain integration; RT-12 defines package/library discovery scope; RT-14/31 inform agent intent and evaluation; RT-16 governs authorization and trust; RT-18 governs versioning; RT-20 constrains exact call binding and caller compatibility.

**Persistent index evidence:** [SQLite index generations](research/semantic-representation/RT-35/RT-35-PERSISTENT-INDEX-GENERATIONS-2026-11-25.md) compare four freshness gates across 28 protocol schedules and seven split-publication controls. Full-key revalidation returns 10 exact results and refuses 18 when the writer publishes index rows and the ready key atomically. A premature ready marker allows five incomplete results. Rebuild and delta have identical projections across 24 maintenance measurements, with fewer writes but full comparison and validation scans in the delta. Production latency, distributed isolation, workload coverage and independent review remain open.

**Status:** research required. Semantic fingerprints and KNN/ANN are proposed discovery mechanisms, not selected architecture or language semantics. Exact function hashes remain authoritative for calls.

**Exit criteria:** a canonical description/fingerprint proposal and benchmark corpus exist; structured, vector, and hybrid baselines are compared; compatibility and ambiguity handling pass negative controls; a bounded prototype resolves candidates to exact hashes against a pinned snapshot; index lifecycle, security, and stale-result behavior are tested.

---

# 4. Cross-cutting prior-art research

This is a continuous comparative track. It informs the stages above but does not replace LLMLang-specific experiments.

| System / technology | Research focus | Relevant stages |
|---|---|---|
| LLVM | IR, lowering, optimization, backend and ABI boundaries | 2, 5, 6 |
| Rust | Ownership, borrowing, lifetimes, type system, systems runtime | 5, 6, 7 |
| Lean | Formalization, proof checking, trusted kernel, executable semantics | 2 |
| TLAPS | Proof of system properties and compositional reasoning | 2 |
| SMT solvers | Constraint encoding, solver protocols, proof evidence, unknown results | 2, 3 |
| Dafny | Contracts, refinement, verification workflow | 1, 2, 5 |
| K Framework | Executable formal semantics and language definition | 2 |
| Vellvm | Formal LLVM semantics and compiler correctness | 2, 6 |
| Alive2 | Translation validation for LLVM optimizations | 2, 6 |
| Bazel / Skyframe | Dependency graphs, incremental evaluation, action caching | 3 |
| Salsa | Incremental computation and dependency tracking | 3 |
| Adapton | Demand-driven incremental computation | 3 |
| Nix | Reproducible, content-addressed builds and dependency isolation | 3, 4, 7 |
| Git | Object model, DAG history, merge drivers, mergetool integration | 4 |
| Unison | Content-addressed code identity and semantic naming | 1, 4 |
| POSIX | Standardized interfaces, conformance, implementation-defined behavior | 5 |
| C / C++ ABIs | Interoperability, memory layout, calling conventions, platform boundary | 5, 6 |
| Package and artifact registries | Distribution, trust, provenance, licensing, retention | 7 |

For each system, record: the specific problem it solves, its model, what can be reused, what cannot be reused, the assumptions it makes, and the LLMLang experiment needed to validate applicability.

---

# 5. Current known research baseline

The following is a snapshot of known work, not a claim that all corresponding questions are resolved.

| Area | Existing artifacts / evidence | Current assessment |
|---|---|---|
| Core concept and SPG | `LLMLang-CONCEPT.md` | Researched; semantic model still evolving |
| Comparative language design space | Scenarios 35 onward and `RESEARCH-OPTION-MATRIX-01.md` | Evidence covers semantics, types and resources, syntax, runtime, identity, verification, cache trust, diagnostics, scheduling, backend preservation, cleanup composition, AST path analysis, optional values, bounded serialization probes (Scenarios 109–111 and reference-only cross-format Scenario 134; no current cross-version wire-compatibility requirement), fairness, and atomic memory orders. Experimental coverage varies by option. |
| RT-03/RT-04 semantics and resource boundaries | `CORE-LANGUAGE-SEMANTICS.md`, RT-04 report, shared corpus, COR-13, Scenarios 35–41, 97–112 | Bounded evaluators and focused checks cover Scenario 97 cleanup outcome/ownership audits; Scenarios 98–103 finite paths, solver outcomes, and worker timeout; Scenarios 104–108 mutation identity, call summaries, and alias precision; Scenario 109 optional-presence JSON round trip; Scenario 110 producer/consumer version skew and defaults; Scenario 111 unknown wire variants with Protobuf/Avro/CBOR prior-art; and Scenario 112 weak/strong fairness cycles with a conditional two-task round-robin bound. Broader timeout distributions, negative-result verification, parser/source completeness, general alias analysis, external-wire/ABI policies if such boundaries are introduced, call/cleanup integration, async/concurrent cases, independent review, and cross-aspect compatibility remain open |
| Identity and call binding | RT-05 lifecycle/recursive/call-site experiments; RT-24 decision matrix | Candidate lifecycle/address models compared on finite fixtures; exact OpHash/ImpHash and contract boundaries, source correspondence, branch conflicts, and canonical SPG integration remain undecided |
| Reference workloads and agent tasks | `RT-01-REFERENCE-WORKLOADS.md`; `PROTOTYPES/CLI-WORKLOADS-01/` | Shared acceptance criteria and C/Python CLI host references exist; LLMLang candidate execution, controlled human/agent evaluation, and workload-weight calibration remain open |
| Formal verification architecture | `LLMLang-FORMAL-VERIFICATION.md` | Researched; complete formal semantics not finished |
| Typed requirements and contracts | Scenarios 15–19; prototypes 16–19 | Prototyped; broader language integration remains |
| Dependency discovery and impact | Scenarios 20–28; prototypes 20–28 | Extensively prototyped; sound end-to-end completeness remains |
| SMT/proof boundary | Scenarios 29–34; Logos/Lean binding prototype; QF_LIA profile and typed query IR | Partially validated; pinned Lean CI build and current tests pass; QF_LIA path remains restricted/candidate and source-to-query/program-level correspondence remains unproved |
| Semantic compilation cache | `SEMANTIC-COMPILATION-CACHE.md` | Researched; implementation and empirical validation remain |
| Cache speedup estimate | `COMPILATION-CACHE-SPEEDUP-ESTIMATE.md` | Analytical estimate exists; controlled runtime benchmarks remain |
| Binding and invalidation measurements | `RT-11-BINDING-INVALIDATION-BENCHMARK.md`; `PROTOTYPES/DEPENDENCY-GRAPH-01/src/binding_build_benchmark.py` | Synthetic C experiment records compile/link/verification action counts for exact versus separate linkage; production dependency discovery, remote trust, and controlled-hardware timing remain open |
| POSIX runtime | `POSIX-RUNTIME-ARCHITECTURE.md` | Researched; profile and vertical slice remain open |
| Translation/backends | `TRANSLATION-AND-TARGET-BACKENDS.md` | Researched; backend implementation remains |
| LLVM backend | `LLVM-BACKEND-ARCHITECTURE.md` | Researched; lowering and validation remain |
| Source-to-LLVM semantic preservation | Scenarios 96, 96A and 96B; LL-020; `LLVM-BACKEND-ARCHITECTURE.md` | LLVM 19.1.7 matches 41,956 integer and 19,600 byte-view observations across two optimization levels. Negative controls lose overflow, bounds or origin checks. General allocation provenance and cross-target validation remain open |
| Libraries and templates | `LIBRARIES-AND-TEMPLATES.md` | Researched; detailed decisions remain |
| Global artifact store | `GLOBAL-SEMANTIC-ARTIFACT-STORE.md` | Researched; store and trust implementation remain |
| Git representation and semantic merge | `GIT-SEMANTIC-REPOSITORY.md`; ADR-014 | Research completed at concept level; ADR-014 is Proposed; implementation and merge evaluation deferred |
| Toolchain Server and semantic development API | `RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md`; Development Engine RFC | Proposal drafted; API, storage, synchronization, MCP adapter, and failure semantics remain unvalidated |
| Security and trust | `RT-16-THREAT-MODEL-01.md`; RT-16 authorization prototype | Initial threat model and 24-fixture policy experiment exist; persistent concurrent authorization, crash recovery, sandbox attacks, authenticated evidence, and operational policy remain open |
| Developer experience and adoption | `RT-01-REFERENCE-WORKLOADS.md`; Development Engine RFC | Initial workload criteria and authoring protocol exist; controlled human/agent usability, diagnostics, review quality, and adoption research remain open |

### PR #47 cumulative research scope

PR #47 merged the cumulative research snapshot `73d37723e6a759159b354c2cd74327517c4036c4`. Its base `eed5f5e` contains valid UTF-8 in `PLAN.md`. The first branch commit `adab2e8` replaced it with binary blob `73dc25c`, which is present in all 99 branch commits and the squash commit `b0638a1`. GitHub records the file as modified with no text patch and zero line counts. The subsequent text consolidation in PR #51 drew on the research mapped below. [PR #47 file changes](https://github.com/aivibeflow/LLMLang/pull/47/files) · [First branch commit](https://github.com/aivibeflow/LLMLang/commit/adab2e860581a3ddf43f6aa87014e6d5221b3f84)

| Snapshot scope | Research in the cumulative snapshot | Plan follow-through |
|---|---|---|
| Core outcomes and resource boundaries | Scenarios 35–41; COR-13; RT-03/04 shared corpus and prototypes for typed calls, owned-resource returns, cleanup dispositions, recursion/fuel, and actor progress | Continue Stage 1.4/1.4.1 with source-to-model/path completeness, ordered effects, call/return/cleanup integration, and independent review. Keep each result bounded to its fixture. |
| Language feature space | Scenarios 42–76, covering generics and dispatch, modules and initialization, compile-time and macro boundaries, numeric/string behavior, API evolution, concurrency, errors, ownership, mutability, initialization, subtyping, interfaces, layouts, disposal, and regex resource bounds | Keep alternatives in the option matrix; add discriminating executable corpora and cross-aspect checks before proposing a coherent profile. The scenario fixtures are bounded comparative probes, not a complete semantic model or a selected feature policy. No feature policy is selected by a prior-art survey. |
| Syntax, evaluation, and API surface | Scenarios 77–89, covering call argument order, floating-point behavior, literal/comment/import/file/numeric/signature/binding/async syntax, defaults, and automatic semicolon insertion | Treat syntax/parser acceptance separately from runtime semantics and API compatibility. Pin source modes and toolchain versions when turning proposed cases into runnable comparisons. |
| Identity and digest lifecycle | Scenarios 90–91; RT-05 lifecycle, recursive identity, and call-site refactor experiments; RT-24 decision matrix | Continue Stage 1.2/1.3 and Stage 4 identity work with rename/move, recursion, call-site changes, migration, and branch-conflict cases. Do not finalize hash payloads or canonical SPG fields by implication. |
| Workloads, measurement, and trust | RT-01 CLI reference workloads, RT-11 binding/invalidation benchmark, RT-16 threat model and authorization prototype, and `RESEARCH-OPTION-MATRIX-01.md` | Continue Stage 3/7 measurements on controlled workloads and hardware, and extend security lifecycle tests. Preserve the current limits: host references are not LLMLang evaluations, synthetic action counts are not production timings, and policy fixtures are not a complete security architecture. |

Subsequent Scenarios 92–122 extend the coverage through atomic execution, typed ownership across calls, and completeness and freshness of close evidence. The research index tracks the full numbered corpus and its prototypes across RT-03/04, RT-05/11/16, and dependency analysis. The dated research register records the evidence, open questions, and next experiments. [Research index](research/README.md) · [Research State](research/research-management/RESEARCH-STATE-2026-11-19.md)

---

# 6. Research vectors and integrated specification synthesis

The project must not treat an individual research report as producing one mandatory answer. Each research may identify multiple promising development vectors (approaches, design choices, or internally coherent option families), including assumptions, trade-offs, constraints, evidence, and unresolved questions.

## 6.1 Required output of each research

Each research report should, where applicable, provide:

- A clearly scoped aspect of LLMLang and the questions investigated.
- Multiple viable development vectors rather than only one preferred recommendation. Do not manufacture alternatives when only one viable vector is known.
- For each vector: principles, assumptions, benefits, costs, risks, limitations, and evidence.
- Compatibility requirements, constraints, and known incompatibilities with other aspects.
- Upstream dependencies and downstream impact, linked to the dependency map.
- Open questions and confidence/evidence level; distinguish facts from hypotheses and recommendations.

For each new report, update the research taxonomy and affected dependency-map edges before marking the research complete.

## 6.2 Cross-aspect dependency model

Maintain explicit directed relationships:

- **Requires:** one aspect/vector depends on another.
- **Constrains:** a choice narrows viable choices elsewhere.
- **Influences:** a choice changes trade-offs without making other choices impossible.
- **Conflicts with:** two choices cannot coexist under stated assumptions.
- **Enables:** a choice makes another capability or vector practical.

Each edge must record rationale, affected vectors, direction, and confidence. Revisit edges when evidence changes assumptions. Use the map to identify foundational topics, downstream topics, feedback loops, and parallel work.

## 6.3 Research order

Research order is dependency-driven, not simply the order topics were proposed. The current provisional sequence is:

1. Goals, constraints, and semantic foundations.
2. Program representation and identity.
3. Core language semantics, types, effects, ownership, and concurrency.
4. Specification and verification model.
5. AI-native authoring and change model, including separate Knowledge Context and Task Context research (LL-026 and LL-027).
6. Build, incremental computation, and tooling.
7. Version control and collaboration.
8. Runtime, deployment, interoperability, and ecosystem.

This is a dependency hypothesis, not a rigid serial schedule. Independent subtopics may proceed in parallel using explicit provisional assumptions.

## 6.4 Synthesis: from vectors to complete specifications

After relevant research coverage is sufficient:

1. Normalize vectors into a common decision/option model, preserving links to evidence.
2. Identify mutually compatible, conditionally compatible, dependent, and conflicting vectors.
3. Construct the Cartesian product of viable vector sets as the initial candidate specification space.
4. Eliminate or mark combinations violating explicit compatibility constraints; do not silently treat every combination as valid.
5. Preserve traceability from each candidate choice to research, evidence, assumptions, and dependency edges.
6. Compare complete candidate specifications as integrated wholes using shared criteria: coherence, correctness, expressiveness, simplicity, feasibility, performance, incremental behavior, AI-agent usability, interoperability, and evolvability.
7. Use pairwise/local analysis only as diagnostic tools; the primary comparison unit is the complete candidate specification.
8. If exhaustive enumeration is impractical, use documented constraints, equivalence classes, staged enumeration, or representative sampling without losing promising vectors.

## 6.5 Synthesis status

The [scoped comparisons](research/research-management/RESEARCH-OPTION-MATRIX-01.md#52-comparisons-supported-by-the-november-24-reproductions) and [bounded toolchain route comparisons](research/research-management/RESEARCH-OPTION-MATRIX-01.md#53-bounded-toolchain-route-comparisons) record verified conditions for later whole-candidate comparison. The toolchain ledger checks shared integer source across three emitters and keeps measured JIT, verification, Git publication and runtime limits attached to their exact profiles.

| Activity | Status | Exit condition |
|---|---|---|
| Define research taxonomy and initial dependency map | **Completed** | 18 research areas and 35 initial dependency edges are documented; ongoing updates remain required |
| Conduct and complete aspect research | **In progress** | RT-03 now has a candidate-profile survey; semantic validation/reference semantics, types/effects/ownership, security, and other gaps remain |
| Normalize vectors and validate compatibility | **In progress** | The option matrix records initial choices and bounded resource compatibility constraints. Extend normalization and validate constraints across all research areas. [Option matrix](research/research-management/RESEARCH-OPTION-MATRIX-01.md) |
| Generate candidate specification space | **Not started** | The four illustrative bundles anchor the comparison. The full compatible space still needs enumeration or a documented constrained search. [Initial bundles](research/research-management/RESEARCH-OPTION-MATRIX-01.md#4-integrated-candidate-vectors) |
| Compare complete candidate specifications | **Not started** | Integrated candidates are evaluated against shared criteria and representative scenarios |
| Select and baseline a specification direction | **Not started** | A coherent candidate is selected with rationale and unresolved risks recorded |

# 7. Cross-stage invariants

These invariants guide every research and implementation stage:

1. **Semantic source of truth:** target languages, generated code, and backend IRs do not redefine LLMLang semantics.
2. **Explicit operation identity:** a call identifies the intended immutable operation semantics; analogue discovery is a separate optimization.
3. **Explicit implementation identity:** a concrete implementation has its own identity, including all semantics-relevant inputs.
4. **Evidence is scoped:** tests and proofs apply only to the exact subjects, assumptions, targets, and tool versions they cover.
5. **Unknown is not proven:** unsupported, incomplete, ambiguous, or unchecked cases fail closed.
6. **Sound incremental reuse:** a result is reused only when all result-determining dependencies are captured and unchanged.
7. **Semantic changes propagate by identity:** hash-relevant changes alter the appropriate identity and invalidate dependent results automatically.
8. **Provenance is not semantics:** authorship, history, and audit data do not alter semantic identity unless explicitly defined as behaviorally relevant.
9. **No silent weakening:** a backend or runtime must report restrictions and unsupported semantics rather than silently dropping guarantees.
10. **Research is not specification:** only reviewed and explicitly accepted decisions enter `draft/`.

---

# 8. Immediate execution order

The [Research State 2026-11-19](research/research-management/RESEARCH-STATE-2026-11-19.md) consolidates the new corpus, evidence levels, open questions, and synthesis gates recorded in the research continuation work. The [Research Preparation Pack](research/preparation/README.md) contains scoped briefs for the planned work below; those briefs are not research results. The priorities below incorporate the cumulative research content of PR #47. Experiments and prior-art comparisons inform candidate vectors; they do not select semantics or authorize transfer into `draft/`.

1. **Close the shared source-semantics and type/resource gap.** Compare typed calls, owned-resource results, transfer/return, cleanup failure composition and ordering, ordered effects, cancellation, and recursion/fuel across RT-03 profiles and RT-04 type/resource alternatives. Scenarios 97–108 provide bounded outcome composition, ownership auditing, finite predicate paths, solver cross-checking, conservative UNKNOWN handling, one real worker deadline, mutation-identity counterexamples, call-summary transitions, alias-sensitive path cases, a bounded source-derived alias adapter, and finite path-sensitive alias precision. Scenarios 109–111 add bounded JSON observations for presence, version skew/defaults, and unknown variants. [Scenario 134](research/packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md) compares Protobuf, Avro, and CBOR rules and separates parsing fingerprints from evolution-policy and wire-contract identity. Real-runtime conformance, migration behavior, schema/ABI policy, and semantic identity boundaries remain open. Broader hard-formula distributions, negative-result trust/checking, full parser/source correspondence, general alias/call/loop analysis, and independent review remain required before claiming source-level completeness.

   Scenarios 119–130 cover returned ownership, native cleanup outcomes, scoped role and alias checks, concurrent and reentrant guards, cancellation, and durable results. Scenarios 131–133 check a bounded common source workload with two transfer rules, typed caller arms, and a second foreign operation through aliases. Extend source and runtime correspondence and compare full profiles using static admission, ordered effects, live capabilities, and completion evidence. [COR-13 follow-up](research/language-design/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md#cor-13-follow-up-on-foreign-resource-lifetimes)

2. **Advance identity and dependency completeness in parallel where independent.** Reconcile stable IDs, content-derived values, explicit lineage, and scoped selectors against import, rename/move, duplication, split/merge, recursive groups, call-site edits, and branch conflicts. Bind calls to explicit contract/implementation choices; test negative and fallback dependency reads; retain `UNKNOWN` when completeness or provenance is absent. Do not settle OpHash/ImpHash or canonical SPG fields by implication.
3. **Complete the evidence and backend-preservation gate.** Continue Scenario 34's source-to-query proof from explicit wire-envelope assumptions through the supported encoder and program fragment. For LL-020 / Scenario 96, extend the version-pinned source-to-LLVM corpus from integer overflow and partial operations to memory bounds, provenance, and optimization-sensitive facts. Run a narrow shared workload against reference semantics and a second implementation/backend, comparing results, ordered effects, errors, resources, diagnostics, and rejected constructs. Keep the QF_LIA profile restricted and fail closed.

   Scenario 133 supplies a pinned Rust result for COR-13 under ADR-016. General translation, native foreign effects, and the stage 0–2 bootstrap chain still need separate conformance evidence. [Generated Rust probe](research/compiler-and-translation/RT-13/RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md)

   Scenario 96A runs wrapping and checked integer operations through generated LLVM IR with ordered effect payloads. The finite corpus matches under O0 and O3. A verifier-accepted mutation demonstrates the need for a separate source observation check. [LLVM integer corpus](research/compiler-and-translation/RT-13/RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md)

   Scenario 96B compares one-past formation, byte reads and view identity across adjacent and overlapping ranges. Two verifier-accepted controls violate the source contract while accessing the same live allocation. [LLVM byte-view corpus](research/compiler-and-translation/RT-13/RESEARCH-SCENARIO-96B-LLVM-BYTE-VIEW-PRESERVATION.md)
   **Integrated Rust foundation study (RT-29):** map Rust's language capabilities, compiler/runtime techniques, libraries, package/build ecosystem, and interoperability to LLMLang's capability model. Separate Rust as semantic prior art from Rust as an implementation substrate; classify every capability by layer (language, compiler/Toolchain, runtime/library, external service), record mismatches and non-transferable guarantees, and validate high-impact candidates with pinned reproducible probes. Consume existing Rust scenarios and generated-Rust evidence rather than repeating them. No Rust semantics or component is adopted by this study.
4. **Run representative workloads and human/agent evaluations.** Use RT-01's shared acceptance criteria and CLI corpus with C/Python host references when LLMLang candidates can execute it. Define workload weights before aggregate scoring; measure task success, repair attempts, diagnostics, context/token use, review quality, and scope violations separately from correctness.
5. **Extend security and operational-lifecycle evidence.** Build on RT-16's threat model and policy fixtures with persistent multi-client authorization, concurrent reservation, crash recovery around apply/accept/commit/push/publication, hostile build-worker sandbox cases, and authenticated evidence/provenance. Specify which lifecycle actions require human or policy approval.
6. **Continue package/cache validation without fixing speculative wire formats.** For RT-11/12/19/23, measure controlled cold/warm and scoped-change cases, implement a public immutable snapshot adapter and canonical dependency extraction against the SPG, and extend manifest/cache-index validation. Keep ZIP, binary index, codec, and provider choices provisional until the contracts and resource bounds are validated.
7. **Refresh the option matrix and synthesis gates from results.** Record evidence class, assumptions, confidence, unknowns, compatibility constraints, and falsifiers for each surviving vector. Compare complete candidate specifications only after major criteria have evidence; publish workload-weight sensitivity and preserve failed or unknown cases.
   **Freestanding feasibility:** start RT-37 profile constraints alongside the shared semantics and backend gates, then run the embedded firmware pilot before RT-38 microkernel experiments; both contribute evidence to the final compatibility audit. [RT-37](research/runtime-and-systems/RT-37/README.md) · [RT-38](research/runtime-and-systems/RT-38/README.md).

8. **[Run the final feature compatibility and feasibility audit after all other research is complete](https://github.com/aivibeflow/LLMLang/issues/370).** This is the final cross-cutting research activity, not an early filter for individual research proposals. Start it only after all other registered aspect research, required follow-up experiments, evidence reviews, and candidate-vector synthesis have reached their documented completion gates. Re-read the then-current feature registry and the relevant research, option-matrix, and dependency-map evidence; do not rely on earlier preliminary estimates or assume the registry's current feature count will remain unchanged.

   - Assess every registered feature and every materially relevant feature pair or group for compatibility and feasibility. Distinguish direct contradictions from conditional tensions, dependencies, scope limitations, unresolved evidence, and ordinary implementation difficulty.
   - Use explicit classifications: **Compatible**, **Conditional**, **Conflict**, **Impossible**, **Unresolved**, and **Not Selected**. A **Conflict** or **Impossible** finding must identify the exact assumptions and requirements that cannot jointly be satisfied; complexity, cost, or lack of a current prototype is not by itself proof of impossibility.
   - For each conditional relationship, state the conditions, required architectural mechanisms, and guarantees or scope restrictions. For each conflict, document the evidence, affected feature vectors, possible resolutions, and which guarantees or capabilities each resolution would weaken or remove.
   - Check both pairwise relationships and higher-order interactions; pairwise compatibility alone must not be treated as proof that a complete feature set is coherent. Include determinism/concurrency, verification/completeness, dependency-analysis soundness/completeness, cross-language translation, SPG identity/versioning, merge behavior, ownership/FFI/resource lifetimes, and any additional interactions exposed by the completed research.
   - Produce a traceable compatibility/feasibility matrix covering the full registry, a conflict-and-limitation register, and a concise executive assessment. Every finding must link to the relevant feature IDs, research evidence, assumptions, and dependency-map edges. Explicitly mark unreviewed or insufficiently evidenced relationships rather than silently treating them as compatible.
   - Update the research taxonomy, dependency map, option matrix, and this plan with the audit results and resulting follow-up decisions. The audit must not silently delete or rewrite feature requests; proposed changes require explicit rationale and traceability.

   **Expected output:** `research/FEATURE-COMPATIBILITY-AND-FEASIBILITY-AUDIT.md` (or a successor path recorded in the plan), with supporting machine-readable matrix if useful. **Exit condition:** every current registry feature has an explicit assessment; all material pairwise and higher-order interactions are classified or explicitly marked unresolved; every claimed conflict/impossibility is evidence-backed; and remaining limitations and decisions are recorded for specification synthesis.

9. **[Draft the RFC after the final audit and candidate comparison](https://github.com/aivibeflow/LLMLang/issues/371).** Select and baseline only a coherent candidate with explicit rationale, compatibility evidence, and unresolved risks. A narrower RFC may proceed earlier only if it clearly scopes and labels unresolved design choices. Keep ADR-014 Proposed and defer end-to-end semantic-merge implementation/benchmarks until synthesis narrows the representation and merge policy.

## External evidence and approval dependencies

The [RT-19 process crash experiment](research/toolchain-and-collaboration/RT-19/RT-19-SQLITE-GIT-PROCESS-RECOVERY-2026-11-24.md) checks a persistent journal, eight abrupt process exits, exact Git-tree/root recovery, and idempotent outcomes for one closed source profile. The broader gate still needs source/SPG/dependency/authorization binding and production Git/filesystem recovery. An [independent MCP client](research/toolchain-and-collaboration/RT-19/RT-19-MCP-STDIO-SCHEMA-INTEROPERABILITY-2026-11-24.md) covers the in-memory lifecycle. Persistent integration and an authenticated multi-client environment remain external to that fixture. Maintainer approval of ADR-015 and any production backend selection remains an external decision. These gates do not prevent further contract-level comparisons, but they prevent treating the proposed protocol as implementation-complete.

The open inputs below affect implementation selection. Record the result in the linked study at its exact scope and revision when the input becomes available. Continue evidence collection for eligible work while each input is pending.

| External input | Current evidence and release condition |
| --- | --- |
| Independent review of research claims and evidence quality | Stage 0.2 and [#285](https://github.com/aivibeflow/LLMLang/issues/285) have two pending review artifacts. A reviewer records adjudication against the archive-pinned [24-document queue](research/quality-audit/2026-11-23-root-census-observations.json) and the separate [eight-claim handoff](research/quality-audit/2026-11-23-independent-review-handoff.md). Independent reviews are unavailable. Keep the review gate pending until the two artifacts have independent dispositions. |
| Maintainer approval of the review method and candidate decisions | The [quality review protocol](research/research-management/QUALITY-REVIEW-PROTOCOL.md) and case-specific evidence gates remain proposed. Record explicit approval for §0.2 conventions and use the applicable [decision records](TODO.md) for architecture adoption. Baseline RFC selection follows [#370](https://github.com/aivibeflow/LLMLang/issues/370) and [#371](https://github.com/aivibeflow/LLMLang/issues/371). |
| Original author or archival execution records | The [eight original-run provenance gaps](research/research-management/RT-00/RT-00-QUALITY-RULES-PROVENANCE-RECHECK-2026-11-23.md) need attested original source state and execution data where recoverable. If recovery fails, record the missing information and retain independent reruns under their own identities. Historical provenance affects §0.1 and §0.2 evidence claims. |
| Scenario 16 archival or author record | The [scenario crosswalk](research/research-management/RT-00/RT-00-A-SCENARIO-CROSSWALK-RECONCILIATION-2026-11-23.md) and [history recheck](research/research-management/RT-00/RT-00-B-12-TEXT-OVERLAP-2026-11-24.md#scenario-16-boundary) preserve the numbering gap. An author or archive record can establish the intended scope or location. |
| Upstream reference scope and foreign-contract evidence | The [reference register](research/references/README.md) records omissions in partial upstream snapshots. Obtain exact source revisions or authoritative contract evidence for claims that depend on an omitted reference or a foreign provider. [RT-36](research/formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md) and [CF-008](research/formal-verification/CONTRACT-FORMALIZATION-CORPUS/cases/CF-008-linux-pipe-transfer.md) identify how undischarged assumptions constrain the claim. |
| Logos native computation trust decision | The [completed proof audit](research/formal-verification/RT-07/RT-07-LOGOS-VERDICT-PROOF-2026-11-25.md) checks the pinned verifier and the source composition, both with the same 2,118 native computation axioms. Record explicit acceptance of the native computation trust boundary or adopt a revision or restricted proof meeting the selected policy. The isolated [model witness replacement](research/formal-verification/RT-07/RT-07-LOGOS-KERNEL-MODEL-WITNESS-2026-11-24.md) covers one dependency and leaves the pinned verdict axioms in scope. |
| Stakeholder, developer and reviewer participation | The controlled human-review comparison in [RT-02 / #287](https://github.com/aivibeflow/LLMLang/issues/287) needs domain stakeholders, predeclared thresholds and results bound to the same requirement/evidence revision. Adoption evaluation in [#336](https://github.com/aivibeflow/LLMLang/issues/336) needs representative human-developer and reviewer observations. |
| Access to selected model and provider versions for controlled experiments | [RT-31 / #342](https://github.com/aivibeflow/LLMLang/issues/342) needs the selected provider and model profile together with exact toolchain, task, configuration and environment records. Record unavailable profiles as coverage gaps in the comparative result. |
| Representative workloads and controlled measurement hardware | Compile-speedup [#318](https://github.com/aivibeflow/LLMLang/issues/318), scalability [#332](https://github.com/aivibeflow/LLMLang/issues/332), and package delivery [#333](https://github.com/aivibeflow/LLMLang/issues/333) need the representative workloads and environment required by their measurement gates. Pin target hardware or emulator/toolchain revisions for [RT-37 / #440](https://github.com/aivibeflow/LLMLang/issues/440) and [RT-38 / #441](https://github.com/aivibeflow/LLMLang/issues/441) and record when timing evidence applies only to an emulator. Applying the [checked seL4 design correspondence](research/runtime-and-systems/RT-38/RT-38-SEL4-REFINED-LOOKUP-2026-11-24.md) to LLMLang needs a checked source model and separate native implementation evidence. |
| Physical Cortex-M3 register, DMA and timing evidence | The [RT-37 metadata comparison](research/runtime-and-systems/RT-37/RT-37-MMIO-METADATA-AND-CAPABILITIES-2026-11-24.md) records the absence of an exact LM3S SVD in the pinned dataset. An authoritative target register contract and board observations are needed before transferring emulator MMIO or timing results to physical devices. The [DMA lease model](research/runtime-and-systems/RT-37/RT-37-DMA-LEASE-OWNERSHIP-2026-11-24.md) needs a concrete controller contract for descriptor identity, quiescence, queue drain, cache visibility and device address ranges. |
| Authorized native performance-counter measurement | [RT-26 Linux performance counters](research/runtime-and-systems/RT-26/RT-26-LINUX-PERFORMANCE-COUNTER-BOUNDARY-2026-11-24.md) records EPERM for every tested self-thread perf event. Selection of cycle- or instruction-based resource contracts requires a measurement environment with usable events and explicit target and scheduling scope. |
| Native checkout on selected filesystem profiles | The [profile-bound Git paths](research/toolchain-and-collaboration/RT-24/RT-24-PROFILE-BOUND-GIT-PATHS-2026-11-25.md) experiment in §4.4 and §4.5 covers case-sensitive Linux and a declared UTF-8 comparison profile. Cross-platform exit evidence needs native checkouts on the selected case-insensitive or normalization-sensitive filesystems with pinned OS, filesystem and Git versions. |

The active Stage 0 gates also require technical claim-level and experiment review. The published evidence currently supports the completed scoped checks in §0.1–0.2. Broader results and dispositions remain in [#284](https://github.com/aivibeflow/LLMLang/issues/284) and [#285](https://github.com/aivibeflow/LLMLang/issues/285).

## GitHub issue index

The issue numbers below are navigation links, not execution priorities. Execute the research work packages in the dependency-aware stage/order defined by this plan and the predecessor gates in each issue. Complexity estimates and detailed checklists are maintained in the issue bodies. Research 18 has one canonical active issue (#318); the duplicate #301 is closed.

| Research order | Work package | GitHub issue |
|---:|---|---:|
| 01 | Reconcile the research corpus | [#284](https://github.com/aivibeflow/LLMLang/issues/284) |
| 02 | Research quality and decision rules | [#285](https://github.com/aivibeflow/LLMLang/issues/285) |
| 03 | Research taxonomy and cross-aspect dependency map | [#286](https://github.com/aivibeflow/LLMLang/issues/286) |
| 04 | Intent, requirements, and human-validated formalization (RT-02) | [#287](https://github.com/aivibeflow/LLMLang/issues/287) |
| 05 | Semantic Program Graph and program representation | [#288](https://github.com/aivibeflow/LLMLang/issues/288) |
| 06 | Semantic identity, hashes, and canonical encoding | [#289](https://github.com/aivibeflow/LLMLang/issues/289) |
| 07 | Contracts and compatible implementations | [#290](https://github.com/aivibeflow/LLMLang/issues/290) |
| 08 | Core language semantics (RT-03) | [#291](https://github.com/aivibeflow/LLMLang/issues/291) |
| 09 | Type, effect, ownership, and capability alternatives (RT-04) | [#292](https://github.com/aivibeflow/LLMLang/issues/292) |
| 10 | Formal semantics of the language | [#293](https://github.com/aivibeflow/LLMLang/issues/293) |
| 11 | Proof architecture and proof boundary | [#294](https://github.com/aivibeflow/LLMLang/issues/294) |
| 12 | Lean, Logos, SMT, and solver integration | [#295](https://github.com/aivibeflow/LLMLang/issues/295) |
| 13 | Verified SPG-to-Lean pipeline (RT-32) | [#296](https://github.com/aivibeflow/LLMLang/issues/296) |
| 14 | Correctness of optimization and translation | [#297](https://github.com/aivibeflow/LLMLang/issues/297) |
| 15 | Semantic dependency model | [#298](https://github.com/aivibeflow/LLMLang/issues/298) |
| 16 | Incremental analysis and invalidation | [#299](https://github.com/aivibeflow/LLMLang/issues/299) |
| 17 | Semantic build and cache graph | [#300](https://github.com/aivibeflow/LLMLang/issues/300) |
| 18 | Quantify compilation speedup | [#318](https://github.com/aivibeflow/LLMLang/issues/318) |
| 19 | Semantic object storage | [#319](https://github.com/aivibeflow/LLMLang/issues/319) |
| 20 | Git representation and repository model | [#320](https://github.com/aivibeflow/LLMLang/issues/320) |
| 21 | Semantic diff, merge, and conflict resolution | [#321](https://github.com/aivibeflow/LLMLang/issues/321) |
| 22 | Git integration workflow | [#322](https://github.com/aivibeflow/LLMLang/issues/322) |
| 23 | End-to-end semantic merge and synchronized commit lifecycle | [#323](https://github.com/aivibeflow/LLMLang/issues/323) |
| 24 | Type system and data model | [#324](https://github.com/aivibeflow/LLMLang/issues/324) |
| 25 | Execution semantics and runtime architecture | [#325](https://github.com/aivibeflow/LLMLang/issues/325) |
| 26 | POSIX architecture and conformance | [#326](https://github.com/aivibeflow/LLMLang/issues/326) |
| 27 | Translation architecture | [#327](https://github.com/aivibeflow/LLMLang/issues/327) |
| 28 | Required bidirectional translation study (RT-30) | [#328](https://github.com/aivibeflow/LLMLang/issues/328) |
| 29 | Backend selection and cross-backend validation | [#329](https://github.com/aivibeflow/LLMLang/issues/329) |
| 30 | LLVM backend | [#330](https://github.com/aivibeflow/LLMLang/issues/330) |
| 31 | Implementation discovery, selection, and optimization | [#331](https://github.com/aivibeflow/LLMLang/issues/331) |
| 32 | Performance and scalability | [#332](https://github.com/aivibeflow/LLMLang/issues/332) |
| 33 | Package indexes and dynamic package delivery | [#333](https://github.com/aivibeflow/LLMLang/issues/333) |
| 34 | Parallel development and collaboration | [#334](https://github.com/aivibeflow/LLMLang/issues/334) |
| 35 | Security, trust, and reproducibility | [#335](https://github.com/aivibeflow/LLMLang/issues/335) |
| 36 | Developer experience and adoption | [#336](https://github.com/aivibeflow/LLMLang/issues/336) |
| 37 | Toolchain Server and semantic development API (RT-19) | [#337](https://github.com/aivibeflow/LLMLang/issues/337) |
| 38 | LLM patch planning, caller migration, hash propagation, and verified commit (RT-20) | [#338](https://github.com/aivibeflow/LLMLang/issues/338) |
| 39 | Knowledge Context (LL-026) | [#339](https://github.com/aivibeflow/LLMLang/issues/339) |
| 40 | Task Context (LL-027) | [#340](https://github.com/aivibeflow/LLMLang/issues/340) |
| 41 | Joint integration and exit criteria | [#341](https://github.com/aivibeflow/LLMLang/issues/341) |
| 42 | AI-oriented syntax experimentation and MCP session observability (RT-31) | [#342](https://github.com/aivibeflow/LLMLang/issues/342) |
| 43 | Final feature compatibility and feasibility audit | [#370](https://github.com/aivibeflow/LLMLang/issues/370) |
| 44 | Draft the LLMLang RFC after final audit and candidate comparison | [#371](https://github.com/aivibeflow/LLMLang/issues/371) |


The package work has separate implementation details in Stage 7.2 and the semantic storage work in Stage 4. Do not skip a gate because a document or prototype exists: each artifact is evidence for only the claims and inputs it actually covers, not proof that its design is correct or complete.

---

**Additional tracked research directions:** [RT-37 / #440](https://github.com/aivibeflow/LLMLang/issues/440) (Stage 5.4) and [RT-38 / #441](https://github.com/aivibeflow/LLMLang/issues/441) (Stage 6.5); order is determined by the dependency gates above.

# 9. Maintenance
- Update this plan when a research item starts, produces evidence, is superseded, or reaches an accepted decision.
- Keep stable item names and links where possible so other documents can refer to them.
- Add new work to the appropriate stage rather than appending an unprioritized backlog.
- Record cross-stage dependencies explicitly.
- When a decision is accepted, update `TODO.md` and the relevant research/design document; do not mark it accepted solely because this plan recommends it.
- Keep implementation bugs and short-lived tasks in the appropriate issue/task tracker; this document is the ordered research and development programme.
- Review this plan whenever the research corpus or architecture changes materially.
