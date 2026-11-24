# RT-07 — Proving a rewrite preserves order and failure

**Date** · 2026-11-21  
**Baseline** · `017e64b87c87371309197a392165258b8b088dd1`  
**Status** · Lean proof for a bounded [Plan §2.4](../../../PLAN.md#24-correctness-of-optimization-and-translation) fragment

## Question

Can a bottom-up optimizer rewrite well-typed expressions while preserving successful results, error codes, and the events that occurred before an error?

The Lean model uses typed integer and Boolean expressions with one integer input, integer addition and equality, lazy conditionals, event emission, and failure. The interpreter evaluates operands from left to right. The first failure skips the continuation and retains its event prefix. A run is the pair of an outcome and an ordered list of events. This is an executable research model. The [typed SPG study](../../semantic-representation/RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md) supplies the motivating order-sensitive observation, and [Scenario 97](../../language-design/RT-04/RESEARCH-SCENARIO-97-CLEANUP-ERROR-COMPOSITION-AND-OWNERSHIP.md) distinguishes richer cleanup and ownership cases outside this model.

## Compared evidence strategies

| Strategy | Evidence and dependency |
|---|---|
| Prove each rule and compose the proof over the typed tree | Covers every model term and integer input, including errors and order. Requires a stable reference model and a structural account of sequencing. The experiment implements this strategy. |
| Validate each transformed artifact | Can accept results from an independent optimizer. Needs a verifier that models effects and failure and binds its judgment to the exact original and transformed artifacts. LLVM-level translation validation can complement this step after source-to-IR correspondence is established. |
| Compare executions against a reference interpreter | Supports fast counterexample discovery and validation at real compiler/runtime boundaries. Coverage is limited to the selected terms and inputs, as in the native backend experiments. |

[Alive2 snapshot](../../references/snapshots/Alive2/README.md) · [Typed source and solver proof boundary](RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md) · [LLVM preservation study](../../compiler-and-translation/RT-13/RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md)

## Checked results

The executable pass folds literal addition, removes a pure integer zero on either side of an addition, and selects the branch of a literal Boolean condition. It descends through other terms while preserving their evaluation forms. The proof `rewrite_preserves` uses the two local fold lemmas and induction over the typed expression. It quantifies over every finite expression in the grammar and every integer input. The preserved equality includes the entire outcome and ordered trace, independently of expression depth or the number of repeated events.

- Swapping two emitting addends gives the same integer result with traces `[1, 2]` and `[2, 1]`. Lean proves the runs differ.
- Replacing a conditional by its identical branches drops the condition. A guard that emits event 1 and fails with code 7 distinguishes the original run from a successful constant result. Lean proves the runs differ.
- Removing zero from an expression whose other operand emits event 1 and fails with code 7 preserves exactly that code and trace.

A language-level rule needs an observation relation before it can inherit this argument. In particular, the mathematical integer model omits machine overflow and the event list omits state, cleanup, calls, concurrency, and resource consumption. The pass has no proof of binding to source programs, a serialized SPG, or compiled artifacts. Lean 4.36.0 checked all three named theorems with its standard `propext`, `Classical.choice`, and `Quot.sound` assumptions. The checks use no solver results or admitted theorems.

The result provides a proof shape for source and graph rewrites with ordered observations. Per-artifact translation validation and backend differential tests remain useful at their own boundaries. RT-03 supplies the observation relation, RT-04 determines which effects and resource states need to appear in it, and RT-09 needs a separate relation through lowering. [Dependency map](../../research-management/RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

From the repository root, use Lean 4.36.0, revision `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Required CI also checks the standalone module. [Proof source](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ObservableRewrite.lean)

```sh
lean -DwarningAsError=true research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ObservableRewrite.lean
```
