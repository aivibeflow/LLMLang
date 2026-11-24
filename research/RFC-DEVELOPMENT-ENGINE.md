# RFC: LLMLang Development Engine

**Status:** Draft proposal  
**Scope:** Development tooling and LLM orchestration for LLMLang  
**Related documents:** `LLMLang-CONCEPT.md`, `TOKEN_EFFICIENCY.md`, `RFC-REQUEST-CHANGE.md`

> This document proposes a development environment for LLMLang. It is a design proposal, not a declaration that every described feature or policy has already been accepted.

---

## 1. Summary

LLMLang needs more than a compiler or an AI-enabled editor. Its development environment must coordinate structured program changes, context selection, semantic analysis, independent verification, review, and accepted snapshots.

This RFC proposes the **LLMLang Development Engine (LDE)**: a toolchain and orchestration layer built around the Semantic Program Graph (SPG).

The central principle is:

**LLMs should make semantic proposals; deterministic tools should perform mechanical work and independently check the result.**

LDE has two primary objectives:

1. **Reduce token consumption** by supplying only the context needed for a specific operation, reusing unchanged analysis, and returning compact diagnostics.
2. **Reduce defects** by representing changes structurally, checking their preconditions, analyzing their impact, and verifying them independently of the model that proposed them.

LDE should not depend on a particular model provider. It should expose stable interfaces that can be used by an IDE, CLI, CI system, or an LLM agent.

## 2. Goals

LDE SHOULD:

- make SPG, rather than generated source text, the authoritative representation for supported operations;
- provide a structured API for inspecting and changing SPG entities;
- assemble minimal sufficient context for each LLM operation;
- preserve the distinction between confirmed requirements, assumptions, derived information, and open questions;
- detect stale baselines and semantic conflicts before applying changes;
- calculate the impact of proposed changes;
- perform incremental validation and verification;
- bind verification results to exact content hashes and tool configurations;
- make review, approval, and commit behavior consistent with the Request and Change model;
- expose token, cost, quality, and verification metrics;
- support multiple LLMs and non-LLM clients without changing program semantics.

## 3. Non-goals

The initial LDE is not intended to:

- guarantee that all generated programs are defect-free;
- treat an LLM response as evidence of correctness;
- replace human authority over business meaning and project policy;
- require a large multi-agent system for every task;
- send the complete project graph to a model by default;
- make free-form source-code replacement the primary change mechanism;
- require a distributed architecture or a full graphical IDE for the MVP;
- mandate one specific model provider, protocol, hash algorithm, or formal prover.

## 4. Architectural Overview

LDE is logically divided into six cooperating subsystems. They MAY initially be implemented as modules in one process; the boundaries describe responsibilities, not mandatory deployment units.

```text
 Human / IDE / CLI / CI
          |
   LLM Development Interface
          |
   Request & Workflow Orchestrator
          |
   +------+-------------------------------+
   |                                      |
 Context Planner                     Change Engine
   |                                      |
 Semantic Retrieval                  Semantic Diff
   |                                      |
   +---------------+----------------------+
                   |
             Semantic Engine
                   |
           Verification Engine
                   |
             SPG Store
          + Merkle DAG / Indexes
```

### 4.1 LLM Development Interface

Provides the machine-facing interaction surface for LLMs and agents.

Responsibilities:

- expose typed operations and structured response schemas;
- authenticate the caller and enforce capabilities;
- expose object references and content hashes;
- return concise results and diagnostics;
- allow a caller to request additional context;
- prevent a model from bypassing Change, policy, or commit controls.

The interface SHOULD be model-agnostic. MCP MAY be supported as an adapter, but the underlying semantic API SHOULD not depend on MCP.

### 4.2 Context Planner

Determines the smallest sufficient context for a requested operation.

Responsibilities:

- resolve the target entities and relevant dependencies;
- retrieve linked requirements, contracts, types, effects, tests, proofs, and decisions;
- select a context profile appropriate to the task;
- enforce a token budget;
- identify omitted dependencies and explain why they were excluded;
- record the exact object hashes supplied to the model.

The planner MUST NOT silently omit a dependency known to be required by the selected operation or policy. If the available budget cannot accommodate required context, it SHOULD ask for a narrower task, use staged retrieval, or report that the operation cannot safely proceed.

