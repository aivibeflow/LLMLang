# RT-00 B6 — Unified Contradictions and Unresolved Register — 2026-11-21

**Status:** consolidated audit register; no architecture decisions accepted  
**Baseline:** `main` at `b0142c27f5632a859c379b78a10cb22f500ebfd8`  
**Inputs:** merged B3 and B-02b.1–B-02b.5 reports; PLAN and inventory; original B4 PR #127 and B5 PR #130 audit-time branch inputs; current-main refresh after RT-23 PR #126 merged. The original 017e64b snapshot is retained in §§7 and 11; current state is in §12.  
**Purpose:** distinguish actual contradictions, apparent conflicts explained by scope/time, scoped supersession, stale status, design/proof gaps, and branch-only evidence.  
**Boundary:** this is an audit register, not an architecture decision record and not a claim that all unresolved items are solved.

## 1. Executive result

The reviewed corpus does **not** establish a single direct semantic contradiction that requires an immediate language/runtime architecture choice. The principal issue is that the documents operate at different semantic layers, evidence strengths, revisions, and time snapshots. Several apparent conflicts disappear when those dimensions are made explicit.

The audit records:
- **4 reconciled apparent conflicts** where claims are compatible once scope is preserved;
- **18 open terminology, design, proof, evidence, provenance, traceability, or validation gaps**;
- **7 scoped historical/supersession/companion relationships** that must not be widened to whole-document replacement;
- **6 stale-status or count/revision discrepancies** requiring documentation reconciliation;
- **5 branch/PR integration states** whose evidence is not part of the main-baseline corpus.

The machine-readable companion register contains **40 records** with stable B6-local IDs, classification, status, source paths, finding, required action, and decision/maintenance boundary. B6 IDs identify audit records only; they are not promoted to global research Claim IDs.

## 2. Conflict taxonomy and disposition

Use these distinctions consistently:

| Classification | Meaning | Treatment |
|---|---|---|
| Direct contradiction | Two current claims address the same subject, scope, assumptions and time but cannot both hold | None confirmed in the reviewed core set; reopen if a specific counterexample is found |
| Apparent conflict | Claims look incompatible but differ by layer, scope, input, or evidence type | Retain both with explicit boundary |
| Temporal/status conflict | An earlier status is overtaken by later implementation or CI evidence | Preserve historical record; update current status with dated evidence |
| Supersession | A later artifact replaces a defined section/claim within an explicit scope | Record a scoped edge; never infer whole-document deletion |
| Complementary progression | A later study adds a distinct input, proof, execution, or falsifier | Keep both; link as progression/companion |
| Unresolved gap | A required mapping, proof, decision, or evidence edge is absent | Keep UNKNOWN/unresolved; state closure criterion |
| Pending branch evidence | Evidence exists only on an unmerged PR branch | Exclude from main-baseline conclusions until merge and re-audit |

## 3. Reconciled apparent conflicts — not contradictions

### B6-C01 — LLVM backend and canonical source semantics

The LLVM backend research assigns source semantics and semantic validation to LLMLang; LLVM is a replaceable backend. RT-05's SPG experiment explicitly does not validate lowering. Scenario 96A/96B add bounded LLVM experiments, not a general source-to-runtime proof. These statements are consistent. The unresolved item is the proof obligation, not the choice between LLVM and SPG.

### B6-C02 — Scenario 32/33 parser bridge and Scenario 34 open proof boundary

The parser bridge can decode a typed query and compare CPC assumptions against a Lean-constructed expected term. Scenario 34's remaining source-to-query/CPC obligations ask whether that expected term is exactly the formula derived from the source program. Structural parser-state binding and source-derived semantic correspondence are different propositions.

### B6-C03 — Experimental dependency discovery and formal dependency semantics

Scenarios 20–24 study discovery, interventions, scheduling and interaction analysis. Scenario 25 describes a formal semantic dependency direction. The experimental studies provide observations and exploration mechanisms; they do not claim to be the final formal semantics. This is a progression, not a contradiction.

### B6-C04 — RT-05 resource vocabulary and RT-26 enforcement

RT-05 can represent resource-related concepts while excluding runtime accounting/enforcement from its validated scope. RT-26 independently studies attribution, task hierarchy, limits, overshoot, handlers and platform enforcement. Representation is not enforcement evidence.

