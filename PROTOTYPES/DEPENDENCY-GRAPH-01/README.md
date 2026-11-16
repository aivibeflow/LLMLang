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

## Combined project-state persistence

`src/project_state.py` composes graph and binding-snapshot documents into one deterministic, checksummed envelope. It validates each embedded document on reload. This is not a multi-writer transaction or database. See [Research Scenario 11](../../RESEARCH-SCENARIO-11-ATOMIC-PROJECT-BINDING-PERSISTENCE.md).

## Layered build / deployment / execution identities

`src/execution.py` models BuildSnapshot, BuildArtifact, DeploymentSnapshot, ExecutionSnapshot, ReleaseManifest, and compare-and-swap publication of a mutable release-channel head. See [Research Scenario 12](../../RESEARCH-SCENARIO-12-PROJECT-BUILD-DEPLOYMENT-EXECUTION.md).

## Scoped implementation binding

`src/scoped_binding.py` models project, tenant, and request binding layers with explicit precedence and override permissions. It pins the resolved binding decision. See [Research Scenario 13](../../RESEARCH-SCENARIO-13-MULTI-LEVEL-BUSINESS-RULE-AND-IMPLEMENTATION-BINDING.md).

## Behavioral contract refinement experiment

`src/contract_model.py` defines a finite observable-trace model and checks whether every modeled implementation trace is allowed by a contract. It distinguishes PROVEN, DISPROVEN, and UNKNOWN. PROVEN applies only when both finite models explicitly declare complete semantics; this is an exhaustive proof of the finite model, not a proof that arbitrary source code conforms to that model.

See [Research Scenario 14](../../RESEARCH-SCENARIO-14-FORMAL-BEHAVIORAL-CONTRACTS-AND-REFINEMENT.md).
