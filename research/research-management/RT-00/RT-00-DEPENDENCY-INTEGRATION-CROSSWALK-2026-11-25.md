# Dependency register evidence and integrated checks

**Scope.** PLAN §0.3 and [issue #286](https://github.com/aivibeflow/LLMLang/issues/286), on research/all at 92a121b69d5d3389ee413850f33dc62d6d63bcbb. This study checks the register's evidence navigation and verifies two newly completed composition checks against their exact archived outcomes.

## Register coverage

The checker reads all 264 edge rows, the 38 aspect identifiers, and the pinned Git tree. It requires every edge identifier exactly once, valid endpoints, and a documented relation. It records each row's scope label and each relative evidence path and target blob. All 223 relative path occurrences across 94 edge rows resolve. The other 170 rows have no relative evidence path in their scope cells. Some have relevant evidence reachable through area-level sections. Their lack of direct links gives no basis for accepting or discarding the hypothesis. Fragment existence, external URLs and the meaning of individual cited results are separate checks. DEP-087 was missing the final Markdown table delimiter. Its wording and evidence remain identical after the delimiter repair.

## Changes supported by the pinned evidence

| Edge | Verified result | Remaining hypothesis or implementation work |
| --- | --- | --- |
| DEP-012 | Exact replacement changes 5,720 ordered observations for each native route. A signed statement for a different action and mismatched rebuilt bytes both refuse. | Completeness of real ambient dependency inventories and reuse granularity. |
| DEP-043 | The current local provider admits cache reuse through a scoped Ed25519 attestation. Old attestations and original-generation signatures refuse even when a candidate still has an address. | Actual publisher trust roots and remote package resolution and policy. |
| DEP-048 | Revocation refuses rollback and leaves the new selection intact. Fresh authority can select the old bytes with the current parent. | Remote fencing and competing revocation across processes. |
| DEP-054 | Missing descriptor audit, stale evidence, narrow projection, and missing artifact identity each refuse. Both native routes record three admitted transitions and eleven refusals. | Evidence-issuer trust, source correspondence and wider effect and evidence profiles. |
| DEP-094 | The structured tool covers 16,468 inputs, including twelve exact register projections, eight refusal controls and three semantic mutants. This supersedes the CLI-only characterization for the bounded dependency-tool claim. | Selected full language profile, source correspondence and project-wide self-development. |

[Exact release admission](../planning-and-synthesis/EXACT-PROVIDER-RELEASE-2026-11-25.md) connects cache admission, ordered evidence and publication in a single local catalog. The checker recomputes 167,936 native observations from eight executions and validates verdict classes and selected-state preservation from the saved receipt. The [structured dependency tool](../../toolchain-and-collaboration/RT-21/RT-21-STRUCTURED-DEPENDENCY-BOOTSTRAP-2026-11-25.md) contributes a separate authoring check. The current synthesis reconciles the stale CLI-proxy description and links the new release scope directly on DEP-043 and DEP-054. The map remains a research hypothesis register with scoped evidence, with ongoing validation at the individual studies.

## Reproduce

Run from the branch checkout with Git 2.56.1 and CPython 3.12.14 on Linux x86-64 6.18.57. The archived [ledger](DEPENDENCY-INTEGRATION-01/evidence.json) holds the edge-by-edge report paths, target blobs, and exact input hashes. The check rereads pinned archives and recalculates the crosswalk. It uses the separate native reports for their recorded execution provenance.

```sh
study=research/research-management/RT-00/DEPENDENCY-INTEGRATION-01
PYTHONHASHSEED=8 python3 -B "$study/check.py" > /tmp/llmlang-dependency-integration.json
cmp "$study/evidence.json" /tmp/llmlang-dependency-integration.json
```
