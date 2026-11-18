# RT-04 Prototype 01 — Executable Scenario Set

Implemented by PROTOTYPES/RT-04-01/test_rt04_model.py. Scope is declaration-level checker behavior, supplied finite resource-control-flow graphs, and explicitly asserted call-graph completeness metadata.

| ID | Fixture | Profile A | Profile B |
|---|---|---|---|
| RT4-P01 | Primitive signature with fs.read | Accept | Accept |
| RT4-P02 | Open effect row | Reject unsupported | Accept annotation |
| RT4-P03a | Positive refinement value | Unsupported | Accept |
| RT4-P03b | Negative refinement value | Unsupported | Reject |
| RT4-P03c | Missing refinement evidence | Unsupported | UNKNOWN |
| RT4-P04 | entry → load → read; leaf has fs.read | Summary includes effect | Summary includes effect |
| RT4-P05 | Callee requires network.send; caller omits it | Requires ambient context | Reject undeclared caller capability |
| RT4-P06 | Ambient capability in A / explicit caller requirement in B | Accept | Accept |
| RT4-P07 | Same resource consumed twice in a linear sequence | No static affine rejection | Reject use-after-move |
| RT4-P08 | Unknown resource consumed | No static affine rejection | Reject |
| RT4-P09 | Unknown callee | Reject | Reject |
| RT4-P10 | Unknown effect label | Reject outside closed vocabulary | Reject without an open row; accept with an explicit row variable |
| RT4-P11 | Malformed declaration envelope | Reject | Reject |
| RT4-P12 | Two exclusive branches both consume the same resource before join | No static affine check | Accept; incoming states agree |
| RT4-P13 | One branch consumes and the other preserves a resource before join | No static affine check | Reject inconsistent join state |
| RT4-P14 | One reachable branch consumes the same resource twice | No static affine check | Reject use-after-move |
| RT4-P15 | A loop consumes the same resource on successive iterations | No static affine check | Reject use-after-move |
| RT4-P16 | CFG edge points to an undeclared block | No CFG validation | Reject malformed CFG |
| RT4-P17 | Linear consumes and CFG resource_flow both declared | No affine check | Reject ambiguous resource-flow input |

| RT4-P18 | Transitive effects fit a declared effect bound and every reachable function is marked complete | Not yet compared | Accept |
| RT4-P19 | A transitive callee introduces an effect outside the caller's bound | Not yet compared | Reject |
| RT4-P20 | A reachable function lacks call-graph completeness evidence | Not yet compared | UNKNOWN |
| RT4-P21 | No outgoing call edge is listed but the function is not certified complete | Not yet compared | UNKNOWN, not an empty effect summary |
| RT4-P22 | A callee target is unresolved while checking a bound | Not yet compared | UNKNOWN |
| RT4-P23 | A known direct effect violates the bound while another call edge is unresolved | Not yet compared | Reject the known violation and report incomplete summary |
| RT4-P24 | Completeness evidence names an undeclared function | Not yet compared | Reject malformed evidence |
| RT4-P25 | Multiple direct effects are all within the declared bound | Not yet compared | Accept |
| RT4-P26 | Typed call has matching argument and result types | Not yet compared | Accept |
| RT4-P27 | Typed call has wrong argument count | Not yet compared | Reject |
| RT4-P28 | Typed call has an argument type mismatch | Not yet compared | Reject |
| RT4-P29 | Caller expects a result type different from the callee result | Not yet compared | Reject |
| RT4-P30 | Typed call targets a function without an explicit complete signature | Not yet compared | UNKNOWN |
| RT4-P31 | Typed call-site target is absent from caller call-graph edges | Not yet compared | Reject malformed model input |
| RT4-P32 | Result<Ok, Err> descriptors match structurally | Not yet compared | Accept |
| RT4-P33 | Nested Result error component differs | Not yet compared | Reject |
| RT4-P34 | Profile A receives a Profile B Result descriptor | Reject unsupported type | Not yet compared |
| RT4-P35 | Result<Ok, Err> is used as a callee parameter type and matches at the call site | Not yet compared | Accept |
| RT4-P36 | Scoped grant covers a narrower required path | Not yet compared | Accept |
| RT4-P37 | Required path is outside the grant scope | Not yet compared | Reject |
| RT4-P38 | Child grant narrows its parent scope without changing capability | Not yet compared | Accept |
| RT4-P39 | Child grant broadens its parent scope | Not yet compared | Reject malformed grant graph |
| RT4-P40 | Child grant changes its parent's capability | Not yet compared | Reject malformed grant graph |
| RT4-P41 | Revoking a parent grant revokes descendant grants | Not yet compared | Reject use of descendant |
| RT4-P42 | A directly revoked grant is used to satisfy a requirement | Not yet compared | Reject |
| RT4-P43 | Caller explicitly delegates a sufficient grant to a callee that accepts it | Not yet compared | Accept |
| RT4-P44 | Scoped callee requirement has no explicit call-site delegation | Not yet compared | UNKNOWN |
| RT4-P45 | Caller attempts to pass a grant it does not hold | Not yet compared | Reject malformed model input |
| RT4-P46 | Grant scope contains parent traversal | Not yet compared | Reject malformed grant |
| RT4-P47 | Profile A receives scoped grant declarations | Reject unsupported | Not yet compared |
| RT4-P48 | Callee has not declared a passed grant as accepted | Not yet compared | Reject |
| RT4-P49 | Grant parent graph contains a cycle | Not yet compared | Reject malformed grant graph |
| RT4-P50 | Scope prefix matches only on a path-segment boundary | Not yet compared | Reject out-of-scope requirement |

