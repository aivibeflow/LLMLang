# Research Scenario 37 — Effect Rows, Handlers, and Observable Traces

**Status:** Evidence-linked comparison; no LLMLang effect or handler model selected  
**Research area:** RT-03 core semantics and RT-04 type/effect/resource model  
**Updated:** 2026-11-19

## 1. Question

What does a static effect signature say about a computation, and what evidence is needed to describe what it actually does?

The distinction matters because LLMLang uses effect information for at least three different purposes: checking that a call is permitted, reasoning about handler composition, and comparing observable behavior for verification or reuse. A set of possible operation names may be enough for one purpose and insufficient for another. This report compares Koka's effect rows and algebraic handlers with F*'s computation types and indexed-effect designs, then relates both to the existing RT-03/04 observations. It selects no semantics.

## 2. Candidate representations

| Vector | Representation | Main claim | Main limitation to investigate |
|---|---|---|---|
| **R — Effect-row bound** | A function has a closed or open row of effects it may use. | Composable, polymorphic upper bound for calls and capabilities. | A row is not automatically the ordered events, payloads, handler choices, or result of a particular execution. |
| **I — Indexed effect discipline** | A computation carries an index such as an allowed operation set, state transition, or pre/postcondition. | The index can express a stronger static discipline than a flat label. | The meaning depends on the index algebra; a set-union index intentionally forgets event order and multiplicity. |
| **T — Observable event trace** | Execution produces an ordered sequence, or a concurrency-aware partial order, of operation/payload/outcome events. | Supports behavioral comparison, replay, and explicit observation boundaries. | Requires trace equivalence, projection, and concurrency rules; can carry more information than a type-level upper bound needs. |
| **H — Handler-aware summary** | A summary describes effects introduced, handled, forwarded, masked, resumed, and exposed by a handler. | Captures the boundary between a request and its interpretation. | Handler order and dynamic scope affect semantics; summary and runtime evidence must remain complete. |

These are dimensions that may be combined, not mutually exclusive alternatives. A plausible analysis to test is an effect row for allowed/potential operations, a handler-aware type/evidence boundary, and a separate dynamic trace for realized observations.

## 3. Prior-art comparison

### Koka

Koka uses effect rows and supports effect-polymorphic higher-order functions: `map` carries the callback's effect row to its result. Its handlers interpret user-defined operations, and the output effect row excludes an operation when it is handled inside the action. Handler-clause effects can still escape. In the documented `catch` example, the handler itself can raise the same effect, so the final row still contains that effect.

Koka allows duplicate labels in an effect row. Its documentation connects duplicates to nested handlers and runtime evidence vectors: one occurrence can describe a request handled by an inner handler while another occurrence remains for a surrounding handler. `mask<effect>` skips a matching inner handler once; the operation may then reach an outer handler. This shows that a Koka row is not simply an idempotent set of permissions. It carries handler-context structure needed by the type system and effect implementation. It still does not say which requests occur at runtime, in what order, or with which payload values.

Koka's handler-order examples also show why handled effects cannot be erased from behavioral evidence: composing state and exception handlers in different orders changes whether the final state is retained on failure. The existing [COR-10 experiment](../RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md#8-cor-10--what-a-state-handler-exposes) independently finds that replacing a private state handler with logging or rejection changes observable events and terminal outcomes even where call declarations and successful scalar results agree.

