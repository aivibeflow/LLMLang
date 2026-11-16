# Research Scenario 24 — Adaptive Interaction Discovery

**Status:** Research result and prototype; not a normative LLMLang decision.

## 1. Research question

Scenario 22 creates a finite-domain candidate pool and schedules it under a budget. Scenario 23 can analyze joint interventions and repeated 2×2 factorial blocks. This scenario connects them into an adaptive loop:

**Which experiment should LLMLang run next, given the evidence already collected?**

The goal is not to enumerate every combination. It is to use previous results to decide where to increase interaction order, where to retry, and where to preserve exploration of still-unknown combinations.

## 2. Related work and what it teaches us

### Feedback-driven adaptive combinatorial testing

Dumlu, Yılmaz, Cohen, and Porter describe feedback-driven adaptive combinatorial testing (FDA-CIT). Their work addresses masking effects: an earlier failure can perturb execution and prevent later combinations from being meaningfully exercised. The process detects potential masking, heuristically isolates likely causes, and generates later samples that allow previously masked combinations to be tested.

**LLMLang implication:** a static covering array is not always enough. Execution feedback can change the next experiment set. However, LLMLang's evidence is richer than pass/fail: it includes observable behavior, trace-only changes, inconclusive runs, typed requirements, and dependency hypotheses. Our prototype does not implement FDA-CIT's masking diagnosis; it adopts the iterative feedback principle.

### Combinatorial interaction testing

NIST describes t-way testing and covering arrays as practical ways to exercise combinations without exhaustive enumeration. NIST's empirical work reports that many faults involve a small number of factors, while also documenting higher-order interactions. This is a useful prioritization prior, not a theorem that all programs have low-order dependencies.

**LLMLang implication:** begin with single factors and pairs, but never translate pairwise coverage into a claim that higher-order dependencies do not exist.

### Code-aware and directed testing

Code-aware combinatorial testing uses structural feedback to focus stronger interaction coverage on factors that influence relevant code regions. Directed greybox fuzzing similarly prioritizes inputs that approach target program locations rather than spending all resources on undirected coverage growth.

**LLMLang implication:** static dependency hints, taint paths, branch feedback, and trace events can prioritize candidate factors or pairs. These are search signals only. They do not establish semantic dependency or observable influence.

### Property-based and stateful generation

Hypothesis stateful testing generates action sequences as well as values, using rules and invariants to explore stateful behavior.

**LLMLang implication:** the same adaptive scheduler can later operate on sequences and state transitions, but the current prototype is limited to finite-valued factors and static assignments.

## 3. Distinguish three things

1. **Candidate generation:** which assignments or factorial blocks could be tested?
2. **Experiment scheduling:** which complete block should consume the next execution budget?
3. **Evidence interpretation:** what does the observed result justify saying?

The scheduler must not silently convert "high priority" into "proven dependency." Priority is a policy for spending test budget, not an evidence status.

## 4. Proposed adaptive loop

### Phase A — Single-factor interventions

Start with a pinned baseline and test every declared alternative value of each factor independently. Each intervention is a repeated pair:

- baseline;
- treatment changing one factor;
- same artifact, context, binding, environment, dependency roots, policy, and observation model;
- repeated trials under the same execution protocol.

Single-factor results classify factors as observed influential, trace-only, no observed difference, or inconclusive. Static/taint/Requirement IR guidance can be attached separately.

### Phase B — Pairwise factorial blocks

After all single-factor candidates have results, generate 2×2 blocks for pairs of factors.

For two selected levels of A and two selected levels of B, the block contains all four cells: A0/B0, A1/B0, A0/B1, A1/B1. For multi-valued factors, the prototype enumerates every unordered pair of levels for each factor, including pairs that do not contain the global baseline value. This avoids the blind spot where an interaction occurs only between two non-baseline levels.

Each cell is repeated. The default is two repetitions per cell, matching the repeated-evidence floor used by the Scenario 23 prototype. The block is atomic: the scheduler never spends budget on only part of a factorial block.

### Phase C — Evidence-triggered higher-order escalation

An OBSERVED_INTERACTION result for a pair creates higher-order hypotheses by adding one additional factor at a time. For each added factor, the scheduler creates a full 2^k factorial block using the pair's selected levels and each possible two-level selection for the added factor.

If a higher-order analyzer later reports an interaction for that block, the scheduler can add another factor. The maximum interaction order is configurable and bounded by the number of declared factors.

Important distinction:
- OBSERVED_INTERACTION triggers higher-order escalation.
- OBSERVED_BEHAVIORAL_INFLUENCE for a joint intervention does not, by itself, prove interaction. It indicates a joint effect that still needs attribution.
- NO_INTERACTION_OBSERVED is scoped to the tested levels, context, observable algebra, and design. It does not prove global absence.
- INCONCLUSIVE triggers a bounded retry of the same complete design.

### Phase D — Exploration/exploitation balance

The scheduler prioritizes:
1. bounded retries of inconclusive experiments;
2. higher-order blocks triggered by observed interactions;
3. pairs declared related by Requirement IR, static analysis, taint, or prior discovery;
4. pairs containing factors with positive, trace-only, or inconclusive single-factor evidence;
5. unrelated, still-unexplored pairs.

A deterministic exploration reserve prevents high-priority hypotheses from permanently starving unrelated pairs. The prototype defaults to 20% of execution budget when both priority and exploration queues exist and the budget is large enough to fit a complete repeated 2×2 block. For smaller budgets, it does not reserve an unusable fraction.

This is a transparent heuristic, not a learned probability model or a claim of optimal information gain. A future scheduler could use calibrated uncertainty, execution cost, risk, and expected information gain.

## 5. Budget model

The budget is measured in actual execution runs, not just unique input configurations.

