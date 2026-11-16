# Dependency Graph Prototype 01

Experimental content-addressed semantic dependency graph. Python 3.10+, standard library only.

Run from this directory:

```bash
python -m unittest discover -s tests -v
python -m src.semantic_graph
```

The prototype includes deterministic JSON persistence for semantic values, context-scoped relations, and project snapshots (`src/persistence.py`).

## Contract / implementation bindings

`src/binding.py` adds immutable BindingSnapshots. Callers may depend on contract hashes while a snapshot selects concrete implementations. The snapshot hash changes when the implementation selection changes; execution-sensitive verification keys include that root. Binding rows validate semantic kinds and an exact hash-relevant `implements` dependency. Serialization is deterministic and checksummed.

Run the full test suite with the command above. Binding snapshots currently persist as a separate document; atomic integration with project snapshot persistence, dynamic dispatch, compatibility checking, runtime loading, and formal conformance remain unimplemented. See [Research Scenario 10](../../RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md).