### 4.3 Change Engine

Manages proposed graph mutations.

Responsibilities:

- validate Change operation schemas;
- check target identity and expected baseline hashes;
- apply proposals to an isolated working snapshot;
- detect stale writes and conflicting changes;
- produce semantic diffs;
- preserve proposal history and provenance;
- prepare a Change Set for verification and review;
- commit only through the authorized workflow.

The Change Engine MUST NOT mutate an accepted snapshot in place.

### 4.4 Semantic Engine

Performs deterministic analysis of the graph.

Responsibilities MAY include:

- structural and reference validation;
- type checking;
- effect and capability checking;
- contract consistency checks;
- state-machine validation;
- dependency and compatibility analysis;
- requirement traceability checks;
- semantic queries and impact analysis.

The engine SHOULD return machine-readable diagnostics with stable identifiers.

### 4.5 Verification Engine

Runs tests, proof checks, and other independent verification tasks.

Responsibilities:

- select checks affected by a Change Set;
- execute checks in controlled environments;
- reuse valid results when all relevant inputs are unchanged;
- invalidate stale results;
- preserve evidence, counterexamples, and execution metadata;
- distinguish passed, failed, unknown, not-checked, and stale outcomes.

The LLM that proposed a change MUST NOT be treated as the independent verifier of that change.

### 4.6 SPG Store and Merkle DAG

Stores immutable content-addressed SPG states and accepted snapshots.

Responsibilities:

- maintain Stable IDs and Content Hashes;
- store immutable entity states;
- maintain typed dependency edges and reverse indexes;
- support graph snapshots and isolated proposal branches;
- support content-addressed retrieval and caching;
- preserve provenance and audit references.

The semantic graph and workflow/audit records MAY use separate physical stores, provided their relationships and consistency rules are explicit.

## 5. Core Data and Identity

LDE adopts the identity model described in `LLMLang-CONCEPT.md`:

- **Stable ID** identifies a logical entity across edits.
- **Content Hash** identifies one exact immutable semantic state.
- A mutation creates a new state and hash while preserving the Stable ID.
- Parent hashes change only when local semantic content or a hash-relevant dependency changes.
- An accepted snapshot is identified by its semantic root hash or defined set of layer-root hashes.

LDE SHOULD distinguish at least:

- accepted snapshots;
- isolated working snapshots;
- Change proposals and Change Sets;
- verification records;
- context packages;
- cache entries;
- audit events.

A context package is not a new source of truth. It is a bounded projection of existing graph data, with references to the exact source hashes from which it was assembled.

## 6. Token-Efficient Context Management

### 6.1 Minimal sufficient context

Context selection SHOULD be operation-specific. A request to explain a public operation does not normally need the full implementation graph; a request to modify an implementation may need its contract, callers, relevant types, tests, and selected implementation dependencies.

The planner SHOULD prefer semantic relationships over broad text search.

Examples:

- For a contract change: the target contract, owning operation, related requirements, affected consumers, and relevant tests.
- For an implementation change: target implementation nodes, applicable contracts, relevant types/effects, callers, and affected tests.
- For a test change: the requirement or behavior under test, scenario definition, test interface, and current implementation reference where needed.
- For an architecture proposal: confirmed requirements, constraints, relevant design decisions, and public interfaces.

### 6.2 Context profiles

The system SHOULD provide named profiles as starting policies, not rigid templates:

| Profile | Typical context |
|---|---|
| Planning | Request, confirmed decisions, constraints, open questions |
| Specification | Business rules, requirements, scenarios, contracts |
| Design | Requirements, interfaces, components, dependencies |
| Implementation | Target implementation, contracts, types, effects, callers |
| Testing | Requirements, scenarios, test interfaces, relevant behavior |
| Audit | Change diff, impact, decisions, diagnostics, verification evidence |

The planner MAY combine profiles or retrieve additional objects when the task crosses boundaries.

### 6.3 Context delta and reuse

Within a session or an explicitly supported context cache, LDE SHOULD avoid retransmitting unchanged content that the model can reliably access.

