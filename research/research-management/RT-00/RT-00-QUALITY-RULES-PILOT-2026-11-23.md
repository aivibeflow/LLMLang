# RT-00 — Stage 0.2 research quality structural pilot

**Research item:** [PLAN §0.2](../../../PLAN.md#02-establish-research-quality-and-decision-rules), [issue #285](https://github.com/aivibeflow/LLMLang/issues/285)  
**Status:** Bounded implementation/test result; proposed protocol, not accepted policy  
**Baseline:** `main` at `99151528f8bcc51ffccb6eaee8213acb0f9905c9`  
**Updated:** 2026-11-23  
**Evidence type:** Executable  
**Fixture:** Synthetic inline fixtures in [checker unit tests](../../../.github/scripts/test_check_research_quality.py); no LLMLang compiler input  
**Tool versions:** CPython 3.13.5, local Linux environment; Python standard library only  
**Expected output:** `Ran 6 tests` and `OK`, process exit 0 (ordering of test names is not normative)  
**Normative boundary:** This study measures a formatting checker against its own fixtures; no claim correctness, reviewer impact, or design acceptance is established.

## Problem and hypotheses

Can an isolated warning-only check identify missing research metadata while allowing evidence-specific reproduction fields?

- **H1 (hypothesis, not tested):** review time/claim-boundary comprehension improves with the new form.
- **H2 (bounded hypothesis):** the checker detects missing baseline and executable fixture/output/command fields in synthetic examples.

## Prior art and alternatives

[Original quality-rules proposal](../../RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md) defines evidence vocabulary, Q1–Q5, and traceability. [Rollout study](RT-00-QUALITY-RULES-ROLLOUT-OPTIONS-2026-11-23.md) compares (A) corpus retrofit, (B) manual audit, and (C) hybrid warning-first. [Evidence-shape recheck](RT-00-QUALITY-RULES-EVIDENCE-SHAPE-RECHECK-2026-11-23.md) compares fixed prose, type-specific attachments, and freeform indexing. This pilot implements a narrow part of hybrid C, not an accepted selection.

## Formal model and assumptions

Input is UTF-8 Markdown/MDX text plus a repository-relative path. A simple header/metadata regular-expression presence function yields a deterministic list of **warnings**, not a compliance proof. Candidate files are newly added top-level `research/RT-*.md` and `research/RESEARCH-SCENARIO-*.md` from the merge-base diff; historical documents, nested third-party snapshots, and changed pre-existing reports are excluded from automatic sampling. A direct `--files` argument can inspect any explicit report. If `**Evidence type:** Executable` is declared, three evidence-specific fields and a fenced shell command are additionally sought. The tool does not parse semantics, check external URLs, or run a report's experiments.

## Experiments and method

The following test suite uses synthetic complete/missing samples, an evidence-type swap, explicit path selection and path-scope checks. Reproduce from the repository root:

```sh
python3 -B -m unittest discover -s .github/scripts -p 'test_check_research_quality.py' -v
python3 -B .github/scripts/check_research_quality.py --files research/RT-00-QUALITY-RULES-PILOT-2026-11-23.md
```

The second command reports heuristic warnings in JSON, and exits 0 in warning mode even if warnings exist. The separately available `--strict` flag returns nonzero for warnings and is **not** used in CI. On PRs, the pilot workflow compares newly added eligible files against the PR base and uploads its JSON; the workflow is not part of Required CI.

## Results and evidence classification

**Experimental result C-01 (local synthetic fixtures):** On CPython 3.13.5 the six unit tests passed (`Ran 6 tests ... OK`). The fixtures cover a complete synthetic executable report, missing executable fields, N/A executable fields for prior art, missing metadata/sections, report-path selection, and explicit missing paths. This is only test-suite behavior, not corpus-quality validation.

**Observation C-02 (repository):** Existing [Scenario 98](../../semantic-representation/RT-06/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md), [Scenario 133](../../compiler-and-translation/RT-13/RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md) and [RT-05](../../semantic-representation/RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) have heterogeneous evidence shapes, as recorded in the prior [rollout comparison](RT-00-QUALITY-RULES-ROLLOUT-OPTIONS-2026-11-23.md). This study did not rerun their experiments.

**Hypothesis C-03 (open):** Automated warnings improve reviewers' ability to locate missing evidence. No participant study was performed.

### Negative results, rejected alternatives and UNKNOWN

The missing-field fixture triggers expected warnings rather than silent success. A source-only comparison is **not** required to include an executable fixture/command. Rejected **for this pilot**: mandatory blocking CI, corpus-wide forced migration, and claiming that a keyword match proves an evidence class. No runtime UNKNOWN case was generated; tool-unavailable and corpus validation remain untested rather than silently passing.

## Limitations and threats to validity

Regular expressions can miss valid differently worded reports or accept misleading boilerplate. Six synthetic tests do not measure precision/recall on a representative corpus. The tests use one CPython version and a local Linux host; no clean-environment verification or cross-platform result is claimed. The checker cannot verify source-to-model correspondence, proof trust, experiment inputs/outputs, human approval, or consistency with `draft/`. No reviewer-effort or cost data have been collected. Report checks may emit warnings even for adequately documented concise studies.

## Decision boundary and recommendation

**Recommendation, not a decision:** collect warnings, false positives and misses on a representative set of real new reports plus a blinded human review before considering enforcement. Keep the warning-only pilot separate from Required CI. Do not mark the underlying research quality issue or the policy adopted solely because the six unit tests pass.

## Draft impact and traceability

- **Draft impact:** None; `draft/` unchanged by this study.
- **Research area:** RT-08 (verification/evidence process); Stage 0.2.
- **Relevant open design questions:** [TODO LL-008](../../../TODO.md#ll-008--specify-evidence-identity-compatibility-and-reuse) and LL-019/020 on evidence scope (not resolved here).
- **Process proposal:** [Quality Review Protocol](../../QUALITY-REVIEW-PROTOCOL.md) and [templates](../../templates/REPORT-TEMPLATE.md).
- **Unresolved dependencies:** maintainer acceptance, representative human-review pilot, full claim-by-claim corpus audit, foundational experiment reproduction, and validated spec-change crosswalk.

## Reproduction and quality gates

**Q1:** traceable to issue/PLAN/RT-08; **Q2:** synthetic method and exact commands recorded; **Q3:** C-01/C-02/C-03 classified above, human correctness review not performed; **Q4:** missing-field and conditional-field counterexamples covered, real-corpus error rate unknown; **Q5:** no normative rule accepted, draft unchanged. This is a self-review of presence and stated boundaries, not independent evidence certification.