Primary sources: [Koka effect rows, polymorphism, duplicate labels, and masking](https://koka-lang.github.io/koka/doc/book.html#polymorphic-effects), [Koka handler implementation notes on evidence vectors and row kinds](https://koka-lang.github.io/koka/doc/std_core_hnd-source.html), and [Koka's standard effect and handler types](https://koka-lang.github.io/koka/doc/std_core_types.html).

### F*

F* assigns computations a computation type. In its primitive account this includes an effect constructor and a weakest-precondition transformer; user-defined indexed effects can add indices and custom proof disciplines. The effect ordering and subeffecting can allow a computation with a smaller effect to be used where a larger effect is expected. This gives effect declarations a logical contract, not just a list of operation names.

The F* indexed-effects paper demonstrates an algebraic-operation tree containing operations in execution structure, then indexes a computation by an over-approximating set of allowed operation labels. Its `abides` predicate requires each operation to belong to the set. The paper explicitly interprets the list index by membership, so order and multiplicity are irrelevant, and combines indices using set union. The computation tree can preserve operation sequence; the set index does not. The distinction is deliberate and is a direct example of why an effect bound and a realized trace should not share a representation accidentally.

F*'s older official tutorial and its ICFP 2015 design paper also document that general parametric polymorphism over effects is not supported in the cited design; subeffecting and user-defined indexed effects provide other abstraction mechanisms. Keep this limitation attached to the relevant F* design/version and verify it against a release if future experiments depend on exact current behavior.

Primary sources: [F* user-defined indexed effects](https://fstar-lang.org/papers/indexedeffects/), [paper's operation-set index and effect tree](https://fstar-lang.org/papers/indexedeffects/indexedeffects.pdf), [F* computation types and effect order](https://fstar-lang.org/tutorial/book/part4/part4_computation_types_and_tot.html), [higher-order effect-polymorphism discussion](https://fstar-lang.org/tutorial/old/tutorial.html#higher-order-functions-on-lists), and [ICFP 2015 design paper](https://fstar-lang.org/papers/icfp2015/full.pdf).

## 4. Minimal counterexample: equal row, different trace

Let `emit : String -> <console> Unit`. Both programs below have the same effect row:

```text
emit("open"); emit("close")
emit("close"); emit("open")
```

The row `<console>` expresses the same possible effect in both cases. Their event traces differ in order and payload. If a handler buffers, rejects, transforms, or persists these requests, the difference can also change the returned value, terminal outcome, or external state. A type-level set of effect names cannot establish equality of these runs.

For concurrent code, even a total sequence may be too strong: independent events can commute while conflicting events require a happens-before relation. COR-11 already exhibits schedules with the same event kinds and different delivery order; commuting increments preserve the scalar result while noncommuting writes do not.

## 5. Cross-area constraints and discriminators

- **Permission vs behavior:** a declared effect row is an upper bound or required interface. It does not prove that the implementation is effect-free outside the row; completeness and trust in the checker remain separate evidence obligations.
- **Static allowance vs realized observation:** effect rows can reject an unhandled or unauthorized operation. Trace evidence records whether an operation occurred, its payload, handler outcome, and relative order.
- **Handling vs erasure:** a handler may turn a request into a result, another effect, a trace event, or terminal rejection. Removing a handled label from the residual type does not imply the request had no observable consequence.
- **Nesting and masking:** duplicate labels or equivalent handler-scope information may be needed when an inner handler is skipped or when a handler clause can re-perform an operation.
- **Concurrency:** effect rows do not choose a schedule. Use a sequence for sequential semantics and a defined partial-order/schedule witness when concurrency makes multiple traces legal.
- **Incremental reuse:** hashing only an effect-name row cannot justify reuse if handler identity/order, externalization policy, payloads, or trace observations changed.

Discriminating follow-up probes should include two operation orders with equal rows; a handler clause that performs the same operation it handles; nested handlers with masking/forwarding; state+failure handler composition in both orders; and two concurrent writes under commuting and noncommuting operations. Record static row, handler stack/scope, observed event trace, result, terminal outcome, and final store independently.

The evidence weakens a vector that treats an unordered effect-label set as a complete behavioral summary if any pair of programs has the same labels but distinct traces or handler outcomes. It weakens a trace-only type discipline if the required permissions and unexecuted possible effects cannot be checked compositionally. It does not establish which combined representation LLMLang should adopt.

## 6. Current conclusion

Koka demonstrates that effect rows may carry higher-order callback effects and nested handler evidence, including duplicate labels and masking. F* demonstrates that a richer indexed effect system can define custom proof obligations while an operation-set index still deliberately discards order and multiplicity. COR-10 and COR-11 show that handler outcomes and event order are observable in the LLMLang research corpus. Therefore, future comparisons should test effect bounds, handler summaries, and runtime traces as separate evidence fields. No LLMLang feature is selected here.