A hash or Stable ID alone is not a substitute for the underlying content. Context reuse is safe only if the model still has access to the exact earlier content through retained context or an explicit retrieval mechanism. If that guarantee is absent, LDE MUST supply the required content again.

Context reuse MUST be invalidated when any relevant content hash, policy, schema, or other task input changes.

### 6.4 On-demand retrieval

The model SHOULD be able to request additional context by typed reference, query, or dependency relation. LDE SHOULD return only the requested objects and the minimum metadata required to interpret them.

A model's request for more context does not itself grant access. Normal authorization and capability checks still apply.

### 6.5 Compact diagnostics

Diagnostics SHOULD include:

- stable diagnostic code;
- severity and status;
- affected Stable ID and relevant Content Hash;
- concise explanation;
- direct cause or violated rule;
- references to related objects;
- a minimal repair context or counterexample, when available.

Repeated unchanged diagnostics SHOULD be referenced by identifier rather than retransmitted in full. Full logs remain available for human debugging and audit.

## 7. Structured Change Operations

LLMs SHOULD propose typed graph operations rather than rewrite entire files or documents when the target is represented in SPG.

An illustrative operation envelope:

```text
ChangeOperation {
    operation_id
    operation_kind
    target_stable_id
    expected_content_hash
    payload
    preconditions
    request_reference
    rationale
}
```

Possible operation kinds include:

- ADD entity or relation;
- UPDATE semantic fields;
- REMOVE entity or relation;
- REPLACE a typed subgraph;
- LINK or UNLINK a relation;
- INSTANTIATE a template;
- DEPRECATE an entity.

This list is illustrative; the initial API SHOULD implement only operations with well-defined validation and conflict semantics.

### 7.1 Preconditions and stale targets

Each mutation SHOULD identify the expected target state. If the current target hash differs from the expected hash, LDE MUST reject or suspend the operation for conflict resolution. It MUST NOT silently apply the patch to a different state.

### 7.2 Isolation

Proposals are applied to an isolated working graph or equivalent transactional view. The accepted snapshot remains unchanged until commit.

### 7.3 Schema validation

Malformed or ambiguous operations MUST be rejected before semantic application. LDE SHOULD return a concise diagnostic identifying the invalid field or relation.

## 8. Semantic Diff and Impact Analysis

A textual diff is useful for source-oriented artifacts but is insufficient as the primary review representation.

Semantic Diff SHOULD show:

- entities and relations added, changed, or removed;
- old and new semantic values;
- contract, type, state, and effect changes;
- changes to public interfaces;
- changed requirement links and traceability;
- affected consumers and dependent entities;
- tests and proofs that are stale or need rerunning;
- unresolved assumptions and open questions.

Impact analysis MUST distinguish confirmed graph dependencies from heuristic or probabilistic suggestions. Heuristic results MUST be labelled as such.

Before review, LDE SHOULD provide a concise impact summary and allow a reviewer to inspect the full affected subgraph.

## 9. Independent Validation and Verification

### 9.1 Validation layers

Depending on language maturity and project policy, validation MAY include:

1. schema and structural validation;
2. reference and graph integrity checks;
3. type checking;
4. effect and capability checking;
5. contract consistency and verification;
6. dependency and compatibility analysis;
7. requirement traceability checks;
8. test execution;
9. proof validation;
10. build and artifact validation.

Not every project or Change Set must run every possible check. Required checks are determined by the applicable policy and the semantic scope of the change.

### 9.2 Verification status

At minimum, LDE SHOULD preserve distinct statuses:

- `PASSED` — the check completed successfully for its declared scope;
- `FAILED` — the check found a violation or counterexample;
- `UNKNOWN` — the check could not establish either success or failure;
- `NOT_CHECKED` — the check was not run;
- `STALE` — the recorded result no longer applies to the current inputs.

For formal proof results, the language-level vocabulary MAY additionally use `PROVEN` and `DISPROVEN`, as described by the core concept.

Unknown, not-checked, or stale results MUST NOT be displayed or interpreted as success.

### 9.3 Incremental verification

LDE SHOULD use dependency indexes and exact input hashes to determine which checks are affected by a Change Set.

A verification cache key SHOULD include all semantically relevant inputs, including:

