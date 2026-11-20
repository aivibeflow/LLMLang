# RT-04 Prototype 01 — Two Candidate Checker Vectors

Python 3.10+, standard library only.

Run from this directory:

    python -m unittest -v

## Scope

The model compares two declaration-level checker profiles:

- **A:** primitive types, closed effect vocabulary, ambient capability context, no static affine-use check.
- **B:** positive-integer refinement experiment, effect-row annotations, transitive capability propagation, affine resource consumption.

Both profiles compute fixed-point summaries of direct/transitive effects and capabilities. Profile B supports two deliberately small resource-use inputs: a linear `consumes` sequence and an explicit control-flow graph (`resource_flow`). The CFG model propagates exact sets of consumed resources along reachable paths, rejects repeated consumption, and requires all paths reaching a join to agree on each resource's available/consumed state. Its finite state space converges on cycles.

The model accepts function declarations, optional typed call-site records, scoped capability grants, and supplied call/control-flow edges; it does not parse LLMLang source, discover calls or branches, execute functions, prove graph completeness, or implement runtime authorization.

The model's UNKNOWN refinement outcome is distinct from acceptance and rejection. Missing evidence is not treated as success.

## Return and cleanup projection (COR-13)

[`rt03_return_cleanup.py`](rt03_return_cleanup.py) compares a staged reserve/commit rule with transfer-before-cleanup for one returned owned handle and an alternative error-return branch. It records the result, ordered resource events, and final owner/debt slots; static rejection fixtures cover a local borrow and implicit escape. The focused cases are in [`test_rt03_return_cleanup.py`](test_rt03_return_cleanup.py). The branch fixture exposes the cleanup-failure result difference, and caller-side handling checks disposal of a value carried with an error. Common cleanup paths match the RT-03 evaluator and path model. This remains an ownership-obligation projection, not a source evaluator, borrow checker, or selected rule.

[`test_rt04_owned_result_boundary.py`](test_rt04_owned_result_boundary.py) records the RT-04 checker boundary: primitive `Result` is accepted, while nested `Owned` and `ErrorWithValue` descriptors report `UNKNOWN_TYPE`. Its typed-call evaluator probe requires Python 3.10+ and is skipped on older interpreters.

[`rt04_owned_call.py`](rt04_owned_call.py) and [`test_rt04_owned_call.py`](test_rt04_owned_call.py) add separate caller-obligation models for explicit `Result<Owned<Handle>, E>` and `ErrorWithValue<Owned<Handle>, E, CleanupError>` outcome branches. `check_owned_call_tree` lowers a small structured tree of sequences, conditionals, release attempts, and ownership actions into the CFG consumed by `check_owned_call_cfg`; `execute_owned_call_tree` independently executes one path from that same tree with explicit release and branch inputs. The CFG checker tracks ownership through blocks and rejects incompatible states at joins. A `release_attempt` has explicit `ok` and `error` successors: the error edge retains caller ownership as cleanup debt, which must be discharged or propagated with the owned value. Tests contrast outcome coverage: `Result`'s ordinary error branch carries no handle, while `ErrorWithValue`'s cleanup-error branch must preserve the handle; missing or unrecognized outcome tags return `UNKNOWN`. Cycles or unsupported tree/type constructs also fail closed. The legacy atomic `release` action still assumes success, so the paired cleanup counterexample remains a regression guard. This grammar is research-specific and is not LLMLang syntax: the existing typed-call AST has no owned-resource/result-match constructs. The paired interpreter/checker is bounded implementation cross-checking, not an independent semantics, and remains isolated from `rt04_model`.

[`rt04_owned_call_oracle.py`](rt04_owned_call_oracle.py) is a table-driven one-path trace oracle that imports neither the checker nor the interpreter. [`test_rt04_owned_call_oracle.py`](test_rt04_owned_call_oracle.py) compares 9,856 combinations across 154 trees of depth at most two (actions, two-item sequences, two-arm conditionals, and two-arm cleanup attempts), release and branch inputs, output-carriage flags, and initial ownership. This is a bounded implementation cross-check, not an independent human review or proof of general semantics.

[`rt04_cleanup_disposition.py`](rt04_cleanup_disposition.py) explores LIFO cleanup stacks with four API-declared outcomes (`ok`, retained error, consumed error, indeterminate) and two unwind policies (continue or stop). [`test_rt04_cleanup_disposition.py`](test_rt04_cleanup_disposition.py) exhausts 168 depth-1-to-3 disposition/policy paths and keeps resource liveness separate from cleanup errors. It is a generic envelope experiment, not an OS-resource implementation or source semantics.

