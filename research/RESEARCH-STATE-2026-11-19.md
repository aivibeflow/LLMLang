# LLMLang Research State — 2026-11-19

**Status:** Research state and next-work register; not a language decision or normative specification.  
**Branch:** `codex/save-research-state-2026-11-19`  
**Purpose:** Preserve an evidence-linked snapshot that makes the current research corpus reviewable and identifies the gates before integrated candidate scoring and an RFC.

## 1. Current position

The research corpus has moved from broad proposals toward bounded, evidence-bearing comparisons. The [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md) is the current integration point. It compares candidate bundles but deliberately selects none. The [Research Taxonomy](RESEARCH-TAXONOMY.md) remains the coverage register; neither is normative.

The strongest evidence is concentrated in language semantics, type/resource boundaries, identity/change lifecycle, package/build behavior, and bounded authorization:

| Area | Evidence available | Establishes | Does not establish |
|---|---|---|---|
| RT-01 workloads | Reference workload catalogue and executable CLI pilot with Python/C references | Shared concrete workloads and host-level observable behavior | LLMLang usability, workload weights, or performance versus candidate language profiles |
| RT-03/04 semantics | [Shared corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md), bounded evaluators and fixture families COR-01–13, plus [Scenario 36](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) | Distinguishing observations for errors, effects, state, cancellation, cleanup, typed calls, actor schedules, and one resource-return boundary; prior-art comparison of recursion/effects/runtime limits, abstract source-fuel and fuel/cleanup probes, a derived fuel × owned-return matrix, and the distinction between source fuel, VM operator gas, and host/evidence limits | Complete source semantics, sound surface type system, general ownership model, LLMLang recursive evaluator/effect inference, cross-product evaluator for fuel and ownership transitions, or validated concurrency runtime |
| RT-05 identity | Lifecycle, call-site refactoring, recursive group identity experiments | Counterexamples and trade-offs for continuity, call obligations, symmetric members, and change propagation | Canonical identity envelopes, authenticated lineage, import/merge completeness, or final Stable ID/value model |
| RT-06/20 dependencies | Scenario 15–34 studies and dependency/impact prototypes | Bounded dependency classification, counterfactual analysis, symbolic proof boundary, and plan/change lifecycle structures | Complete source dependency extraction, graph-completeness proof, or end-to-end accepted change correctness |
| RT-07/08 evidence | Lean/Logos CPC parser binding, strict QF_LIA relational query, source-to-query correspondence work | Exact binding and kernel-checked results for a declared narrow integer/boolean relational fragment | Proof of arbitrary LLMLang programs, complete evidence trust chain, or coverage of effects/resources/concurrency |
| RT-09/10/13 execution | Compiler/backend, LLVM, POSIX and runtime architecture proposals | Candidate boundaries and hazards worth testing | Selected execution model, backend equivalence, ABI, or measured feasibility |
| RT-11 incremental build | [Binding invalidation benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md) | In its synthetic C fixture, separate stable-ABI linkage reduces caller recompilation on an implementation-only edit | General LLMLang cache safety, real-language speedup, or validated action-key projection |
| RT-12 package/reuse | Package identity, manifest/index models, merge/closure/archive prototypes | Deterministic logical-index and exact-hash dependency behavior within prototype fixtures | Normative wire/archive format, multi-provider behavior, production store snapshot guarantees, or registry trust |
| RT-14/16/19/20–23 workflow/security | Toolchain/workflow proposals, Toolchain prototype, RT-16 threat model and authorization fixtures | Lifecycle boundaries, scoped authorization properties, replay cases, bounded workspace/change-set behavior | Production concurrency, sandbox security, signed evidence, full recovery, or final approval policy |

The latest bounded type/semantics results include a counterexample: transfer-first cleanup failure can require returning both an error and a still-owned value. The current typed-call/checker boundary cannot express that envelope. Effect summaries also lose ordering and payload details, and an open-row marker does not implement row unification or handler-coverage analysis. See COR-13 and the cross-profile comparison in the shared corpus and option matrix.

## 2. Candidate vectors still open

The current matrix keeps these integrated candidates for comparison:

- **C1 — Verifiable pure-first language:** pure strict core, explicit effects/capabilities, reference semantics first, later native backend.
- **C2 — Systems language with explicit ownership:** ordered mutation and ownership/borrowing, with a conservative verification boundary.
- **C3 — Isolated concurrent language:** message/protocol types with trace and model-checking evidence.
- **C4 — Effectful functional language:** immutable functional core with explicit handlers and effectful runtime boundaries.

These are candidate bundles, not exhaustive specifications. No vector has passed the complete compatibility gates.

## 3. Cross-area constraints supported by current evidence

