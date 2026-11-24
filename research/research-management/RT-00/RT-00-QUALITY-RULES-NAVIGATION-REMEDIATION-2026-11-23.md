# RT-00 — Repairing nine Stage 0.2 research navigation gaps without revising experimental claims

**Work item:** [issue #285](https://github.com/aivibeflow/LLMLang/issues/285), PLAN §0.2  
**Date:** 2026-11-23  
**Status:** Nine retrospectively documented alternatives, prior-art, method, question and draft-impact links; **not** an approved quality policy or a recreated original experiment  
**Method:** Claim-boundary/document-navigation check, scoped to the original 33-entry [adjudication register](../../quality-audit/2026-11-23-adjudication.json).  
**Evidence type:** Document observation, source correspondence to the five passing [archived-source CI runs](../../quality-audit/2026-11-23-historical-rerun-observations.json) where applicable; no fresh experiment executed by this document.  
**Audit baseline:** [Ten-report fixed sample](../../quality-audit/2026-11-23-sample.json) at Git commit `419ae2c02b27eb52c63eef3a255a83004444222e`. The later report modifications are *not* retroactive changes to that immutable sample.  
**Normative boundary:** `draft/` untouched. Reviewer approval of these classifications and repository-wide adoption are still open.

## Question and alternatives

Can nine non-baseline process gaps from the first ten-report audit be repaired with short, accurately scoped evidence-navigation appendices instead of replacing published reports or fabricating research results?

- **Option A:** enforce rigid headings and rewrite all original results. Rejected: it risks changing their historical scope and produces misleading provenance.
- **Option B:** append clearly labelled retrospective crosswalks that state the evidence class, what was/was not tested, alternate methods and exact non-decision, while retaining the original report and archival Git snapshot.
- **Option C:** mark the warnings as harmless because some text is already present elsewhere. Rejected for the nine classified gaps: important hypotheses, reproduction instructions or explicit decision boundaries were incompletely documented.

Option B is implemented as a **proposed documentation correction**, not a language or governance decision. Each addition distinguishes retrospective reviewer commentary from original observed results.

## Exact nine-item crosswalk

| Original report | Gap from the previous adjudication | Now recorded | Still not established |
| --- | --- | --- | --- |
| [Scenario 98](../../semantic-representation/RT-06/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) | Hypotheses/alternatives | Explicit bounded AST witness hypothesis and independently untested parser/CFG alternative | Source-language path completeness or proof |
| [Scenario 98](../../semantic-representation/RT-06/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) | Prior art and sources | Link to RT-03/04 [COR-06 corpus](../../language-design/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md) and Scenario 102 | Automatic source extraction and solver soundness |
| [Scenario 98](../../semantic-representation/RT-06/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) | Draft/decision impact | Explicit `draft/` **none**, bounded observation only | Accepted parser or language semantics |
| [Scenario 103](../../semantic-representation/RT-06/RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md) | Alternatives | Process isolation contrasted with in-process blocking and unimplemented persistent pools | Certified UNSAT, stable resource limits or throughput |
| [Scenario 103](../../semantic-representation/RT-06/RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md) | Draft impact | Explicit `draft/` **none**, pin of worker/test/requirements source and fresh CI | Solver/backend selection or pruning policy |
| [Scenario 118](../../language-design/RT-04/RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md) | Draft impact | Candidate-order contrast, exact global-order oracle scope, no selected memory policy | Independent validation of weaker memory model |
| [Scenario 29](../../formal-verification/RT-07/RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md) | Experiments/method | Exact Python unittest command, fake-executable fixtures, pinned source revision and observed 15-pass rerun | Real cvc5/Logos checked certificate or program-to-query proof |
| [DEP-007 recheck](RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md) | Explicit research question | Scalar-only vs outcome-and-ordered-trace equality for finite rewrite grammar | Full LLMLang optimizer correctness |
| [DEP-007 recheck](RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md) | Draft impact | Retain bounded DEP-007 research confidence, no normative change | Parser/SPG/backend correspondence |

The nine findings are closed **only as document-navigation gaps addressed by appendices**, not as scientific validations. No numeric claim is silently recategorized as a theorem.

## Preserving original audit reproducibility

The original structural-audit manifest contains the **Git blob identity and expected warning strings of each file at its historical baseline commit**. Editing those reports necessarily changes their current blobs and often their header warnings. A correct historical replay must not compare current working-tree bytes with a supposedly immutable old sample.

The [sample replayer](../../../.github/scripts/replay_research_quality_sample.py) now supports `--from-baseline`, retrieving each report from `baseline_commit:path` using Git and confirming its exact blob SHA and recorded warning set. Its existing working-tree mode remains available for intentional drift observation. The [regression tests](../../../.github/scripts/test_replay_research_quality_sample.py) cover later document edits, incorrect blob IDs, unavailable history and unsafe paths; CI checks the frozen historical sample **without** treating that warning count as evidence of research correctness.

From a full-history repository checkout:

```sh
python3 -B -m unittest discover -s .github/scripts -p 'test_replay_research_quality_sample.py' -v
python3 -B .github/scripts/replay_research_quality_sample.py \
  --root . --from-baseline --assert-snapshot \
  --manifest research/quality-audit/2026-11-23-sample.json
```

**Expected from the historical snapshot:** 4 regression tests `OK`; 10 original reports; 62 original warning strings after the metadata-format fix; zero historical Git blob mismatches and zero expected-warning mismatches. These are expected outcomes, not independently confirmed CI until the PR checks finish.

## Remaining negative evidence and next decisions

- **Eight original-execution provenance gaps remain open**. The [eight-report publication history](../../quality-audit/2026-11-23-publication-provenance.json) and [five new historical-source reruns](../../quality-audit/2026-11-23-historical-rerun-observations.json) establish recoverable committed code and new execution results, but not the complete historical uncommitted source/host environment in which the earlier results were made.
- Source-only comparative research such as RT-04 and Scenario 134 must not be forced into a single executable evidence schema.
- Formal checker adapter tests with fake binaries never constitute a cvc5/Logos certificate. The bounded DEP-007 Lean proof still needs a source/lowering correspondence chain for full-language implications.
- No sampling-based false-negative study, independent human reviewer-effort study or corpus-wide claim-by-claim check is completed.
- **Proposed next step:** maintainers review the nine retroactive crosswalks, accept or amend the Stage 0.2 protocol, and prioritize original-run provenance recovery/independent reruns for the eight remaining source/environment gaps. Issue #285 remains open until its full acceptance criteria are evidenced.