No current core contradiction was confirmed by this pass. This is a bounded conclusion over the inspected documents, not a proof that no contradiction exists anywhere in all 493 current-main artifacts.

## 4. Unified unresolved register

The companion JSON records every item in machine-readable form. The main categories are:

### 4.1 Terminology and design decisions

- **B6-T01 — ImpHash / ImplHash:** unresolved naming discrepancy. No silent normalization.
- **B6-U01 — identity layers:** semantic value, managed occurrence/slot, stable ID and lineage have no normative lifecycle mapping.
- **B6-U02 — contract conformance:** call-site refinement is not mapped to OpHash, ImplHash, CCHash and exact evidence.
- **B6-U03 — cache/action identity:** complete per-action dependency closure, resolved binding inputs and evidence freshness remain open.
- **B6-U05 — package trust:** content identity, provider closure, provenance authenticity and publisher trust remain independent gates.
- **B6-U07 — authority composition:** parent budget delegation, task capabilities, tool/agent authorization and OS/container enforcement are not composed into one explicit model.

### 4.2 Proof and implementation boundaries

- **B6-U04 — LLVM preservation:** finite pinned probes do not establish general lowering, target or runtime preservation.
- **B6-U06 — RT-26:** main now contains a bounded cooperative cumulative-budget reservation model and a four-method test module. This is partial model evidence only; exact historical execution-to-blob provenance, the other mandatory resource dimensions, attribution, real-time limits/overshoot, handlers, and platform enforcement remain unresolved.
- **B6-U08 — Scenario 34:** SC-1–SC-7 support the restricted Int/Bool source-to-canonical-query fragment; Python JSON/CPC binding, trusted-computing-base and SCW-30–41 obligations remain distinct.
- **B6-U09 — Python test coverage:** 32 test modules / 376 named test methods are not equivalent to the 12 modules / 177 methods selected by the reviewed Required CI configuration.
- **B6-U10 — reproduction provenance:** selected native/LLVM slices are reproduced, but exact environment and input/output binding is not uniform. Scenario 130's historical report lacks the exact SQLite source ID, so only version-level equivalence is established.

### 4.3 Corpus-wide graph and provenance

- **B6-U11 — external snapshots:** partial snapshots, missing relative links and incomplete proto import closure remain limitations.
- **B6-U12 — links and anchors:** the historical link scan does not validate the current full corpus.
- **B6-U13 — Claim IDs:** no corpus-wide stable claim namespace exists. B6 IDs must not be mistaken for one.
- **B6-U14 — test/evidence state:** declared, discovered, executed, passed and claim-supporting tests must be separate relations.
- **B6-U15 — PLAN:** scheduling metadata does not prove exit-criteria acceptance.
- **B6-U16 — semantic duplicate coverage:** B4's exact-blob scan is exhaustive for its pinned tree; semantic candidate review is bounded, not all-pairs.
- **B6-U17 — Scenario 16:** missing number remains unexplained; do not renumber or fabricate.

## 5. Scoped supersession and complementary relationships

These relationships are deliberately narrow:

| B6 record | Relationship | Required interpretation |
|---|---|---|
| B6-S01 | Git semantic repository proposal → current Git representation/merge and ADR-014 | Only the external-KV-authoritative proposal/current direction is superseded; preserve broader historical research |
| B6-S02 | Initial related-project scan → deep comparison | Partial supersession for four deeply reviewed projects only |
| B6-S03 | Scenario 134 wire matrix | Inactive as a current internal implementation requirement under the recorded same-build decision; prior-art value remains |
| B6-S04 | Scenario 31 initial query representation → Scenarios 32–34 | Supersede only the initial text-oriented path/bridge sketches; retain the strict QF_LIA profile |
| B6-S05 | Scenario 30 “no Lean wrapper” status → Scenario 33 | Historical status only; source-derived proof-binding goal remains open |
| B6-R01 | Scenario 95 study + execution report | Companion artifacts; neither replaces the other |
| B6-R02 | Scenario 96, 96A and 96B | Broad study plus two distinct focused evidence layers; no whole-study supersession |

