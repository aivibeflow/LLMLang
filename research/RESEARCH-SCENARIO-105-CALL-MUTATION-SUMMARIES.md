# Research Scenario 105 — Call Mutation Summaries and Path Feasibility

**Status:** exhaustive finite transition comparison; no effect or call rule selected
**Research areas:** RT-03 state/calls; RT-04 effects and aliasing; RT-06 path/dependency analysis
**Updated:** 2026-11-19

## 1. Question

How must a path analyzer update a symbolic value across a call when the callee may preserve, mutate, or alias the caller's state? What is the sound behavior when the effect/call summary is incomplete?

## 2. Fixture

The finite fixture evaluates `if x`, invokes a call that may affect `x`, and then evaluates `if x` again. The domain is one Boolean value before and after the call, with four possible state pairs. Executable alternatives are in [`rt03_call_mutation_summaries.py`](PROTOTYPES/RT-04-01/rt03_call_mutation_summaries.py) and its focused tests.

| Summary | Allowed state transition | Feasible routes | Consequence |
|---|---|---|---|
| Complete pure | `x1 = x0` | `FF`, `TT` | A stable value may be reused when purity and alias boundaries are complete evidence. |
| Complete toggle | `x1 = ¬x0` | `FT`, `TF` | Explicit state transition preserves the exact caller-visible result. |
| May-write / unknown | `x1 ∈ {false,true}` independent of `x0` | `FF`, `FT`, `TF`, `TT` | Conservative havoc retains every possible post-call branch. |
| Name-conflated | Reuse one `x` for both reads, regardless of call effects | `FF`, `TT` | Unsound for a mutating/may-alias callee; it prunes `FT` and `TF`. |

The four state pairs are enumerated exhaustively. The five focused tests pass. These are input summaries to the path model; they do not prove source-level effect discovery or alias analysis.

## 3. Findings

1. A call boundary is a state-version boundary whenever the callee may write reachable caller state. The path formula must encode its state transition, not only its result value.
2. A complete pure summary permits reuse only for the state locations it proves unchanged and only under a complete alias/call graph.
3. A complete mutating summary should express the relevant relation (the toggle fixture demonstrates one exact relation). A may-write or incomplete summary should conservatively havoc the affected value and retain all possible paths.
4. A call's unknown effect summary cannot be treated as a pure function summary without risking false path pruning and missing dependencies.

This study links RT-03 value semantics with RT-04 effects/aliasing and RT-06 dependency completeness. It does not select pure functions, references, ownership, effect annotations, interprocedural analysis, or a language profile.

## 4. Limits and next discriminators

The fixture contains one Boolean location and one call with a hand-supplied transition summary. It does not derive summaries from source, model object graphs, partial alias sets, multiple writes, exceptions/cancellation, recursion, dynamic dispatch, concurrency, or formula solving. A summary saying "may write" is represented as unconstrained Boolean havoc, which is sound but may be imprecise.

Next compare field-sensitive versus whole-object havoc, points-to/alias uncertainty, call-graph incompleteness and dynamic dispatch, writes before call failure/cancellation, and transitive effect summaries. Bind each summary to the immutable source and call-target versions from which it was derived; missing or stale summary provenance must preserve UNKNOWN.

## 5. Reproduction

From `research/PROTOTYPES/RT-04-01`:

```sh
python -m unittest -v test_rt03_call_mutation_summaries.py
python rt03_call_mutation_summaries.py
```
