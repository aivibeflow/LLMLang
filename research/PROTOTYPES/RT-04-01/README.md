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

This is a bounded executable semantics experiment, not a selected language
semantics. It does not implement parsing, variables/functions/recursion,
general effect handlers or row inference, implicit Result propagation,
exceptions/cancellation, resource lifecycle, concurrency, divergence, or
source-to-expression completeness. The deterministic handlers use in-memory
fixtures and do not access the host filesystem or network.

See [RT-03/RT-04 cross-profile trace findings](../../RT-04-RT-03-CROSS-PROFILE-TRACES.md)
and the [reference-slice tests](test_rt03_reference.py).
