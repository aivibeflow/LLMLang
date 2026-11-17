# Related Projects: Initial Research

**Research date:** 2026-11-16  
**Status:** Exploratory landscape scan; maturity claims are primarily maintainer-reported.

## Executive summary

Several projects already implement substantial parts of the LLMLang direction. The closest overlaps are:

1. **linkly** — an LLM-native programming platform combining a semantic IR, language, interpreter/native compilation, knowledge base, and agent protocol.
2. **Edict** — an agent-first language with a structured JSON AST, type/effect checking, SMT-backed contracts, WASM execution, and MCP tools.
3. **DSP CodeGen** — a graph-based IR used as persistent structural memory and as the source of truth for deterministic polyglot code generation.
4. **agent-spec** — an intent compiler that turns governed requirements into Task Contracts and mechanically checked implementation work.

Other relevant projects include Forma, Intent, Spec2Code, Atlas, AutoSpec+, SpecMD, PlanCompiler, IntentLang, Lumen, and agentic-code-reviewer.

No project identified in this initial scan clearly combines all of the following:
- independently maintained Specification, Design, and Implementation graph layers;
- fine-grained immutable content-addressed semantic nodes and a Merkle DAG;
- explicit human-intent governance and auditable Request / Decision / Change / Change Set lifecycle;
- token-aware context planning and structured semantic change operations;
- independent, incremental verification whose evidence is tied to exact input identities.

This is preliminary, not a uniqueness claim. Deeper source-level review is required.

## Closest projects

### 1. linkly
Repository: https://github.com/choiyounggi/linkly

An LLM-native programming platform, not merely a language. Its published architecture includes a semantic IR, parser/lowering, interpreter, MLIR-based native compilation, runtime, shared knowledge base, and agent protocol. It reports a working implementation and differential checking between interpreter and native execution.

**Potentially reusable ideas**
- Semantic IR as the stable center of the system.
- Explicit agent roles and machine protocol.
- Knowledge base with progressive disclosure.
- RFC-driven architecture and executable golden scenarios.
- Differential validation across execution backends.

**Differences / questions**
- No evident three independently existing Specification, Design, and Implementation semantic graphs.
- No evident fine-grained Merkle DAG for semantic state and verification evidence.
- Compare its knowledge base and agent protocol with LLMLang's context and change governance at schema/API level.

### 2. Edict
Repository: https://github.com/Sowiedu/Edict

A programming language designed for agents. Programs are JSON ASTs rather than source text. The documented pipeline includes schema validation, name resolution, type checking, effect checking, Z3-based contract verification, WASM code generation, and sandboxed execution. MCP exposes schema, checking, compilation, patching, diagnostics, tests, and replay.

**Potentially reusable ideas**
- Machine-native canonical AST and compact representation.
- Fine-grained patch operations addressed by node identity.
- Typed diagnostics designed for agent repair.
- Separation of structural validation, typing, effects, contracts, compilation, and execution.
- Capability-aware sandboxing and deterministic replay.
- Incremental checking based on dependency graph and diff.

**Differences / questions**
- Primarily a language/compiler/runtime, not a project-level intent and change-governance system.
- Inspect how node IDs survive edits, how canonicalization works, and whether caches include all semantically relevant inputs.
- Examine proof outcomes and unsupported proof cases.

### 3. DSP CodeGen
Repository: https://github.com/Loqira-Labs/dsp-codegen

An agent-first graph IR for structural memory and deterministic polyglot code generation. The graph models modules, types, configurations, functions, and typed relationships. Stable UIDs bind graph entities to code regions; public interfaces receive contracts and generated seams/stubs; changes are graph-first and impact-aware.

**Potentially reusable ideas**
- Graph as persistent structural representation rather than repeatedly prompting over source files.
- Stable entity UIDs independent of paths.
- Explicit graph-to-code bindings.
- Deterministic interface/stub generation and cross-language seams.
- Impact analysis and incremental regeneration.

**Differences / questions**
- Private implementation bodies are intentionally not modeled in the graph.
- The documented verify layer is structural lint; deeper confidence comes from compilers and coherence tests.
- Its graph is primarily a code-structure IR, not a full specification/design/implementation semantic model.

### 4. agent-spec
Repository: https://github.com/ZhangHanDong/agent-spec

An intent compiler for AI coding. Human intent is captured in a governed Requirement IR, lowered into Task Contracts and work units, linked to a derived Code Graph IR, and checked through linting, verification, traceability, and execution bundles. It explicitly separates human-owned requirements from rebuildable code facts.

