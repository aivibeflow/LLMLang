# Research Scenario 55 — Loop Results, Labels, and Control Transfer

**Status:** Evidence-linked prior-art comparison; no LLMLang loop/control-transfer model selected  
**Research area:** RT-03 control flow and evaluation, RT-04 ownership/cleanup, RT-09 translation  
**Updated:** 2026-11-19

## 1. Question and scope

How should loops repeat, terminate, transfer control across nesting, and produce a result? Treat these dimensions separately:

1. Loop forms: condition, iterator/range, and infinite loop.
2. `break` target and optional label.
3. `continue` target and whether it may skip intermediate loops.
4. Break result/value and type join across exits.
5. Whether loop syntax is a statement or expression.
6. Labels' scope, shadowing, and permitted targets.
7. Cleanup and ownership effects on each exit path.
8. Divergence and proof/termination interpretation.

This report compares Rust, Go, and Swift references. It does not select a preferred loop surface or conflate loop values with exhaustiveness of `match`.

## 2. Prior-art comparison

### Rust: multiple loop expressions, labeled exits, selected value-producing forms

Rust supports `loop`, `while`, and iterator-based `for` expressions, as well as labeled block expressions. All loop forms support labeled `break`; loop forms support labeled `continue`. A plain `loop` and a labeled block can produce a value through `break expr`, and the type is the least upper bound of break operands. `while` and `for` do not produce a non-unit break value. Labels identify which enclosing loop is affected, and label scope is specified lexically.

This gives a direct expression form for search/retry/state-machine loops while retaining statement-like unit behavior for condition/range loops. It introduces path-sensitive result typing and needs clear rules for exits that carry different values, diverge, or transfer owned resources.

Source: [Rust Reference — Loop expressions](https://doc.rust-lang.org/reference/expressions/loop-expr.html), [Rust Reference — Label scopes](https://doc.rust-lang.org/reference/names/scopes.html#loop-label-scope).

### Go: one `for` construct, labeled statements, no loop result

Go uses a generalized `for` statement for infinite loops, condition loops, three-clause loops, and range iteration. `break` may target an enclosing `for`, `switch`, or `select`; `continue` may target an enclosing `for`. Labels identify targets and are function-scoped; they do not turn the loop into an expression or carry a value. A result is communicated through assignment, return, or a surrounding variable.

The single loop construct reduces surface forms and makes result flow explicit in statements. The trade-off is more scaffolding for search-like constructs that naturally yield a found value, and labeled control transfer remains a nonlocal jump that tools must explain.

Source: [Go specification — For statements and branch statements](https://go.dev/ref/spec#For_statements), [Go specification — Labeled statements](https://go.dev/ref/spec#Labeled_statements).

### Swift: condition/collection loops and labeled statement exits

Swift provides condition-based and collection-based loops as statements. `break` and `continue` may use a statement label to target a particular enclosing loop; `break` can also terminate a labeled conditional statement. Loop constructs do not yield a result value, so callers assign or return through explicit state/control flow.

Labels make nested control transfer explicit, including targeting an outer loop. Keeping loops statement-oriented avoids loop-result type joins; the cost is explicit result variables or helper functions for early-exit searches.

Source: [Swift Language Guide — Control Flow and Labeled Statements](https://docs.swift.org/latest/documentation/the-swift-programming-language/controlflow/).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift |
|---|---|---|---|
| Surface loop forms | `loop`, `while`, iterator `for`, labeled block | Generalized `for` with condition/clause/range | `while`, `repeat-while`, `for-in` |
| Loop is expression | Yes | No | No |
| Break labels | Yes | Yes; target restrictions include for/switch/select | Yes; target loop or conditional statement |
| Continue labels | Yes | Yes; target must be enclosing loop | Yes; target labeled loop |
| Break carries value | Only `loop` and labeled block | No | No |
| Label scope | Lexical extent of loop expression | Function body | Labeled statement/control structure |
| Result typing | Join of `break` operands for result-producing forms | Explicit assignments/returns | Explicit assignments/returns |
| Main risk | Exit-value joins and ownership paths | Boilerplate for value-producing search | Boilerplate for value-producing search |

## 4. Discriminating fixtures

1. Search a collection and return the first matching value, with no result, and with multiple typed exits.
2. Nest loops and test unlabeled versus labeled `break`/`continue`, including a label naming a non-loop statement if the language permits it.
3. Test condition, iterator, and infinite loops with normal completion, labeled exit, return, error/throw, cancellation, and divergence.
4. Give separate `break` arms values of equal type, subtype/coercible types, incompatible types, and owned-resource types.
5. Capture values/borrows in loop exits and verify that all discarded paths run cleanup once and preserve the winning returned value.
6. Test label shadowing, duplicate labels, out-of-scope labels, transfers from closures/functions/macros, and diagnostics that show the target.
7. Compare lowering and semantic graph for a result-producing loop versus an explicit mutable accumulator plus `break`.
8. Test `continue` behavior in three-clause loops (whether post/step clauses execute), iterator loops, and nested labeled loops.
9. Use bounded model checking or trace enumeration to verify that each branch reaches the correct target and that every exit path has the same declared result contract.

Record CFG targets, loop result type, value ownership, cleanup order, observable trace, and finite/divergent classification.

## 5. Cross-area implications and open hypotheses

- A `break` label system addresses which construct receives control; it does not determine whether a loop yields a value. These should remain independent option dimensions.
- Value-producing loops can encode search and retry without sentinel state, but increase type/ownership joins across exits. A dedicated `Option`/result return helper may make outcomes more explicit.
- Statement-only loops simplify CFG result typing, but developers and code generators must manage initialized accumulators and prove assignment before use.
- Labels can improve nested-loop clarity, but their target set matters: allowing `break` from switch/select/conditional constructs increases expressiveness and the surface for nonlocal control.
- Loop exits interact with defer/drop/cleanup, cancellation, and effect handlers. Each transfer kind must specify which scopes unwind, in what order, and how cleanup failure composes with a break value.
- Loop expressions are not automatically termination proofs. A loop may diverge; static analysis should represent the divergent path distinctly from missing result or unit.
- Semantic dependency graphs should capture the exact target label and loop result edges so a refactor that moves a label or changes a break value invalidates relevant consumers.

No LLMLang loop form, labeled-target rule, break-result rule, or loop cleanup policy is selected.

## 6. Next research and falsifiers

Implement a small CFG and typing prototype for (A) statement-only loops with labeled transfers and (B) Rust-like `loop` result expressions plus shared labels. Add a resource-owning iterator and injected cleanup failure to compare exit typing. Measure generated-code scaffolding, missing initialization errors, diagnostic target clarity, type/ownership inference complexity, and optimizer preservation.

Loop expressions are weakened if value joins produce frequent surprising type errors or obscure exits. Statement-only loops are weakened if searched/control-flow tasks become boilerplate-heavy and static analysis cannot establish accumulator initialization. Labels are weakened if blind readers frequently misidentify targets; nested unlabeled-only control is weakened if realistic algorithms require flags or helper extraction.

## 7. Sources and temporal limits

Official references were consulted 2026-11-19. Rust and Swift references are rolling; Go's specification is versioned. Pin toolchains and test control-flow/cleanup traces before treating compiler behavior as normative.
