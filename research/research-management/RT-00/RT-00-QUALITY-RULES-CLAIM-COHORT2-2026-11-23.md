# RT-00 — Stage 0.2 second-cohort claim/evidence boundary audit (24 claims)

**Date:** 2026-11-23  
**Status:** Second **purposive**, bounded claim-level source trace; quality protocol remains proposed, not adopted  
**Issue:** [#285](https://github.com/aivibeflow/LLMLang/issues/285), [PLAN §0.2](../../../PLAN.md#02-establish-research-quality-and-decision-rules)  
**Immutable source baseline:** `ff1295c1769bfe8546c4b63590c9f607349215ee` (main when selected)  
**Exact input and structured output:** [12 reports / 24 source-bound claim entries](../../quality-audit/2026-11-23-claim-cohort2.json)  
**Evidence class of this audit:** Documentation/source observation and preliminary claim-level interpretation; **no scientific result reexecuted or independently proof-checked here**.  
**Specification impact:** **None.** This is a research-quality audit; no proposed language guarantee is accepted into `draft/`.

## 1. Question, hypotheses and alternatives

Previous [Stage 0.2 initial ten-report pilot](RT-00-QUALITY-RULES-REAL-REPORT-PILOT-2026-11-23.md) audited document structure, then [triaged 33 warning instances](RT-00-QUALITY-RULES-ADJUDICATION-2026-11-23.md) and repaired nine metadata/navigation gaps. Those are necessary but do not establish that material assertions are correctly classified or that their technical evidence is enough.

**Question:** Across a *different* set of scientific evidence shapes, can we locate the particular report lines and source artifacts supporting material claims and state what the evidence **does not** establish, without conflating a checked theorem, a finite fixture, a comparative proposal, and a historically dated audit?

- **H1 (bounded, document-level):** At least one versioned report/source trace and an explicit generalization limit can be documented for each of 24 selected claims.
- **H2 (untested scientific hypothesis):** Every claim is correct with respect to its referenced source. This audit **does not** test H2; mechanical Git blob equality and an inspectable reference do not prove behavior.
- **H3 (untested user study):** A short claim-level register improves independent reviewer accuracy/time. No participants were studied.

**Alternatives:** (A) blanket structural keyword checks would miss evidence-class overreach; (B) promote each reported passing test to proof or a normative decision—rejected as unsafe; (C) trace sampled material claims to immutable text/source and record negative scope, while requiring separate human/technical validation before decisions. This report applies **C**, provisionally. No opinion is expressed about whether every selected experiment is correct.

**Prior work:** [Proposed quality protocol](../../QUALITY-REVIEW-PROTOCOL.md), [claim register template](../../templates/CLAIM-REGISTER-TEMPLATE.md), [first cohort audit](RT-00-QUALITY-RULES-REAL-REPORT-PILOT-2026-11-23.md), [first warning adjudication](RT-00-QUALITY-RULES-ADJUDICATION-2026-11-23.md), and the [RT-00 B5 Scenario 130 claim trace](RT-00-B-05-01-SCENARIO-130-CLAIM-TRACEABILITY-PILOT-2026-11-21.md). The latter traces a different cohort of Scenario 130 claims; it is **not** treated as an independent adjudication of the two claims here.

## 2. Method, model, and exact provenance

The selection is **purposive**, not random or statistically representative: 12 first-party reports outside the initial ten, chosen to include one bounded Lean proof, a proposed RT-24 merge contract, finite identity/solver/serialization/scheduler fixtures, SQLite/ownership/durable receipt probes, a Git source-completeness experiment and a multi-baseline RT-00 status report. No claim is made about the frequency of defects across hundreds of other files.

For each of the 12 reports the [manifest](../../quality-audit/2026-11-23-claim-cohort2.json) records:
- exact historical report Git blob at the common baseline and one linked artifact's Git blob (source, test, ADR or inventory reconciliation);
- two material claim IDs, text, **one primary evidence class**, exact report lines, related scope/limit lines and what remains unknown;
- explicit distinction between **published result** and a new independent rerun or checked proof (neither performed as part of this second-cohort audit);
- a decision boundary: no `draft/` changes or new accepted language policy.

Each Git source reference was located in the same pinned repository revision. The [reproducibility validator](../../../.github/scripts/validate_research_claim_cohort.py) retrieves `baseline:path` bytes rather than today's worktree, verifies the report/reference Git hashes, rejects duplicated IDs, checks valid line ranges and known evidence classes, and requires nonempty scope, falsifier/negative, draft-impact and review-status fields. The validator does **not** parse the referenced Python/Lean code into behavioral semantics, rerun it, prove a theorem or establish soundness of a claimed source-to-spec correspondence.

## 3. Cohort findings, by evidence shape

| Report | Two sampled primary claim types | Scope that must not be lost |
| --- | --- | --- |
| [RT-07 rewrite correctness](../../formal-verification/RT-07/RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md) | 2 × **Proof** | The reported Lean theorems apply to a finite typed expression grammar with ordered traces; no source/SPG/backend correspondence |
| [RT-24 candidate merge contract](../../toolchain-and-collaboration/RT-24/RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) | 2 × **Hypothesis / conjecture** | A proposed protocol and exit gates are not an implemented repository-wide proof or approval |
| [RT-05 identity lifecycle](../../semantic-representation/RT-05/RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) | **Experimental result** + **Observation** | Equal content can hide occurrence continuity; full discovery also had two historically documented failures |
| [Scenario 101 solver vs truth table](../../semantic-representation/RT-06/RESEARCH-SCENARIO-101-SOLVER-VS-TRUTH-TABLE-PATHS.md) | 2 × **Experimental result** | Truth-table agreement and three-run median timings concern a tiny, favorable Boolean formula family |
| [Scenario 110 wire defaults](../../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md) | 2 × **Model result** | Two-version, tiny JSON record fixture is not real schema/runtime interoperability |
| [Scenario 112 fairness](../../runtime-and-systems/RT-10/RESEARCH-SCENARIO-112-WEAK-STRONG-AND-BOUNDED-FAIRNESS.md) | 2 × **Model result** | Periodic enablement vs continuous enablement is distinct; fixed two-task schedule not a general liveness proof |
| [Scenario 120 SQLite cleanup](../../language-design/RT-04/RESEARCH-SCENARIO-120-SQLITE-CLEANUP-DEPENDENCIES.md) | 2 × **Experimental result** | `sqlite3_close` and `close_v2` observations use selected SQLite API paths and in-memory resources |
| [Scenario 124 SQLite synchronization](../../language-design/RT-04/RESEARCH-SCENARIO-124-CLOSE-SYNCHRONIZATION.md) | 2 × **Experimental result** | 11 controlled schedules cannot guarantee safety across arbitrary foreign aliases |
| [Scenario 130 durable invocation](../../runtime-and-systems/RT-10/RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md) | **Model result** + **Observation** | A later SQLite source-ID is a **prospective baseline**, not identity proof for original runs |
| [Scenario 132 typed caller recovery](../../language-design/RT-04/RESEARCH-SCENARIO-132-TYPED-CALLER-RECOVERY.md) | 2 × **Experimental result** | 20,736 finite inputs per fixture and admission counts do not establish general native FFI soundness |
| [RT-24 merged-tree source completeness](../../toolchain-and-collaboration/RT-24/RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md) | 2 × **Experimental result** | Seven bounded Git source/tree fixtures demonstrate failure cases, not a full production semantic merge |
| [RT-00 G stage exit audit](RT-00-G-CURRENT-STATUS-AND-EXIT-REPORT-2026-11-21.md) | 2 × **Observation** | Several “current” inventory counts refer to **different, dated Git baselines**; do not cite them as current main |

**Count:** 24 claims = **2 Proof**, **2 Hypothesis / conjecture**, **11 Experimental result**, **5 Model result**, **4 Observation**. These are author/report evidence classes assigned for research-review navigation, not an independent certification of those claims.

### Concrete interpretation hazards and follow-up queue

| Local finding | Risk in downstream use | Follow-up evidence requirement |
| --- | --- | --- |
| Q285-C2-R01 · proof boundary | Treating the RT-07 Lean theorem as an optimizer/backend preservation proof | Pin exact Lean source/theorems and prove or test source lowering / observation correspondence separately |
| Q285-C2-R02 · historical failed tests | Citing RT-05's 122 selected passes while omitting the two reported full-suite failures | Revisit failure statuses on an exact source tree; preserve `NEEDS_REVIEW` vs `UNKNOWN` distinction |
| Q285-C2-R03 · formula-family bias | Inferring a general SAT speedup from Scenario 101's 3-run conjunction microbenchmarks | Compare hard/parity/random formula families and distributional timings with timeout/UNKNOWN handling |
| Q285-C2-R04 · source-only vs native | Treating Scenario 110 finite JSON matrix as LLMLang/Protobuf/Avro/CBOR interoperability | Require actual pinned runtime/schema fixtures and a separately accepted wire-policy decision |
| Q285-C2-R05 · cross-process provenance | Treating the prospective SQLite 3.53.1 source-ID as proof of Scenario 130's original host | Retain both **original identity unknown** and **prospective reproduction identity recorded** |
| Q285-C2-R06 · historical status counts | Copying RT-00 G inventory numbers as latest total | Recount current Git tree and cite that commit; retain old numbers with their dated baselines |
| Q285-C2-R07 · normative inference | Treating the RT-24 proposal/gates as accepted merge semantics | Link an explicit authority/ADR decision, source-to-model completeness and production acceptance evidence before promotion |
| Q285-C2-R08 · negative evidence completeness | Treating successful finite SQLite/ownership samples as complete FFI capability enforcement | Test uncooperative aliases, resource lifecycle failures, long-lived concurrency and backend correspondence |

These are **interpretation risks and suggested evidence**, not a set of eight independently verified code defects. Some supporting documentation/prototypes already exist in neighboring reports; a focused follow-up must check them before opening duplicate implementation tasks.

## 4. Reproduction and expected output

Use Python 3.10+ standard library and Git, from a full-history checkout containing the exact pinned baseline commit:

```sh
python3 -B -m unittest discover -s .github/scripts -p 'test_validate_research_claim_cohort.py' -v
python3 -B .github/scripts/validate_research_claim_cohort.py \
  --root . \
  --manifest research/quality-audit/2026-11-23-claim-cohort2.json \
  --json-out /tmp/llmlang-claim-cohort2-check.json
```

**Expected accounting:** 6 unit tests pass; `reports: 12`, `claims: 24`, `errors: []`; every report and referenced source blob matches the frozen baseline. A separate [GitHub Actions workflow](../../../.github/workflows/research-claim-cohort-audit.yml) archives the machine-verified source-link JSON. These figures are *structural reproduction expectations*; passing them confirms neither science nor the exact historic experiment environment.

**Explicitly not executed here:** the selected 12 studies' Python/SQLite/native experiment suites, Lean compilation, alternative compiler backends, external URL source validation or full corpus research replication. A previously cited CI build is *prior evidence*, not an independently reexecuted action in this audit.

## 5. Quality gates, recommendation and decision boundary

Q1 (traceability) and a limited part of Q3 (primary-class labelling) are addressed **for the 24 selected claims** through exact paths/lines/blobs; Q2 (technical adequacy/method), Q4 (falsifier and negative completeness) and Q5 (decision authority) require human independent validation and cannot be passed by the script. Proposed Q1–Q5 gates are **not yet accepted**; their absence is not a reason to declare every old report invalid.

**Recommendation only:** retain warning-first structural checks, apply evidence-type-specific reproduction templates and source-bound claim registers for proposed `draft/` decisions, commission an independent second reviewer for the 24 claims and a representative sampled cohort including non-warning documents. Track review time, disagreements and actual missed technical defects before making a blocking quality gate.

**Unresolved prerequisites:** previous eight original-run working-tree/host attestations, independent/corpus-wide scientific claim-level audit, decision-to-draft links for any future proposed specification change, and maintainer acceptance of the quality workflow. All of [issue #285](https://github.com/aivibeflow/LLMLang/issues/285)'s global completion criteria stay open. **No `draft/` edit or accepted LLMLang semantics decision is implied.**
