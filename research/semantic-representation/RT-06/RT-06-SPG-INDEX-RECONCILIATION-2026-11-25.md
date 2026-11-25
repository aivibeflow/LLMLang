# RT-06 — Candidate dependency-index reconciliation

The [dependency-index contract](SEMANTIC-DEPENDENCY-INDEX.md) identifies concrete canonical inputs that a production index will need. This report checks the current candidate implementation and records which parts can already be compared against project evidence. It addresses [PLAN §3.1](../../../PLAN.md#31-semantic-dependency-model) and [#298](https://github.com/aivibeflow/LLMLang/issues/298).

| Boundary | Reconciled candidate behavior | Required for normative adoption |
| --- | --- | --- |
| Canonical semantic subject | Declaration schema v2 and the SPG admission suite check typed objects, immutable content and selected snapshots. | Choose the canonical object kinds, exact operation and implementation envelopes, artifact granularity and identity encoding. [LL-001](../../../PLAN.md#ll-001--define-the-canonical-ophash-envelope) · [Identity decisions](../../../PLAN.md#semantic-identity-and-artifact-store) |
| Call edges and contract boundary | Dependency projection v3 records each required caller contract and follows the selected callee for its provided contract. It preserves exact call-site identity in the admitted subset. | Approve the canonical identity of operation, caller contract, declaration occurrence, direct pin and abstract binding. Establish correspondence for all admitted source forms. [Typed dependency discovery](RT-06-SPG-GUARDED-DEPENDENCY-DISCOVERY-2026-11-25.md) |
| Ordered effects and recursion | The ordered-lowering and recursive-identity suites cover the candidate traversal rules and internal group edges. The SCC study checks analysis schedules separately from identity. | Select operational observation rules, admissible cycle representation and recursive group identity semantics. [Formal semantics](../../../PLAN.md#21-formal-semantics-of-the-language) · [SCC scheduling](RT-06-SCC-DEPENDENCY-SCHEDULING-2026-11-25.md) |
| Hash and observation roles | The candidate separates consumed dependencies and reverse retrieval. Profile-specific metadata can become observable. | Approve hash-relevant edge kinds and correspondence per observation scope. [LL-005](../../../PLAN.md#ll-005--define-hash-relevant-dependency-edges-and-cycles) |
| Invalidation and authority | Impact-plan format v5 checks exact baseline, scoped completeness and call dispositions. Missing or stale evidence requires conservative validation. | Approve evidence issuer and compatibility rules and integrate trusted index construction with Toolchain publication. [LL-008](../../../PLAN.md#ll-008--define-compatibility-evidence-and-evidence-reuse-rules) · [ADR-015](../../../draft/adr/015-toolchain-server-semantic-api.md) |

The fresh archive replay passed 104 tests across eight suites, covering the typed index, SPG shape and admission, ordered lowering, recursive identity, impact planning, scoped binding and call-site refactoring. The runner also reads the pinned decision records. LL-001, LL-004, LL-005, LL-006 and LL-008 are open at the archive. ADR-014 and ADR-015 have Proposed status, and the dependency index describes itself as a research proposal. These are distinct acceptance conditions from passing a prototype.

The rechecked inputs support an implementation that derives the index as a versioned projection from authoritative SPG and compiler facts. Existing checked fixtures remain usable under their recorded profiles. Normative reconciliation still requires an accepted canonical schema and formal profile, plus confirmed correspondence across the adopted scope. The project tracks candidate compatibility and eventual RFC selection separately. [Compatibility audit #370](https://github.com/aivibeflow/LLMLang/issues/370) · [RFC #371](https://github.com/aivibeflow/LLMLang/issues/371)

## Reproduce

Use Git 2.56.1 and CPython 3.12.14 from the repository root with archive commit `ba145588905bda1c80b150a87bccf75d8da1a647`. The [ledger](SPG-INDEX-RECONCILIATION-01/evidence.json) records exact document digests, candidate version names and suite totals.

```sh
set -eu
fixture=research/semantic-representation/RT-06/SPG-INDEX-RECONCILIATION-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
