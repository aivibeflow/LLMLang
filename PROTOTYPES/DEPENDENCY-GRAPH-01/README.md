# Dependency Graph Prototype 01

Minimal executable experiment for LLMLang's dependency-driven, content-addressed semantic graph hypothesis.

## Requirements

- Python 3.10+
- Standard library only

## Run

From this directory:

```bash
python -m unittest discover -s tests -v
python -m src.semantic_graph
```

## Persistence experiment

The prototype now includes deterministic JSON serialization and reload:

```python
from src.persistence import save_graph, load_graph

save_graph("graph.json", store, relations, [snapshot])
store2, relations2, snapshots2 = load_graph("graph.json")
```

The format includes a schema version and whole-document SHA-256 checksum. Loading validates semantic value hashes, dependency references, snapshot roots, and selected values. Writes use a temporary file followed by atomic replacement.

This remains an experimental local file format, not a production database or a concurrency-safe multi-process store. See [the experiment report](../../PROTOTYPE-01-RESULTS.md) for results and limitations.