**Potentially reusable ideas**
- Requirement governance with explicit accepted/rejected/historical states.
- Human-reviewed requirements as normative truth; code graph as derived evidence.
- Requirement-to-code linking and traceability.
- Task Contracts, test obligations, dependency DAGs, and execution bundles.
- Freshness-aware code intelligence and explicit unavailable-provider outcomes.
- Human decision gates represented as machine-readable questions.

**Differences / questions**
- It is a requirements/workflow toolchain, not a new programming language.
- Its requirement IR and code graph are two distinct tracks; LLMLang's three-layer SPG would need a more expressive Design layer.
- Inspect acceptance, evidence, liveness, stale bindings, and provider failure semantics.

## Other relevant projects

| Project | Repository | Relevant contribution | Main limitation relative to LLMLang |
|---|---|---|---|
| Forma | https://github.com/sfw/forma | Systems language prototype with affine ownership, capability-gated effects, contracts, structured diagnostics, bounded verification reports | Language/compiler focus; no full project semantic graph or change governance |
| Intent | https://github.com/lhaig/intent | Contract-based language for AI code assistants; pre/postconditions, invariants, Z3, intent blocks | Primarily a language and contract mechanism |
| Spec2Code | https://github.com/rse-verification/Spec2Code | Requirements-to-safety-critical-C workflow with static analysis and formal verification | Domain-specific, research-oriented; licensing constraints should be checked |
| Atlas | https://github.com/LordCasser/atlas | Local semantic code graph, stable IDs, content-hash incremental indexing, symbol/call/impact queries | Code intelligence substrate rather than full semantic program state |
| AutoSpec+ | https://github.com/Xidian-ICTT-GZ/AutoSpec | LLM-generated contracts, loop invariants, ranking functions, Frama-C/WP verification | Narrow formal-methods pipeline |
| SpecMD | https://github.com/glauberportella/specmd | Markdown/LaTeX specs linked to Intent IR, property tests, optional SMT | Specification workflow, not full language/runtime |
| PlanCompiler | https://github.com/prnvh/plancompiler | Typed execution graphs compiled deterministically to code over a fixed node library | Bounded execution-plan domain |
| IntentLang | https://github.com/l3yx/intentlang | Intent-oriented Python framework and externalized object references | Different runtime and trust/security assumptions |
| Lumen | https://github.com/sardor-M/lumen | Persistent local knowledge graph for coding agents, retrieval and MCP | Agent memory rather than authoritative program semantics |
| agentic-code-reviewer | https://github.com/royxforge/agentic-code-reviewer | Multi-agent review with deterministic evidence checks | Review subsystem, not development platform |

## Preliminary comparison against LLMLang

| LLMLang concern | Strongest project to inspect | Why |
|---|---|---|
| Semantic IR and agent-native language platform | linkly | Broadest language/platform architecture |
| Structured AST, patch API, diagnostics, incremental checking | Edict | Explicit machine-native programming interface |
| Persistent graph and graph-to-code binding | DSP CodeGen | Concrete graph-first implementation |
| Human-owned requirements and traceability | agent-spec | Most developed requirements governance overlap |
| Contracts, ownership, effects, proof evidence | Forma, Intent, Edict | Different points in the language/verification design space |
| Semantic code retrieval and freshness | Atlas | Useful implementation substrate |
| Requirements-to-formal-code verification | Spec2Code, AutoSpec+ | Specialized verification patterns |

## Suggested deep-review order

1. **linkly** — inspect RFCs, semantic IR schema, agent protocol, knowledge-base routing, interpreter/compiler pipeline, and tests.
2. **Edict** — inspect AST schema, node identity, patch semantics, incremental dependency tracking, contract outcomes, MCP protocol, and sandbox boundary.
3. **DSP CodeGen** — inspect graph schema, UID lifecycle, code binding markers, diff/impact algorithms, generation boundaries, and verification tests.
4. **agent-spec** — inspect requirement state machines, Task Contract schema, intent-code linker, evidence model, stale/freshness handling, and lifecycle gates.
5. **Forma / Intent / Atlas** — inspect focused mechanisms that may improve LLMLang's type/effect/contract system and context planner.

## Research caveats

- Feature and maturity claims in README files are self-reported. Test counts and production-ready labels are not independent quality evidence.
- Repository activity, versions, licenses, and implementation status change. Re-check before adopting code or design.
- Similar terminology does not imply equivalent semantics. Compare schemas, invariants, failure behavior, and tests rather than feature labels.
- This document records findings, not decisions to adopt any design.
