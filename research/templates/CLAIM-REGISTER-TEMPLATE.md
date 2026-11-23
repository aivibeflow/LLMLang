# Claim and proposed-decision traceability template

**Status:** Blank research aid; not an accepted LLMLang decision  
**Related:** [Research Quality Review Protocol](../QUALITY-REVIEW-PROTOCOL.md), [quality-rule study](../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md)

Use **one primary evidence class** per material claim; a supporting class may be separately noted. **Recommendation**, **proposed decision**, and **accepted decision** are different from empirical proof strength. Small single-claim scenarios may use an inline equivalent instead of a full table.

| Claim ID | Verifiable assertion | Primary evidence class | Exact scope/assumptions | Source/fixture/proof/output permalink | Confidence and reason | Falsifier or missing evidence | RT/LL/PLAN and draft impact |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C-01 | <single scoped claim> | Observation / Assumption / Hypothesis / Prior-art claim / Model result / Experimental result / Proof / Accepted decision | <revision, model, bounds> | <immutable revision and reference> | <high/medium/low + reason> | <negative probe or gap> | <links or none> |

## Negative/rejected/UNKNOWN register

| Case ID | Test/alternative | Expected predicate | Actual result / not run | Evidence pointer | Scope of rejection / next action |
| --- | --- | --- | --- | --- | --- |
| N-01 | <counterexample or failed option> | <predicate> | <observed/UNKNOWN/not run> | <link> | <conclusion and remaining test> |

## Candidate `draft/` change map

| Proposal ID | Draft file and exact section | Supporting claim IDs | Input evidence + limitations | LL question / dependency | Decision status and durable record |
| --- | --- | --- | --- | --- | --- |
| D-01 | `draft/<file>#<heading>` | C-01 | <pinned link> | LL-XXX / PLAN | **Proposed**; no acceptance record yet |

**Rules:** never set status **Accepted** without explicit authorized project decision and linked PR/record. An approved documentation-process PR does not itself select an LLMLang semantic rule. If a proposed draft change lacks evidence, leave it proposed and record the gap.
