# <Research item / question>

**Research item:** RT-XX / Scenario N / PLAN §X.Y  
**Status:** Proposed research / bounded result / partially reproduced / decision needed  
**Baseline:** `<exact source commit SHA and branch>`  
**Evidence type:** Prior art / Model / Executable / Formal proof / Mixed  
**Updated:** YYYY-MM-DD  
**Normative boundary:** Exploratory only; no `draft/` rule accepted

## Problem and hypotheses

State the answerable question and scope. H1/H2: falsifiable claims, not conclusions.

## Prior art and alternatives

Link primary sources with editions/versions and compared alternatives. Identify rejected or deliberately excluded options.

## Formal model and assumptions

State definitions, grammar, axioms, bounds, profiles, assumed premises; or explain why N/A.

## Experiments and method

Name exact source revision, input fixtures, provenance, tools, versions, configuration, seeds, limits, independent oracle, raw output paths. For source-only studies/proofs, explain the type-specific reproduction route.

**Fixture:** `<path and digest or inline inputs; required if Evidence type is Executable>`  
**Tool versions:** `<exact versions and platform; required if Executable>`  
**Expected output:** `<exit code and invariant/range; required if Executable>`

```sh
# Exact reproduction commands for executable evidence; remove with N/A explanation otherwise
python3 -B path/to/experiment.py
```

## Results and evidence classification

Classify each material claim: Observation / Assumption / Hypothesis / Prior-art claim / Model result / Experimental result / Proof / Accepted decision. For claims affecting `draft/`, link a stable [claim register](CLAIM-REGISTER-TEMPLATE.md). A recommendation is not a decision.

| Claim ID | Claim | Primary class | Scope/bounds | Evidence pointer | Confidence and reason | Falsifier/missing evidence |
| --- | --- | --- | --- | --- | --- | --- |
| C-01 | <one sentence> | <class> | <scope> | <permalink/output> | <reason> | <counterexample> |

### Negative results, rejected options and UNKNOWN

Record failures, timeouts/UNKNOWN, counterexamples, and rejected alternatives, or justified N/A.

## Limitations and threats to validity

State missing source-to-model/compiler correspondence, untested targets, sampling and unverified assumptions.

## Decision boundary and recommendation

Exactly what is supported and not supported; recommendation and explicit **not accepted / accepted with durable record** status.

## Draft impact and traceability

Link RT/scenario, PLAN section, LL ID in TODO (or explain why none), affected `draft/` section or **none**. If a spec change is proposed, provide claim-ID → evidence pointer → exact draft section → approval record mapping.

## Reproduction and quality-gate review

State exact outputs, environment, and Q1–Q5: pass / fail / N/A with rationale / not reviewed. Structural checks are not evidence review.

See [quality review protocol](../research-management/QUALITY-REVIEW-PROTOCOL.md).
