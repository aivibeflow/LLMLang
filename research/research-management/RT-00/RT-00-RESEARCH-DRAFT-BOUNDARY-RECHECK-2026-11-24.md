# RT-00 — Research-to-draft boundary recheck

**Research item:** `PLAN.md` §0.2 — keep `research/` exploratory and `draft/` as the candidate specification  
**Date:** 2026-11-24  
**Baseline main:** `738853e571b7e04915441b91075cae9046292cb8`  
**Compared historical report baselines:** `0aa0527b0df36b94ba3b4ec4a4bd06aca0db2915` (negative-result recheck), `5434727fae861c42887419f63c06b22cc6c33807` (evidence-class recheck)  
**Evidence type:** bounded document and decision-boundary crosswalk  
**Status:** selected-artifact audit; no architecture decision or policy adoption

## Question and method

Does the current repository distinguish proposed research from candidate-specification text and accepted decisions clearly enough that linking a study cannot silently promote its recommendation? I inspected the draft index, the accepted architecture decision, the proposed quality-review protocol, and three recent research outputs: the evidence-class, negative-result, and owned-provider/generated-Rust studies. Each cited path was checked at its stated historical baseline or at current main. This checks recorded boundaries and links; it does not independently validate the scientific claims or infer author intent.

## Crosswalk

| Artifact | Recorded status and link | What is supported | Boundary / open item |
|---|---|---|---|
| `draft/README.md` | Says research proposals and alternatives belong in `research/` and do not become normative by reference; links RT-05 as non-normative related research. | A direct, discoverable directory-level rule separates research links from candidate requirements. | This statement is itself a documented convention; it does not show every historical report or future change followed it. |
| `draft/ARCHITECTURE-DECISIONS.md` | One accepted decision, dated 2026-11-20, names scope, five concrete rules, non-decisions, consequences and reconsideration triggers. It links RT-20 and Scenarios 109–111/134. | The decision limits compatibility to one coherent toolchain build, excludes several cross-version wire promises, separates callable type compatibility from behavioral refinement, and identifies triggers for reopening. The research links are explicitly not amendments. | This document does not prove every accepted rule has complete evidence; contract identity, behavior refinement, and any external/persistent boundary remain separate work. |
| `QUALITY-REVIEW-PROTOCOL.md` | Explicitly proposed, not accepted. Separates recommendation/proposed-decision status from evidence class; requires an exact candidate-spec diff and durable maintainer decision before updating `draft/`. | A concrete workflow prevents a research report, PR, test or link from being treated as an accepted decision by itself. | The protocol hypotheses have not had independent reviewer trials; maintainer adoption and broad validation remain pending. |
| RT-00 evidence-class recheck | Calls itself a bounded selected-document audit and concludes it does not close Stage 0.2; recommendations do not select the RT-19 backend, RT-25 allocator or full RT-32 proof architecture. | Observation, bounded result, proof, recommendation and accepted-decision status are kept separate for the four sampled studies. | Its source baseline is `5434727`; this is document classification, not a fresh reproduction or independent decision review. |
| RT-00 negative-result recheck | Says it adds no normative rule and distinguishes tested bounded counterexamples, recommendation-scoped exclusions and unavailable evidence. | An experiment-specific rejection is not generalized into permanent architecture policy. | Historical source baseline `0aa0527`; no global negative-result vocabulary or full-corpus audit. |
| RT-04 owned-provider replay / RT-13 generated Rust | Report finite fixtures, exact commands and host details, and leave the choice of transfer policy, general lowering and independent review open. No draft amendment is linked. | These results support comparing observed caller outcomes while preserving explicit profile, source and resource limits. | They do not choose a public ownership contract or establish general runtime/FFI semantics. |

## Findings

The inspected current artifacts show three distinct layers: research reports state scoped evidence and limits; the draft index labels related research non-normative; and an accepted architecture decision records an exact scope, non-decisions and reconsideration triggers. The proposed review protocol fills a process gap by requiring an exact draft change and an explicit approval record. In this sample, the recent empirical studies do not silently modify or amend the accepted decision.

This is evidence that the repository has a workable boundary pattern in the selected artifacts, not proof that the whole corpus or every future PR follows it. The protocol remains proposed, the accepted decision does not settle behavioral contract refinement or future external-data requirements, and the research results still need their own technical review before use in implementation selection.

## Remaining dependencies

- Apply the boundary check across all major historical reports and future candidate-spec changes; verify each proposed draft diff against exact source-bound claims.
- Independent review of the Stage 0.2 quality protocol and the pending claim-review artifacts; maintainer approval of the protocol.
- Reconcile technical claims and external/runtime scope before proposing amendments to the accepted architecture decision.

**Conclusion:** the selected artifacts preserve the `research/` versus `draft/` boundary and make the accepted decision's scope inspectable. The evidence supports this bounded process finding only; it does not complete Stage 0.2 or close the external review gates.
