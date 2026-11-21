# RT-00 B6 — Unified Contradictions and Unresolved Register — 2026-11-21

**Status:** consolidated audit register; no architecture decisions accepted  
**Baseline:** `main` at `017e64b87c87371309197a392165258b8b088dd1`  
**Inputs:** merged B3 and B-02b.1–B-02b.5 reports; PLAN and inventory at baseline; B4 PR #127 and B5 PR #130 as explicitly pending branch inputs; open RT-17/RT-23/RT-26 PR state at audit time.  
**Purpose:** distinguish actual contradictions, apparent conflicts explained by scope/time, scoped supersession, stale status, design/proof gaps, and branch-only evidence.  
**Boundary:** this is an audit register, not an architecture decision record and not a claim that all unresolved items are solved.

## 1. Executive result

The reviewed corpus does **not** establish a single direct semantic contradiction that requires an immediate language/runtime architecture choice. The principal issue is that the documents operate at different semantic layers, evidence strengths, revisions, and time snapshots. Several apparent conflicts disappear when those dimensions are made explicit.

The audit records:
- **4 reconciled apparent conflicts** where claims are compatible once scope is preserved;
- **18 open terminology, design, proof, evidence, provenance, traceability, or validation gaps**;
- **7 scoped historical/supersession/companion relationships** that must not be widened to whole-document replacement;
- **5 stale-status or count/revision discrepancies** requiring documentation reconciliation;
- **5 branch/PR integration states** whose evidence is not part of the main-baseline corpus.

The machine-readable companion register contains **39 records** with stable B6-local IDs, classification, status, source paths, finding, required action, and decision/maintenance boundary. B6 IDs identify audit records only; they are not promoted to global research Claim IDs.

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

No current core contradiction was confirmed by this pass. This is a bounded conclusion over the inspected documents, not a proof that no contradiction exists anywhere in all 488 artifacts.

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
- **B6-U06 — RT-26:** the main baseline has no complete merged evidence chain across the required resource dimensions and enforcement mechanisms.
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

The B4 report also identifies one repeated exact blob: the same Apache-2.0 license text in OCI and REAPI snapshots. It is expected duplicated licensing material, not a duplicate research result or prototype. No file deletion or deduplication is recommended.

## 6. Stale status and evidence discrepancies

1. **B6-F01 — Lean version/status:** implementation and workflow pin Lean 4.36.0, while some Scenario 33/34 and family README current-status text still says 4.34.0 or cites older CI as latest. B-02b.1 records successful exact-head CI evidence. Update current status while retaining historical toolchain/run references.
2. **B6-F02 — Scenario 30/31/32 headers:** statements such as “no wrapper”, “no code changes”, and “CI running” lag later implementation/CI. Scenario 31 also contains a status claim inconsistent with its own implementation section. Preserve chronology; add dated current status.
3. **B6-F03 — Scenario 102 test count:** report says seven focused tests passed; current test file contains eight `test_*` methods. The audited source revision and exact CI selection have not been reconciled.
4. **B6-F04 — PLAN historical counts:** PLAN §0.1 includes older snapshots (24 RT/94 DEP, 243/245 prototype files, 471/474 research artifacts). The current main inventory at the B6 baseline records 26 RT, 108 DEP, 248 prototype-tree files and 488 research artifacts. Historical blocks may remain, but current-status text must not repeat old counts as current.
5. **B6-F05 — 243 prototype-file review count:** 243 is a historical review-snapshot scope, not the current 248-file prototype tree. B4 PR #127 updates the README caveat and inventory; those changes are pending until merged.

A historical run passing at its own revision is not “stale evidence” for that historical claim. It is stale only if presented as the latest/current validation without a current revision binding.

## 7. Pending PR and branch-only evidence at audit time

The following state was observed before creating B6; none is treated as merged main evidence:

| PR | Subject | State and treatment |
|---|---|---|
| #126 | RT-23 exact-tree recovery | Open, reported non-mergeable; authored against an earlier base and depends on merged #125. Rebase/reconcile separately. |
| #127 | B4 duplicate/supersession audit | Open; Required CI and policy run succeeded. Supersession and inventory changes are pending review/merge. |
| #128 | RT-17 diagnostic replay | Open branch-only evidence; exclude from main until merged. |
| #129 | RT-26 budget reservation | Open branch-only evidence; bounded schedule experiment does not close all RT-26 dimensions. |
| #130 | B5 traceability graph audit | Open; Required CI and policy run succeeded. B5 is used as a pending audit input, not a main-baseline artifact. |

B6 is based directly on the current main SHA, not on PR #127 or #130. This avoids creating an implicit dependent PR. Once those PRs merge, the register should be refreshed against the new main and pending records promoted only within their validated scope.

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

1. Refresh B6 after PR #127 and #130 are reviewed/merged; reconcile the inventory and research index without rewriting historical evidence.
2. Perform RT-00-C reproducibility closure for the remaining claim/evidence gaps, starting with Scenario 102 test-count reconciliation and exact experiment provenance.
3. Perform RT-00-D external snapshot/provenance closure.
4. Perform RT-00-E current full-corpus link/anchor audit.
5. Reconcile PLAN §0.1 current-state summary and historical snapshots.
6. Continue targeted semantic duplicate review only where shared claims, test fixtures, or evidence indicate plausible overlap; do not claim all-pairs semantic completeness without that method.

## 10. Conclusion

**Disposition: B6 register consolidation complete as a bounded audit pass. No direct core semantic contradiction was confirmed.** The corpus has material unresolved design/proof/provenance/traceability issues and several stale status/count discrepancies. Scoped supersession and complementary study relationships are recorded without deleting history or promoting unmerged branch evidence.

RT-00 is **not complete**. B6 does not close the remaining proof, reproducibility, external-source, link/anchor, or PLAN acceptance gates. No architecture decision was made.
