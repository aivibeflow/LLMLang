# Research Scenario 11: Atomic Persistence of Project and Binding State

**Status:** Research / exploratory; not normative.  
**Date:** 2026-11-16  
**Predecessor:** RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md.

## Question

A binding snapshot is not useful for reproducible project state if it is stored separately and can be paired with a graph snapshot from a different point in time. Can the semantic graph and its implementation selections be persisted as one integrity-checked document without changing the existing graph-store API?

## Proposed envelope

```
ProjectState {
  format
  schema_version
  graph_document
  binding_snapshot_documents[]
  checksum
}
```

The embedded graph document retains its own checksum and schema version. Each binding snapshot retains its own checksum and root hash. The outer checksum commits to the complete project state, preventing accidental mixing or partial replacement of the graph and binding selection.

Loading validates in layers:
1. outer format, schema, and checksum;
2. embedded semantic graph document, including value hashes and project snapshot roots;
3. each binding snapshot, including its checksum, contract/implementation references, and root;
4. duplicate binding snapshot roots.

This is an experimental serialization boundary, not a concurrent database or transaction protocol. Atomic file replacement, locking, crash recovery, and multi-writer coordination remain separate concerns.

## Prototype addition

Prototype 01 adds `src/project_state.py` with deterministic `dumps_project_state` and `loads_project_state`. It composes the existing graph and binding serializers into one envelope and returns the graph store, relations, project snapshots, and binding snapshots after validation.

Tests cover:
- graph + bindings round-trip in one document;
- preservation of graph and binding roots;
- deterministic reserialization;
- outer checksum tampering;
- dangling implementation reference;
- unsupported schema version.

## Important boundary

A project snapshot and a binding snapshot are still distinct immutable objects with separate roots. The project-state envelope commits to both, but this prototype does not yet define whether a project snapshot must reference exactly one binding snapshot, whether several deployment/test bindings may coexist, or how a branch head atomically selects a pair. Those are semantic questions for the next design step.

## Preliminary conclusion

Persisting graph and bindings in one integrity-checked envelope is a useful minimum for reproducible reload. It does not by itself solve atomic concurrent updates or establish that a selected implementation conforms to its contract. A future project-root model should explicitly decide whether binding roots are direct members of the project snapshot or separately selected deployment/execution state.

## Public-interface integration (2026-11-24; proposed)

Extend the project-state candidate envelope to pin the semantic graph, public export catalog, exact provider binding selections, applicable external mappings and required evidence closure as one consistent snapshot. Each logical revision remains immutable and independently identified. Reject mixed revision combinations even when each checksum validates; verify authorization and refinement separately from structural integrity. The original serialization experiment is not evidence of this stronger transaction/admission contract.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This follow-up does not change earlier results or accepted rules.
