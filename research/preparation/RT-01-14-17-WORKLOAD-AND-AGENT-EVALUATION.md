# Research Preparation — RT-01/14/17 Workload and Agent Evaluation

**Status:** Prepared; not executed.  
**Priority:** P1 — define before integrated candidate scoring.  
**Related open questions:** LL-001–008 and cross-cutting RT-01, RT-14, RT-17, RT-18 criteria.

## 1. Objective

Prepare a reproducible evaluation that separates language/toolchain correctness, workload fit, developer experience and AI-agent behavior. Establish workload weights before scoring candidate profiles. Keep unknown evidence visible rather than assigning an arbitrary zero.

## 2. Existing material

Read:
- [RT-01 reference workloads](../RT-01-REFERENCE-WORKLOADS.md)
- [Research State](../RESEARCH-STATE-2026-11-19.md), Gates D and the candidate-vector section
- [Research Option Matrix 01](../RESEARCH-OPTION-MATRIX-01.md)
- [Scenario 95 — diagnostics for humans and coding agents](../RESEARCH-SCENARIO-95-DIAGNOSTICS-FOR-HUMANS-AND-AGENTS.md)
- [RT-14 AI authoring / RT-17 DX**] (use the taxonomy and dependency map to locate the current detailed reports before execution)

## 3. Questions

### Workload validity and weights
- Which reference workloads represent the target classes of programs?
- Which workloads are mandatory, common, rare, safety-critical or exploratory?
- Who defines the weights, and how are disagreements and sensitivity reported?
- Which candidate profiles cannot express a workload without escape hatches?
- How do unsupported cases affect the comparison?

### Human and agent authoring
- Can participants make a bounded, semantically correct change from a task specification?
- How many repair iterations and diagnostic round trips are needed?
- Does the agent change files/entities outside the authorized scope?
- How much context, token use, wall time and tool interaction are required?
- Can reviewers understand the change and its evidence?
- Are diagnostics actionable for both humans and coding agents?

### Correctness versus usability
- How can authoring success be scored independently from runtime correctness?
- How are task difficulty, participant experience, model/tool version and prompt exposure controlled?
- How are failed, abandoned and unsafe attempts reported?

## 4. Experimental preparation

Prepare:
- a frozen task catalogue with one intended semantic change per task;
- equivalent tasks for each candidate implementation/toolchain;
- a baseline task and a deliberately ambiguous task;
- hidden acceptance tests and an independent reviewer rubric;
- instrumentation for task completion, repairs, diagnostics, context/token use, latency, scope violations and review quality;
- a preregistered workload-weight proposal and sensitivity plan.

Randomize task order where appropriate. Record participant/model/tool versions and permitted assistance. Avoid mixing a correctness benchmark with an unblinded preference survey.

## 5. Analysis plan

Report each measure separately:
- task completion and correctness;
- repair iterations and diagnostic resolution;
- unsupported/abandoned tasks;
- out-of-scope or unauthorized changes;
- review agreement and reproducibility;
- context/token use and tool calls;
- elapsed time and resource consumption.

Then evaluate candidate ranking under alternative plausible workload weights. Show where rankings change and preserve unknowns. Do not combine correctness, usability, speed and trust into one opaque score.

## 6. Exit criteria

- Workloads and acceptance criteria are frozen before candidate scoring.
- Weights have an explicit source and sensitivity analysis.
- Tasks are comparable across candidates and tool versions.
- Correctness and usability are reported separately.
- Scope violations and failed attempts are retained, not filtered out.
- Reproduction data and reviewer agreement are available.
- A candidate is not declared best where material dimensions remain unknown.

No language profile is selected by this study alone.
