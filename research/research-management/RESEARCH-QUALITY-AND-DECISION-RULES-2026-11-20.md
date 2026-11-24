# Research Quality and Decision Rules — 2026-11-20

**Research item:** `PLAN.md` §0.2 — Establish research quality and decision rules  
**Status:** Partial research result; proposed working rules, not yet adopted project-wide  
**Updated:** 2026-11-20  
**Baseline:** `main` at the revisions inspected during this study (see §8)  
**Normative boundary:** This document governs how research claims should be recorded and evaluated. It does not select LLMLang language semantics, architecture, identity formats, runtime behavior, or implementation policy.

## 1. Research question

What minimum common structure and evidence vocabulary lets LLMLang distinguish prior-art observations, bounded model results, executable experiments, formal proofs, assumptions, conjectures, and accepted project decisions—without overstating what a result establishes?

The study also asks how research results should be made reproducible and connected to open questions and candidate specification changes.

## 2. Method

A qualitative cross-document review was performed on representative artifacts with different evidence shapes:

- `research/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md` — bounded exhaustive fixture and evaluator cross-check.
- `research/RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md` — executable process-isolation experiment with pinned SymPy.
- `research/RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md` — bounded model comparison over memory-order relations.
- `research/CORE-LANGUAGE-SEMANTICS.md` — broad comparative synthesis, source provenance, and a later executable slice.
- `research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md` — cross-dimensional alternatives report and scenario corpus.
- `research/preparation/README.md` — execution requirements and preparation/execution distinction.
- `research/RESEARCH-TAXONOMY.md`, `research/RESEARCH-DEPENDENCY-MAP.md`, `research/README.md`, `TODO.md`, and `PLAN.md` — management and traceability documents.

The review compared document structure, status language, source/version provenance, method detail, explicit limits, reproducibility instructions, evidence labels, and links to downstream questions. It was a documentation review, not an independent rerun of every experiment or external-source verification.

## 3. Findings

### 3.1 Strong existing practices

1. The preparation pack already requires exact source commit, branch, toolchain/dependency versions, fixture provenance, commands, configuration, seeds, limits, raw outputs, positive/negative/rejected/UNKNOWN cases, evidence classification, limitations, falsifiers, cross-area implications, and affected open-question IDs.
2. Scenario 98 clearly limits its result to a declared finite AST fixture and explicitly identifies the missing source-parser/source-extraction correspondence.
3. Scenario 103 describes a concrete worker handshake, a real query deadline, timeout termination/reaping, request identity, and failure behavior. Its status is scoped to a reproducible bounded experiment rather than a general solver guarantee.
4. Scenario 118 states the bounded operation grammar and the memory-model fragment being compared; it distinguishes the result from a complete language/compiler/hardware model.
5. The RT-03 and RT-04 synthesis documents separate alternatives from selected language rules and contain explicit open questions and falsification plans.

### 3.2 Inconsistencies and gaps

1. **Evidence labels are not yet uniform.** Some artifacts use a clear Status line and explicit method/results/limits; others mix comparative claims, model results, and recommendations without a compact claim-by-claim evidence register.
2. **Reproduction detail varies by evidence type.** Executable experiments often provide a reproduction section; bounded mathematical models and broad comparative reports do not always state the exact reproduction route in the same predictable place.
3. **Source provenance is unevenly discoverable.** Some documents state source editions, versions, and links in the body; others rely on the reference register or general citations without a compact source manifest.
4. **Decision boundaries need a standard statement.** Most studies say no policy is selected, but the reader should be able to find, in a predictable place, exactly what the result supports, what it does not support, and whether any recommendation is being proposed.
5. **Traceability is distributed.** Research indexes, taxonomy, dependency map, and `TODO.md` provide useful links, but individual reports do not consistently expose affected LL IDs, taxonomy IDs, scenario dependencies, and candidate draft sections together.
6. **A passing test or bounded exhaustive enumeration can be over-read.** The preparation pack already warns against this; the same warning should be attached to each report's claims and acceptance statement.

These are consistency and discoverability issues, not evidence that the existing research conclusions are false.

## 4. Evidence vocabulary

Use one primary evidence class per claim. A document can contain multiple classes, but do not assign one class to the whole document if its claims differ.

