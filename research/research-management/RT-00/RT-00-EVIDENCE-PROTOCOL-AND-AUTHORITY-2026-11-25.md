# Evidence protocol and decision authority

**Research item:** RT-00, PLAN §0.2  
**Status:** Verified methodology and scoped application  
**Baseline:** research/all, 1ec32a8c356a1a44c3531a59e25d73a60120313b  
**Evidence type:** Archived evidence reconciliation and executable checks  
**Updated:** 2026-11-25  
**Normative boundary:** Exploratory only

## Problem and hypotheses

H1. The template and protocol can express a claim's class, reproduction route, adverse outcome, and authority as separately inspectable facts. A structurally complete report would still need a claim-specific test or source.

H2. Five recent studies preserve their adverse outcomes and their testing boundaries when checked against their archived ledgers. An omitted adverse row or an unexpected accepted authority mapping would falsify the corresponding check.

## Prior art and alternatives

[Structural warning coverage](RT-00-C-QUALITY-WARNING-COVERAGE-2026-11-25.md) found both missed nested documents and a syntactically conforming placeholder. [Warning adjudication](RT-00-C-NEGATIVE-RESULT-WARNING-ADJUDICATION-2026-11-25.md) located real negative evidence through content and citations. Use heading checks for navigation and read the evidence when adjudicating claims. [Decision history](RT-00-C-DRAFT-BOUNDARY-HISTORY-2026-11-25.md) and the [draft citation audit](RT-00-C-DRAFT-CITATION-RESEARCH-ALL-AUDIT-2026-11-25.md) supply independent archive checks for provenance and the target of each citation.

## Formal model and assumptions

The unit of review is a claim with a scope, evidence pointer, and authority. A reported experimental result is bound to its recorded inputs, execution environment, and oracle. A theorem is bound to its imported definitions and assumptions. A decision requires a durable accepted authority record. The checker assumes Git object integrity and reads immutable file contents through the pinned tree.

## Experiments and method

Inspect the template and policy status, check the authority summary, then recalculate the recorded checks below from the five archived machine-readable ledgers. The cohort spans a proof session, native/cross-target ABI observations, a pressure benchmark, a kernel I/O benchmark, and a migration fixture.

**Fixture:** [Underlying pinned file paths and SHA-256 digests](EVIDENCE-PROTOCOL-BOUNDARY-01/evidence.json)  
**Tool versions:** CPython 3.12.14, Git 2.56.1, Linux 6.18.57 x86-64  
**Expected output:** exit 0 and JSON byte-identical to the checked-in ledger in both hash-seed runs

```sh
p=research/research-management/RT-00/EVIDENCE-PROTOCOL-BOUNDARY-01
for seed in 37 71; do
  PYTHONHASHSEED="$seed" python3 -B "$p/check.py" > "/tmp/llmlang-rt00-evidence-$seed.json" || exit 1
  cmp "$p/evidence.json" "/tmp/llmlang-rt00-evidence-$seed.json" || exit 1
done
```

## Results and evidence classification

| Claim | Primary class | Verified scope and evidence | Falsifier or missing evidence |
| --- | --- | --- | --- |
| QP-01 | Observation | Ten named template sections, including claim class, reproduction, limitations, and draft impact. The template requires a command, fixture, version, expected output, and Q1–Q5 disposition. | Loss of a field or inability to record an adverse outcome. |
| QP-02 | Archived experimental result | RT-13 retains 16 wrong-symbol refusals across its build profiles and 96 native observations on its single native host. | Adverse profile succeeds or recorded native scope changes. |
| QP-03 | Archived experimental result | RT-25 retains 28 startup errors in 280 runs. RT-26 records 92,160 admission decisions across 72 runs. RT-28 records 48 cases and two complete cutover-and-rollback outcomes. | A run or outcome is missing, or definition of an outcome changes. |
| QP-04 | Archived proof result and counterexample observations | RT-38 records four theorem names with two passing clean sessions, both shortcut flags disabled, three expected Quickcheck counterexamples and one expected genuine Nitpick counterexample. | Proof shortcut enabled, missing negative control, invalid session receipt, or failure of correspondence beyond the tested model. |
| QP-05 | Observation about accepted decisions | The separate authority audit maps two accepted feature entries among 143, F-PORT-002 and F-TOOL-003. The architecture record explicitly carries acceptance; the quality protocol explicitly carries proposal status. | Authority change documented in an accepted record or an unsupported accepted registry mapping. |

### Negative results, rejected options and UNKNOWN

QP-02 through QP-04 retain refusals, startup errors, bounded cutover, and proof counterexamples with distinct meanings. The archived structural check's placeholder is a negative control for using formatting as evidence. The cases do not establish whether a production-compatible implementation would produce the same distributions.

## Limitations and threats to validity

The checker re-reads archived results and does not initiate new benchmark or proof runs. Five purposively selected studies are insufficient for a claim of uniform historical compliance. Original-run attestations, independent adjudication, and maintainer adoption still require their own records.

## Decision boundary and recommendation

Use the ten-section structure or a content-equivalent structure for future reports. Record scope and adverse outcomes at claim level. Require runnable evidence or a source-specific procedure for archived and non-executable findings. Use the explicit authority record to identify accepted project decisions.

## Draft impact and traceability

PLAN §0.2, RT-00, and issue #285. No change proposed to an LL decision or candidate draft rule. [Research protocol](../QUALITY-REVIEW-PROTOCOL.md) and [architecture authority record](../../../draft/ARCHITECTURE-DECISIONS.md).

## Reproduction and quality-gate review

Both runs exited 0 and reproduced the committed JSON byte-for-byte. Q1 passes for the bounded questions, Q2 passes for pinned archive and template provenance, Q3 passes for auditable replay of the archive checks, Q4 passes for retained adverse controls, and Q5 passes for the stated draft boundary. External independent review and approval are tracked separately in PLAN §0.2.