The CFG tests assume the supplied blocks and edges are complete and correctly represent source control flow. They do not model symbolic branch conditions, borrow lifetimes, resource return/drop, terminal-path cleanup, or prove that the CFG extractor is sound. Effect-bound tests likewise trust fixture-level completeness assertions; they do not prove source call-graph completeness or discover dynamic, generated, FFI, handler, or reflective calls. These are not whole-program semantics.


## RT-03 × RT-04 shared observable-trace fixtures

The companion [cross-profile report](../RT-04-RT-03-CROSS-PROFILE-TRACES.md) and
[executable tests](PROTOTYPES/RT-04-01/test_rt03_rt04_cross_profile.py)
add a deliberately small hand-authored trace oracle. These are not complete
reference semantics and do not replace the declaration-level tests above.

| ID | Shared trace | RT-03 A | RT-03 D | RT-04 checker A | RT-04 checker B |
|---|---|---|---|---|---|
| RT3-RT4-X01 | Pure return, no events | Admissible | Admissible | Accept | Accept |
| RT3-RT4-X02 | Declared fs.read event | Reject as effectful | Admissible when declared | Accept with ambient capability | Accept with scoped grant and effect-row annotation |
| RT3-RT4-X03 | Two ordered fs.write events | Reject as effectful | Admissible; event order remains observable | Effect-label summary only | Effect-label summary only |
| RT3-RT4-X04 | net.send event absent from declared effects | Reject | Reject | Reject unknown closed label | Accepts with open-row annotation; row unification/handler coverage are not implemented |

The trace tests expose a key boundary: RT-04's effect summaries are not
observational traces. They discard order and payload, and an open-row annotation
does not establish that an effect is handled.


## RT-03 executable reference-semantics slice

Implemented by `PROTOTYPES/RT-04-01/rt03_reference.py` and
`PROTOTYPES/RT-04-01/test_rt03_reference.py`. These are interpreter tests,
not declaration-checker fixtures.