Scenario 119 derives the result shapes for a named owned-resource call from the callee's AST and its declared close contracts. The caller matches each shape and forwards every live or unresolved obligation once. Shape inference matches 4,096 concrete inputs from the disposition model. [Prototype](rt04_owned_call_match.py) · [Fixtures](test_rt04_owned_call_match.py) · [Results](../../RESEARCH-SCENARIO-119-OWNED-RESULT-MATCHING.md)

Scenario 120 includes a standalone probe against the system SQLite library. It compares a busy close with successful recovery, a finalization error that consumes its statement, and a `close_v2` success that delays destruction. [Probe](sqlite_cleanup_probe.py) · [Results and reproduction](../../RESEARCH-SCENARIO-120-SQLITE-CLEANUP-DEPENDENCIES.md)

Scenario 121 compares 510 plans for close and statement finalization. Run the probe with `--recovery-matrix` to check admitted plans against native SQLite return codes and destruction callbacks. The model tests cover the rejected preconditions and remaining ownership at the caller boundary. [Model](rt04_sqlite_recovery.py) · [Tests](test_rt04_sqlite_recovery.py) · [Results](../../RESEARCH-SCENARIO-121-SQLITE-LOCAL-CLOSE-RECOVERY.md)

Scenario 122 analyzes a source fragment and compares complete source proof, unvalidated snapshots, and checked current observations against 4,116 concrete cases. Run the SQLite probe with `--snapshot-freshness` for the native stale snapshot example. [Model](rt04_close_evidence.py) · [Tests](test_rt04_close_evidence.py) · [Results](../../RESEARCH-SCENARIO-122-CLOSE-EVIDENCE-FRESHNESS.md)

Scenario 123 composes source and snapshot evidence with owned-result forwarding on 36 shared inputs. The native probe checks 114 call boundaries, including errors that retain a connection and successful closes with pending destruction. [Model](rt04_close_call_boundary.py) · [Tests](test_rt04_close_call_boundary.py) · [SQLite probe](sqlite_close_call_probe.py) · [Results](../../RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md)

Scenario 124 runs 11 ordered schedules on a serialized SQLite connection. It compares separate version validation, a guard shared by both threads, and a producer that uses another lock for the same handle. [Model](rt04_close_interleavings.py) · [Tests](test_rt04_close_interleavings.py) · [SQLite probe](sqlite_close_interleavings_probe.py) · [Results](../../RESEARCH-SCENARIO-124-CLOSE-SYNCHRONIZATION.md)

Scenario 125 checks 12 callback cases and eight close calls over different dependent kinds on SQLite. It compares close reservation with reinspection, and observes destruction after `finalize`, `blob_close`, and `backup_finish`. [Model](rt04_close_reentry.py) · [Tests](test_rt04_close_reentry.py) · [SQLite probe](sqlite_close_reentry_probe.py) · [Results](../../RESEARCH-SCENARIO-125-CLOSE-REENTRY-AND-COVERAGE.md)

Scenario 126 checks role compatibility under aliases and compares 432 reservation plans. The SQLite probe checks overlapping backups on a common source, same-connection rejection, and retries after failed initialization. [Model](rt04_backup_roles.py) · [Tests](test_rt04_backup_roles.py) · [SQLite probe](sqlite_backup_roles_probe.py) · [Results](../../RESEARCH-SCENARIO-126-MULTI-RESOURCE-FFI-ROLES.md)

Scenario 127 parses aliases at two backup calls and compares independent role sets, role pairs, and complete routes. The tests cross-check 147,456 inputs and the reservations preserved on refusal. [Parser and model](rt04_backup_source_roles.py) · [Tests](test_rt04_backup_source_roles.py) · [Results](../../RESEARCH-SCENARIO-127-SOURCE-ROLE-CORRELATION.md)

Scenario 128 compares four policies for handling foreign errors after reservation. The native probe observes a `backup_finish` that returns the prior step error and destroys the retired source. [Model](rt04_backup_outcomes.py) · [Tests](test_rt04_backup_outcomes.py) · [SQLite probe](sqlite_backup_outcomes_probe.py) · [Results](../../RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md)

## Cleanup-error composition (Scenario 97)

[`rt03_cleanup_composition.py`](rt03_cleanup_composition.py) applies six candidate outcome policies (preserve with suppression, flat aggregate, nested wrapping, replace, discard, and abort on cleanup panic during active panic unwind) to an ordered cleanup trace. [`rt03_cleanup_composition_audit.py`](rt03_cleanup_composition_audit.py) independently reconstructs caller ownership and cleanup debt from that trace and API-declared resource dispositions; it does not import the operational model. [`test_rt03_cleanup_composition.py`](test_rt03_cleanup_composition.py) covers all 12 named Scenario 97 discriminators under all six policies (72 observations) and checks 13,230 valid combinations. All observations satisfy the obligation projection. The policies differ in outcome cause carriage while the same fixture's cleanup trace and resource/owner projection remain invariant. This is bounded model agreement, not a source-level semantics, proof of extraction completeness, independent specification review, or policy selection.

