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

The prototype is an in-memory model. It is not a production persistence layer, language frontend, compiler, or formal verifier.

See [the experiment report](../../PROTOTYPE-01-RESULTS.md) for measured results, interpretation, and limitations.
