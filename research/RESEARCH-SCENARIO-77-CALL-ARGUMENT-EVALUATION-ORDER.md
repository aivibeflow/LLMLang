# Research Scenario 77 — Call Argument Evaluation Order

**Status:** Evidence-linked prior-art comparison; no LLMLang call order selected
**Research area:** RT-03 expression semantics, effects, determinism, optimizer legality
**Updated:** 2026-11-19

## 1. Question and scope

When a call target and multiple arguments have effects, which evaluations happen first, which may be reordered, and what happens when an earlier evaluation fails or diverges? The question is narrower than general expression semantics and complements Scenario 59 (Boolean operators), Scenario 56 (closure capture/callability), and RT-03's trace model.

This is a specification comparison, not a cross-compiler runtime experiment. It distinguishes source-mandated sequencing from implementation freedom and does not conflate unspecified order with undefined behavior.

## 2. Prior-art comparison

### Rust: recursive left-to-right operand evaluation

The Reference says the operands of listed expression kinds—including calls, method calls, operators, tuples, indexes, and `await`—are evaluated before the containing expression's effects; multiple operands are evaluated left-to-right as written. The rule recurses into nested expressions, so inner expressions finish before their containing operation, while sibling subexpressions follow source order. This is broad and gives a straightforward trace for side-effecting call arguments. The specification separates the operand sequence from what the enclosing operation then does.

Source: [Rust Reference — Evaluation order of operands](https://doc.rust-lang.org/reference/expressions.html#evaluation-order-of-operands).

### Go: order key events, leave some operand ordering open

The specification orders function calls, method calls, receives, and binary logical operations lexically left-to-right while evaluating operands of expressions, assignments, and returns. Other operations such as reading/indexing ordinary variables may be unordered relative to those events when no lexical constraint applies. Its examples permit distinct results for a composite literal that reads a variable and calls a mutating function in the same expression. Thus Go offers a narrower event-order guarantee than a blanket left-to-right rule; expression shape and which events are explicitly ordered matter.

Source: [Go specification — Order of evaluation](https://go.dev/ref/spec#Order_of_evaluation).

### Java: left-to-right operands and arguments, abrupt completion stops later work

Java specifies left-to-right operator operands and call arguments. An argument that completes abruptly prevents evaluation of arguments to its right, and a receiver expression is evaluated before arguments in an instance method call. The JLS additionally constrains optimizations that would change values or observable side effects. This provides a clear sequencing baseline, but the JLS advises against making expressions depend on many side effects, because readability and exception selection suffer.

Source: [Java Language Specification §15.7 — Evaluation Order](https://docs.oracle.com/javase/specs/jls/se25/html/jls-15.html#jls-15.7).

### C++: function designator/arguments before body, parameter initializations indeterminately sequenced

The current working draft requires every argument expression and the postfix expression naming the function to be sequenced before precondition assertions and the function body. Parameter initializations are indeterminately sequenced with respect to one another: one completes before another, but the implementation chooses which first. This allows predictable non-interleaving without promising lexical order. The source at eel.is is a live working draft and therefore needs a pinned standard edition for any conformance experiment.

Source: [C++ working draft — Function call](https://eel.is/c++draft/expr.call).

## 3. Comparison matrix

| Question | Rust | Go | Java | C++ current draft |
|---|---|---|---|---|
| Call arguments | Left-to-right by general operand rule | Calls ordered relative to other calls/receives/logical operators; not all ordinary operand work is ordered | Left-to-right | Each completes before body; parameter initialization order unspecified between parameters |
| Function/member target | Operand sequencing rule applies recursively | Function calls ordered; broader operands may remain unspecified | Instance receiver before arguments | Postfix expression and arguments before body; relative sequencing with arguments is a separate rule |
| Failure in an earlier argument | Later operands are not reached under sequential evaluation | An earlier call's failure/panic aborts that call path, but order of some non-call reads remains open | Later arguments not evaluated after abrupt completion | An argument's own control flow applies; parameter order can vary before body |
| Optimization boundary | Must preserve specified sequencing/observable effects | Must respect specified ordering; open relations allow more schedules | Explicit value and observable-effect equivalence limits rewrites | May choose among permitted parameter orders; individual evaluations are sequenced |
| Main trade-off | Strong predictability; less freedom to reorder effectful operands | Narrow guarantee leaves some compact expressions ambiguous across runs/compilers | Predictability and simple tracing; side-effect-heavy expressions can be hard to read | More implementation freedom with no interleaving; caller cannot infer lexical parameter order |

## 4. Discriminating fixtures for LLMLang research

Use a trace-producing `mark(label, value)` and a shared state cell to compare:

1. `call(mark("a", 1), mark("b", 2))`: argument order and observed trace.
2. `factory().method(mark("arg", 1))`: receiver creation versus argument effects and receiver failure.
3. `call(fail(), mark("later", 2))`: whether the later argument runs after recoverable error, panic, or divergence.
4. `call(read(cell), mutate(cell))`: whether reads count as observable events and whether a result is portable.
5. Nested calls such as `outer(inner(a(), b()), c())`: recursive sequencing and inner-call failure.
6. A call returning multiple values and immediately passed to another call: which callee/argument effects precede the outer body.
7. Default arguments, implicit conversions, overloaded operators, and contract preconditions: when their effects enter the sequence.
8. Async calls and task creation: argument evaluation completion versus task body start, suspension, and scheduling (coordinate with Scenarios 58/59).

For each fixture record result, ordered effect trace, error identity, state, resources acquired/released, divergence, and whether the behavior is source-mandated or one permitted outcome. Include a no-effect case to check whether an optimizer may reorder freely when equivalence is established.

## 5. Consequences and unresolved LLMLang vectors

- **Strict source order** makes deterministic replay, effect traces, and proof rules simpler, but constrains instruction scheduling when effect order is observable. It does not imply serial execution of explicitly parallel tasks.
- **Selective ordering** can preserve source order only for effectful/communication events and leave pure operand computations free, but requires a sound effect classification and careful rules for reads, traps, allocation, and divergence.
- **Unspecified-but-sequenced order** can allow compiler freedom while forbidding interleaving, but makes results non-portable whenever arguments conflict through state or resources.
- **Undefined/conflicting-effect boundary** could reject or make erroneous conflicting unsequenced effects, yet would require diagnostics and a precise notion of conflict; it must not be described as ordinary nondeterminism.
- Any chosen rule must define target expression evaluation, argument evaluation, conversions/defaults, pre/postconditions, call-body entry, error propagation, and async task-body start as separate sequencing edges.
- Scenario 59's short-circuit operators are a distinct conditional-evaluation rule; these results do not settle their Boolean semantics.

No LLMLang call evaluation order, conflict rule, or optimizer permission is selected. A next discriminator is an executable common trace corpus over representative compilers plus a formal small-step rule that captures effects and abrupt outcomes. Ensure the corpus tests permitted outcome sets, rather than assuming each implementation happens to choose a stable order.

## 6. Evidence quality and limits

The comparison uses official specifications/References, opened 2026-11-19. Rust and C++ draft sources are rolling; Go's specification is versioned by the selected language release; Java's cited JLS is SE 25. No compiler versions were run and no optimizer behavior was measured. The C++ source is explicitly a working draft, not a substitute for pinning the edition used in future experiments.