| ID | Program/condition | Profile A | Profile D |
|---|---|---|---|
| RT3-REF-01 | Strict pure integer addition | Return 42, empty trace | Return 42, empty trace |
| RT3-REF-02 | Explicit error-shaped result value | Return the error value, no event | Same |
| RT3-REF-03 | `perform fs.read` | Reject effectful expression | Reject unless fs.read is declared |
| RT3-REF-04 | Declared fs.read with fixture file | Not applicable | Return contents and record request/outcome event |
| RT3-REF-05 | Declared fs.read for missing path | Not applicable | Return explicit NotFound outcome and record event |
| RT3-REF-06 | Ordered state write/read/write/read sequence | Reject effectful expression | Preserve all four events and final state |
| RT3-REF-07 | Reverse two writes to the same state key | Reject effectful expression | Trace and final result change |
| RT3-REF-08 | net.send with deterministic fixture response | Reject effectful expression | Return configured response and record event |
| RT3-REF-09 | Declared effect without a reference handler | Reject effectful expression | Fail closed as unsupported handler |
| RT3-REF-10 | Malformed expression tree | Fail closed | Fail closed |
| RT3-REF-11 | Mutating operations with caller-owned initial fixtures | Not applicable | Internal copies change; caller inputs remain unchanged |

The RT-04 checker comparison remains intentionally separate: it can summarize
the set of effect labels but cannot represent repeated event occurrences,
ordering, payloads, handler outcomes, or final state.


## RT-03 independent path-model scenarios

A separate structural model enumerates control paths without running either evaluator. A non-literal condition represents an unknown boolean and forks into both branches; a literal boolean selects one branch. Cancellation during condition evaluation selects neither branch. The model tracks resource acquire/release order and failed-cleanup leftovers.

| ID | Case | Expected path-model behavior |
|---|---|---|
| RT3-PATH-01 | Unknown condition with two branches | Enumerate both branch paths |
| RT3-PATH-02 | Nested unknown conditions | Enumerate the three reachable structural paths |
| RT3-PATH-03 | Cancellation while evaluating condition | Produce one cancelled path and no branch choice |
| RT3-PATH-04 | Nested resources with successful cleanup | Predict LIFO release on every path |
| RT3-PATH-05 | Nested cleanup failures during cancellation | Preserve cancellation, report failures in unwind order, retain active resources |
| RT3-PATH-06 | Result error in ordinary sequence | Continue structural evaluation; do not implicitly short-circuit |
| RT3-PATH-07 | Result error in `result_sequence` | Stop enumerating later items |

The path model is compared with both concrete evaluators for resource events and final active-resource sets. An exhaustive finite matrix covers 72 combinations of branch selection, two nested release outcomes, and selected/unselected normal, Result-error, and cancellation expressions. This is not a source-level path completeness proof.


## RT-03 branching and resource cleanup scenarios

The `if` expression evaluates a boolean condition and exactly one branch. Resource scopes surrounding a branch must release their resources when the selected branch returns normally, produces a Result error, or cancels execution. These are concrete execution tests, not a proof of source-level path completeness.

| ID | Case | Expected behavior |
|---|---|---|
| RT3-BR-01 | True condition | Evaluate only the `then` branch |
| RT3-BR-02 | False condition | Evaluate only the `else` branch |
| RT3-BR-03 | Non-boolean condition | Reject the expression |
| RT3-BR-04 | Selected branch returns Result error inside resource scope | Release resource and preserve the branch error |
| RT3-BR-05 | Selected branch cancels inside resource scope | Release resource during cancellation unwind |
| RT3-BR-06 | Cancellation occurs while evaluating condition | Unwind enclosing resource scopes; evaluate neither branch |

The current finite corpus checks concrete conditions. Symbolic/path-sensitive analysis and proof that all source-level branches are represented remain open.


## RT-03 structured resource lifecycle scenarios

The opt-in `with_resource` scope acquires a fixture resource, evaluates its body, and releases it on normal completion, Result error, or cancellation. Nested scopes release in LIFO order. A failed release remains visible as an active resource and is not silently treated as successful cleanup.