| Class | Meaning | What it can support | What it cannot establish by itself |
|---|---|---|---|
| **Observation** | Directly recorded fact about a named source, implementation, artifact, or run. | A scoped statement about what was observed under recorded conditions. | General behavior outside those conditions; correctness of the observed system. |
| **Assumption** | Premise deliberately taken as input to a model or argument. | Conditional conclusions: if the premise holds, then… | That the premise is true in LLMLang or in a target implementation. |
| **Conjecture / hypothesis** | A falsifiable proposition not yet adequately tested or proved. | A research direction and discriminating experiment. | A design guarantee or accepted requirement. |
| **Prior-art claim** | A claim about a language, standard, tool, or implementation, supported by an identified primary/authoritative source. | What the cited source specifies or documents, within its version and scope. | That LLMLang should adopt the same rule or that an implementation conforms. |
| **Model result** | A result derived from an explicitly bounded formal, executable, or enumerated model. | A theorem or outcome within the stated model, grammar, axioms, and bounds. | Source correspondence, completeness beyond the model, or runtime behavior unless separately validated. |
| **Experimental result** | An observed outcome of a reproducible executable experiment with recorded environment and inputs. | Empirical behavior of the tested implementation/version/configuration and fixture. | General correctness, untested configurations, or a formal guarantee. |
| **Proof** | A machine-checked or otherwise auditable derivation from explicit definitions and assumptions. | The proposition proved in the formal system and its stated context. | Correctness of the formalization's correspondence to source/runtime unless that correspondence is separately established. |
| **Decision** | An explicitly accepted project choice recorded by the authorized project process and linked to its durable record. | The current project baseline within its stated scope. | A scientific proof that the decision is optimal or universally correct. |

A recommendation is not an evidence class. Label it **Recommendation** and link the evidence classes that motivate it. A proposed decision remains a proposal until explicitly accepted.

## 5. Minimum report structure

For new substantive research reports, use the following sections. Small scenario notes may combine sections, but must preserve their information.

1. **Metadata:** title, stable research/scenario IDs, status, updated date, source commit, owner/author where applicable.
2. **Question and scope:** one answerable question; in-scope and out-of-scope claims.
3. **Prior evidence and sources:** linked LLMLang artifacts, primary sources, versions/editions, retrieval dates where relevant.
4. **Hypotheses and alternatives:** explicit competing explanations or candidate vectors; state what would falsify each.
5. **Model and assumptions:** definitions, grammar, axioms, bounds, target profile, and assumptions.
6. **Method:** procedure, fixture provenance, tools/versions, commands, configuration, seeds, resource limits, and independent checks.
7. **Results:** raw-output locations or compact result tables; classify each material claim using §4.
8. **Limits and threats to validity:** missing cases, model/source gaps, external validity, UNKNOWN/timeouts, possible confounders.
9. **Conclusion and decision boundary:** what is supported, what remains open, what is explicitly not concluded, and whether a recommendation is made.
10. **Traceability:** affected RT areas, scenario dependencies, LL IDs in `TODO.md`, candidate draft sections, and related plan items.
11. **Reproduction:** exact commands and expected outputs, or a precise explanation of why the result is a source-only comparison/proof rather than an executable experiment.

## 6. Minimum claim record

For each conclusion that could influence a specification or architecture decision, record:

| Field | Required content |
|---|---|
| Claim ID | Stable local ID, e.g. `Q-01` |
| Claim | One falsifiable or verifiable sentence |
| Evidence class | One or more classes from §4 |
| Scope | Exact versions, fixture, model, assumptions, bounds, target |
| Evidence pointer | Source URL/version, raw output, test, proof, or file/section |
| Confidence | High / medium / low, with a short reason; do not use as a substitute for evidence class |
| Falsifier / missing evidence | What result would weaken or invalidate the claim, or what correspondence is not yet checked |
| Downstream impact | RT area, LL ID, draft section, or explicitly “none identified” |

For an accepted decision, add the decision record/PR/commit and the authority or process by which it was accepted.

## 7. Reproducibility and quality gates

A study is **reproducible** only when another contributor can identify the exact inputs and environment and can follow the documented procedure to obtain the same class of result. Exact byte-for-byte output is required only when the experiment claims deterministic output; otherwise define the expected invariant or result range.

### Gate Q1 — Traceable

- [ ] Research item and question are identified.
- [ ] Inputs and source versions are identified.
- [ ] Related prior research and open questions are linked.

### Gate Q2 — Method is inspectable

- [ ] Alternatives/hypotheses and assumptions are explicit.
- [ ] Model, bounds, and scope are stated.
- [ ] Tools, versions, configuration, seeds, commands, and limits are recorded where applicable.

### Gate Q3 — Claims are evidence-labelled

- [ ] Material claims have evidence classes and evidence pointers.
- [ ] Observed facts are not presented as assumptions or vice versa.
- [ ] Model results and tests are not promoted to source/runtime guarantees without correspondence evidence.
- [ ] Recommendations and accepted decisions are clearly distinguished.