The B4 report and its current-main revalidation in PR #152 identify one repeated exact blob: the same Apache-2.0 license text in OCI and REAPI snapshots. It is expected duplicated licensing material, not a duplicate research result or prototype. No file deletion or deduplication is recommended.

## 6. Stale status and evidence discrepancies

1. **B6-F01 — Lean version/status:** implementation and workflow pin Lean 4.36.0, while some Scenario 33/34 and family README current-status text still says 4.34.0 or cites older CI as latest. B-02b.1 records successful exact-head CI evidence. Update current status while retaining historical toolchain/run references.
2. **B6-F02 — Scenario 30/31/32 headers:** statements such as “no wrapper”, “no code changes”, and “CI running” lag later implementation/CI. Scenario 31 also contains a status claim inconsistent with its own implementation section. Preserve chronology; add dated current status.
3. **B6-F03 — Scenario 102 test count:** report says seven focused tests passed; current test file contains eight `test_*` methods. The audited source revision and exact CI selection have not been reconciled.
4. **B6-F04 — PLAN historical counts:** PLAN §0.1 includes older snapshots (24 RT/94 DEP, 243/245 prototype files, 471/474 research artifacts). Current main at b0142c2 contains 26 RT, 108 DEP, 250 prototype-tree files and 493 research artifacts; the main inventory manifest still records 488. Historical blocks may remain, but current-status text must not repeat old counts as current.
5. **B6-F05 — 243 prototype-file review count:** 242 is the semantic-review aggregate of individually role-mapped prototype artifacts; 245 is an earlier PLAN aggregate with unresolved per-file basis; 248 is the previous inventory path count; current main has 250 prototype paths. PR #149 proposes the README/PLAN/manifest reconciliation but remains unmerged.

A historical run passing at its own revision is not “stale evidence” for that historical claim. It is stale only if presented as the latest/current validation without a current revision binding.

## 7. Pending PR and branch-only evidence at the original audit snapshot

This table preserves the original state observed at the 017e64b audit baseline before PR #126 merged. It is historical; current PR status is recorded in §12. None of the then-pending evidence was treated as merged main evidence at that time:

| PR | Subject | State and treatment |
|---|---|---|
| #126 | RT-23 exact-tree recovery | Open, reported non-mergeable; authored against an earlier base and depends on merged #125. Rebase/reconcile separately. |
| #127 | B4 duplicate/supersession audit | Open; Required CI and policy run succeeded. Supersession and inventory changes are pending review/merge. |
| #128 | RT-17 diagnostic replay | Open branch-only evidence; exclude from main until merged. |
| #129 | RT-26 budget reservation | Open branch-only evidence; bounded schedule experiment does not close all RT-26 dimensions. |
| #130 | B5 traceability graph audit | Open; Required CI and policy run succeeded. B5 is used as a pending audit input, not a main-baseline artifact. |

At the original audit snapshot, B6 was based directly on main, not on PR #127 or #130. The register has now been refreshed to b0142c2 in §12; B4 PR #152 is merged and B5 PR #151 remains branch-only.

## 8. Completion criteria for unresolved items

An item may be closed only when its closure evidence is attached to the exact affected claim and revision:

- terminology: an explicit glossary/decision update plus migrated references;
- design boundary: a selected decision or an explicit retained-alternatives record with consumer rules;
- proof: theorem/checker evidence and declared trusted boundary;
- test: exact test selection, execution record, result and claim coverage;
- reproduction: exact source revision, toolchain, command, environment, inputs and outputs;
- provenance: source revision, completeness/import closure and retrieval integrity;
- supersession: section/claim-level scope and successor reference;
- PLAN: evidence that the stated exit criterion is satisfied, not merely that work is scheduled or a report exists.

UNKNOWN is not success. “Not found in this pass” is not “does not exist.” A green CI workflow does not prove an unselected test or unrelated research claim.

## 9. Next work

