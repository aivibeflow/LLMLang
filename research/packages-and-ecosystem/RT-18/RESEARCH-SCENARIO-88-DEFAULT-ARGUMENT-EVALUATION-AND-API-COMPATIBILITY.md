# Research Scenario 88 — Default Argument Evaluation and API Compatibility

**Status:** Evidence-linked prior-art comparison; no default-argument policy selected
**Research area:** RT-03 call semantics, RT-04 effects, RT-05 interface identity, RT-18 compatibility
**Updated:** 2026-11-19

## 1. Question and relation to prior work

When a caller omits an argument, when is its default expression evaluated, in which source environment are names and call-site metadata resolved, and which version of the declaration controls the value?

[Scenario 84](../../language-design/RT-31/RESEARCH-SCENARIO-84-FUNCTION-SIGNATURE-AND-CALL-SURFACE.md) compares parameter names/labels, defaults, returns, variadics, and receivers. [Scenario 77](../../language-design/RT-03/RESEARCH-SCENARIO-77-CALL-ARGUMENT-EVALUATION-ORDER.md) studies expression and argument sequencing. This scenario isolates defaults as implicit call operands: it examines evaluation epoch, lexical/source provenance, side effects, and compatibility. It does not choose whether LLMLang has optional parameters, named arguments, or overloads.

## 2. Prior-art comparison

### Swift: evaluate the expression when the function is called

The Swift language reference says an omitted argument uses its default expression, evaluated when the function is called. The expression need not be a compile-time constant. Swift's macro rules add a useful distinction: a macro used as the entire default value can use the call-site source location, while a macro inside a larger default expression is evaluated using the location where that expression is declared. Runtime evaluation time, macro expansion time, and source-location provenance therefore need separate fixture fields.

Source: [Swift Language Reference — Declarations](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/), [Swift Language Reference — Expressions](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/).

### Kotlin: evaluate only omitted defaults, after explicit arguments

Kotlin specifies that explicit arguments evaluate in their textual call order. Any omitted defaults are then evaluated in parameter declaration order, and only after that is the function invoked. A used default expression is reevaluated for every call that omits that argument; an explicitly supplied value suppresses that default expression. Named-argument order can therefore differ from parameter declaration order without changing the order of explicit expression evaluation.

