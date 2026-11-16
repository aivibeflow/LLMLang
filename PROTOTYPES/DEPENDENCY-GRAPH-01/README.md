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

## Business intent to formal contract experiment

`src/business_intent.py` models immutable intent sources, explicit clarification decisions, caller-scoped business rules, provenance-carrying formal clauses, candidate acceptance gates, effective-date examples/counterexamples, and a two-caller tax-policy evolution scenario. It demonstrates that changing one caller's business rule can change only that caller's selected semantic value while leaving a generic callee contract and another caller unchanged.

Run the focused experiment tests:

```bash
python -m unittest discover -s tests -p 'test_business_intent.py' -v
```

See [Prototype 16 Results](PROTOTYPE-16-RESULTS.md) and [Research Scenario 15](../../RESEARCH-SCENARIO-15-BUSINESS-INTENT-TO-FORMAL-CONTRACT.md). This is not a natural-language parser, authorization system, formal logic engine, or source-code proof.

## Typed Requirement IR experiment

`src/requirement_ir.py` models typed predicates, requirement ownership/scope, source and decision provenance, triggers, actions, temporal metadata, assumptions, unresolved questions, and explicitly required dimensions. It checks types and provenance, detects contradictions and selected underdetermination cases over finite domains, generates satisfying and violating scenarios, and checks caller-policy ownership against explicit callee policy inputs.

Run the focused experiment tests:

```bash
python -m unittest discover -s tests -p 'test_requirement_ir.py' -v
```

See [Prototype 17 Results](PROTOTYPE-17-RESULTS.md) and [Research Scenario 17](../../RESEARCH-SCENARIO-17-TYPED-REQUIREMENT-IR.md). The analyzer is finite-domain only; temporal fields are metadata, not evaluated temporal logic. It is not a natural-language parser or implementation proof.

## Requirement evolution and semantic impact experiment

`src/requirement_evolution.py` models immutable requirement revisions, snapshot-local selection keys, hash-relevant semantic dependency edges, separate lineage/provenance records, direct/transitive impact, verification-key changes, split/merge, and three-way concurrent branch merging.

Run the focused experiment tests:

```bash
python -m unittest discover -s tests -p 'test_requirement_evolution.py' -v
```

See [Prototype 18 Results](PROTOTYPE-18-RESULTS.md) and [Research Scenario 18](../../RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md). This is not a semantic-diff engine, complete impact planner, authorization system, or distributed transaction.

## Semantic impact planning and dependency completeness experiment

`src/impact_planning.py` audits whether independently observed dependency identities are covered by declared dependencies within an exact artifact/scope/evidence binding. It distinguishes GAP_FOUND, SUPPORTED_WITHIN_SCOPE, UNKNOWN, and NOT_CHECKED. It maps impacted artifact kinds to typed actions and forces HUMAN_REVIEW + FULL_REVALIDATION when completeness is not supported within scope. A no-action decision requires a matching PROVEN non-interference certificate record; the prototype checks binding only and does not verify the proof.

Run the focused tests:

```bash
python -m unittest discover -s tests -p 'test_impact_planning.py' -v
```

See [Prototype 19 Results](PROTOTYPE-19-RESULTS.md) and [Research Scenario 19](../../RESEARCH-SCENARIO-19-IMPACT-PLANNING-AND-DEPENDENCY-COMPLETENESS.md). This is not a dependency extractor, runtime tracer, proof checker, or action executor.

## Dependency discovery and semantic classification experiment

`src/dependency_discovery.py` models evidence-bearing dependency candidates from explicit declarations, static analysis, dynamic tracing, sandboxing, and proof analysis. Candidates require explicit semantic classification before entering the hash-relevant dependency set. Unknown candidates block a completeness claim. The module consumes normalized observations; it does not implement the discovery tools.

Run the focused tests:

```bash
python -m unittest discover -s tests -p 'test_dependency_discovery.py' -v
```

See [Prototype 20 Results](PROTOTYPE-20-RESULTS.md) and [Research Scenario 20](../../RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md).

## Counterfactual dependency analysis experiment

src/counterfactual_analysis.py compares normalized repeated baseline/treatment execution records for one declared input factor. It distinguishes reproducible observable effects from trace-only changes, no observed difference, and inconclusive experiments. No observed difference is not proof of irrelevance.

Run focused tests with:
python -m unittest discover -s tests -p 'test_counterfactual_analysis.py' -v

See PROTOTYPE-21-RESULTS.md and Research Scenario 21.

## Coverage-guided dependency discovery experiment

`src/coverage_guided.py` generates typed finite-domain single-factor and t-way interventions, adds integer-extrema and optional static/taint guidance targets, deduplicates candidates by pinned artifact/context/observation-model identity, and schedules candidates with deterministic greedy set cover under a run budget. The coverage ledger preserves uncovered targets. It does not execute the program or prove dependency completeness; multi-factor execution still needs an extension to Scenario 21's single-factor comparison API.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_coverage_guided.py' -v
```

See [Prototype 22 Results](PROTOTYPE-22-RESULTS.md) and [Research Scenario 22](../../RESEARCH-SCENARIO-22-COVERAGE-GUIDED-DEPENDENCY-DISCOVERY.md).


## Multi-factor counterfactual analysis experiment

`src/multifactor_analysis.py` provides separate APIs for repeated paired joint interventions and repeated 2×2 factorial interaction analysis. Numeric outcomes use difference-in-differences; categorical outcomes use limited conditional equality patterns. It consumes normalized run records and does not execute programs or prove dependency completeness.

Run focused tests:

```bash
python -m unittest discover -s tests -p 'test_multifactor_analysis.py' -v
```

See [Prototype 23 Results](PROTOTYPE-23-RESULTS.md) and [Research Scenario 23](../../RESEARCH-SCENARIO-23-MULTI-FACTOR-COUNTERFACTUAL-ANALYSIS.md).
