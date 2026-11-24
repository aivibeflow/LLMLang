# Research Scenario 21 — Counterfactual Detection of Semantic Dependencies

**Status:** Research result and prototype proposal; not a normative LLMLang decision  
**Date:** 2026-11-16  
**Depends on:** Scenarios 18–20 and Dependency Graph Prototype 01

## 1. Research question

Scenario 20 defined a discovery pipeline that preserves evidence-bearing dependency candidates and requires explicit semantic classification. Scenario 21 asks how the system can produce stronger evidence automatically: if one input is changed while the rest of the execution context is held fixed, does observable behavior change? Can the system distinguish an observed behavioral effect from a mere read or internal path difference? What can be concluded when no difference is observed? How should nondeterminism, external effects, multiple interacting inputs, and limited coverage affect the result?

## 2. Executive conclusion

Add a **counterfactual experiment layer** between dependency discovery and semantic classification. It performs controlled interventions: execute a baseline and a treatment that differ in one declared input factor, under the same pinned context, and compare observable outcomes. Repeated paired trials help detect instability. Execution traces are retained as explanatory evidence but are not themselves treated as proof of semantic influence.

Use four outcomes:

- **OBSERVED_BEHAVIORAL_INFLUENCE** — paired runs show a reproducible difference in the defined observable outcome.
- **INTERNAL_PATH_CHANGE_ONLY** — execution traces differ but the defined observable outcome does not.
- **NO_OBSERVED_DIFFERENCE** — no difference was found in the tested intervention set and scope.
- **INCONCLUSIVE** — the experiment is invalid, insufficient, context-mismatched, or unstable.

Only OBSERVED_BEHAVIORAL_INFLUENCE is positive experimental evidence for a semantic dependency. NO_OBSERVED_DIFFERENCE is not evidence of non-dependence and must never be translated automatically into INCIDENTAL_ACCESS. INTERNAL_PATH_CHANGE_ONLY is diagnostic evidence, but does not establish a difference at the chosen semantic boundary.

## 3. Research basis

### 3.1 Causal testing and controlled interventions

The Causal Testing Framework models a test as a control configuration, a treatment configuration, an intervention, and an expected effect. It treats input changes as experiments designed to isolate cause/effect relationships and discusses experimental and observational evidence. This is a close conceptual match for dependency discovery, provided LLMLang pins the exact program, input, and execution context.

### 3.2 Difference-exposing tests

Differential testing searches for inputs that make two program versions or configurations produce different outputs. Execution-driven test generation can iteratively use observed execution feedback to find such inputs. For LLMLang, the two executions need not be two source versions: they can be two executions of the same immutable program state with one input factor deliberately changed.

### 3.3 Dynamic dependency capture

Pluto demonstrates that build steps can report the files and other build steps they dynamically require, and that a sound incremental build algorithm can interleave dependency discovery with execution while enforcing graph invariants. This supports collecting dependencies during actual execution, but dynamic access alone still does not determine whether an access changes language-level observable behavior.

### 3.4 Taint and data-flow evidence

Dynamic taint analysis tracks whether input-derived values propagate to selected operations. It can provide a useful explanation of how an input reaches an output or effect. It is not equivalent to semantic dependence: a tainted value may be overwritten, masked, used only for diagnostics, or reach an operation whose result is unobservable. Conversely, control dependence can affect behavior without the input value flowing directly into an output value.

## 4. Define the observable boundary first

A counterfactual experiment is meaningful only relative to a declared observation model. A candidate observable outcome may include returned values and structured outputs; declared error/exception class and payload; state changes visible through the contract; externally visible effects such as database writes, messages, and network requests; termination or timeout class; and ordering/concurrency observations where the contract exposes them.

The observation model must exclude implementation-only details unless the contract explicitly exposes them. Internal call traces, instruction counts, temporary allocations, and branch paths are diagnostic evidence, not automatically semantic outputs. The observation model itself is an exact input to experiment identity. Changing it invalidates the previous result.