[`rt04_return_disposition.py`](rt04_return_disposition.py) composes one local cleanup disposition with function body outcome, transfer timing, pending-handle cleanup, and caller action. [`test_rt04_return_disposition.py`](test_rt04_return_disposition.py) checks four compatible body/timing scenarios and enumerates 2,048 input combinations. Resource dispositions remain supplied API-contract inputs; the model is not connected to source AST or the ownership checker.

## Resource-flow envelope

A function may provide either `consumes` or `resource_flow`, not both:

    "resource_flow": {
      "entry": "branch",
      "blocks": {
        "branch": {"successors": ["left", "right"]},
        "left": {
          "ops": [{"consume": "socket"}],
          "successors": ["join"]
        },
        "right": {
          "ops": [{"consume": "socket"}],
          "successors": ["join"]
        },
        "join": {}
      }
    }

Each resource starts available. A consume changes it to consumed. A second consume on any reachable path is a use-after-move. A join receiving both available and consumed states is rejected as a resource-state mismatch. This prototype does not model resource creation, borrowing, return/transfer, drop/finalization, path predicates, or state-dependent operations.

## Transitive effect bounds

A function may declare an `effect_bound` list. The checker compares this upper bound with the union of its direct effects and the effects inferred through all reachable callees.

The program-level `call_graph_complete` list is explicit completeness evidence for the supplied call graph. Every function in the root's reachable call closure must appear in that list before the bound can be accepted. If a reachable function is not certified complete, or a callee is unresolved, the effect-summary result is `UNKNOWN`. A known effect outside the bound is still a definite violation and causes rejection even when other parts of the graph are incomplete.

This is an input assertion for the experiment, not authenticated proof that a source-level extractor found every call. It does not discover omitted edges, dynamic dispatch, FFI, generated calls, handlers, or reflection. A real implementation must bind completeness evidence to the exact source/snapshot, extractor, scope, and assumptions.

Example:

    {
      "call_graph_complete": ["entry", "read"],
      "functions": {
        "entry": {"calls": ["read"], "effect_bound": ["fs.read"]},
        "read": {"effects": ["fs.read"]}
      }
    }

## Limitations

This is an experiment about checker obligations, not a language decision:
- effect-row syntax is only an annotation; row unification and handlers are not implemented;
- type checking is limited to primitive names and one positive-integer predicate;
- resource dataflow uses explicit CFGs and exact finite path-state sets; it does not model source branch discovery, symbolic path conditions, borrows, lifetimes, async suspension, returns, destructors, or cleanup behavior;
- terminal paths are not required to consume the same resources unless they later join;
- capability propagation checks declared call graphs and grant fixtures, not actual runtime authority;
- effect-bound acceptance additionally requires every function in the reachable call closure to be listed in `call_graph_complete`; this list is only an asserted fixture input, not authenticated completeness evidence;
- no SPG schema, hash envelope, ABI, compiler, or runtime is defined.

See [RT-04 Prototype 01 Results](../../RT-04-PROTOTYPE-01-RESULTS.md).

## Typed call-site envelope

Typed call-site checking is opt-in through a caller's `call_sites` list. Each record contains `target`, an ordered `args` list of argument type descriptors, and optionally `expected_result`. The target must also appear in the caller's `calls` list so that effect/capability propagation cannot omit a typed site.

The callee must explicitly declare both `params` and `result`; otherwise the checker reports `CALL_SIGNATURE_UNKNOWN` and the overall result is `UNKNOWN`. Known arity, argument-type, and expected-result mismatches are rejected. Profile B additionally supports the structural type descriptor `{"Result": [OkType, ErrType]}`; both components are recursively checked and compared structurally. This is a small type-constructor experiment, not a complete user-defined ADT declaration or pattern-matching system.

Example:

    {
      "functions": {
        "caller": {
          "calls": ["parse"],
          "call_sites": [{"target": "parse", "args": ["String"], "expected_result": {"Result": ["Int", "String"]}}]
        },
        "parse": {"params": {"text": "String"}, "result": {"Result": ["Int", "String"]}}
      }
    }


## Scoped capability grant envelope (Profile B)

