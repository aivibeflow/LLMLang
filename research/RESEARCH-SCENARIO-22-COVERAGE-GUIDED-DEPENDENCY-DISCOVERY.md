# Research Scenario 22 — Coverage-Guided Dependency Discovery

**Status:** Research result and prototype proposal; not a normative LLMLang decision.

## 1. Question

Scenario 21 compares repeated baseline/treatment runs for a preselected intervention. It does not choose interventions. This scenario asks how LLMLang can generate useful input mutations, explore boundaries and factor interactions, use runtime feedback, and report what remains untested under a finite execution budget.

## 2. Research findings

### Property-based generation

Hypothesis separates an input domain from the probability distribution used to sample it. Its guidance recommends describing a sufficiently general domain rather than prematurely narrowing it; the engine can emphasize useful values such as integer endpoints and adapt its distribution. Hypothesis also supports stateful generation of action sequences, not just isolated values.

**LLMLang implication:** Requirement IR describes admissible domains, constraints, semantic partitions, and state transitions. The exploration engine chooses and records a search distribution independently; sampling policy must not become part of the requirement itself.

### Structure-aware and coverage-guided fuzzing

Coverage-guided fuzzers retain and prioritize inputs that expose new execution coverage. Structure-aware fuzzing uses a grammar or typed generator to avoid wasting most runs on malformed inputs rejected before meaningful behavior. Taint/data-flow guidance can help cross difficult input constraints, but a taint path is a lead for an intervention—not proof that the factor changes observable behavior.

**LLMLang implication:** Mutate typed Requirement IR values and constraints as the primary semantic strategy. Byte-level fuzzing remains valuable for parser/serializer robustness, but is a separate layer.

### Combinatorial interaction testing

NIST describes t-way combinatorial testing and covering arrays as a way to cover selected combinations of parameter values with fewer test cases than exhaustive enumeration. Pairwise coverage is useful, but higher-order interactions exist and must not be treated as impossible.

**LLMLang implication:** Pairwise is a default exploration tier, not a completeness guarantee. Requirement predicates, observed conditional effects, risk, and uncovered evidence should raise interaction strength to 3-way or higher when justified.

### Semantic coverage feedback

HypoFuzz supports user-defined coverage events as virtual branches. This matters because control-flow branches do not represent every meaningful behavior category or boundary condition.

**LLMLang implication:** Collect separate feedback dimensions. A new semantic partition or observable outcome class may be interesting even without a new code branch.

## 3. Coverage dimensions must remain separate

| Dimension | Measures | Does not establish |
|---|---|---|
| Input-domain | Declared values/partitions exercised | Completeness of the declared domain |
| Boundary | Numeric extrema and requirement-defined thresholds | All relevant boundaries |
| Semantic partition | Business-rule and Requirement IR cases exercised | Correctness of partition definitions |
| Interaction | t-way value combinations exercised | Absence of higher-order interactions |
| Branch/edge | Instrumented control-flow locations reached | Semantic dependency or observable influence |
| Taint/data-flow | Candidate paths from inputs to internal/observable sinks | Causality or output change |
| Trace event | Internal execution events observed | User-visible behavioral difference |
| Observable outcome | Contract-defined outcome classes observed | Exhaustiveness outside tested scope |
| Dependency candidate | Candidate factors/interventions tested | Completeness of discovered dependencies |

Never collapse branch coverage, taint reachability, and observable influence into one “dependency found” flag.

## 4. Proposed exploration pipeline

1. **Pin context:** artifact, project, binding, environment, dependency roots, observation model, and policy.
2. **Extract typed factors:** derive candidates from Requirement IR variables, finite domains, partitions, triggers, policy inputs, and assumptions. Invalid/unresolved models cannot support clean acceptance; exploratory runs must be labelled.
3. **Build a baseline:** select and record one valid assignment. It is a control and must not drift between pairs.
4. **Generate interventions:** single-factor changes first, pairwise combinations next, then targeted higher-order combinations. Include numeric extrema and explicit requirement thresholds. Do not invent “near-boundary” values without a meaningful scale/threshold.
5. **Attach guidance:** static analysis, taint, symbolic/concolic constraints, branch feedback, and prior Scenario 21 outcomes may prioritize candidates. They do not classify dependencies.
6. **Schedule under budget:** prefer candidates covering the largest number of currently uncovered targets, with deterministic tie-breaking. A production scheduler should additionally consider risk, execution cost, novelty, uncertainty, and exploration/exploitation.
7. **Execute controlled comparisons:** reuse Scenario 21's pinned repeated baseline/treatment design and compare observables separately from traces. Its current analyzer accepts exactly one changed factor; multi-factor candidates need a future comparison-API extension.
8. **Record feedback:** persist semantic partitions, branch/edge IDs, taint paths, trace events, outcome classes, failures, timing, and exact input/artifact/context digests.
9. **Update the ledger:** add observed coverage only. Preserve uncovered targets and why they remain untested (budget, infeasible constraints, execution error, unresolved requirement, missing instrumentation, or scheduler policy).
10. **Stop conservatively:** stop at budget/time limits, no remaining candidates, or a documented saturation policy. “No new coverage” is not proof of completeness or irrelevance.

## 5. Mutation strategy

- **Typed value mutation:** choose another value from the declared finite domain while retaining type correctness.
- **Boundary mutation:** try declared minimum/maximum and explicit predicate thresholds or adjacent values where domain semantics justify them.
- **Constraint-aware mutation:** generate valid and deliberately violating cases separately. Violating cases test guards and error behavior; do not discard them.
- **Single-factor interventions:** establish baseline influence for each factor.
- **Pairwise combinations:** cover relevant pairs, including cases where one factor remains at its baseline value.
- **Higher-order combinations:** target conditional requirements, interactions indicated by traces/taint, unresolved effects, and high-risk paths.
- **Sequence/state mutation:** for stateful requirements, mutate action sequences and state transitions.
- **Grammar/byte mutation:** separately fuzz the IR parser, serializer, compiler frontend, and protocol boundary.

