# RT-00 — Quality Rules Rollout Options

**Research item:** `PLAN.md` §0.2 — Establish research quality and decision rules
**Status:** Comparative process study; recommendation only
**Updated:** 2026-11-23
**Baseline:** `main` at `9d3dc0e127f8df162831918ae947c927b9a3eb58`
**Normative boundary:** This study compares ways to apply research-documentation rules. It does not adopt a project policy or select LLMLang semantics or architecture.

## 1. Question and scope

Given the proposed evidence vocabulary and review gates in [Research Quality and Decision Rules](../../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md), how should the project apply them to existing and future research without implying that document structure proves a claim?

The comparison covers three rollout strategies: retrospective migration of the corpus, incremental review of high-impact reports, and a hybrid with lightweight checks for new reports plus prioritized retrospective review. It does not audit every report, independently reproduce experiments, or decide which project authority may adopt the rules.

## 2. Method and evidence

This is a qualitative comparison against the current `main` tree, not a statistical sample or a validation of the underlying experiments. I compared the earlier quality-rules proposal and preparation checklist with three reports that represent different evidence shapes:

| Artifact | Observed strengths | Observed rollout-relevant gap |
|---|---|---|
| [Scenario 98](../../semantic-representation/RT-06/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) | Names a bounded AST fixture, method, result, limitations, and reproduction command. | Its compact format does not expose a uniform claim register or all downstream traceability fields in the report itself. |
| [Scenario 133](../../compiler-and-translation/RT-13/RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md) | Records exact measured counts, host/toolchain versions, command, comparison boundary, and unsupported cases. | There is no standardized claim-ID/evidence-class table or explicit Q1–Q5 gate record. |
| [RT-05 Typed SPG](../../semantic-representation/RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) | Compares candidate models, gives falsifiers, scoped results, and reproduction limitations. | It combines literature observations, design hypotheses, and bounded executable results across sections without a compact per-claim evidence register. |

These observations are direct document observations. They do not show that any underlying technical result is wrong or unreproducible. The previous proposal reviewed other representative artifacts and the preparation pack already specifies exact source revisions, tools, fixtures, commands, outcomes, and limits. This follow-up checks the rollout choice against current-main examples; it does not re-run that prior review or reproduce their experiments.

## 3. Candidate rollout vectors

| Vector | Process | Benefits | Costs and risks | Evidence needed to falsify or weaken |
|---|---|---|---|---|
| **A — Corpus-wide retrofit** | Apply one detailed report and claim schema to every substantive existing report before new research proceeds. | Uniform discoverability; broad traceability can be measured against one target. | Highest migration effort; encourages repetitive boilerplate for short scenario notes; editing can accidentally change historical scope or interpretation; cannot itself validate claims. | A pilot showing low reviewer agreement, material scope changes, or high maintenance cost would weaken it. |
| **B — Priority-ordered manual audit** | Review high-impact foundational reports first and apply the conventions as each report is revised. | Concentrates effort on decisions with the most downstream impact; preserves concise historical artifacts; supports human judgment where evidence types differ. | Inconsistent treatment persists elsewhere; no guard against new reports drifting; completion is difficult to measure without an inventory. | A pilot showing recurring omissions in new reports or reviewers unable to find evidence boundaries would weaken it. |
| **C — Hybrid, staged enforcement** | Define a minimal template for new substantive work, initially run structural checks as warnings, and audit existing high-impact reports in stages. Promote only low-noise structural checks to blocking CI after a pilot. | Limits future drift while prioritizing old reports; separates machine-checkable presence/link checks from human claim-quality review; makes adoption measurable and reversible. | Requires template and checker maintenance; structural presence can create false confidence; blocking policy needs maintainer approval and measured false-positive rates. | A pilot showing frequent false positives, template-induced boilerplate, or no improvement in reviewer traceability would weaken it. |

## 4. Comparative result

On the criteria of migration effort, preservation of historical scope, prevention of future drift, and ability to measure adoption, Vector C has the best provisional balance. Vector A offers the most uniform shape but imposes the largest retrofit and over-standardization risk. Vector B is least disruptive for existing work but leaves future reports without a consistent entry point. The current examples support the existence of discoverability differences, not a measured estimate of effort or reviewer performance.

**Recommendation (not a decision):** pilot Vector C with a short template that preserves evidence class, scope, source revision, reproduction route, limitations, decision boundary, and traceability. Treat the template as a checklist, not a required prose outline: scenario reports may combine sections. Begin with warning-only checks for required metadata, local links, and stable plan/taxonomy references. Keep evidence classification, adequacy of falsifiers, external validity, and claim-to-evidence correctness under human review. Do not make CI blocking until a representative pilot records false positives, missed defects, and maintenance cost and maintainers explicitly approve enforcement.

## 5. Decision boundary and external dependencies

This comparison does not close §0.2. The following work remains external to this study:

1. Project maintainers must accept, revise, or reject the proposed vocabulary, template, and gate policy.
2. A repository-wide audit must identify substantive reports and measure claim-level evidence/traceability coverage; the prior review is a qualitative sample only.
3. Foundational reproducibility-sensitive claims still need clean-environment reruns where the plan requires them. A template or CI check cannot substitute for those runs.
4. Any warning or blocking checker requires implementation, a representative pilot, and an explicit decision on the false-positive threshold and maintenance owner.
5. Human-review effectiveness and whether these conventions reduce overclaiming have not been measured.

No language or architecture dependency edge is added: this is a cross-cutting evidence-process choice and does not establish a semantic prerequisite between RT aspects. The existing RT-08 evidence model remains the applicable taxonomy area; updating a dependency edge would imply a technical dependency not established by this study.

## 6. Traceability

- **Plan:** `PLAN.md` §0.2.
- **Taxonomy:** RT-08, Testing, validation, and evidence model.
- **Related LL questions:** LL-008 (evidence compatibility/reuse); LL-019 and LL-020 (scoped conformance/backend evidence).
- **Prior study:** [Research Quality and Decision Rules](../../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md).
- **Preparation guidance:** [Research Preparation Pack](../../preparation/README.md).
- **Dependency map:** no new edge proposed; this study concerns evidence recording across the map.

## 7. Reproduction and limits

The result is a qualitative document comparison against the exact baseline commit above. To inspect the evidence, open the three linked reports and compare their metadata, method, results, limitations, reproduction, and traceability sections with §§4–7 of the prior quality-rules proposal and the preparation pack's required-evidence checklist. There is no executable experiment or numerical outcome to reproduce.

This comparison covers three current-main examples selected for different evidence shapes. It cannot establish corpus-wide prevalence, reviewer usability, retrofit effort, or the correctness of technical claims. It is not an accepted policy and does not mark any report as validated by virtue of matching a template.
