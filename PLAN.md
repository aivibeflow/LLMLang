# LLMLang Project Plan

**Updated:** 2026-11-17

This file tracks project-level work that is not yet fully specified in the draft language definition. Research reports and ADRs record evidence and architectural decisions; this plan records execution status and next steps.

## Current workstreams

| Workstream | Status | Outcome / next step |
|---|---|---|
| Git representation and semantic merge research | **Completed** | Report: [research/GIT-SEMANTIC-REPOSITORY.md](research/GIT-SEMANTIC-REPOSITORY.md). ADR-014 records the current Proposed direction; implementation remains deferred until whole-specification synthesis. |
| Git-backed source representation | **Research completed; implementation deferred** | Research direction is recorded in ADR-014; revisit the implementation shape after cross-aspect research and whole-specification comparison. |
| Semantic identity and hashing | **Research in progress** | Investigate canonicalization, semantic identity, hash boundaries, and invalidation as part of the wider research programme; avoid locking the implementation before cross-aspect synthesis. |
| Semantic diff and three-way merge | **Research completed at concept level; implementation deferred** | Preserve the researched merge vectors and constraints; revisit detailed design after the integrated specification direction is selected. |
| Git integration | **Deferred** | Prototype only after the relevant representation, identity, and merge choices have been evaluated together with the other LLMLang aspects. |
| Merge evaluation | **Deferred** | Define evaluation scenarios during research; run implementation benchmarks after a coherent specification candidate is selected. |


## Research program and specification design space

The project must not treat an individual research report as producing one mandatory answer. Each research may identify multiple promising development vectors (approaches, design choices, or internally coherent option families), including their assumptions, trade-offs, constraints, evidence, and unresolved questions.

The objective of the research phase is to investigate all relevant aspects of LLMLang before committing to a single integrated design. Research conclusions are inputs to a later synthesis process, not isolated decisions that must be selected independently as soon as a report is completed.

### Required output of each research

Each research report should, where applicable, provide:

- A clearly scoped aspect of LLMLang and the questions investigated.
- Multiple viable development vectors rather than only a single preferred recommendation.
- For each vector: core principles, assumptions, benefits, costs, risks, limitations, and evidence.
- Compatibility requirements, constraints, and known incompatibilities with other aspects.
- Upstream dependencies (decisions or capabilities this aspect relies on) and downstream impact (other aspects it can constrain or change).
- Open questions and confidence/evidence level; distinguish established facts from hypotheses and recommendations.

A report may conclude that only one viable vector is currently known, or that more research is needed. Do not manufacture alternatives merely to fill a list.

### Cross-aspect dependency model

Maintain an explicit dependency map across research topics and design aspects. Record at least:

- **Requires:** one aspect or vector depends on another.
- **Constrains:** a choice narrows the viable choices elsewhere.
- **Influences:** a choice changes trade-offs or design parameters elsewhere without making them impossible.
- **Conflicts with:** two choices cannot coexist under the stated assumptions.
- **Enables:** a choice makes another capability or vector practical.

Dependencies must identify their direction, rationale, affected vectors, and whether the relationship is confirmed or still a hypothesis. Use the map to identify foundational topics, downstream topics, feedback loops, and research that can proceed in parallel. Revisit dependency edges when new evidence changes assumptions.

### Order for conducting research

Research order should be dependency-driven, not simply the order in which topics were proposed. First investigate foundational concepts that can alter the shape of many other decisions; then investigate dependent mechanisms; finally investigate integration and operational concerns. A provisional ordering is:

1. **Goals, constraints, and semantic foundations:** language purpose, target users and workloads, correctness model, observable guarantees, compilation/execution model, and core semantic entities.
2. **Program representation and identity:** graph and source representation, canonicalization, stable identity, semantic hashing, persistence, versioning, and reproducibility.
3. **Core language semantics:** type system, effects, ownership/resource model, modules/interfaces, evaluation and execution semantics, errors, and concurrency.
4. **Specification and verification model:** contracts, invariants, refinement, proof obligations, solver/prover integration, test generation, and the boundary between static guarantees and runtime checks.
5. **AI-native authoring and change model:** structured edits, agent/compiler protocol, validation boundaries, provenance, reviewability, and deterministic acceptance.
6. **Build, incremental computation, and tooling:** dependency/action model, caching and invalidation, compiler pipeline, diagnostics, editor/tool interfaces, and reproducible builds.
7. **Version control and collaboration:** Git representation, semantic diff/merge, conflict policy, branching, and multi-user/concurrent change workflows.
8. **Runtime, deployment, interoperability, and ecosystem:** target platforms, FFI, package/dependency model, security/isolation, distribution, and operational constraints.