1. Refresh B6 after replacement PRs #151/#152 and the current inventory/index PR #149 are integrated; reconcile the inventory and research index without rewriting historical evidence.
2. Perform RT-00-C reproducibility closure for the remaining claim/evidence gaps, starting with Scenario 102 test-count reconciliation and exact experiment provenance.
3. Perform RT-00-D external snapshot/provenance closure.
4. Perform RT-00-E current full-corpus link/anchor audit.
5. Reconcile PLAN §0.1 current-state summary and historical snapshots.
6. Continue targeted semantic duplicate review only where shared claims, test fixtures, or evidence indicate plausible overlap; do not claim all-pairs semantic completeness without that method.

## 10. Conclusion

**Disposition: B6 register consolidation complete as a bounded audit pass. No direct core semantic contradiction was confirmed.** The corpus has material unresolved design/proof/provenance/traceability issues and several stale status/count discrepancies. Scoped supersession and complementary study relationships are recorded without deleting history or promoting unmerged branch evidence.

RT-00 is **not complete**. B6 does not close the remaining proof, reproducibility, external-source, link/anchor, or PLAN acceptance gates. No architecture decision was made.


## 11. Historical C–F follow-up snapshot (pre-RT-23/B4 merge) — 2026-11-21

This addendum updates the sequencing/status in §9 without changing the original 40-record B6 register or treating any open PR as merged.

### Completed bounded follow-ups (branch-only until merged)

1. **C — reproducibility:** PR #136 adds a non-required workflow. Run [44937172020](https://github.com/aivibeflow/LLMLang/actions/runs/44937172020) passed RT-16 tests 24/24 and CLI Python/C host references 34/34 each. PR #138 records exact commit/tool/input hashes and the retained artifact. PR #137 corrects the stale RT-04 native-reproduction opening status using the already recorded run #44774296240 (10/10 native commands and 2/2 LLVM probes). Remaining SQLite source identity, Provider benchmark/profiler, Scenario 36 fuel, and broad prototype reproducibility gaps remain open.
2. **D — external provenance:** PR #141 corrects the stale D report statement about README provenance documentation and revalidates 13/13 local snapshot blobs against the manifest. It does not re-fetch upstream repositories or repeat signature verification. OCI/Alive2/REAPI completeness and external URL/version refresh remain open.
3. **E — local links and anchors:** PR #142 scans 251 Markdown + 3 MDX files in its PR checkout (254 documents). Run [44938052704](https://github.com/aivibeflow/LLMLang/actions/runs/44938052704) records 2,876 link occurrences, 1,312 unique, 1,630 accepted, 82 errors, and 1,164 excluded. All 82 errors are in upstream snapshots: 44 MCP root-absolute upstream-site paths, 32 OCI omitted-document links, and six Alive2 omitted assets/README links. No LLMLang-authored local link or available-target anchor error was found. External URL availability was not checked because the scan was offline.
4. **F — document alignment:** PR #145 verifies 26 unique RT areas and 108 unique DEP edges, with all endpoints valid, no duplicate IDs or self-loops, and the two documented SCCs. Candidate/non-normative statuses remain aligned. The inventory role-review counts remain distinct (242 individual role mappings, 245 prior PLAN aggregate, 248 previous manifest paths, 250 current prototype paths).
5. **A — inventory freshness follow-up:** PR #146's recursive audit scanned exact main commit `017e64b87c87371309197a392165258b8b088dd1`: 490 research artifacts excluding the manifest, 249 prototype files, 250 Markdown, 3 MDX, 202 Python, 23 Lean, and 136 Scenario-named documents. PR #126 then added two research artifacts (RT-23 report/test) with no deletions; current main b0142c2 therefore has 493 research artifacts, 250 prototype files, 252 Markdown, 3 MDX, 203 Python, and 23 Lean. At the earlier 017e64b baseline, the manifest had two missing RT-24 paths and four SHA/size mismatches. After the RT-23 additions and B4 report merge, current main has five missing paths and five stale blob metadata records; PR #149 proposes their reconciliation. Artifact [14720512241](https://github.com/aivibeflow/LLMLang/actions/runs/44938305811/artifacts/14720512241) preserves the exact report.

### Pending branch reconciliation