A program may declare capability_grants as a map of grant IDs to records containing capability, canonical absolute POSIX scope, optional parent, and optional boolean revoked. A parentless grant is a trusted root input to this experiment. A child grant must retain the parent's capability and have a scope contained by the parent's scope; broadening or changing the capability is malformed input. Parent cycles are rejected.

A function's grants list declares the grant IDs available in that function's static capability context. Its capability_requirements list contains records with capability and scope. A grant authorizes a requirement only when the capability matches and the grant scope contains the entire required path. Scope matching is path-segment-aware (/workspace does not cover /workspace-old). Scopes reject relative paths, dot segments, duplicate separators, trailing separators (except /), and backslashes.

At a call boundary, each call-site may pass an explicit grants list. Every passed ID must be held by the caller and declared as accepted by the callee. The passed, non-revoked grants must cover every callee requirement. If a callee has scoped requirements but no call-site record is supplied, the checker reports CAPABILITY_DELEGATION_UNKNOWN and returns UNKNOWN rather than assuming implicit authority. A revoked grant, or any descendant of a revoked grant, cannot authorize a requirement.

Example:

    {
      "capability_grants": {
        "workspace-read": {"capability": "fs.read", "scope": "/workspace"},
        "source-read": {
          "capability": "fs.read",
          "scope": "/workspace/src",
          "parent": "workspace-read"
        }
      },
      "functions": {
        "caller": {
          "grants": ["workspace-read"],
          "calls": ["read_source"],
          "call_sites": [{
            "target": "read_source",
            "args": [],
            "grants": ["workspace-read"]
          }]
        },
        "read_source": {
          "grants": ["workspace-read"],
          "capability_requirements": [
            {"capability": "fs.read", "scope": "/workspace/src"}
          ]
        }
      }
    }

This is a static declaration-level model. Parentless grant provenance/authenticity is trusted input; the experiment does not model issuer identity, token cryptography, expiry, dynamic revocation consistency, concurrent calls, process boundaries, non-path scopes, or time-of-check/time-of-use races. Revocation is a boolean in the supplied snapshot, and ancestor revocation is propagated through the declared grant-parent chain. Profile A does not support scoped grants.


## RT-03 cross-profile trace fixtures

The companion `test_rt03_rt04_cross_profile.py` checks a small shared observable-trace corpus against RT-03 semantic profiles A/D and RT-04 checker vectors A/B. It is intentionally a fixture oracle, not a reference interpreter. See [the cross-profile findings](../../RT-04-RT-03-CROSS-PROFILE-TRACES.md).

## RT-03 A/B/D typed call and state experiment