| ID | Case | Expected behavior |
|---|---|---|
| RT3-RES-LC-01 | Successful acquire/use/body/release | Record ordered acquire, use, release events; no active resource remains |
| RT3-RES-LC-02 | Acquire fails | Skip body and release; return acquisition error |
| RT3-RES-LC-03 | Body returns Result error | Release resource and preserve primary error |
| RT3-RES-LC-04 | Body is cancelled | Release resource during cancellation unwind |
| RT3-RES-LC-05 | Nested scopes are cancelled | Release inner resource before outer resource |
| RT3-RES-LC-06 | Release fails after body error | Preserve both primary and cleanup errors; retain active resource |
| RT3-RES-LC-07 | Nested releases fail during cancellation | Preserve cancellation and report cleanup failures in LIFO order |

The model is a structured fixture experiment. It does not define ownership/borrowing, transfer, arbitrary destructors, async cancellation, or branching path analysis.


## RT-03 execution cancellation scenarios

Cancellation is a terminal execution outcome, not a Result error. The current bounded evaluator represents it as `{"cancelled": reason}`, discards pending continuations, and does not execute later expressions. Effects completed before cancellation remain observable; rollback and resource cleanup are not yet specified.

| ID | Case | Expected behavior |
|---|---|---|
| RT3-CAN-01 | Cancel a pure expression | Return a distinct cancelled outcome |
| RT3-CAN-02 | Cancel after a completed effect | Preserve the completed event and state transition |
| RT3-CAN-03 | Pending sequence items follow cancellation | Do not evaluate any later item |
| RT3-CAN-04 | Cancellation occurs inside `result_sequence` | Stop the enclosing evaluation; do not treat cancellation as a Result error |
| RT3-CAN-05 | Cancellation and Result error carry the same reason payload | Keep `cancelled` and `error` outcomes distinct |

The recursive and small-step evaluators are differentially checked for these cases. The model is synchronous and does not yet cover asynchronous/concurrent cancellation, function-call boundaries, resource finalization, or cleanup.


## RT-03 explicit Result propagation scenarios

The opt-in `result_sequence` construct propagates the first Result error and skips later expressions. Ordinary `sequence` remains strict and does not implicitly propagate Result values.

| ID | Case | Expected behavior |
|---|---|---|
| RT3-RES-01 | All items are `ok` | Return the final `ok` value |
| RT3-RES-02 | An `error` follows one or more `ok` values | Return the first error unchanged |
| RT3-RES-03 | An effect follows an error item | Do not evaluate it; no event or state change is recorded |
| RT3-RES-04 | An item is not Result-shaped | Reject the expression |
| RT3-RES-05 | Ordinary `sequence` contains an error-shaped value before an effect | Continue evaluation; preserve prior strict sequence behavior |

Both recursive and small-step evaluators are differentially checked for these cases. This does not define exceptions, implicit propagation from function calls, cancellation, or resource cleanup.


## RT-03 differential evaluator scenarios

The [recursive evaluator](PROTOTYPES/RT-04-01/rt03_reference.py) is
cross-checked against a second [small-step evaluator](PROTOTYPES/RT-04-01/rt03_smallstep.py).
The second implementation uses explicit continuations/value stack and does not
import the first. Full differential tests are in
[`test_rt03_differential.py`](PROTOTYPES/RT-04-01/test_rt03_differential.py).

| ID | Differential case | Compared observations |
|---|---|---|
| RT3-DIFF-01 | Pure values, nested arithmetic, sequence, explicit Result values | Result, empty events, final stores |
| RT3-DIFF-02 | Ordered state writes and reads | Event order/payload/outcomes, result, final state |
| RT3-DIFF-03 | File write/read/missing read | Ordered events, explicit missing-file error, final files |
| RT3-DIFF-04 | Deterministic network response | Request payload, event outcome, result |
| RT3-DIFF-05 | Reordered state writes | Both implementations preserve the changed trace and final state |
| RT3-DIFF-06 | Generated two-write combinations over values 0, 1, 2 | Nine generated programs, full trace/result/state equality |
| RT3-DIFF-07 | Effect in pure A / undeclared effect in D | Both implementations reject |
| RT3-DIFF-08 | Malformed arithmetic | Both implementations fail closed |

Agreement is limited to this finite hand-authored expression grammar and
fixture handlers. The models share the same exploratory contract, so agreement
does not exclude a common specification error.