Semantic partitions (e.g. below/at/above threshold) should be defined in the requirement model and carry provenance; they should not be invented by the fuzzer.

## 6. Interaction coverage and budget

Exhaustive enumeration costs the product of all domain sizes, which grows rapidly. Covering arrays can reduce the number of assignments for a chosen interaction strength, but are not automatically optimal for semantic dependency discovery: constraints make some combinations infeasible, and factors have different relevance and execution costs.

Recommended policy:
- reserve an initial tranche for baseline and feasible single-factor interventions;
- next cover pairs of factors that share a semantic scope, dependency, or contract boundary;
- increase interaction order when predicates conjoin factors, static/taint evidence suggests a path, or prior runs show conditional effects;
- reserve a small exploration tranche for low-priority candidates to avoid overfitting to known paths;
- report untested combinations explicitly.

Do not stop merely because every individual value has been seen: important combinations may remain untested.

## 7. Evidence semantics

Scenario 21's statuses remain useful at the execution-comparison level:
- OBSERVED_BEHAVIORAL_INFLUENCE: repeated paired runs differ at the contract-defined observable boundary.
- INTERNAL_PATH_CHANGE_ONLY: traces differ but observables do not.
- NO_OBSERVED_DIFFERENCE: no difference was seen for this intervention and pinned context.
- INCONCLUSIVE: evidence is incomplete, unstable, mismatched, or invalid.

Coverage is a separate axis. A run can be inconclusive; a target can be scheduled but not executed; a branch can be covered without observable effect. A negative result is scoped to exact intervention, artifact, context, observation model, trial policy, and tested partition. It cannot justify globally deleting an edge or classifying an input as incidental.

## 8. Prototype design

The standard-library prototype models:
- Factor: finite domain plus optional value-specific static/taint guidance tags;
- Candidate: immutable assignment, changed-factor list, coverage targets, digest;
- PlannedExperiments: pinned artifact/context/observation-model identities and target universe;
- CoverageLedger: observed targets and per-candidate feedback;
- build_plan: single-factor and t-way interventions, numeric extrema, interaction targets, deterministic identities;
- schedule: deterministic greedy set-cover selection under an explicit run budget;
- coverage_report: explicit uncovered targets.

Candidate identity includes artifact, context, observation model, assignment, and changed factors. Equivalent assignments are deduplicated while unioning targets contributed by different factor subsets.

The prototype does not execute programs, implement a fuzzer, parse Requirement IR automatically, derive partitions from natural language, solve constraints, perform concolic execution, instrument branches, run taint analysis, or invoke Scenario 21. It consumes normalized factor domains and feedback from an external analysis/execution layer.

## 9. Integration with earlier scenarios

- Scenario 17 supplies typed finite domains, predicates, and scenario constraints.
- Scenario 18 supplies immutable requirement revisions and semantic impact relations.
- Scenario 19 supplies typed impact actions and conservative completeness handling.
- Scenario 20 supplies dependency candidates with discovery provenance and semantic classification.
- Scenario 21 supplies controlled counterfactual comparison semantics.
- Scenario 22 supplies exploration planning, a coverage ledger, and budgeted candidate scheduling.

Conceptual loop:

Requirement IR → typed factor/partition extraction → intervention plan → budgeted scheduler → pinned execution → Scenario 21 comparison → coverage/evidence ledger → next intervention batch

## 10. Limitations and open questions

1. How should requirement-defined partitions and thresholds be represented canonically in Requirement IR?
2. How should covering arrays combine with constraints and violating scenarios?
3. What is the right abstraction for stateful and temporal interventions?
4. How should branch/taint feedback map to typed input factors without overstating causality?
5. How should nondeterminism and flaky observations be modeled statistically?
6. How should execution cost, risk, and expected information gain be estimated?
7. How should Scenario 21 compare multi-factor interventions while preserving interpretable causal claims?
8. How can instrumentation blind spots and unknown input dimensions be detected?
9. How should confidence and coverage gaps be reported to a human reviewer?
10. Who is authorized to accept residual unknowns, and under what stopping policy?

## 11. Preliminary recommendation

Adopt coverage-guided exploration as a **separate planning layer**, not as a replacement for dependency evidence or verification. Start with typed finite-domain single-factor and pairwise interventions, explicit boundary/semantic-partition targets, deterministic budget scheduling, and a multi-dimensional coverage ledger. Escalate to higher-order and stateful exploration when requirements, static analysis, taint, or observed behavior justify it.

No branch, pairwise, semantic, or other coverage percentage should be presented as proof that the dependency graph is complete.

## 12. References

- Hypothesis, Domain and distribution: https://hypothesis.readthedocs.io/en/latest/explanation/domain.html
- Hypothesis, Stateful tests: https://hypothesis.readthedocs.io/en/latest/stateful.html
- Google, Structure-Aware Fuzzing with libFuzzer: https://github.com/google/fuzzing/blob/master/docs/structure-aware-fuzzing.md
- NIST, Kuhn, Kacker, Lei, Combinatorial Testing (2012): https://www.nist.gov/publications/combinatorial-testing
- NIST CSRC, Combinatorial Methods for Trust and Assurance FAQs: https://csrc.nist.gov/Projects/automated-combinatorial-testing-for-software/faqs
- HypoFuzz, Custom coverage events: https://hypofuzz.com/docs/manual/behavior.html