- subject and dependency Content Hashes;
- verifier or test runner identity and version;
- relevant configuration;
- target platform or execution environment, where applicable;
- test data or fixture hashes;
- policy and schema versions where they affect the result.

A cached result MAY be reused only when its complete declared input identity matches. A changed relevant dependency MUST invalidate the result or trigger explicit revalidation.

### 9.4 Test selection

Automatic test selection SHOULD be dependency-aware and conservative. The system SHOULD explain why a test was selected or omitted. Project policy MAY require a broader test suite for high-risk or public-interface changes.

A test can verify multiple requirements. LDE MUST rely on explicit traceability links rather than proximity or naming similarity.

## 10. Traceability and Quality Guards

LDE SHOULD provide guards for broken or incomplete relationships across:

```text
Request
  -> Decision / Clarification
  -> Requirement
  -> Contract / Scenario
  -> Design
  -> Implementation
  -> Test / Proof / Verification Evidence
```

Potential diagnostics include:

- confirmed requirement with no required realization link;
- externally observable implementation change with no requirement or approved rationale;
- changed contract with unreviewed consumers;
- requirement missing a test or proof where policy requires one;
- verification evidence tied to stale hashes;
- implementation no longer linked to the design or specification it claims to satisfy.

These guards MUST respect project policy. LDE SHOULD NOT impose a universal rule that every requirement needs a separate test or proof if the applicable specification does not require it.

## 11. Approval, Commit, and Authority

LDE SHOULD integrate with the Request and Change lifecycle defined in `RFC-REQUEST-CHANGE.md`.

The general flow is:

1. receive a human Request or authorized development task;
2. classify confirmed information, assumptions, and open questions;
3. assemble context;
4. create one or more isolated Change proposals;
5. calculate semantic diff and impact;
6. run required validation and verification;
7. present the review package;
8. obtain approvals required by policy;
9. commit the Change Set atomically;
10. create a new accepted snapshot and update indexes/caches.

A commit MUST be checked against the exact baseline and proposal digest that were reviewed. If the proposal, baseline, or approval-relevant policy changes, the relevant approval MUST be renewed.

LDE MUST enforce caller capabilities for read, propose, approve, and commit operations. An LLM's ability to propose a change does not imply authority to approve or commit it.

## 12. Model Orchestration

LDE MAY include a Model Router that selects models by task, quality requirements, latency, context capacity, and cost.

Potential task classes:

- clarification and requirement analysis;
- architecture and design;
- specification authoring;
- implementation;
- test generation;
- independent review;
- diagnostic repair.

Routing SHOULD be policy-driven and observable. The router SHOULD record the selected model and relevant settings where available.

A second model or Audit Agent MAY review complex changes for omissions, contradictions, and weak reasoning. Such review is supplementary: it does not replace deterministic validation, test execution, formal verification, or required human approval.

The system SHOULD avoid unnecessary agent proliferation. Multiple agents are justified only when independent work or review is expected to improve the result enough to justify coordination and token costs.

## 13. Interfaces

LDE SHOULD expose a shared semantic engine through several interfaces.

### 13.1 CLI

The CLI supports developers, scripts, and CI.

Illustrative commands:

```bash
lde init
lde request create
lde context inspect
lde query
lde change propose
lde change diff
lde change impact
lde validate
lde verify
lde review
lde commit
lde snapshot inspect
```

The exact command names and argument syntax are implementation decisions.

### 13.2 IDE

An IDE integration MAY provide:

- SPG graph navigation;
- Business, Formal, and Scenario views;
- semantic diff and impact visualization;
- Change Set review and approval;
- diagnostics and verification status;
- provenance and snapshot history;
- context package inspection.

The IDE is a presentation and interaction layer. It MUST use the same semantic and authorization rules as the CLI and Machine API.

### 13.3 Machine API

The Machine API is the primary integration surface for LLM agents and automation. It SHOULD expose typed operations such as:

- `inspect`
- `query`
- `explain`
- `context`
- `propose`
- `diff`
- `impact`
- `validate`
- `verify`
- `review`
- `commit`
- `compare`

Operation schemas, authorization, error semantics, and compatibility guarantees SHOULD be documented independently of any specific transport protocol.

## 14. Additional Capabilities

The following capabilities are valuable but need not all be part of the MVP:

- **Template Instantiation:** create graph structures from parameterized templates with provenance.
- **Library Resolver:** resolve package and library dependencies by content identity and declared dependency kind.
- **Compatibility Checker:** detect interface and contract incompatibilities.
- **Proof Reuse:** reuse proof results only when all proof assumptions and inputs remain identical.
- **Reproducible Build:** bind build outputs to source roots, compiler/toolchain, configuration, and target.
- **Change Replay:** reconstruct a proposal or accepted state from immutable events and graph states.
- **Conflict Resolver:** present overlapping semantic changes and support explicit resolution.
- **Token Accounting:** measure prompt, completion, retrieval, and repair-loop usage.
- **Policy Engine:** apply project-specific approval and verification requirements.

## 15. Metrics

LDE SHOULD measure efficiency and quality together.

Suggested metrics:

| Metric | Purpose |
|---|---|
| Input tokens per task | Measures context and prompt cost |
| Output tokens per task | Measures generation cost |
| Context reuse ratio | Measures safe reuse of previously supplied context |
| Retrieval precision | Measures how much retrieved context is actually relevant |
| Repeated context ratio | Detects unnecessary retransmission |
| Diagnostics size | Measures repair-feedback overhead |
| First-pass acceptance rate | Measures proposal quality |
| Repair iterations per Change Set | Measures avoidable correction cycles |
| Verification reuse ratio | Measures incremental-check effectiveness |
| Human intervention rate | Measures workflow friction |
| Defects found after acceptance | Measures escaped defects |
| Cost per accepted change | Measures end-to-end delivery cost |

The key composite metric SHOULD be **Cost per Correct Change**: the total cost of producing a change that passes the required checks and does not produce known regressions within the defined evaluation scope.

This metric is not proof of defect-free software. It is a practical measure that should be interpreted alongside severity, coverage, and the limits of the verification methods.

## 16. Security and Trust Boundaries

LDE SHOULD treat all model-generated content as untrusted input.

At minimum:

- every operation is schema-validated;
- every operation is authorized;
- access checks are performed at the time of the operation;
- model output cannot directly mutate accepted state;
- tool results and retrieved graph content are treated as data, not executable instructions;
- secrets are excluded from context unless explicitly required and authorized;
- audit records distinguish human, model, tool, and system actors;
- commit and approval authority are enforced outside the model.

The deterministic validators, verifier implementations, storage integrity mechanisms, and policy enforcement code form part of the trusted computing base. LLMs do not.

## 17. Failure Handling

LDE SHOULD fail closed for operations that could corrupt accepted state or bypass policy.

Examples:

- stale target hash: reject or suspend the mutation and report a conflict;
- incomplete required context: request additional context or narrow the task;
- validator unavailable: preserve the proposal as unverified; do not report success;
- verification timeout: report unknown or not checked, not passed;
- conflicting proposals: require explicit semantic resolution;
- commit interrupted: recover using transaction and snapshot integrity mechanisms;
- cache inconsistency: discard the questionable cache entry and recompute.

Failure messages SHOULD identify the failed operation, affected entity, and safe next action without returning unnecessarily large logs.

## 18. MVP Scope

The MVP SHOULD prioritize a small, reliable vertical slice over a broad collection of partially implemented features.

### 18.1 MVP components

1. SPG Store with Stable IDs, immutable states, Content Hashes, and a Merkle DAG.
2. Basic graph query and reverse-dependency index.
3. Context Planner with a small number of context profiles and token accounting.
4. Structured Change API with expected-hash preconditions and isolated proposals.
5. Semantic Diff for supported entity types.
6. Structural validator and initial type/reference checks, as supported by the language model.
7. Basic impact analysis.
8. Verification record model and exact-input cache.
9. CLI.
10. Machine API for inspect, query, context, propose, diff, validate, verify, and commit.
11. Basic policy enforcement and append-only audit records.

### 18.2 Deferred capabilities

The following SHOULD generally be deferred until the core workflow is reliable:

- full graphical IDE;
- distributed collaboration and complex merge workflows;
- advanced formal proof engine;
- sophisticated multi-agent orchestration;
- hosted package registry;
- advanced template migration;
- signatures, attestations, and trust federation;
- broad model-routing optimization.

