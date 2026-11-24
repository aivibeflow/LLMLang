# RT-09 — Ordered instructions from a typed SPG

**Date** · 2026-11-21  
**Baseline** · `b52ba2fb32e2c315997c74d8924c2c9aaeb177dc`  
**Status** · Bounded executable experiment for [Plan §6.1](../../../PLAN.md#61-translation-architecture)

## Question and alternatives

What must survive an intermediate lowering stage between a semantic graph and its execution target? This study uses the existing typed SPG fixture's Int/Bool operations, ordered events, lazy conditionals, and exact or operation-bound calls. The comparison evaluates the same compiled graph directly and through a normalized instruction representation. [Typed SPG](../../semantic-representation/RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) · [Translation architecture](../RT-13/TRANSLATION-AND-TARGET-BACKENDS.md#4-intermediate-representation-and-backend-architecture)

| Approach | Trade-off |
|---|---|
| Interpret or translate directly from typed SPG bodies | Reads the semantic source with fewer intermediate artifacts. Each target must implement evaluation order, branch selection, and dispatch resolution consistently. The existing interpreter supplies a baseline. |
| Normalize to an ordered register instruction stream | Makes effects, branches, argument evaluation and resolved calls visible to an executor. Introduces an instruction schema, a new validation boundary and a separate artifact identity. |
| Share a control-flow IR with explicit types and effects | Can supply stronger invariants and more targets. Needs rules for joins, dynamic binding, ownership, failures and resource cleanup before those cases qualify for translation. |

## Model and observations

Lowering starts with one selected implementation and follows its reachable calls. It materializes the selected implementation for each operation call from the graph's binding table. The artifact records the entry implementation address and the reachable functions keyed by exact value address. It contains register assignments, ordered events, forward jumps, calls and returns. Both paths use mathematical integers and count fuel at function entry. The artifact identity covers the ordered instructions and exact reachable function entries under a versioned domain.

| Control | Observation |
|---|---|
| Two arithmetic forms, two call modes, five constants and seven inputs | All 140 cases match an arithmetic and ordered-event oracle in both the source interpreter and the instruction executor. The unselected branch emits no events. |
| Change only a provider binding | The operation caller's SPG address stays equal. The lowered artifact changes, and its result moves from 5 to 6. The exact caller and unrelated entry keep their artifacts. |
| Edit a body outside the reachable closure | The selected artifact remains identical. Compiling the same graph twice also produces identical artifacts. |
| Binding-resolved recursion and fuel | Both paths return three ordered events when five calls fit and report exhaustion at four. |
| Exact recursive group | The lowerer reports an unsupported representation for this profile. |
| Mutate the instruction event order | The result remains 5. The trace changes from left/right to right/left, and the oracle detects the discrepancy. |

The key decision boundary is where operation binding becomes fixed. Early binding makes the required inputs visible in an artifact generated for one context. Runtime dispatch can preserve broader reuse if all executable contexts bind an explicit provider set and arrange appropriate validation. A global snapshot digest is conservative but can invalidate a byte-identical reachable artifact on an unrelated edit.

This experiment executes two Python realizations. It supplies evidence for an IR boundary and reachability-sensitive identity. It leaves external target code generation, IR admission for independently produced instructions, recursive group encoding, heterogeneous effects, machine arithmetic and general preservation open. RT-03 supplies the observations, RT-05 and RT-06 constrain graph identity and closure, and RT-13 must compare actual target artifacts. [Dependency map](../../RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

Run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` with CPython 3.12.14. All 16 tests passed. [Lowering and executor](../../PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_ordered_lowering.py) · [Fixtures](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_spg_ordered_lowering.py)

```sh
python -B -m unittest -v tests.test_spg_ordered_lowering tests.test_spg_representation
```

### Exact retained reproduction (2026-11-21)

The declared command was rerun on exact checkout `8d2c085f31685457a66669a6d4db604ab7b1c80a` with CPython 3.12.14: **16/16 tests passed**. See [workflow run #44948779526](https://github.com/aivibeflow/LLMLang/actions/runs/44948779526) and retained [artifact 14724810775](https://github.com/aivibeflow/LLMLang/actions/runs/44948779526/artifacts/14724810775). The run records source SHA-256 values and log digest `9c9540d147cdf48c9d2bf563b36dbe8bac232d4d5cc96c6498b5e59fd8e4e1e0`. This validates the bounded Python lowering experiment only; it does not validate LLVM or machine-code generation.
