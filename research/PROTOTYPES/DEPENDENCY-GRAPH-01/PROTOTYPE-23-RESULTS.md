# Prototype 23 Results — Multi-Factor Counterfactual Analysis

## Implemented

Added \`src/multifactor_analysis.py\` and \`tests/test_multifactor_analysis.py\`.

Two separate analyses are implemented:

1. **Joint intervention:** repeated paired comparison of a pinned baseline and a treatment changing one or more factors. Detects observable influence, trace-only change, no observed difference, or inconclusive evidence.
2. **Pairwise factorial interaction:** repeated complete 2×2 blocks for two factors under a pinned context. Checks all four simple effects and detects conditional interactions.

Numeric scalar outcomes use decimal difference-in-differences. Categorical/structured JSON outcomes use conditional equality patterns. The categorical method is limited and can miss interactions; the behavioral contract must eventually define the observable algebra.

## Test execution

Focused command:

\`\`\`bash
python -m unittest discover -s tests -p 'test_multifactor_analysis.py' -v
\`\`\`

Result: **18 tests passed** in the isolated prototype directory.

Tests cover joint effects, no observed difference, trace-only changes, incomplete pairs, context mismatch, duplicate sides, hidden conditional interaction, additive numeric effects, numeric interaction with main effects, categorical conditional effects, categorical ambiguity handling, missing factorial cells, context drift, unstable cell outcomes, duplicate cells, evidence-digest sensitivity, and assignment validation.

The complete existing prototype regression suite was not run in this environment. The focused result is not a full-suite pass.

## Limitations

- Consumes normalized execution records; does not execute programs.
- Joint intervention cannot attribute the effect to individual factors.
- Factorial interaction implementation is 2×2 only.
- Categorical equality patterns detect conditional presence/absence only; if unequal outcomes provide no comparable scale, the result is INCONCLUSIVE rather than a negative claim.
- Numeric difference-in-differences is meaningful only if the contract defines a meaningful numeric observable scale.
- No stochastic/statistical inference, higher-order factorial estimator, constraint solver, or source-code proof.
- No automatic integration with Scenario 22's scheduler yet.