Source: [Kotlin Language Specification — Function calls](https://kotlinlang.org/spec/expressions.html).

### Python: evaluate once when the definition executes

Python evaluates default parameter expressions from left to right when the function definition executes. The resulting precomputed values are reused by later calls. For mutable defaults, multiple calls can therefore observe the same object unless the function uses an explicit sentinel/factory pattern. This is a different semantic contract from per-call recomputation, even though both forms visually place an expression in a parameter declaration.

Source: [Python Language Reference — Function definitions](https://docs.python.org/3/reference/compound_stmts.html#function-definitions).

### C++: call-point use, declaration-point lookup, static selection for virtual defaults

The C++ working draft specifies defaults for missing trailing arguments, with available defaults assembled from reachable declarations in the relevant scope. Names in a default expression are looked up and checked where the default appears, while its expression participates in a call when needed. For a virtual call, the default comes from the declaration selected by the static type of the pointer/reference; dynamic dispatch can then invoke an overriding body that does not inherit the base declaration's default. This separates expression evaluation, name binding, and implementation dispatch.

Sources: [C++ working draft — Default arguments](https://eel.is/c%2B%2Bdraft/dcl.fct.default), [C++ working draft — Declarations](https://eel.is/c%2B%2Bdraft/dcl.decl).

## 3. Independent semantic axes

Default arguments should not be described with one vague label such as “call-site expansion.” At least four questions are independent:

| Axis | Alternatives to compare |
|---|---|
| Evaluation epoch | Definition execution once; every call that omits the parameter; compile-time constant; explicit thunk evaluated by the callee. |
| Evaluation order | Interleaved with explicit arguments in call order; explicit arguments first then defaults in parameter order; another specified sequence. |
| Name/source environment | Declaration environment; caller environment; explicit call-site source metadata; a deliberately restricted constant environment. |
| Dispatch/version source | Statically selected declaration; dynamically selected implementation; client-compiled default; callee-provided current default. |

The cited languages demonstrate that these axes can differ. Python contrasts definition-time value capture with repeated computation; Kotlin explicitly orders supplied and omitted expressions; Swift distinguishes call-time evaluation from macro source location; C++ separates declaration-time lookup and static default selection from virtual body dispatch. These observations motivate the axes; they do not establish a preferred LLMLang profile.

## 4. Consequences for semantics and API evolution

A default expression is an implicit operand whose effects may occur even though the caller wrote no expression. If it reads mutable state, allocates, throws, diverges, accesses a capability, or starts asynchronous work, its evaluation epoch and ordering are observable and must participate in Scenario 77's trace model. If it constructs a mutable value, definition-time reuse and per-call construction have different aliasing behavior.

Default changes can also affect clients differently depending on whether omission is resolved from declaration text available to a client, supplied by a callee at runtime, or materialized as a value/factory. This is an inference from the prior-art mechanisms, not a binary-compatibility result measured here. Before an API policy is selected, test source recompilation and already-compiled callers separately; record the compiler/language version and the declaration visible to each caller.

Defaults also interact with overload resolution and named labels. Adding a default can make a previously invalid call applicable or make a call ambiguous. Renaming a label can break callers even if the value and implementation are unchanged. Those are signature/API-evolution questions (Scenario 84); do not attribute every such break to evaluation timing.

## 5. Proposed discriminator cases

These are experiment designs, not executed results:

1. **Per-call marker:** a default invokes a counter-producing function; call twice with omission and once explicitly. Record count, returned values, and trace order.
2. **Mutable value:** a default constructs a mutable collection; mutate the first result and inspect the next call to distinguish reused from fresh state.
3. **Argument ordering:** explicit arguments and multiple defaults append labels to a trace; include positional and named calls where supported.
4. **Failure boundary:** a default expression fails or diverges; record whether later explicit/default expressions run and whether the function body begins.
5. **Context access:** default reads a changing local/global, capability, clock, or source-location macro; record lookup binding and observed value/location independently.
6. **Virtual dispatch:** invoke an override through base and derived static types with an omitted parameter; record both chosen default and invoked body.
7. **Evolution:** change a default after a client is compiled; compare recompiled and unrecompiled callers, and separately compare a value default with a thunk/factory.
8. **Overload interaction:** add a defaulted parameter or overload; preserve the call set and classify new ambiguity or changed resolution.
9. **Async/effect boundary:** use a default that can suspend or perform an effect, if the candidate language permits it; test effect checking, order, and whether omission hides a suspension point.

For every case, record explicit-argument order, omitted-parameter set, default evaluation order, environment/version, trace, terminal outcome, and whether the callee body was entered. Run API compatibility cases against both source and binary consumers.

## 6. Open questions and scope limits

Open choices include whether defaults may contain arbitrary effectful expressions, whether the language restricts them to pure/constant computations, whether asynchronous defaults are legal, how defaults interact with named-argument reordering, and whether call sites or callees supply omitted values. API evolution must state whether changing a default is source-compatible, behavior-compatible, and binary-compatible for each deployment model.

No LLMLang default evaluation policy, call-site lowering, effect rule, or compatibility promise is selected. No compiler or runtime experiment has been run. The comparison uses language references current on 2026-11-19; pin compiler/spec versions before turning the proposed cases into conformance requirements.

## 7. References

- [Swift Language Reference — Declarations](https://docs.swift.org/latest/documentation/the-swift-programming-language/declarations/)
- [Swift Language Reference — Expressions](https://docs.swift.org/latest/documentation/the-swift-programming-language/expressions/)
- [Kotlin Language Specification — Function calls](https://kotlinlang.org/spec/expressions.html)
- [Python Language Reference — Function definitions](https://docs.python.org/3/reference/compound_stmts.html#function-definitions)
- [C++ working draft — Default arguments](https://eel.is/c%2B%2Bdraft/dcl.fct.default)
- [C++ working draft — Declarations](https://eel.is/c%2B%2Bdraft/dcl.decl)

## Public-interface integration (2026-11-24; proposed)

If defaults are adopted, specify whether their evaluation semantics belong to the public operation revision or a separately pinned adapter. A provider cannot silently replace public default expressions or their effects merely by matching a signature. Distinguish a changed default value, changed evaluation order, changed captured context and provider-only body change; test omitted and explicit arguments separately. This does not select default-argument syntax.

Related: [Public interfaces and verified contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This follow-up does not change earlier results or accepted rules.