## 5. Controlled intervention model

For one factor, define a baseline input configuration X0, a treatment configuration X1, and a pinned context C containing program, binding, environment, dependency, policy, and observation-model identities. X0 and X1 must differ in exactly one declared factor. Let O(P, X, C) be the canonical observable outcome.

A paired experiment compares O(P, X0, C) with O(P, X1, C). If they differ, the intervention has an observed effect for that tested input/context. This is stronger than observing that the program read the input, because the experiment manipulates the input and compares outcomes under a controlled context.

The conclusion remains scoped to the exact intervention, context, and observations. It is not a universal theorem about every possible input.

## 6. Experimental protocol

1. Pin exact program semantic hash, binding snapshot, runtime/toolchain, dependency closure, policy, and observation-model hash.
2. Select a baseline input and generate a valid treatment by changing one declared factor.
3. Validate that both input configurations satisfy the same scenario constraints and differ only in the declared factor.
4. Execute paired baseline/treatment runs under the same pinned context.
5. Repeat pairs to detect nondeterminism and environmental instability.
6. Canonicalize observable outputs, errors, state deltas, and external effects.
7. Compare observable outcome digests separately from execution-trace digests.
8. If observable outcomes differ reproducibly, emit positive behavioral-influence evidence.
9. If only traces differ, emit internal-path-change evidence; do not automatically create a semantic edge.
10. If outcomes are equal, emit only NO_OBSERVED_DIFFERENCE for the tested scope.
11. If contexts differ, pairs are missing, outcomes are unstable, or intervention validity is uncertain, return INCONCLUSIVE.
12. Store all run identities and evidence in an immutable experiment record.
13. Feed positive evidence and unresolved results to Scenario 20 classification. Do not let the experiment layer unilaterally approve INCIDENTAL_ACCESS.

## 7. Repetition and nondeterminism

A single baseline/treatment pair can be misleading when the program is nondeterministic. The prototype requires a configurable minimum number of paired trials and checks that baseline outcomes are stable across repeats and treatment outcomes are stable across repeats.

This is deliberately conservative. Real systems may require statistical models, randomized assignment, confidence intervals, blocking, or causal inference over historical observations. Those methods can be introduced later, but a statistical estimate must not be mislabeled as a deterministic proof.

External services and clocks should preferably be replaced by pinned fixtures or deterministic replay. If that is impossible, their identities and responses must be captured as part of the context and effect transcript.

## 8. Interaction effects and limits of one-factor-at-a-time

A factor may matter only in combination with another factor. For example, discount_code may affect output only when customer_tier=gold. A test that mutates the discount code while holding the tier at standard can observe no difference even though the code is semantically relevant in another context.

Therefore:
- one-factor experiments establish only local effects at their tested context;
- scenario partitions and boundary values must be explored;
- pairwise or higher-order interventions may be required to discover interactions;
- the experiment record must identify tested factor levels and context;
- absence of an observed effect cannot justify deleting a dependency edge.

The next research step should investigate coverage-guided intervention selection and interaction discovery.

## 9. Distinguish the evidence types

| Evidence | What it supports | What it does not establish |
|---|---|---|
| File/API access trace | Input was accessed | Input changes observable behavior |
| Data taint reaches output/effect | Data-flow path to an observed sink | Output/effect necessarily changes |
| Control-flow path changes | Input altered executed path | Contract-visible behavior changes |
| Paired observable outcome differs | Intervention changed observed behavior in this context | Universal dependence across all inputs |
| Repeated paired outcomes differ consistently | More robust scoped evidence under tested conditions | Formal proof for untested conditions |
| No difference observed | No effect found in sampled scope | Input is irrelevant |
| Formal non-interference proof | No influence under proof model and assumptions | Correctness of model or human intent |

## 10. Prototype 21