### Gate Q4 — Adversarial coverage

- [ ] Negative, boundary, rejected, failure, and UNKNOWN cases are considered where applicable.
- [ ] At least one meaningful falsifier or counterexample search is recorded.
- [ ] Limitations and threats to validity are explicit.

### Gate Q5 — Decision-safe

- [ ] Conclusion states exactly what is and is not supported.
- [ ] Downstream impact and open questions are linked.
- [ ] No normative draft change is implied by an exploratory result.
- [ ] Any accepted decision links to its durable decision record.

A gate may be marked **Not applicable** only with a short reason. A study should not receive an overall “complete” label merely because a prototype or test passes; the conclusion must meet the stated scope and correspondence obligations.

## 8. Evaluation of sampled artifacts

| Artifact | Strength observed | Gap against proposed rules |
|---|---|---|
| Scenario 98 | Clear finite grammar, bounded exhaustive assignments, evaluator cross-check, source-extraction limitation. | Could expose a compact claim/evidence table and exact reproduction entry point in the report itself. |
| Scenario 103 | Reproducible worker experiment, pinned solver version, timeout and worker-reaping behavior, explicit failure modes. | Could provide a compact claim register and downstream LL/draft links alongside the narrative. |
| Scenario 118 | Explicit model fragment and bounded generated-program count; distinguishes model result from complete memory model. | Reproduction metadata and a direct claim-to-evidence map are less standardized than in Scenario 103. |
| RT-03 synthesis | Extensive alternatives, scope limits, source provenance, open questions, and later executable slice. | Needs claim-level evidence labels across a large mixed comparative/synthetic document. |
| RT-04 alternatives | Explicit dimensions, cross-profile analysis, scenario corpus, falsification criteria. | Needs consistent evidence labels and compact traceability from major claims to exact scenario/source artifacts. |
| Preparation pack | Strong execution/reproducibility checklist and explicit non-overclaim warning. | It is preparation guidance, not proof that every existing report conforms; corpus-wide migration/audit remains outstanding. |

This is a qualitative sample, not a statistical measurement of all research documents. It does not establish that every artifact has the listed gaps.

## 9. Recommendations

1. Adopt the evidence vocabulary in §4 as a research-documentation convention, not as a language-specification rule.
2. Use §5 and §6 as the default report/claim structure for new substantive research.
3. Apply Q1–Q5 to research completion reviews; allow justified N/A entries.
4. Keep `research/` exploratory and `draft/` candidate/normative as the current project boundary states. A research recommendation must not silently become a specification rule.
5. Add a gradual audit/migration pass for existing high-impact reports first (RT-03, RT-04, RT-05, RT-07/09/10/13), rather than rewriting every scenario at once.
6. Require every proposed draft change to cite the exact supporting claim IDs and evidence pointers; record accepted choices separately as decisions.
7. Keep raw outputs and fixtures immutable or versioned where practical; summarize them in reports rather than replacing them with paraphrase.

These are recommendations from this study and are not yet accepted project policy.

## 10. Open work

- [ ] Review the proposed vocabulary with project maintainers and accept/revise it explicitly.
- [ ] Create a reusable report template and claim-register template if the conventions are accepted.
- [ ] Audit all existing substantive reports for evidence labels and traceability.
- [ ] Link material unresolved claims to stable `TODO.md` IDs; create new IDs only when the register lacks the question.
- [ ] Verify that every candidate draft change has explicit research support and an acceptance record.
- [ ] Re-run reproducibility-sensitive experiments from clean environments where their conclusions are used for foundational decisions.

## 11. Sources inspected

- `PLAN.md`
- `research/README.md`
- `research/RESEARCH-TAXONOMY.md`
- `research/RESEARCH-DEPENDENCY-MAP.md`
- `research/preparation/README.md`
- `research/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md`
- `research/RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md`
- `research/RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md`
- `research/CORE-LANGUAGE-SEMANTICS.md`
- `research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md`
- `TODO.md`

The reviewed baseline files were fetched from `main` during 2026-11-20. This review did not independently execute all referenced commands or verify every external source.

---

**Conclusion:** The repository already has strong reproducibility guidance, but it lacks a uniformly applied claim-level evidence vocabulary and predictable traceability/decision-boundary structure. This study proposes a compact evidence taxonomy, report schema, claim record, and five quality gates. PLAN.md §0.2 remains partial until the conventions are explicitly accepted and the existing corpus is audited against them.