`rt03_typed_calls.py` checks and executes first-order, acyclic programs over Int, Bool, and Unit. All three semantic variants use strict lexical calls. A uses immutable `let` bindings. B adds private `local` cells and ordered `set` operations. The RT-04 declaration checker receives the actual call sites and argument types derived from each body, including both branches of every conditional. The checker vector is selected independently of the execution variant. See [COR-09 for fixtures and results](../../RT-03-04-SHARED-SEMANTICS-CORPUS.md#7-cor-09--typed-calls-and-private-local-state).

Variant D adds `{"handle_state": [initializer, observe_writes, reject_negative, body]}`, `{"state_get": null}`, and `{"state_put": value_expression}`. The second and third fields are boolean configuration flags. A function can declare `requires_state=True` to request an enclosing handler. The body checker enforces that requirement throughout the call graph and requires a closed entry. The RT-04 projection for D covers signatures and calls. See [COR-10 for the observation and failure rules](../../RT-03-04-SHARED-SEMANTICS-CORPUS.md#8-cor-10--what-a-state-handler-exposes).

## RT-03 C actor schedules

`rt03_actor_model.py` explores every enabled schedule of finite producer scripts sending integer updates to a single receiver. It compares per-channel FIFO with closed batch ordering and isolates producer failure or aborts the group according to the chosen policy. Each distinct terminal observation has a replayable witness. An independent oracle checks the full trace sets for small cases, and the shared scalar workload compares C with A/B/D. [COR-11 results](../../RT-03-04-SHARED-SEMANTICS-CORPUS.md#9-cor-11--actor-traces-and-failure-policies)


## RT-03 A/D executable reference slice

The separate `rt03_reference.py` module implements a small strict expression
interpreter for RT-03 candidate profiles A and D. It is deliberately not part
of `rt04_model.py`: the former evaluates expressions and produces observable
traces; the latter checks declaration-level type/effect/capability/resource
fixtures.

The supported expression forms are `literal`, strict left-to-right integer
`add`, left-to-right `sequence`, explicit `result_ok`/`result_error`
values, and `perform`. Profile A rejects `perform`. Profile D requires each
effect to be declared and supports finite deterministic handlers for file
read/write, state read/write, and network send. Events retain order, operation,
payload, and outcome; the returned trace also includes result and final
fixture state/files.

Run all tests, including the reference semantics slice, from the repository
root:

    python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v

### Explicit Result propagation

The opt-in `result_sequence` form evaluates a non-empty list of Result-shaped expressions left-to-right. It returns the first error unchanged and skips later expressions; if every item succeeds, it returns the final success value. Non-Result items fail closed. This is explicit propagation only: ordinary `sequence` remains strict and continues evaluating after an error-shaped Result value.

### Execution cancellation

The `cancel` expression produces a terminal execution outcome `{"cancelled": reason}`, distinct from both ordinary values and `{"error": reason}` Result values. Cancellation discards pending expression continuations, so no later sequence or Result-sequence item executes. Effects completed before cancellation remain visible in the trace and fixture state; this slice does not roll them back.

Both evaluators are differentially checked for cancellation nested inside pending continuations, skipped later effects, preservation of prior effects, and distinction from a Result error with the same reason payload. This is a synchronous terminal-control experiment only. It does not define cancellation propagation across function calls, asynchronous tasks, concurrent work, exception handling, resource finalization, or cleanup guarantees.


### Independent structural path model

`rt03_path_model.py` is a third, separately derived model for the bounded control/resource fragment. It does not import either evaluator and does not execute values or effect handlers. Instead, it enumerates structural paths, follows literal boolean conditions, forks only an explicit `unknown_bool` analysis marker into both outcomes, traverses nested `add` and Result-wrapper expressions in evaluation order, and tracks resource obligations, LIFO release events, cancellation, Result short-circuit markers, and resources left active by failed cleanup. Its tests compare predicted resource-event sequences and final active-resource sets against both concrete evaluators over a finite scenario corpus.

The path-model suite also exhausts a 72-case finite matrix: both boolean branch choices, both release-success/failure flags for two nested resources, and all combinations of normal, Result-error, and cancellation outcomes in the selected and unselected branches. Every case compares predicted resource event order and remaining active-resource identities with both evaluators.

This provides a different kind of cross-check from evaluator-vs-evaluator differential testing. It can expose shared control/unwind mistakes in both interpreters, but it is not a source-level control-flow extractor, does not prove that all source branches were represented, and does not model type correctness, actual effect outcomes, aliases, ownership transfer, concurrency, or arbitrary cleanup code.

The follow-up [Scenario 98](../../RESEARCH-SCENARIO-98-FINITE-AST-PATH-COVERAGE.md) builds a depth-three AST decision tree with seven unique `unknown_bool` markers. All 128 concrete assignments are executed through both evaluators and compared with all eight path-model outcomes; each feasible path has a distinct resource-trace witness. This strengthens coverage evidence for the generated AST grammar only; parser and source-to-AST completeness remain unproved.

[Scenario 99](../../RESEARCH-SCENARIO-99-REPEATED-PATH-PREDICATES.md) extends the path model so repeated occurrences of the same `unknown_bool` marker reuse the earlier choice on that path. A two-branch sequential fixture therefore has two feasible paths (`TT`, `FF`) instead of the four independent-occurrence combinations. This fixture convention does not solve relationships between different predicates or establish source-level value identity.

[Scenario 100](../../RESEARCH-SCENARIO-100-FINITE-BOOLEAN-PATH-FEASIBILITY.md) adds a separate exhaustive analyzer for a small pure Boolean predicate IR. Across all four assignments to `x` and `y`, the branches `x` then `x or y` have three feasible vectors (`TT`, `FT`, `FF`) and one infeasible vector (`TF`); both concrete evaluators and the existing path/resource model agree. The analyzer scales exponentially and is not an SMT solver or source-CFG extractor.

[Scenario 101](../../RESEARCH-SCENARIO-101-SOLVER-VS-TRUTH-TABLE-PATHS.md) cross-checks the same route constraints with pinned SymPy 1.14.0 `dpll2`. It returns the same three paths for `x` then `x or y`, and a contradiction fixture excludes an impossible arm. On one left-associated conjunction family, truth-table median grows from 0.000885 s at 8 variables to 1.635 s at 18, while DPLL2 remains around 0.001–0.003 s. This is not a general solver performance claim; the family is easy for DPLL and the solver becomes part of the analysis trust boundary.

The solver experiment uses the pinned test dependency in [`requirements-solver.txt`](requirements-solver.txt). Reproduce the comparison with:

```sh
python benchmark_rt03_predicate_paths.py
```

### Independent resource outcome rules

`rt03_resource_rules.py` defines a separate outcome algebra for acquired resource scopes. It imports neither evaluator nor the structural path model. Given an outer-to-inner list of acquired scope frames and one body outcome (normal value, Result error, or cancellation), it derives the exact acquire/release event trace, final result envelope, and resources retained after failed release. An optional acquisition-failure position models the rule that a failed acquisition skips that scope's body and all inner scopes while already-acquired outer scopes still unwind.

The rules distinguish two cleanup cases: a failed release after normal/Result completion becomes a `CleanupFailed` Result error (retaining a prior Result error as `primary`), while a failed release during cancellation is accumulated in LIFO order without converting cancellation into a Result error. Repeated outer cleanup failures wrap the already-produced inner cleanup error as the next `primary`.

`test_rt03_resource_rules.py` checks exact event payloads/outcomes, result envelopes, and final resource maps against both evaluators and projects the result back to the independent path model. Its finite matrix covers depths one through three, every release-success/failure combination, normal/Result-error/cancellation body outcomes, and every possible acquisition-failure position: 144 cases. This is a bounded executable rule model, not a selected language ownership model or proof of arbitrary cleanup semantics.

### Conditional branching

The bounded `if` expression evaluates a boolean condition and exactly one selected branch. A non-boolean condition is rejected. The small-step evaluator represents the condition result as a continuation, so cancellation while evaluating the condition still unwinds any enclosing resource scopes. Branches are concrete runtime paths in this prototype; the evaluator does not prove that all possible paths in a source program were discovered.

### Structured resource scope and cleanup

The opt-in `with_resource` expression acquires a named fixture resource, evaluates its body, and releases the resource on normal completion, a Result error value, or terminal cancellation. The body can observe the active resource through the declared `resource.use/use` effect. Acquisition failure skips the body and release. Release failure is observable and leaves the resource in the final resource map; if the body already produced a Result error, both the primary and cleanup errors are retained. During cancellation, active scopes unwind in LIFO order; cleanup failures are attached to the distinct cancelled outcome. Effects completed before cancellation are not rolled back.

This is a structured fixture protocol, not a general ownership or borrow checker. It does not yet model aliases, transfer/return, asynchronous suspension, arbitrary destructors, exception classes, branch-sensitive resource paths, or source-to-scope completeness. Profile A rejects resource scopes.


This is a bounded executable semantics experiment, not a selected language semantics. It does not implement parsing, variables/functions/recursion, general effect handlers or row inference, resource lifecycle, concurrency, divergence, or source-to-expression completeness. The deterministic handlers use in-memory fixtures and do not access the host filesystem or network.

See [RT-03/RT-04 cross-profile trace findings](../../RT-04-RT-03-CROSS-PROFILE-TRACES.md) and the [reference-slice tests](test_rt03_reference.py).


## Differential cross-check with a second RT-03 evaluator

`rt03_smallstep.py` is a second evaluator for the bounded RT-03 A/D expression
fragment. Unlike the recursive evaluator, it uses explicit continuation and
value stacks. It does not import `rt03_reference.py`. The differential tests
compare full traces and final fixture stores across hand-written examples and
a generated set of two-write sequences.

Run the full suite from the repository root:

    python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_*.py' -v

This is algorithmic cross-checking, not independent human review or proof:
both implementations share the same exploratory contract and may share
specification mistakes. See [differential test cases](test_rt03_differential.py).


## Bounded recursion and source fuel

[`rt03_recursion_fuel.py`](rt03_recursion_fuel.py) is a small executable cost model for one structural recursive countdown and one self-recursive divergent loop. It counts abstract source transitions (entry, test, decrement, return addition) rather than host instructions. For the countdown, `countdown(3)` returns 3 at fuel 14 and exhausts at fuel 13 before its final addition. The loop exhausts any finite budget; the model keeps possible divergence as separate metadata because this outcome alone cannot prove divergence.

This is not a source parser, termination checker, optimizer, or runtime gas implementation. It does not model effects/resource cleanup or establish a selected fuel semantics. Scenario [36](../../RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) records the prior-art comparison and open compatibility questions.

Keep this source-transition count distinct from Wasmtime-style VM operator fuel, an external wall-time/memory cap, and a verifier harness stopping rule. The runtime/evidence identity for VM metering includes engine version and operator-cost configuration; a verifier timeout should yield incomplete/unknown evidence, not become a source-level program result. Cleanup and prior effects on budget exhaustion remain unmodeled here.

[`rt03_fuel_cleanup.py`](rt03_fuel_cleanup.py) is a separate observation probe: after a visible write and resource acquisition, fuel runs out before the next body step. It compares reserved cleanup allowance, cleanup charged to depleted fuel, and an abortive trap. All preserve the earlier trace; only reserved cleanup releases the resource. This fixed model does not specify real LLMLang behavior or cover cleanup failure/ownership transfer.

[`rt03_fuel_owned_return.py`](rt03_fuel_owned_return.py) crosses that boundary with COR-13's staged versus transfer-first return timing. Under its stated candidate rule, staged return owns a pending handle until normal commit; fuel exhaustion aborts commit and attempts to dispose of the handle, while transfer-first leaves the handle with the caller. The observation records fuel exhaustion, any returned handle, prior effects, attempted or blocked cleanup, and remaining owners independently. Its staged-disposal and cleanup-debt rules are comparison inputs, not selected LLMLang semantics.

[`rt03_fuel_owned_return_audit.py`](rt03_fuel_owned_return_audit.py) reconstructs expected cleanup obligations and owner states from those output fields without reusing the transition code. A direct run audited eight selected finite cases and found no missing/duplicated owner entry, unaccounted blocked cleanup, or lost prior effect. This is a small independent projection over the prototype's outputs; it does not establish case completeness or source correspondence.

Scenario [36](../../RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) also compares the fuel boundary with COR-07's [`rt03_resource_rules.py`](rt03_resource_rules.py): terminating cleanup failures wrap prior `Result` errors in LIFO order, while cancellation remains a separate outcome with an ordered cleanup-error list. That model does not charge cleanup fuel or allow cleanup to diverge. A separate two-frame command probe informed the Scenario 36 note; no full test suite was run for this comparison.

[`rt03_cleanup_fuel_stack.py`](rt03_cleanup_fuel_stack.py) compares a shared cleanup-fuel pool to a fixed reserve per scope across a two-resource LIFO unwind. With inner cost 3 and outer cost 1, shared reserve 3 leaves the outer cleanup blocked; reserve 4 completes both. Per-scope reserve 3 completes both with 6 reserved and 4 spent. A failed inner cleanup consumes its cost, leaves that resource retained, and permits outer cleanup to continue when fuel remains. The probe assumes bounded terminating cleanup actions.

## Real solver timeout isolation (Scenario 103)

[`rt03_bounded_solver_worker.py`](rt03_bounded_solver_worker.py) starts one POSIX worker per query, waits until SymPy is imported, then enforces a wall-clock deadline around a generated pigeonhole query. A 12-pigeon/11-hole DPLL2 query times out at 0.5 seconds; the parent kills and reaps the worker and reports `UNKNOWN` with no model. A completed UNSAT answer from this worker remains untrusted in the path-result classifier and cannot prune a may-path. This experiment has no memory or concurrent-worker limit and does not validate a persistent worker pool.

Focused tests, including the real deadline case:

    python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt03_bounded_solver_worker.py' -v

## Mutable predicate identity (Scenario 104)

[`rt03_mutable_predicate_identity.py`](rt03_mutable_predicate_identity.py) compares two concrete initial states with three path formulas for sequential `if x`, `x := not x`, `if x`: one symbolic name reused across reads, independent state versions, and state versions tied by the update relation. Reusing the name prunes the two concrete routes; independent versions admit two extra routes; the explicit toggle relation matches the concrete route set. The exhaustive four-case comparison is in [`test_rt03_mutable_predicate_identity.py`](test_rt03_mutable_predicate_identity.py). Aliasing, calls, loops, and source extraction remain open.

## Call mutation summaries (Scenario 105)

[`rt03_call_mutation_summaries.py`](rt03_call_mutation_summaries.py) exhausts the pre-call/post-call Boolean state relation for complete pure, complete toggle, and may-write/unknown summaries. A complete summary yields the exact two-route set; incomplete effects conservatively allow all four state-pair routes. Reusing one symbolic name across an unknown call drops the crossed routes. Tests are in [`test_rt03_call_mutation_summaries.py`](test_rt03_call_mutation_summaries.py). These summaries are hand-authored; alias/call graph analysis and source binding are not implemented.

## Field-sensitive call-site aliases (Scenario 106)

[`rt03_alias_sensitive_call_paths.py`](rt03_alias_sensitive_call_paths.py) compares a call that toggles a referenced Boolean field under exact `flag`, exact disjoint `other`, may-alias, and unknown target sets. Exact target evidence preserves precise route sets; may-alias and incomplete sets union transitions, while incorrectly assuming no alias drops reachable routes. Five focused tests are in [`test_rt03_alias_sensitive_call_paths.py`](test_rt03_alias_sensitive_call_paths.py). This models a finite target relation, not a points-to analyzer.

## Source-derived call aliases (Scenario 107)

[`rt03_source_alias_extraction.py`](rt03_source_alias_extraction.py) recognizes a bounded Python-shaped AST subset, extracts the `ref.value = not ref.value` toggle summary, propagates reference targets across assignments, and unions targets at branch joins. Its concrete fixture interpreter enumerates Boolean inputs and unknown-reference targets over the same two-field region. Eight tests cover exact/disjoint references, may-alias joins, unknown references, a correlated join that overapproximates, an omitted-target counterexample, and fail-closed handling of unsupported mutations/fields. The analyzer keeps all concrete routes in this subset; its non-relational join loses alias/value correlation. This is not an LLMLang parser, a source-to-CFG completeness result, or a general points-to analysis. Run with `python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt03_source_alias_extraction.py' -v`.

## Path-sensitive alias precision (Scenario 108)

`execute_path_sensitive_summary` enumerates the two-field Boolean input domain, follows source branches, propagates exact reference targets per valuation, and applies the extracted toggle summary. In the value-correlated fixture it returns exactly two concrete routes where the joined may-alias analysis allows four; for an independent alias choice it preserves all four. Ten focused tests compare the joined and enumerated analyses with the fixture executor. This is a finite exact enumerator with a shared grammar and semantic contract, not a scalable symbolic analysis or independent proof of source completeness.

## Optional presence at a serialization boundary (Scenario 109)

[`optional_presence_model.py`](optional_presence_model.py) and [`test_optional_presence_model.py`](test_optional_presence_model.py) model absent, explicit JSON `null`, integer value, decode failure, and uninitialized read as distinct fixture outcomes. Under the documented mapping, one-level optional collapses absent/null, while nested optional and a presence bit plus nullable payload preserve all three valid field states over JSON round-trip. Decode failure remains an outer error. Eight focused tests pass. This is a one-field integer JSON fixture, not an LLMLang serializer, schema, ABI/layout, or representation decision.

## Wire schema evolution and defaults (Scenario 110)

[`schema_evolution_model.py`](schema_evolution_model.py) and [`test_schema_evolution_model.py`](test_schema_evolution_model.py) compare v1/v2 JSON producers and consumers around an added defaulted Boolean field. The 16-case producer/consumer, unknown-key, and default product shows old payloads can use the new default, while new payloads can be rejected by strict old consumers or accepted with information loss by consumers that ignore unknown keys. Changing the default changes old payload interpretation; an explicit value is stable, and null handling is a separate policy. Six focused tests pass. This is a finite compatibility policy fixture, not a schema standard, real serializer, ABI test, or LLMLang rule.

## Unknown wire variants (Scenario 111)

[`unknown_variant_model.py`](unknown_variant_model.py) and [`test_unknown_variant_model.py`](test_unknown_variant_model.py) compare reject, generic fallback, and opaque-preserve handling when an older consumer receives a new enum case. Reject stops decoding; fallback enables a generic result but loses the case and payload; preserve retains the parsed JSON object so a relay can forward it. Re-encoding preserves JSON structure, not original bytes or whitespace. Malformed known cases remain errors. Seven focused tests pass. This does not implement source-level open enums, exhaustiveness, signatures, or application-level safe behavior.

## Scheduler fairness witnesses (Scenario 112)

[`scheduler_fairness_model.py`](scheduler_fairness_model.py) replays a continuously enabled starvation self-cycle and an intermittently enabled starvation cycle. The first violates weak and strong fairness; the second satisfies weak fairness but violates strong fairness. A fixed two-task round-robin check gives B a selection within one A turn only when both tasks remain runnable and each step returns. Five tests cover the cycles, bound, and invalid witnesses. This is an abstract finite model, not a runtime scheduler or an unbounded liveness proof.
## Store buffering memory orders (Scenario 113)

The prototype enumerates global sequentially consistent orders and independent per-location observations for the two-thread store-buffering litmus. The independent profile admits both reads seeing zero. It also includes isolated fixtures for stipulated synchronization, release sequences, fences, and all four coherence rules on one atomic object. Twelve focused tests cover these relations. [Prototype](rt04_store_buffering.py) · [Coherence fixtures](../../RESEARCH-SCENARIO-117-ATOMIC-WRITE-READ-COHERENCE.md)

## Atomic execution relations (Scenario 118)

The enumerator derives modification order, read-from, happens-before, and values for fixed atomic load and store sequences. An independent sequential interleaving oracle matches the global-order witnesses in all 4,096 layouts. The weaker relation permits additional read values in 98 layouts. [Enumerator](rt04_atomic_execution.py) · [Test cases](test_rt04_atomic_execution.py) · [Results and scope](../../RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md)