Files:
- PROTOTYPES/DEPENDENCY-GRAPH-01/src/counterfactual_analysis.py
- PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_counterfactual_analysis.py
- PROTOTYPES/DEPENDENCY-GRAPH-01/PROTOTYPE-21-RESULTS.md

The prototype consumes normalized paired-run records. It does not execute arbitrary programs, generate mutations, instrument runtime data flow, or collect traces. It verifies basic experiment structure, compares observable and trace digests separately, checks repeated-trial stability, and emits a scoped evidence result with deterministic digest.

## 11. Result statuses

- **OBSERVED_BEHAVIORAL_INFLUENCE:** repeated paired trials show a reproducible observable-outcome difference.
- **INTERNAL_PATH_CHANGE_ONLY:** observable outcomes are equal, but execution traces differ.
- **NO_OBSERVED_DIFFERENCE:** observable outcomes and traces are equal across tested pairs.
- **INCONCLUSIVE:** insufficient pairs, invalid intervention, context mismatch, or unstable repeated outcomes.

No status in this prototype is a formal proof. NO_OBSERVED_DIFFERENCE is not a license to remove a dependency.

## 12. Limitations

- No program execution engine, input mutator, fuzzing engine, taint tracker, or trace collector is implemented.
- The prototype trusts supplied canonical digests and exact context identities.
- It assumes the declared changed factor is accurate; it does not inspect structured input values to prove that only one field changed.
- It uses exact equality of repeated digests rather than statistical inference.
- It does not model stateful cross-run carryover, distributed systems, concurrency, or external-effect compensation.
- It does not discover interaction effects automatically.
- It does not infer INCIDENTAL_ACCESS and cannot prove non-dependence.
- It does not yet integrate experiment evidence into the Scenario 20 dependency audit or Scenario 19 plan identity.

## 13. Acceptance criteria

- Baseline and treatment must have distinct input digests.
- The intervention must declare exactly one changed factor for this prototype.
- All paired runs must refer to the same artifact, observation model, and execution context.
- At least the configured number of pairs must be present.
- Unstable repeated outcomes yield INCONCLUSIVE.
- Observable outcome changes and trace-only changes are classified separately.
- NO_OBSERVED_DIFFERENCE is scoped and never becomes a non-dependence proof.
- Evidence digest changes when artifact, context, observation model, factor, runs, outcomes, or traces change.

## 14. Preliminary recommendation

Use controlled counterfactual execution as a **positive-evidence generator**:
- combine access tracing, taint/data-flow, and controlled interventions;
- define the semantic observation boundary before comparing runs;
- compare observable outcomes separately from internal traces;
- repeat trials to expose instability;
- treat positive observed effects as evidence for a candidate semantic dependency;
- treat no observed effect as unresolved or scoped negative evidence, never as proof of irrelevance;
- retain interaction and coverage gaps for later exploration.

This is a research conclusion, not a normative LLMLang language rule.

## 15. References

- Clark et al., *Testing Causality in Scientific Modelling Software*, ACM TOSEM 33(1), 2023. https://doi.org/10.1145/3607184
- Foster et al., *The Causal Testing Framework*, Journal of Open Source Software, 2025. https://doi.org/10.21105/joss.07739
- Johnson et al., *Causal Testing: Understanding Defects' Root Causes*, ICSE 2020. https://people.cs.umass.edu/~brun/pubs/pubs/Johnson20icse.pdf
- *Mokav: Execution-driven differential testing with LLMs*, Journal of Systems and Software 230, 2025. https://doi.org/10.1016/j.jss.2025.112571
- Erdweg, Lichter, Weiel, *A Sound and Optimal Incremental Build System with Dynamic Dependencies*, OOPSLA 2015. https://doi.org/10.1145/2814270.2814316
- Saito, Sakamoto, Washizaki, *Efficient Build Dependency Verification Using eBPF and Incremental Analysis*, ICSE 2026. https://doi.org/10.1145/3744916.3773204