1. **RT-03 and RT-04 must be compared together.** Equal scalar outputs do not imply equal observable traces. State-handler logging/rejection and actor delivery order provide counterexamples.
2. **Effects need more than a set of effect names.** Ordering, payloads, handler behavior, terminal outcomes, and environmental inputs can change observations and evidence reuse.
3. **Resource cleanup and ownership cross call boundaries.** Cleanup precedence, failure, transfer, and retained values need one outcome model before ownership or error constructors can be frozen.
4. **Identity, compatibility, and behavior are distinct.** Contract conformance does not imply equivalence suitable for inlining; recursive group identity creates caller invalidation; continuity requires explicit lifecycle evidence.
5. **Proof claims must name their exact fragment and inputs.** The QF_LIA/Lean work validates a narrow relational-query pipeline, not general source programs.
6. **Runtime/backend claims need a shared preservation gate.** Architecture proposals and C compiler experiments do not establish that multiple LLMLang backends preserve one source semantics.
7. **Content integrity is not trust.** Hashes do not identify an authorized publisher, verifier, approver, or trusted evidence producer.
8. **Unknown is a research result, not a numeric failure score.** Candidate scoring must expose unknowns and test sensitivity to workload weights.

These refine existing dependency hypotheses; they do not add normative rules. See [Research Dependency Map](RESEARCH-DEPENDENCY-MAP.md), especially the RT-03/04, RT-05/06/07/08, RT-09/10/13, RT-11/12, and RT-14/16/19/20 edges.

## 4. Research gates before RFC synthesis

### Gate A — Shared source-level semantics and type/resource boundary

- Define source-level rules for calls, branches, Result/error propagation, cancellation, resource acquire/use/release, transfer/return, and cleanup failure.
- Make ordered effects and payloads visible to type/dependency summaries.
- Add a typed owned-value return scenario for COR-13.
- State where profiles differ and what equivalence means for results, traces, resource state, and divergence.
- Compare total recursion, general partiality, typed divergence, source fuel, VM operator gas, and external limits; define how exhaustion interacts with effects, rollback, and cleanup.
- Record independent review; parallel evaluators against one hand-authored contract are implementation checks, not independent specification validation.

### Gate B — Identity and dependency completeness

- Compare R-A/R-B/R-C on common import, rename, move, duplicate, split/merge, recursive, call-site edit, and branch-conflict cases.
- Specify exact call/contract/implementation bindings and which observations each artifact hash commits to.
- Validate dependency extraction against source mutations, including negative and fallback lookups.
- Preserve conservative UNKNOWN wherever completeness or provenance is absent.

### Gate C — Evidence and backend preservation

- For each evidence class, record proposition, assumptions, exact source/tool/target inputs, producer identity, trust boundary, soundness claim, and reuse rule.
- Extend the two-backend gate to an executable shared workload; compare outputs, effects, errors, resources, diagnostics, and rejected constructs against reference semantics.
- Keep proof coverage narrow and explicit; unsupported constructs must not inherit proof status.

### Gate D — Workload and human/agent evaluation

- Run reference workloads on candidate implementations when available.
- Define workload weights before aggregate scoring. Publish sensitivity results.
- Measure authoring success, repair attempts, diagnostics, context/token use, and scope violations in controlled agent tasks.
- Keep usability and correctness evidence separate.

### Gate E — Security and operational lifecycle

- Exercise authorization with persistent concurrent clients and crash injection around apply/accept/commit/push/publication.
- Establish sandbox behavior for filesystem, network, credentials, process lifetime, and resource exhaustion.
- Define authenticated evidence and package provenance separately from content hashing.
- Validate worktree isolation and recovery on interrupted operations.

## 5. Suggested next sequence

1. Close Gate A with a narrow source-level owned-resource call boundary, ordered effect summary, and recursive termination/budget semantics.
2. In parallel only where independent, continue Gate B with identity/import completeness and Gate E with persistent authorization/sandbox experiments.
3. Select a small cross-profile executable slice only after Gate A rules are explicit; keep RT-03 alternatives separate in the harness.
4. Run reference semantics and a second implementation/backend against that slice.
5. Update the option matrix with measured outcomes and confidence; do not score candidates while major criteria remain unknown.
6. Draft an RFC only after candidate vectors have explicit compatibility results, failed/unknown cases, and workload-weight sensitivity.

This is planning, not approval of a semantic profile. A scoped RFC may be possible earlier if it labels unresolved parts and does not imply a complete language selection.

## 6. Evidence quality and traceability

For each new result, retain exact branch/commit, files, command and tool versions, fixture selection, assumptions, positive/negative cases, limitations, evidence class, and the vector it could falsify. Update the taxonomy and option matrix when scope changes. Keep decisions in [TODO and open decisions](../TODO.md) open until explicitly accepted.

## 7. References

- [Research Option Matrix 01](RESEARCH-OPTION-MATRIX-01.md)
- [Research Taxonomy](RESEARCH-TAXONOMY.md)
- [Shared Semantics Corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md)
- [RT-05 Identity Lifecycle Experiment](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md)
- [RT-05/RT-20 Call Site Refactoring Experiment](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md)
- [RT-05 Recursive Identity Experiment](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md)
- [RT-11 Binding Invalidation Benchmark](RT-11-BINDING-INVALIDATION-BENCHMARK.md)
- [RT-16 Threat Model 01](RT-16-THREAT-MODEL-01.md)
- [TODO and open decisions](../TODO.md)