### 18.3 MVP acceptance criteria

An MVP is useful when it can demonstrate that:

- a model can inspect a bounded semantic context without receiving the whole project;
- a model can propose a typed Change against an exact baseline;
- malformed or stale changes are rejected safely;
- accepted state is not modified by an uncommitted proposal;
- semantic diff and impact are available before commit;
- required validation and verification results are bound to exact inputs;
- unchanged valid checks can be reused;
- stale, failed, unknown, and not-checked results remain distinguishable;
- commit creates a new immutable accepted snapshot;
- all operations are subject to authorization and auditable;
- token usage and verification reuse can be measured.

## 19. Open Questions

The following decisions remain open and SHOULD be resolved before the corresponding implementation is treated as normative.

### 19.1 Graph and storage

1. Should workflow records live in a separate workflow graph, in SPG, or in a repository event model?
2. What is the initial canonical serialization for context packages and Change operations?
3. Which graph query language or API shape should be used?
4. Should the MVP store the graph in a specialized database, a content-addressed object store, or a simpler embedded store?

### 19.2 Context and model interaction

5. What exact mechanism guarantees that previously supplied context remains accessible to a model?
6. Should context budgets be fixed per operation, project-configurable, or negotiated dynamically?
7. Should models request more context explicitly, or should the orchestrator infer retrieval from structured references?
8. What context metadata is necessary for reliable model-side reference without wasting tokens?

### 19.3 Verification

9. Which validation and verification stages are mandatory for the first language subset?
10. Which test-selection policy is sufficiently conservative for the MVP?
11. What is the minimum evidence required for implementation-only changes that claim to preserve behavior?

### 19.4 API and execution

12. Should MCP be the initial Machine API transport, one adapter among several, or deferred?
13. Should CLI and Machine API share one command model or expose separate abstractions over the same engine?
14. What sandbox and reproducibility guarantees are required for executing tests and generated artifacts?

### 19.5 Governance and optimization

15. Which change classes may be committed automatically under project policy?
16. Which metrics are mandatory, and how should correctness be evaluated without overclaiming?
17. When is a second-model audit worth its additional cost?
18. What is the initial capability and permission model for human, model, and tool actors?

## 20. Recommended Design Principles

For an initial implementation, this RFC recommends the following defaults, subject to explicit project acceptance:

1. Implement LDE as a modular monolith before introducing distributed services.
2. Treat SPG and immutable content-addressed states as the authoritative semantic data.
3. Make Context Planner and Structured Change API first-class from the beginning.
4. Require expected-hash preconditions for mutations.
5. Keep proposals isolated from accepted snapshots.
6. Make semantic diff and impact analysis part of the normal review workflow.
7. Use deterministic validation and verification independent of the proposing model.
8. Bind every reusable analysis and verification result to complete, exact input identities.
9. Use conservative test selection and make its rationale inspectable.
10. Start with CLI and Machine API; add a full IDE after the underlying workflows stabilize.
11. Measure token savings together with defect rates, review effort, and end-to-end cost.
12. Keep model routing and multi-agent review optional and policy-controlled.

## 21. Conclusion

LLMLang's development environment should make correct workflows easier than unsafe ones. It should reduce the amount of information an LLM must process while increasing the amount of correctness work performed by deterministic tools.

The proposed LDE turns development into a controlled loop:

**Request → Context → Structured Change → Semantic Diff → Impact Analysis → Independent Verification → Policy Review → Accepted Snapshot.**

The LLM contributes semantic reasoning and candidate changes. LDE manages identity, context, dependencies, validation, verification, authorization, and history. The result is a development workflow that can be more token-efficient, auditable, and resistant to model-generation errors without claiming that any toolchain can guarantee the absence of all defects.

## Public-interface integration (2026-11-24; proposed)

Context planning should supply an agent modifying a consumer with exact public interface contracts and necessary assumptions, not unrelated private provider bodies; supply provider-specific contracts and evidence when implementing or changing a provider. Structured changes distinguish public contract revision, implementation revision, catalog alias and binding changes. Independent validation checks both proof layers and exact admission, computes separate consumer/provider impact and rejects stale publication. Do not conflate a modular proof with whole-program correctness or claim guaranteed token savings without measurement.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
