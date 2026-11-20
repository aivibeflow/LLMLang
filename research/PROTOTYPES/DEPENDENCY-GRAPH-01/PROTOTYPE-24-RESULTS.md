# Prototype 24 Results — Adaptive Interaction Discovery

## Implemented

Added src/adaptive_discovery.py and tests/test_adaptive_discovery.py.

The scheduler:
- starts with repeated single-factor interventions;
- only opens pairwise factorial exploration after single-factor candidates have recorded results;
- builds complete 2×2 blocks for every unordered pair of factor levels, including non-baseline level pairs;
- defaults to two repetitions per cell;
- measures budget in actual execution runs (2^k × repetitions);
- escalates to higher-order full factorial blocks only after OBSERVED_INTERACTION;
- does not confuse joint behavioral influence with interaction;
- retries inconclusive blocks a bounded number of times;
- prioritizes related/high-signal scopes while preserving an exploration reserve;
- rejects evidence from a different pinned artifact/context/observation model/baseline;
- separates executed experiment targets from observed runtime feedback.

The scheduler accepts Scenario 23 status enums through their string values. It creates higher-order blocks but does not implement a generalized higher-order contrast analyzer.

## Test execution

Command:

    python -m unittest discover -s tests -v

Result: **21 Scenario 24 tests passed** in the isolated prototype working directory.

The Scenario 22 coverage-guided regression tests were also run alongside the new tests: **32 tests passed** across Scenario 22 and Scenario 24.

Coverage includes:
- single-factor-first staging;
- execution-budget accounting and atomic blocks;
- pairwise block generation;
- non-baseline level-pair coverage;
- related-pair and single-signal prioritization;
- evidence-triggered three-factor escalation;
- no escalation from NO_INTERACTION_OBSERVED;
- no false escalation from joint OBSERVED_BEHAVIORAL_INFLUENCE;
- bounded retries;
- exploration reserve and small-budget behavior;
- exact pinned-context checks;
- status compatibility with Scenario 23;
- separate executed and observed coverage.

The full repository regression suite was not run. The 21 focused tests and 32-test Scenario 22 + 24 subset are the tests confirmed passing for this step.

## Limitations

- The planner does not execute programs.
- It does not implement a generalized higher-order interaction analyzer.
- It does not solve Requirement IR constraints or filter infeasible cells.
- It does not statistically model nondeterminism.
- It uses a deterministic heuristic, not a learned expected-information-gain model.
- It does not prove dependency completeness.
