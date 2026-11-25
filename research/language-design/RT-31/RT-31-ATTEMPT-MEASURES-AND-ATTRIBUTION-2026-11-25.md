# RT-31 attempt outcomes, error attribution and reporting

A syntax study needs distinct records for measured failures, attributed causes, terminal success and operational observations. First submissions and repairs have different denominators. Pending observations and unavailable measurements remain visible.

## Candidate report

| Dimension | Required treatment |
| --- | --- |
| Failed check | Preserve parse, semantic, type/effect/ownership, contract, unsupported claim, MCP/tool call and task completion checks separately. A single attempt can fail several checks. |
| Cause attribution | Use exact session, attempt, snapshot, Toolchain and producer binding. Preserve multiple known causes and explicitly record unknown evidence. |
| Outcome | Report first submissions and later repairs with separate counts of successes, failures and pending attempts. Include the semantic oracle coverage independent of parser success. |
| Uncertainty | Report how unresolved attempts can affect the observed rates. In a live experiment, estimate uncertainty from matched task or participant blocks under the predeclared analysis. |
| Cost and effort | Report token and cost telemetry, latency and human review effort with denominators, units and missing-data counts. |
| Reproducibility | Retain exact study assignment, data, toolchain and analysis identities. |

The attribution labels describe model error, ambiguous or incomplete context, Toolchain defects and environment failures. They are distinct from which semantic check recorded a failure. The archived attribution checker matches all 66,048 event schedules. Across those schedules, 43,176 contain multiple known causes and 12,288 contain unknown evidence or lack a terminal marker. These counts characterize the synthetic scheduler. [Attempt attribution](RT-31-MCP-ATTEMPT-ATTRIBUTION-2026-11-25.md) · [Counterbalanced study plan](RT-31-AUTHORING-CORPUS-AND-PROTOCOL-2026-11-25.md)

## Synthetic reporting check

The attempt fixture contains seven first submissions and four repairs. The first-pass results are one success, five failures and one pending. Repairs give two successes, one failure and one pending. Seven distinct failure categories are present. Depending on the pending first submission, the first-pass success numerator is between one and two over seven. This is a missing-outcome bound in the fixture.

The reporting script checks 24 delivery orders and an exact repeated record. A stale attempt does not change results. Token, cost and latency fields each have eight observations and three missing values. Review timing has six observations and five missing values. The emitted medians use only the known values.

All attempt measures here are synthetic. Live reporting needs model/provider telemetry, verified semantic obligations, independent reviewer labels where applicable, and approved tasks. Held-out promotion and real sample sizes remain separate.

## Reproduce

Use CPython 3.12.14. Both hash seeds 37 and 71 yield evidence SHA-256 `86e51a330205c71c0b303c5c3ecdd820f96649f715b4a0527e16306384872ff1`. [Evidence ledger](ATTEMPT-MEASURES-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/language-design/RT-31/ATTEMPT-MEASURES-01/check.py > /tmp/rt31-attempt-measures.json
```