This is a starting dependency hypothesis, not a rigid serial schedule. Build the dependency map early and use it to reorder or split topics. Independent subtopics should run in parallel; a downstream research may start with explicit provisional assumptions, but must be revisited if an upstream result invalidates them. Avoid premature implementation commitments where unresolved foundational choices could cause rework.

### Synthesis: from research vectors to complete specifications

After the relevant research topics have been completed:

1. Normalize the vectors into a common decision/option model, preserving source links to the research evidence.
2. Identify which vectors are mutually compatible, conditionally compatible, dependent, or conflicting.
3. Construct the Cartesian product of the viable vector sets to enumerate candidate LLMLang specifications. The raw Cartesian product is the starting combinatorial space; remove or mark combinations that violate explicit dependency and compatibility constraints rather than silently treating every combination as valid.
4. Preserve traceability from every candidate specification choice to the research report, evidence, assumptions, and dependency edges that justify it.
5. Compare candidate specifications as integrated wholes, not merely as isolated alternatives for one question. Evaluate system-level properties such as coherence, correctness, expressiveness, simplicity, implementation feasibility, performance, incremental behavior, AI-agent usability, interoperability, and long-term evolvability.
6. Use pairwise or local decision analysis only as diagnostic tools; the primary comparison and selection unit is the complete candidate specification and its cross-aspect consequences.
7. Record the evaluation criteria, scenarios, evidence, uncertainty, and trade-offs so that rankings are explainable and can be revised when research changes.

The full product may be too large to materialize naively. If so, use dependency constraints, equivalence classes, staged enumeration, or representative sampling, while documenting what was pruned and why. Do not lose promising vectors solely because exhaustive enumeration is computationally impractical.

### Research programme status

| Stage | Status | Exit condition |
|---|---|---|
| Define research taxonomy and dependency map | **Completed** | [Research taxonomy](research/RESEARCH-TAXONOMY.md) and [cross-aspect dependency map](research/RESEARCH-DEPENDENCY-MAP.md) establish 18 research areas, 35 initial dependency edges, feedback loops, and research waves. |
| Conduct and complete aspect research | **In progress** | Existing Scenarios 15–34 cover a substantial requirements/dependency/formal-verification line. Expand coverage of the complete semantic core, type/effect/ownership model, security, and other identified gaps; capture vectors and dependency edges in each report. |
| Normalize vectors and validate compatibility | **Planned** | Define a common option schema and validate conditional compatibility constraints after sufficient research coverage exists. |
| Generate candidate specification space | **Planned** | Valid combinations are enumerated or represented through a documented constrained search space. |
| Compare complete candidate specifications | **Planned** | Integrated candidates are evaluated against shared criteria and representative scenarios. |
| Select and baseline a specification direction | **Planned** | A coherent candidate is selected with rationale and unresolved risks recorded; only then proceed to detailed specification baseline and implementation commitments. |


## Completed

- [x] Establish the research taxonomy and initial cross-aspect dependency map; define research waves and parallelism guidance.

- [x] Research Git object storage, content-addressed semantic stores, semantic diff/merge approaches, and Git integration mechanisms.
- [x] Save the full research report in `research/GIT-SEMANTIC-REPOSITORY.md`.
- [x] Extract the architectural decision into [ADR-014](docs/adr/014-git-semantic-merge.md).

## Next research priorities

1. Research the complete core language semantic model, including values, evaluation, state, errors, determinism, and observable behavior; distinguish viable semantic models rather than assuming the concept document is final.
2. In parallel, research type-system, effects, ownership/resource, capability, and concurrency alternatives, recording explicit dependencies on the semantic model.
3. Continue the separate Lean/Logos/QF_LIA formal-verification line; connect its results to the taxonomy without treating the narrow proof fragment as the full language semantics.
4. Audit security/trust assumptions across the compiler, runtime, LLM development interface, package/artifact store, and proof pipeline.
5. For every new report, record candidate vectors and affected DEP edges before marking the research complete.

## Next acceptance gate

The Git-representation workstream is ready to move beyond research when the prototype demonstrates all of the following:

1. A clean checkout can reconstruct the semantic graph from repository source and pinned dependencies without relying on an irreplaceable local KV cache.
2. Formatting-only changes and file moves preserve semantic identity where the language rules say they are non-semantic.
3. A semantic change changes the relevant semantic hash and invalidates only computations whose exact action inputs depend on it.
4. Three-way merge is deterministic for identical base/ours/theirs inputs and policy versions.
5. Ambiguous or unsafe merges fail closed and report structured conflicts.
6. A completed Git merge passes repository-wide graph and reference validation.

## Planning notes

- ADR-014 is **Proposed**, not accepted as an irreversible final architecture. Revisit it after prototype evidence.
- A Git merge driver is an initial integration point, not proof that a multi-file graph merge is complete.
- Do not make the external KV store the only recoverable source of program meaning.
