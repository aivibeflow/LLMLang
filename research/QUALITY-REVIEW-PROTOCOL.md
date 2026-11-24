# Research Quality Review Protocol (proposed pilot)

**Status:** Proposed Stage 0.2 research-documentation process; not accepted policy  
**Research item:** [PLAN.md §0.2](../PLAN.md#02-establish-research-quality-and-decision-rules), [issue #285](https://github.com/aivibeflow/LLMLang/issues/285)  
**Baseline reviewed:** `main` at `99151528f8bcc51ffccb6eaee8213acb0f9905c9` (2026-11-23)  
**Scope:** First-party research reports and proposed changes to candidate specifications; no LLMLang semantic rule is selected

## 1. Question, hypotheses, and alternatives

**Problem:** A report can contain a correct bounded result but be read as an accepted language rule. A checklist alone cannot establish the correctness of a claim.

**Hypothesis H1 (untested):** Explicit evidence class, scope, reproduction pointer, and decision status improve reviewers' ability to locate and correctly interpret evidence.

**Hypothesis H2 (untested):** Warning-only structural checks can detect missing minimum fields without forcing unrelated historical reports into a new outline.

**Alternatives:** (A) retroactively rewrite all reports; (B) manual review only; (C) warning-first templates for new reports and targeted review of high-impact existing reports. [Rollout comparison](RT-00/RT-00-QUALITY-RULES-ROLLOUT-OPTIONS-2026-11-23.md) recommends C provisionally. [Evidence-shape comparison](RT-00/RT-00-QUALITY-RULES-EVIDENCE-SHAPE-RECHECK-2026-11-23.md) favors common minimum metadata with evidence-specific attachments. Neither is an accepted policy.

**Prior art within LLMLang:** [Quality-rule proposal](RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md), [preparation pack](preparation/README.md), [research taxonomy](RESEARCH-TAXONOMY.md), [open questions](../TODO.md), [draft boundary](../draft/README.md).

## 2. Report structure and conditional model

New substantive reports should expose **problem/question, hypotheses, prior art, alternatives, formal model/assumptions, experiments/method, results, limitations, decision boundary, and draft impact**. Combine headings for concise studies, but preserve those fields or give an explicit *not applicable* justification. Start from [report template](templates/REPORT-TEMPLATE.md); add a [claim register](templates/CLAIM-REGISTER-TEMPLATE.md) for material mixed-evidence or draft-impacting claims. The contents of older reports are not retroactively deemed invalid solely because of layout.

A material claim is a statement used to support a recommendation, candidate spec change, conformance assertion, or research completion assertion. Record at least: stable claim ID, one-sentence assertion, **one primary evidence class**, exact scope/assumptions/bounds, provenance link, confidence with reason, possible falsifier or missing correspondence, downstream link. Related supporting evidence classes may be included in a separate field.

| Class | What it means | Boundary |
| --- | --- | --- |
| Observation | A source or run was inspected under named conditions | Does not prove general behavior or correctness |
| Assumption | Premise used conditionally | Does not establish that the premise is true |
| Hypothesis / conjecture | Falsifiable but unverified proposition | Not a design guarantee |
| Prior-art claim | Statement grounded in a versioned authoritative source | Source behavior is not an LLMLang choice |
| Model result | Outcome within defined grammar/axioms/bounds | No source-to-model correspondence implied |
| Experimental result | Outcome from specified executable fixture/toolchain | No universal correctness implied |
| Proof | Auditable derivation with stated definitions and assumptions | No source/compiler correspondence without separate argument |
| Accepted decision | Authorized and linked durable decision record | Governance choice, not a scientific proof |

**Recommendation** and **proposed decision** are *statuses*, not evidence classes. An accepted decision requires an explicit approval/merge record and exact scope. A report, passing CI check, PR opening, or issue checkbox is never by itself a decision.

## 3. Reproduction, negative results, and rejection

For **executable evidence**, supply the source commit, platform, fixture path/hash or inline inputs, provenance, tool/dependency versions, command and flags, seeds (or explain determinism), limits, exit status, raw-output location, and expected output/invariants. For nondeterministic outcomes specify an acceptable range and repeated-run protocol. A missing tool or unavailable rerun is recorded as **not reproduced**, not success.

For **formal proofs**, record theorem/definition/module, proof assistant/checker, exact version and dependency lock, build/check command, assumptions/axioms/admissions, result, and the unproved source correspondence. For **bounded models**, record grammar, bounds, oracle and enumeration coverage. For **source-only comparisons**, record primary source edition/version and which executable fields are N/A.

Record successes, failures, negative/edge cases, rejected options, UNKNOWN/timeouts, and their consequences. Rejection means *rejected for this scope and rationale*, not globally disproved. Record failure-to-falsify separately from proof.

## 4. Traceable specification-change protocol

A proposed change to `draft/` should include a reviewable change map (may be in the PR body or report):

| Field | Required link / value |
| --- | --- |
| Proposal | Candidate `draft/` file and section, with proposed normative wording or diff |
| Question | `TODO.md` LL-ID or a named open Stage 0/research item; do not invent LL IDs for transient implementation tasks |
| Research | Research/RT/scenario document and stable claim ID |
| Evidence | Exact source, fixture, run/output or theorem reference, with limitations |
| Status | Proposed / accepted / rejected / superseded, with timestamp and decision authority/PR when accepted |
| Conflict | Rejected alternatives, dependencies, unresolved objections and affected claims |

**Workflow:** (1) author research with evidence labels; (2) review assumptions, negative results and reproduction; (3) identify open LL questions and dependencies; (4) propose a separate exact candidate-spec diff with claim links; (5) accept/reject only via explicit maintainer decision recorded in a durable PR/decision document; (6) update `draft/`, `TODO.md`, and `PLAN.md` as applicable. A proposal does not silently modify the candidate spec. `research/` remains exploratory; `draft/` remains the candidate specification, with accepted decisions explicitly identified. Existing [accepted architecture decision](../draft/ARCHITECTURE-DECISIONS.md) is not reopened by this process proposal.

## 5. Quality gates and authority

Review each report against [Q1–Q5](RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md#7-reproducibility-and-quality-gates): traceability; inspectable model/method; claim-level evidence classification; negative/falsifier coverage; and decision-safe conclusion. Record **pass / fail / N/A with rationale / not reviewed** per gate. "Not reviewed" does not equal "pass." A human reviewer must assess evidence adequacy, source correspondence, and proposed decision; the checker only detects surface patterns.

**Pilot rollout (not adopted):** Use templates for new substantive reports, run `python3 -B .github/scripts/check_research_quality.py --files research/RT-XX-NAME.md` locally, and collect warnings and false positives. A non-blocking workflow reviews newly *added* top-level RT/scenario reports. The opt-in `--strict` flag is for local experiments only. Enforcing CI, migrating all historical reports, or declaring §0.2 complete requires maintainer approval and a measured audit.

## 6. Results, limitations, decision, and draft impact

**Observation:** This protocol synthesizes the three linked prior methodological studies; a six-test prototype of the structural checker is reported in [pilot evidence](RT-00/RT-00-QUALITY-RULES-PILOT-2026-11-23.md). **Hypotheses H1/H2 remain untested** on independent reviewers and representative PRs.

**Negative/rejected alternatives:** Do not require one large fixed prose outline for every evidence shape (risk of misleading boilerplate); do not silently promote warnings to blocking CI (unmeasured false positives); do not equate a structurally compliant report with a proved result. These are process recommendations, not demonstrated empirical superiority.

**Limitations:** No corpus-wide claim audit, no blind reviewer study, no confirmation that all foundational experiments reproduce, and no measured maintenance overhead. Other formats may be equally valid. Gate adoption is **pending explicit maintainer decision**.

**Draft impact:** None. This document does not propose or accept any language semantics, specification text, ABI, grammar, or checker trust rule. The Stage 0.2 work remains open until acceptance and outstanding validation are completed.