- RT-23 PR #126 is merged into main at `b52ba2f`; its exact-tree recovery report and eight focused tests are part of the baseline, with crash durability and worktree-generation gaps still open. PR #152 is also merged at `b0142c2`; its B4 audit report is now in main.
- Original B4 #127 and B5 #130 are closed as stale. B4 replacement PR [#152](https://github.com/aivibeflow/LLMLang/pull/152) is merged; B5 replacement PR [#151](https://github.com/aivibeflow/LLMLang/pull/151) remains branch-only.
- Inventory refresh PR [#149](https://github.com/aivibeflow/LLMLang/pull/149) is based on current main b0142c2; it proposes 494 records including its own report, five missing path records, and five refreshed blob records. It is not merged; current main manifest still has 488 records.
- PR #128 (RT-17) and #129 (RT-26) remain branch-only.
- C/D/E/F follow-up PRs #136–#145 and G PR #147 remain branch-only; their bounded results are not part of main unless merged.
- B6 is itself a branch-only 40-record snapshot, not a live state database. No merge has been performed.

**Updated sequencing:** C, D, and E have bounded evidence follow-ups; F has a current cross-document alignment pass; A inventory freshness remains open pending manifest correction. Next, reconcile the B4/B5 branches and manifest, then refresh B6, complete claim-level traceability/reproducibility and index coverage, and only then prepare the final G report. RT-00 is not complete.


## 12. Current-main refresh after RT-23 merge — 2026-11-21

This addendum refreshes the B6 baseline and PR status while preserving the original 40 audit-record IDs and their historical classifications.

- **Baseline:** main `b0142c27f5632a859c379b78a10cb22f500ebfd8`, which includes merged PRs #126 and #152.
- **Current tree:** 493 research artifacts, 250 prototype paths, 252 Markdown, 203 Python, 23 Lean, 26 RT areas, 108 DEP edges. The count is derived from the exhaustive 017e64b recursive audit plus exact commit deltas through b0142c2 (two RT-23 paths and one B4 report added, zero deletions), not a fresh recursive enumeration at b0142c2.
- **Main inventory manifest:** still 488 records, five missing paths (RT-24 report/test, RT-23 report/test, and B4 audit report), and five stale blob metadata records. PR #149 proposes the correction and remains unmerged.
- **Prototype count meanings:** 242 individually role-mapped artifacts; 245 earlier PLAN aggregate; 248 previous manifest prototype paths; 250 current main prototype paths. These remain distinct measures.
- **B4:** PR #127 closed as stale; replacement [#152](https://github.com/aivibeflow/LLMLang/pull/152) performs incremental exact SHA grouping over 492 current-main artifacts. It finds only the expected OCI/REAPI Apache-2.0 licence pair; semantic candidate review remains bounded.
- **B5:** PR #130 closed as stale; replacement [#151](https://github.com/aivibeflow/LLMLang/pull/151) updates counts and adds the merged RT-23 trace. Claim-level graph completeness remains open.
- **RT-23:** PR #126 is merged. Eight focused tests cover the local publication/retry model; crash/power-loss durability, remote pushes, receipt retention, and monotonic worktree generation remain unresolved.
- **Other pending work:** PRs #128/#129 and C/D/E/F/G follow-ups remain branch-only. Do not promote their results into main-baseline conclusions before integration and re-audit.

The JSON companion's baseline and B6-P03/P04/P05 records reflect these changes. The original 40-record classification counts remain stable except that the current pending-PR-state count is four after RT-23 PR #126 merged.

**Disposition remains unchanged: RT-00 is not complete.**


### E follow-up result — PR #160

The current-main E scan completed on final merge checkout `3643ea099bdd89c64e9fa468bddbc3ad29e80155`: 253 Markdown + 3 MDX = 256 documents; 2,891 occurrences, 1,318 unique, 1,641 accepted, 82 errors, 1,168 excluded. The 82 errors remain confined to copied upstream MCP/OCI/Alive2 snapshots. Lychee returned exit code 2; the evidence-gathering workflow job succeeded and preserved artifact [14721739745](https://github.com/aivibeflow/LLMLang/actions/runs/44942704138/artifacts/14721739745). The E PR is still branch-only. External URLs, non-Markdown resources, and index completeness remain unresolved.


## 13. Current evidence delta — Scenario 130 claim pilot and C–E closure slices

This addendum updates evidence status without deleting or renumbering the original 40 B6 records. The machine-readable companion now contains 41 records; B6-local IDs remain distinct from research Claim IDs.

### 13.1 Scenario 130 claim-level pilot

B5 PR #151 adds a [bounded Scenario 130 claim-level traceability pilot](RT-00-B-05-01-SCENARIO-130-CLAIM-TRACEABILITY-PILOT-2026-11-21.md). It assigns local IDs S130-C01–C05 and traces four falsifiable claims through report sections, model/probe symbols, four test methods, exact source blobs, Required CI run #44942585935, native reproduction run #44942585953, and retained artifacts. The fifth broader independent-provider reconciliation implication remains conditional. This demonstrates a bounded extraction method; it does not establish a global Claim ID scheme or corpus-wide traceability completeness.

### 13.2 Scenario 130 source identity and archive integrity

C-02 PR #164 enforces a prospective Python SQLite 3.53.1 source-ID baseline and checks the SQLite, Python, and LLVM source/package archive digests. Required CI passed; native run #44942585953 passed 10/10 native commands and 2/2 LLVM probes. The recorded Python SQLite source ID matched the new baseline. The original historical Scenario 130 report did not preserve its source ID, so the new pin is not retrospective historical proof. Ubuntu package archive identity, runner/container image digests, and rustup bootstrap identity remain open.

### 13.3 Scenario 102 test-count reconciliation

The current eight-method Scenario 102 test module has the same blob SHA at current main and Required CI run #44801357527's head. That workflow discovered the RT-04-01 suite and passed 364 tests, including all eight methods. The historical focused report's seven-test count remains a separate earlier execution record whose exact source revision is unavailable. B6-F03 is therefore partially reconciled for current execution but retains the historical provenance gap.

### 13.4 External references and snapshot provenance

D PR #168 revalidates 13/13 local snapshot blob identities; OCI/Alive2/REAPI completeness remains partial. E PR #160 completes the bounded offline local link/anchor scan. E-02 PR #169 checks all 17 curated external URLs: 16 returned content, while POSIX returned 403 to the checker and remains indeterminate. This is not a corpus-wide external URL check.

### 13.5 Current branch status

- A inventory reconciliation: PR #149, 494 branch records; audit and Required CI pass.
- B5 graph and Scenario 130 pilot: PR #151; Required CI is pending on the latest pilot update.
- B6 current register: PR #154, 41 B6 records after this append-only evidence update.
- C: PRs #164–#167; #164 native reproduction 10/10 + LLVM 2/2, #165 smoke workflow pass, #166 native reproduction 10/10 + LLVM 2/2, #167 evidence refresh.
- D: PR #168, 13/13 local snapshot blob matches.
- E: PR #160 local scan; PR #169 curated external reachability.
- F/G: PRs #158/#155 current-main cross-document and status refreshes.

All these PRs remain branch-only. Their evidence must not be described as integrated main evidence until reviewed and merged. The final inventory must be refreshed after any integration. RT-00 remains open.


## 13. B6 refresh — RT-26 bounded evidence now present on main (2026-11-21)

The earlier B6-U06 statement that the main baseline had no merged evidence chain is stale in one narrow respect. Current main contains `research/RT-26-COOPERATIVE-BUDGET-RESERVATION.md` and `research/PROTOTYPES/BUDGET-RESERVATION-01/test_budget_reservation.py` (four test methods). The report records a fixed acyclic hierarchy and cumulative cooperative budget: four-of-six split check/charge schedules overshoot; 720 reservation/settlement orders are checked over 4,320 transitions; retry and cancellation behavior are covered.

This changes the evidence classification from “no merged model evidence” to “bounded cooperative model evidence present.” It does not close RT-26. The exact PR #129 test execution checkout is not retained as a source-blob-bound run record. The current test blob was independently run in CPython 3.13.5 with 4/4 passing methods in the RT-00 B-05-02 pilot branch; that pilot itself remains unmerged and its execution is not a CPython 3.12.14 reproduction. No evidence is claimed for instantaneous memory, CPU, disk/network I/O, coroutine switches, PMU counters, OS enforcement, throttling, fairness, or production atomicity.

The separate PR #174 cancellation/terminal-settlement experiment remains branch-only and is not incorporated. B6-U07 authority composition remains unresolved. No architecture decision is implied.
