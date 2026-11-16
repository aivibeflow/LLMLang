# Research Scenario 23 — Multi-Factor Counterfactual Analysis

**Status:** Research result and prototype; not a normative LLMLang decision.

## 1. Problem

Scenario 21 compares one baseline with one treatment changing exactly one factor. Scenario 22 can schedule joint interventions and pairwise/higher-order assignments, but those candidates cannot yet be analyzed by Scenario 21. A dependency can also be conditional: neither input changes behavior alone, while their combination does.

Example: \`customer_tier=gold\` alone has no effect; \`discount_code=active\` alone has no effect; both together activate a discount and change the amount charged.

## 2. Two distinct questions

**Joint intervention:** does this particular combination of changes alter observable behavior? It compares one pinned baseline assignment with one treatment assignment changing one or more factors. It does not attribute the result to individual factors or prove an interaction.

**Factor interaction:** does the effect of one factor depend on the level of another? This requires a factorial contrast, not merely a baseline-versus-joint-treatment pair.

## 3. Repeated 2×2 factorial design

For factors A and B, select two levels each and execute four cells:

| Cell | A | B |
|---|---|---|
| 00 | A0 | B0 |
| 10 | A1 | B0 |
| 01 | A0 | B1 |
| 11 | A1 | B1 |

Repeat the complete four-cell block under one pinned context. Compare each cell's outcomes across repetitions before calculating effects. Missing or unstable cells make the result INCONCLUSIVE.

Simple effects:
- A when B=B0: compare O00 with O10.
- A when B=B1: compare O01 with O11.
- B when A=A0: compare O00 with O01.
- B when A=A1: compare O10 with O11.

A hidden interaction can have O00=O10=O01 while O11 differs: neither factor acts alone at the other factor's baseline, but their combination changes behavior.

## 4. Observable outcome algebra

An opaque digest supports equality/inequality, but not arithmetic contrasts. The prototype therefore has two explicitly limited modes.

1. **Numeric scalar outcomes:** exact decimal difference-in-differences:
   \[
   \Delta_{AB}=(O_{11}-O_{10})-(O_{01}-O_{00})
   \]
   A non-zero contrast is evidence of a numeric interaction under the chosen encoding. Decimal conversion from string representations avoids ordinary binary floating-point subtraction artifacts; it does not define domain units or scales.
2. **Categorical/structured JSON outcomes:** compare equality patterns of conditional simple effects. This detects a factor changing the outcome in one context but not another. It can miss interactions when all four outcomes are distinct or when a domain-specific distance/ordering is needed.

Future work should let the behavioral contract define a typed observable algebra: equality, ordering, numeric scale, set/map comparison, trace properties, and equivalence classes. The analyzer must not invent metrics for arbitrary outputs.

## 5. Evidence statuses

- \`OBSERVED_BEHAVIORAL_INFLUENCE\`: repeated paired baseline/joint-treatment trials show a different observable result.
- \`INTERNAL_PATH_CHANGE_ONLY\`: observables match but traces differ.
- \`NO_OBSERVED_DIFFERENCE\`: no difference for this exact joint intervention and pinned context.
- \`OBSERVED_INTERACTION\`: factorial contrast or conditional simple-effect pattern demonstrates that the effect depends on the other factor's level.
- \`NO_INTERACTION_OBSERVED\`: no interaction detected by the declared observable algebra in this tested 2×2 design.
- \`INCONCLUSIVE\`: missing cells/pairs, unstable outcomes/traces, input drift, context mismatch, or insufficient repetitions.

These are experimental results, not proof statuses. \`NO_INTERACTION_OBSERVED\` is not proof that no interaction exists outside selected levels, partitions, or context.

## 6. Higher-order experiments

A joint intervention over k factors tests one combined assignment but cannot attribute the effect. A full two-level factorial design needs \(2^k\) cells per block and becomes expensive rapidly. Scenario 22's coverage-guided scheduler should select single-factor interventions, pairwise factorial blocks for plausible interactions, and higher-order blocks only where requirements, static analysis, taint, traces, or prior results justify them.

A t-way covering array reduces assignments for selected interaction coverage, but is not a substitute for a complete factorial contrast when estimating a particular interaction. Infeasible combinations must be recorded as constrained/unavailable, not counted as covered.

## 7. Context and causal interpretation

Every factorial block pins all non-target factors plus artifact, binding, environment, dependencies, policy, observation model, and deterministic runtime inputs. Repeated blocks must use the same cell input digest and stable cell outcome.

The result supports causal interpretation only to the extent that the intervention is controlled and the observable boundary is valid. Hidden confounders, incorrect factor declarations, nondeterministic external services, and instrumentation gaps remain threats. Traces are diagnostic evidence, not substitutes for observable outcomes.

## 8. Integration with Scenario 22

Scenario 22 joint assignments can feed the joint-intervention API. A pairwise interaction candidate must expand into four factorial cells; it is not one before/after treatment. Keep separate coverage targets for intervention execution, factor levels, factorial cells, interaction contrasts, and observable outcome classes. A planned candidate is not semantically covered until its required evidence is complete.

## 9. Prototype scope

Added \`src/multifactor_analysis.py\`:
- canonical immutable assignment helper;
- \`MultiFactorRun\` and \`analyze_joint_intervention\` for repeated paired joint changes;
- \`FactorialCellRun\` and \`analyze_pairwise_interaction\` for repeated 2×2 designs;
- strict artifact/context/observation-model and assignment validation;
- complete-pair/cell checks, pinned input identities, repeated stability checks;
- evidence digests binding full run metadata and observable values;
- numeric difference-in-differences and categorical conditional-effect detection.

The module consumes normalized run records. It does not execute code, infer factor levels, create factorial plans, prove source-to-observation correspondence, statistically model probabilistic outcomes, or estimate higher-order interactions.

## 10. Limitations and open questions

1. Which typed observable algebras should contracts define for non-scalar outputs?
2. How should uncertainty and stochastic outcome distributions be handled?
3. How should factorial blocks handle concurrency and partial-order effects?
4. How should constraints and infeasible combinations be represented?
5. How can higher-order interactions be estimated without exponential full factorial designs?
6. How should simultaneous factor effects be attributed without factorial follow-up?
7. How can the runner ensure pinned external state and side-effect isolation?
8. How should Scenario 22 coverage record completed contrasts rather than generated assignments?

## 11. Preliminary recommendation

Keep joint-intervention analysis and 2×2 factorial interaction analysis as distinct APIs. Do not label a joint effect as an interaction without factorial evidence. Require repeated, context-pinned complete cells and stable observables. Use numeric contrasts only when the contract defines a meaningful numeric scale; otherwise report the limited categorical equality analysis. Keep higher-order exploration budgeted and explicitly incomplete.

## 12. References

- NIST, Kuhn, Kacker, Lei, *Combinatorial Testing* (2012): https://www.nist.gov/publications/combinatorial-testing
- NIST, *Combinatorial Methods for Trust and Assurance — FAQs*: https://csrc.nist.gov/Projects/automated-combinatorial-testing-for-software/faqs
- Penn State, *Factorial Design*: https://online.stat.psu.edu/stat503/lesson/4
- UCLA Statistical Methods and Data Analytics, *Factorial ANOVA*: https://stats.oarc.ucla.edu/other/mult-pkg/whatstat/what-is-the-difference-between-a-one-way-and-a-two-way-anova/
- Hypothesis, *Stateful testing*: https://hypothesis.readthedocs.io/en/latest/stateful.html
