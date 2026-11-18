# RT-04 Prototype 01 — Two Candidate Checker Vectors

Python 3.10+, standard library only.

Run from this directory:

    python -m unittest -v

## Scope

The model compares two declaration-level checker profiles:

- **A:** primitive types, closed effect vocabulary, ambient capability context, no static affine-use check.
- **B:** positive-integer refinement experiment, effect-row annotations, transitive capability propagation, affine resource consumption.

Both profiles compute fixed-point summaries of direct/transitive effects and capabilities. Profile B supports two deliberately small resource-use inputs: a linear `consumes` sequence and an explicit control-flow graph (`resource_flow`). The CFG model propagates exact sets of consumed resources along reachable paths, rejects repeated consumption, and requires all paths reaching a join to agree on each resource's available/consumed state. Its finite state space converges on cycles.

The model accepts function declarations and supplied call/control-flow edges; it does not parse LLMLang source, discover calls or branches, execute functions, prove graph completeness, or implement runtime authorization.

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

## Limitations

This is an experiment about checker obligations, not a language decision:
- effect-row syntax is only an annotation; row unification and handlers are not implemented;
- type checking is limited to primitive names and one positive-integer predicate;
- resource dataflow uses explicit CFGs and exact finite path-state sets; it does not model source branch discovery, symbolic path conditions, borrows, lifetimes, async suspension, returns, destructors, or cleanup behavior;
- terminal paths are not required to consume the same resources unless they later join;
- capability propagation checks declared call graphs, not actual runtime authority;
- fixed-point summaries assume the supplied call graph is complete;
- no SPG schema, hash envelope, ABI, compiler, or runtime is defined.

See [RT-04 Prototype 01 Results](../../RT-04-PROTOTYPE-01-RESULTS.md).
