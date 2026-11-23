# RT-00 — Second-cohort selected finite-experiment rerun protocol

**Date:** 2026-11-23  
**Status:** Three independently executed archived-source CI cases passed; full CI run, exact source identities, host and output artifacts recorded below  
**Issue:** [#285](https://github.com/aivibeflow/LLMLang/issues/285), [PLAN §0.2](../PLAN.md#02-establish-research-quality-and-decision-rules)  
**Related claim audit:** [12 reports and 24 material claims](RT-00-QUALITY-RULES-CLAIM-COHORT2-2026-11-23.md), [frozen claim manifest](quality-audit/2026-11-23-claim-cohort2.json)  
**Pinned source baseline:** `ff1295c1769bfe8546c4b63590c9f607349215ee`  
**Evidence type:** New bounded executable reruns against archived source, not original-run attestation or a formal correctness proof  
**Draft impact:** **None**; no accepted syntax/semantics/memory or merge policy is changed.

## 1. Question, hypotheses, and competing methods

A 24-claim review establishes that material assertions can be located in immutable source. A Git blob identifier does not show whether the fixture still executes under an independently declared host. Can three narrowly chosen evidence-shape studies rerun from one pinned Git commit while the audit distinguishes **reported historical results** from **fresh CI observations**?

**H1 (testable):** The archived fixtures for Scenario 110 (finite JSON policy), Scenario 112 (finite fairness), and RT-24 merged-tree completeness pass their respective named unittest suites on a newly provisioned CPython 3.12.14/Ubuntu runner.

**H2 (not established by passing tests):** These bounded suites are sufficient to define the LLMLang wire format, scheduler guarantee or production semantic merge policy. H2 is explicitly **not** accepted by these tests.

Alternatives: use today's moving main (does not preserve the audited claim source); use the original historical author workstation (unavailable, no original state attested); or run the fixed archived commit, verify the exact tests' Git hashes, record the new toolchain/host and retain explicit scope boundaries. The workflow uses the third option.

Prior research: [Scenario 110](RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md), [Scenario 112](RESEARCH-SCENARIO-112-WEAK-STRONG-AND-BOUNDED-FAIRNESS.md) and [RT-24 source completeness](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md). The [quality protocol](QUALITY-REVIEW-PROTOCOL.md) still requires a human scientific reviewer before treating tests as accepted design evidence.

## 2. Executable method and reproducibility

The new [dedicated workflow](../.github/workflows/research-claim-cohort2-reruns.yml) independently checks out exactly `ff1295c17…`, asserts the test-file blob below, pins CPython 3.12.14 on Ubuntu 24.04, saves Git version/host/commit, runs the suite and preserves its full output as a separate artifact.

| Case | Git test blob | Exact test entry | Expected test count |
| --- | --- | --- | ---: |
| SC-110 | `bb5f5bdf3ea0ed71d6ef7a565263740f6febb944` | `test_schema_evolution_model.py` via unittest discovery | 6 |
| SC-112 | `f0770463ee0a13e363394f058a563ff51b9cddca` | `test_scheduler_fairness_model.py` via unittest discovery | 5 |
| RT-24 | `b78452a9c86d7ae7e078c5fcd3b11b77a37513c3` | `tests.test_rt24_merge_tree_gate` | 7 |

Source-root commands, after checking out the specified Git commit in a clean directory:

```sh
python3 -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_schema_evolution_model.py' -v
python3 -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_scheduler_fairness_model.py' -v
(cd research/PROTOTYPES/DEPENDENCY-GRAPH-01 && python3 -B -m unittest -v tests.test_rt24_merge_tree_gate)
```

The workflow stores original stdout/stderr as `result.log` and exact checkout information as `environment.txt`. The independent CI run reported **6 / 5 / 7** passing tests respectively with job-specific complete logs. Any future failed or unsupported environment must still be preserved rather than removed or reinterpreted as a proof. The version of Git supplied by Ubuntu is recorded, **not** assumed equal to the original RT-24 historical Git 2.52.0.

## 3. Observed result and scope limitations

**Observed 2026-11-23 results:** [GitHub Actions run #45259153864](https://github.com/aivibeflow/LLMLang/actions/runs/45259153864) reports **all 3 / 3 jobs successful** with expected Git test blobs and CPython **3.12.14**, Git **2.56.1** on Ubuntu 24.04. Exact job IDs, source blobs, outcomes, per-job logs and artifact links are frozen in the [machine-readable outcome register](quality-audit/2026-11-23-claim-cohort2-rerun-results.json).

| Study | Observed new result | Job / result artifact |
| --- | --- | --- |
| Scenario 110 finite JSON | **6 passing tests**, no failures | [Job #137988897112](https://github.com/aivibeflow/LLMLang/actions/runs/45259153864/job/137988897112), [artifact](https://github.com/aivibeflow/LLMLang/actions/runs/45259153864/artifacts/14858974727) |
| Scenario 112 finite fairness | **5 passing tests**, no failures | [Job #137988896861](https://github.com/aivibeflow/LLMLang/actions/runs/45259153864/job/137988896861), [artifact](https://github.com/aivibeflow/LLMLang/actions/runs/45259153864/artifacts/14858779039) |
| RT-24 closed Git-tree source gate | **7 passing tests**, no failures | [Job #137988896405](https://github.com/aivibeflow/LLMLang/actions/runs/45259153864/job/137988896405), [artifact](https://github.com/aivibeflow/LLMLang/actions/runs/45259153864/artifacts/14858284758) |

This is fresh bounded **executable corroboration of selected claims**, not an additional formal theorem. The [source-bound 24-claim audit](RT-00-QUALITY-RULES-CLAIM-COHORT2-2026-11-23.md) still has 21 other claims without an independent execution specifically in this new workflow. In particular, passing the RT-24 suite on Git 2.56.1 **does not exactly reproduce** its originally reported Git 2.52.0 environment.

- **Scenario 110:** passing six finite JSON decoding tests supports the supplied one-added-Boolean-field model only. No binary serializer, Protobuf, Avro, CBOR, wire format selection, schema evolution policy, ABI, or real migration tested.
- **Scenario 112:** passing five finite-cycle/round-robin tests supports a limited difference between weak and strong fairness on a repeating enabledness trace. It does not establish runtime scheduler latency, crash tolerance, blocked task progress or a normative fairness promise.
- **RT-24:** seven controlled Git merge/import tests can falsify the assumption that a clean Git merge or warm-store graph audit proves source completeness. They do not establish a complete LLMLang parser/SPG importer, all dispatch relationships, accepted ADR-014, synchronized commit/recovery or production merge correctness.

## 4. Negative results, decisions, and outstanding follow-up

The included negative fixtures are valuable: Scenario 110 distinguishes explicit null from missing keys and strict rejection from permissive loss; Scenario 112 shows weak fairness still permits starvation with intermittent enablement; RT-24 tests a clean textual merge that becomes an invalid semantic candidate and counterexamples where index/graph consistency hides lost source declarations. These **bounded counterexamples** do not imply a global LLMLang design choice.

**Recommended next action after the CI run:** cite each exact successful/failed job and environment; integrate the outcomes without rewriting original historical runs; assign a separate technical reviewer to test whether model assumptions match source and intended semantics. Maintain Q1–Q5 as proposed, with a separate explicit maintainer adoption decision.

**Unresolved:** original-run provenance for the eight prior reports, broad representative claim review, missing correspondence between models and full-language implementation, and formal project approval of the quality protocol. [Issue #285](https://github.com/aivibeflow/LLMLang/issues/285) remains open.
