# RT-00 — Stage 0.2 real-report quality pilot: ten evidence shapes

**Research item:** [PLAN.md §0.2](../PLAN.md#02-establish-research-quality-and-decision-rules), [issue #285](https://github.com/aivibeflow/LLMLang/issues/285)  
**Status:** Bounded documentary/structural audit; not a policy decision or technical-proof validation  
**Date:** 2026-11-23  
**Baseline:** `main` at `419ae2c02b27eb52c63eef3a255a83004444222e` (merge of [PR #373](https://github.com/aivibeflow/LLMLang/pull/373))  
**Evidence type:** Mixed: repository-document observation, executable structural-checker experiment, human review of selected warnings  
**Source and exact fixtures:** [Frozen manifest](quality-audit/2026-11-23-sample.json) records all ten paths, individual Git blob SHAs, expected checker warnings, and section/line evidence for adjudicated layout-only warnings.  
**Expected output:** 10 reports; 62 structural warnings after the three metadata-format corrections; zero blob mismatches; zero warning-snapshot mismatches. Before those corrections, the original matcher yields 65 warnings.  
**Normative boundary:** This is not a review of the correctness of the ten studies, a clean rerun of their experiments, or acceptance of the proposed quality protocol.

## 1. Problem, hypotheses and scope

[PR #373](https://github.com/aivibeflow/LLMLang/pull/373) added a warning-only structure checker and six synthetic tests. Those synthetic tests do not establish its false-positive behavior on actual reports. Stage 0.2 requires evidence-sensitive, non-overclaiming rules; the issue cannot be closed just because the checker runs.

- **H1 (testable, bounded):** the structural checker produces warnings for legitimate evidence expressed under alternate legacy headings or metadata punctuation.
- **H2 (testable, bounded):** executable studies with historically descriptive `Status` values can bypass the checker’s executable-specific fixture/version/output requirements because its trigger requires the exact `**Evidence type:** Executable` field.
- **H3 (unmeasured):** a corrected warning-only checker plus targeted human review improves reviewer ability to locate evidence; no human participant/time study is attempted.

**Sample selection:** ten purposively selected, first-party reports already on main: finite AST verification (Scenario 98), SymPy worker/timeout (103), memory-order enumeration (118), generated Rust experiment (133), mixed SPG model and executable RT-05, comparative RT-04, synthetic compilation benchmark RT-11, proof-checker pipeline *proposal* (Scenario 29), official wire-format standards study (134), and a Lean proof/CI-evidence recheck (DEP-007). A proof *proposal* is not a checked proof; the latter appears only as versioned Lean/CI evidence in DEP-007. This is deliberately **not** a random or representative sample of the corpus.

## 2. Prior evidence, alternatives, and method

Prior studies: [Quality rules proposal](RESEARCH-QUALITY-AND-DECISION-RULES-2026-11-20.md), [rollout comparison](RT-00-QUALITY-RULES-ROLLOUT-OPTIONS-2026-11-23.md), [evidence-shape recheck](RT-00-QUALITY-RULES-EVIDENCE-SHAPE-RECHECK-2026-11-23.md), [initial structural pilot](RT-00-QUALITY-RULES-PILOT-2026-11-23.md) and [proposed protocol](QUALITY-REVIEW-PROTOCOL.md).

**Compared alternatives:** A: leave the initial exact-header matcher unchanged; B: accept genuine alternate metadata punctuation and retain warning-only heading heuristics; C: block all older reports on every missing header. The pilot implements **B as a proposed low-risk correction**, not C or an adopted quality policy.

**Model:** `W(report, checker)` is the deterministic list of structural-warning strings returned by `inspect()`. It measures textual pattern presence only. For each report, a manual reviewer may mark warning `w` as **confirmed layout-only** if the actual material is demonstrably present in a named source section/line and the warning is attributable to heading/metadata shape. A residual warning is **unadjudicated**, not automatically a defect or missing scientific result. This review does not classify all major claims or assign an error-rate estimate to the full research corpus.

**Procedure:** inspect the fixed blob contents and section boundaries, run equivalent initial-rule matching for the frozen before snapshot, correct the metadata matching for both `**Status:**` and `**Status** —` / `- **Status** ·` forms (and similarly `Baseline`), rerun the existing warning logic, and manually justify only strongly supported layout-only findings in the manifest. Git blob equality is checked by the replay script so changing input cannot silently inherit the fixed expected result. The Python matcher and tests are the executable verification route; no report-level experiment was rerun.

## 3. Results

| Report / evidence shape | Warnings before | After correction | Confirmed layout-only warnings after | Still unadjudicated |
| --- | ---: | ---: | ---: | ---: |
| [Scenario 98](RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) · finite AST executable | 6 | 6 | 2 | 4 |
| [Scenario 103](RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md) · solver worker | 6 | 6 | 3 | 3 |
| [Scenario 118](RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md) · bounded model | 7 | 7 | 4 | 3 |
| [Scenario 133](RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md) · generated Rust | 7 | 6 | 3 | 3 |
| [RT-05 SPG](RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) · mixed model/experiment | 3 | 1 | 1 | 0 |
| [RT-04 alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md) · survey | 6 | 6 | 3 | 3 |
| [RT-11 benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md) · compiled C | 8 | 8 | 3 | 5 |
| [Scenario 29](RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md) · proposal/fake runner | 8 | 8 | 4 | 4 |
| [Scenario 134](RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md) · standards survey | 5 | 5 | 3 | 2 |
| [DEP-007 recheck](RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md) · checked proof evidence | 9 | 9 | 3 | 6 |
| **Total** | **65** | **62** | **29** | **33** |

**Observation O-01:** All ten documents lack the exact `**Evidence type:** Executable` trigger. Thus the executable-specific subchecks were never entered on this historical sample, *including the clearly executable* Scenarios 98/103/133 and RT-11. An absence of executable-specific warnings therefore does **not** establish adequate fixture provenance, commands, versions, or expected outputs. The trigger is a coverage limitation, not evidence that those experiments are invalid.

**Observation O-02:** Three of the original 65 warnings are demonstrable metadata punctuation false alarms: Scenario 133 uses `**Status** —`; RT-05 uses `- **Status** ·` and `- **Baseline** ·`. The targeted parser correction removes these three without hiding missing fields in the synthetic tests.

**Observation O-03:** At least 29 of the remaining 62 warnings are grounded layout-only mismatches (see precise warning-to-line mapping in the manifest). Examples:

- Scenario 118’s **Model** section (lines 15–22) contains the procedures and primary memory-model references, while its final paragraph (line 47) contains concrete limitations and open design status; the checker expects differently named headings.
- RT-11’s **Question** section (lines 7–9) contains cited prior art, its **Workload and comparison** section (lines 13–21) defines the experiment model, and **Consequences for the RFC** limits generalization (line 44).
- Scenario 29 explicitly states its **Question** in metadata (line 6), lists sources in §11, and lists six unestablished proof obligations in §10. It must not be described as an end-to-end checked proof.
- Scenario 134 places the non-executable **Method** in metadata (line 7) and links an existing accepted decision (line 9), while explicitly denying new `draft/` change authority (line 184).
- The DEP-007 recheck names its theorem, exact blob and passing Lean CI step in **Checked proof and current-main identity** (lines 19–25), including the fact that Lean was **not** locally rerun.

The 29 classification decisions are *manual document readings*, not independent correctness checks or a statistically estimated false-positive rate. The 33 other warnings were **not** established as genuine deficiencies, and the heuristic can miss substantive defects even when it emits no warning. No aggregate precision/recall rate is inferred.

**Observation O-04:** Missing explicit `Baseline` remains flagged in eight sampled reports. Some record dates, tool versions, file references, or a short historical/working-tree base elsewhere; these do not uniformly give a complete immutable source snapshot for the described run. Before retesting a foundational result, trace the exact original fixture and source revision (do not substitute today’s checkout and claim an exact reproduction).

## 4. Reproduction and environment

This report's pinned machine-readable [sample](quality-audit/2026-11-23-sample.json) includes exact Git blob IDs for all inputs. Python 3.10+ and Git are required; the scripts use only Python standard library modules. The locally reproduced synthetic checker unit tests passed on **CPython 3.13.5** (seven tests after the additional metadata regression). The ten-report replay runs in the independent GitHub Actions environment using the repository checkout; its artifact records actual Python version, blob matches, warnings and snapshot matches. Do not confuse the separately observed local unit test with an independent GitHub Actions result.

From a clean checkout of the PR head containing the manifest and checker changes:

```sh
python3 -B -m unittest discover -s .github/scripts -p 'test_check_research_quality.py' -v
python3 -B .github/scripts/replay_research_quality_sample.py --root . --manifest research/quality-audit/2026-11-23-sample.json --json-out /tmp/llmlang-quality-sample.json --assert-snapshot
```

Expected: unit tests `Ran 7 tests`, `OK`, exit 0; snapshot reports `reports_checked: 10`, `total_warnings: 62`, `blob_mismatches: 0`, `warning_snapshot_mismatches: 0`, exit 0. GitHub Actions runs it **without** `--assert-snapshot` and uploads the JSON as output-only exploratory evidence (not a required quality gate). A modified report’s Git blob must cause an explicit mismatch; it is not a silent regression of the historical sample.

To inspect all warnings without the pinned manifest:

```sh
python3 -B .github/scripts/check_research_quality.py --files \
  research/RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md \
  research/RESEARCH-SCENARIO-103-REAL-SOLVER-TIMEOUT-ISOLATION.md \
  research/RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md \
  research/RESEARCH-SCENARIO-133-GENERATED-RUST-OWNED-RESULTS.md \
  research/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md \
  research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md \
  research/RT-11-BINDING-INVALIDATION-BENCHMARK.md \
  research/RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md \
  research/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md \
  research/RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md
```

## 5. Negative results, rejected alternatives and open evidence

- **Rejected for present pilot:** treating all 65 initial warnings as research defects. At least 32 were demonstrable format-only alarms or immediately corrected metadata variants.
- **Rejected:** treating zero executable-subcheck warnings as successful reproducibility auditing; the trigger did not fire on any of the ten reports.
- **Rejected:** mandatory blocking CI for a heading/keyword heuristic without a representative, independently adjudicated false-positive and missed-defect study.
- **Not run:** the ten reports’ actual external experiments, compiler invocations, Lean proof builds, cvc5/Logos integration or real Protobuf/Avro/CBOR runtime matrix. Their claimed results remain those of their original authors and linked CI evidence, not independently reproduced by this audit.
- **Unresolved:** 33 warning classifications; claim-level citation accuracy, raw data integrity, cross-version source correspondence, and maintainer adoption.
- **No blanket design rejection:** Reports with shorter formats may satisfy Q1–Q5 through inline descriptions; an explicit evidence-class/traceability layer could still improve discoverability.

## 6. Review recommendation and decision boundary

**Recommendation only:** preserve warning-only behavior. Keep the metadata punctuation correction and pin an honest historical sample. In a follow-up evaluation, independently review a stratified subset of both warned and unwarned reports, classify omissions and missed defects, and time evidence navigation. Add an explicit evidence-type field for *new* reports only after maintainer acceptance, with proof- and source-only variants handled without spurious executable commands. Do not introduce mandatory headings or a pass/fail quality score based on this pilot.

**No accepted policy:** this audit neither approves the proposed Stage 0.2 conventions nor closes [#285](https://github.com/aivibeflow/LLMLang/issues/285). Maintainer decision, broader claim-level audit, reproducing foundational experiments at their pinned sources and the evidence-to-draft acceptance record remain external.

## 7. Traceability and draft impact

- **Stage/area:** `PLAN.md` §0.2; RT-08 evidence-methodology focus.
- **Open questions:** `TODO.md` LL-008/LL-019/LL-020 govern *technical evidence semantics*, which this documentation pilot does not resolve; the process rollout remains tracked by issue #285, not a new LL design-question ID.
- **Draft impact:** **None.** Research documents remain exploratory. No contents of `draft/` are edited or promoted to accepted language requirements.
- **Quality gate self-review:** Q1 traceable by ten blob IDs and issue/PLAN; Q2 method and script commands provided; Q3 results labeled as observations or proposal, no technical proof claims; Q4 negative cases/false alarms recorded, 33 classifications open; Q5 decision explicitly deferred. No independent human double review or research correctness validation is claimed.