For k factors in a full two-level factorial block and r repetitions per cell:

    Cost(k, r) = 2^k × r

With the default r=2:
- one factor: 4 executions;
- two factors: 8 executions;
- three factors: 16 executions;
- four factors: 32 executions.

The exponential growth is why higher-order blocks are generated lazily, only after evidence triggers them, and why a hard maximum interaction order is required.

## 6. Candidate identity and reproducibility

A candidate root digest binds:
- exact artifact hash;
- pinned context digest;
- observation-model digest;
- experiment kind;
- factor scope;
- selected levels for every factor;
- complete factorial cells;
- repetitions per cell.

A retry receives a new attempt digest while retaining the same root experiment identity. Trigger provenance is recorded separately and does not change the identity of the experiment itself.

Feedback from another artifact, context, observation model, or baseline is rejected. This prevents evidence from being silently reused across different experimental conditions.

## 7. Coverage and evidence remain separate

The ledger maintains separate sets for:
- experiment targets actually executed;
- runtime feedback targets actually observed;
- result status per exact candidate.

A planned candidate does not count as executed. An executed candidate does not automatically mean a new branch, taint path, or observable outcome was observed. Neither dimension is a semantic completeness proof.

The report explicitly returns semantic_completeness_claim: false.

## 8. Prototype design

Added src/adaptive_discovery.py:

- build_adaptive_plan: creates all single-factor interventions and pairwise 2×2 blocks for all selected level pairs.
- AdaptiveCandidate: immutable block with exact cells, pinned identity, repetitions, digest, and trigger provenance.
- AdaptiveLedger: stores one result per exact candidate and keeps executed targets separate from observed feedback targets.
- plan_next_batch: selects whole blocks under an execution-run budget.
- _higher_order_candidates: lazily generates 2^k blocks after OBSERVED_INTERACTION.
- _retry_candidates: creates bounded new attempts for inconclusive blocks.
- adaptive_report: exposes pending single/pair/higher-order work, interactions, inconclusive experiments, and separate coverage dimensions.

The planner accepts Scenario 23 status enums by their string values. It consumes normalized feedback; it does not run the program.

## 9. Deliberate limitations

1. No execution engine or runtime instrumentation.
2. No statistical model for nondeterministic outcomes or confidence intervals.
3. No generalized k-way interaction analyzer; Scenario 23 currently supplies the 2×2 analyzer. The planner can generate higher-order blocks, but an external analyzer must interpret them.
4. No constraint solver. Infeasible factorial cells must be filtered or represented by a future constraint-aware block design; the current planner may generate invalid assignments.
5. No automatic extraction of related factor pairs from Requirement IR, static analysis, taint, or traces. Those signals are supplied by the caller.
6. No active-learning probability model, calibrated expected information gain, or optimal schedule guarantee.
7. Full factorial blocks grow exponentially. The maximum order and execution budget must remain explicit.
8. The current baseline is pinned for all non-selected factors. Context-specific interactions may require separate baseline/context partitions.
9. Stateful event sequences, temporal requirements, and concurrent interventions are not implemented.
10. A failure/masking diagnosis model is not implemented. FDA-CIT demonstrates why this deserves a separate follow-up.

## 10. Open questions

1. Should constraints be solved before candidate creation, or should infeasible cells be represented in the ledger?
2. How should multiple baselines/context partitions be selected and pinned?
3. What higher-order contrast semantics should be defined for numeric, categorical, set-valued, and trace outcomes?
4. How should uncertainty and stochastic behavior affect retries and scheduling?
5. How should masking effects be distinguished from real behavioral influence and execution aborts?
6. How should static/taint/branch evidence map to factor-level hypotheses with provenance?
7. What is the right stopping policy when the budget expires but triggered interactions remain?
8. Should the next scheduler optimize expected information gain, risk reduction, or a reviewable weighted combination?
9. How should a human accept residual unknown interaction scopes?
10. How should stateful/temporal factors and event-sequence covering arrays enter the same planner?

## 11. Preliminary recommendation

Use an adaptive, staged scheduler as a separate planning layer:
- singles first;
- complete repeated 2×2 blocks for all pairs and selected level pairs;
- higher-order blocks only when interaction evidence or explicit structural guidance justifies escalation;
- bounded retries for inconclusive evidence;
- deterministic budget accounting and a protected exploration tranche;
- exact context-bound candidate identities;
- separate execution coverage, observed feedback, and semantic evidence.

Do not present this strategy as exhaustive. It is an evidence-guided way to spend a finite budget while keeping untested combinations visible.

## 12. References

- Dumlu, Yılmaz, Cohen, Porter, Feedback Driven Adaptive Combinatorial Testing, ISSTA 2011, DOI: https://doi.org/10.1145/2001420.2001450
- Dumlu et al., Reducing Masking Effects in Combinatorial Interaction Testing: A Feedback Driven Adaptive Approach, IEEE TSE 40(1), 2014, DOI: https://doi.org/10.1109/TSE.2013.53
- NIST, Combinatorial Methods for Trust and Assurance: https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software
- Kuhn, Kacker, Lei, Measuring and Specifying Combinatorial Coverage of Test Input Configurations, 2015, DOI: https://doi.org/10.1007/s11334-015-0266-2
- Szeles et al., Code-aware combinatorial interaction testing, 2019, DOI: https://doi.org/10.1049/iet-sen.2018.5315
- Böhme et al., Directed Greybox Fuzzing, CCS 2017, DOI: https://doi.org/10.1145/3133956.3134020
- Hypothesis, Stateful testing: https://hypothesis.readthedocs.io/en/latest/stateful.html
- Combinatorial transition testing in dynamically adaptive systems: Implementation and test oracle, Journal of Systems and Software 221, 2025, DOI: https://doi.org/10.1016/j.jss.2024.112260
