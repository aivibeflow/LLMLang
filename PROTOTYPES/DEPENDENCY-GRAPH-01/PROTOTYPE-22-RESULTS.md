# Prototype 22 Results — Coverage-Guided Dependency Discovery

## Implemented

Added src/coverage_guided.py and tests/test_coverage_guided.py.

The prototype provides:
- finite typed-factor domains;
- deterministic generation of single-factor and t-way intervention assignments;
- value and interaction coverage targets;
- numeric minimum/maximum boundary targets for integer-only domains;
- optional value-specific static-analysis/taint guidance targets;
- pinned artifact, context, and observation-model identities in candidate digests;
- deduplication of equivalent assignments while merging their coverage targets;
- deterministic greedy set-cover scheduling under a run budget;
- a coverage ledger for planned targets and normalized runtime feedback;
- explicit reporting of uncovered targets after budget-limited runs.

The scheduler does not execute candidates. An external runner must perform paired baseline/treatment execution, ideally using Scenario 21's evidence model. Scenario 21 currently accepts only one changed factor, so multi-factor candidates cannot yet be evaluated by that API without an extension.

## Test execution

Command:

    python -m unittest discover -s tests -v

Result: **11 tests passed** in the isolated Prototype 22 working directory.

Tests cover single/pairwise planning, deterministic scheduling, runtime feedback collection, no-repeat scheduling, budget-visible gaps, context-sensitive candidate identity, invalid baseline/budget handling, pairwise-vs-higher-order distinction, numeric extrema, static/taint guidance tags, and zero-budget behavior.

A full regression run of the repository's existing test suite was attempted by cloning the repository, but the execution environment could not resolve github.com. Therefore the existing prototype tests were **not** run in this environment. Only the 11 new tests are confirmed passing. Run the full suite in an environment with repository access before treating the integrated prototype as regression-verified.

## Limitations

- No program execution, mutation loop, coverage instrumentation, taint analysis, concolic execution, grammar engine, or Hypothesis integration.
- Finite domains are supplied by the caller; no natural-language or Requirement IR extraction.
- Integer extrema are a minimal boundary heuristic; meaningful thresholds and adjacent values must come from typed requirement metadata.
- The greedy scheduler is a baseline algorithm, not an optimal covering-array generator or information-gain optimizer.
- Runtime feedback is recorded; only feedback dimensions declared as candidate guidance can influence prioritization in later batches.
- No statistical confidence model or nondeterminism handling.
- Higher-order candidates are planned, but Scenario 21's current comparison interface is single-factor only.
- Coverage does not prove dependency completeness or irrelevance.
