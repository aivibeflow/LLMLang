# Research Scenario 107 — Source-Derived Call Aliases

**Status:** Bounded AST-adapter experiment; no LLMLang alias or mutation rule selected
**Research areas:** RT-03 path feasibility, RT-04 aliasing/effects, RT-06 dependency completeness, RT-07 evidence boundary
**Updated:** 2026-11-20

## 1. Question

Scenarios 104–106 showed that path feasibility becomes unsound when mutable predicate versions are conflated, call mutation summaries are assumed pure without evidence, or a possible call-site alias is omitted. Those scenarios supplied transition summaries and target sets by hand. This experiment asks whether a small source adapter can derive a mutator summary and call-site may-alias set, then retain every route observed by exhaustive execution of the same bounded program.

The fixture source uses a tiny Python-shaped subset parsed with Python's `ast` module. Python syntax is only a convenient concrete input format. This is not a Python implementation, LLMLang grammar, or general static analyzer.

## 2. Fixture and method

The accepted mutator is exactly:

```python
def flip(ref):
    ref.value = not ref.value
```

Caller fixtures create a reference with `ref(flag)` or `ref(other)`, optionally reassign it in a conditional branch, then call `flip(target)`. The runtime fixture interpreter enumerates the initial values of `flag` and `other`, the branch selector, and the chosen target of `unknown_ref()` over the declared two-field region. The AST analyzer recognizes the function's direct toggle write, propagates reference target sets through assignments, joins branch targets, and maps the call targets into Scenario 106's state-transition relation.

The evaluator and analyzer use the same parsed AST grammar and share the hand-authored bounded semantic contract. This checks source-to-summary behavior inside the fixture subset; it does not independently validate parsing or establish source-to-CFG completeness.

## 3. Results

Eight focused tests produced these outcomes:

| Source case | Extracted call targets | Concrete versus analyzed routes |
|---|---|---|
| `target = ref(flag)` | `{flag}` | Exact match: the predicate field toggles. |
| `target = ref(other)` | `{other}` | Exact match: `flag` remains unchanged. |
| `target` can be assigned either reference under an independent `choose` branch | `{flag, other}` | Exact match; all four initial/final `flag` pairs are reachable. |
| `target = unknown_ref()` with runtime choices limited to the two modeled fields | `{flag, other}` | Exact match to exhaustive execution over both possible targets. |
| Alias target is correlated with the initial value of `flag` | `{flag, other}` | Sound but imprecise: analysis has four pairs; concrete execution has only `(False, True)` and `(True, True)`. The non-relational join loses the value/alias correlation. |
| One possible target is incorrectly omitted | Not applicable | The restricted transition relation drops concrete routes, reproducing Scenario 106's unsound no-alias assumption. |
| Mutator body or target field falls outside the recognized subset | Not applicable | The analyzer rejects the fixture rather than claiming a summary. |

For these cases the derived target set is sufficient to avoid under-approximating the route set. A may-points-to union can still invent routes when alias choice correlates with state; a relational or path-sensitive analysis could recover precision, at additional cost.

## 4. Evidence boundary and open work

The result covers two Boolean fields, one direct reference parameter, one toggle write, branch assignment and join, one call, and a finite exhaustive input region. It does not cover nested/heap references, pointer arithmetic, escape or lifetime, multiple parameters, aliases through aggregates, dynamic dispatch, unknown call graphs, loops/recursion, concurrency, source diagnostics, or ownership/type checking. The analyzer does not authenticate its source snapshot or effect summary. `unknown_ref()` means the complete top set only within the fixture's explicitly declared region.

Next discriminators should add multiple reference parameters and fields, copy/aggregate aliases, branch-sensitive relational targets, read/write and may-write summaries, nested calls, loop fixed points, escaping references, and a separately implemented source parser/CFG extractor. Differential source-to-route tests must establish which constructs were included before solver UNSAT can remove a may-dependency. No LLMLang points-to algorithm, aliasing policy, or path-pruning rule is selected.

## 5. Reproduction

From the repository root:

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt03_source_alias_extraction.py' -v
```

Prototype: [`rt03_source_alias_extraction.py`](../../PROTOTYPES/RT-04-01/rt03_source_alias_extraction.py). Tests: [`test_rt03_source_alias_extraction.py`](../../PROTOTYPES/RT-04-01/test_rt03_source_alias_extraction.py). The related hand-supplied relation is documented in [Scenario 106](RESEARCH-SCENARIO-106-CALL-ALIAS-SETS-AND-FIELD-SENSITIVE-PATHS.md).
