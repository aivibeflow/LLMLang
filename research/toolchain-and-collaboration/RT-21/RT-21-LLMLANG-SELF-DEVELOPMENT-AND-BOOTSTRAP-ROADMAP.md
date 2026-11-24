# RT-21 — LLMLang Self-Development: Feasibility, Bootstrap, and Migration Roadmap

**Status:** Preliminary feasibility analysis; no implementation architecture is accepted  
**Date:** 2026-11-18  
**Research area:** RT-21 — Self-development and self-hosting toolchain  
**Related:** [RT-03 Core Language Semantics](../../language-design/RT-03/CORE-LANGUAGE-SEMANTICS.md), [RT-09 Compiler and IR](../../research-management/RESEARCH-TAXONOMY.md), [RT-10 Runtime](../../runtime-and-systems/RT-10/POSIX-RUNTIME-ARCHITECTURE.md), [RT-11 Build and cache](../RT-11/SEMANTIC-COMPILATION-CACHE.md), [RT-19 Toolchain Server](../RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md), [RT-20 Patch planning](../RT-20/RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md).

## 1. Research question

How much must LLMLang implement before development of LLMLang's own tools can be conducted primarily in LLMLang, rather than in a host language such as Rust or Python?

The target is deliberately narrower than “the compiler is written in itself.” The first useful milestone is a reproducible development loop in which at least one nontrivial project tool is authored in LLMLang, represented in the canonical semantic model, built and tested by LLMLang tooling, and safely changed through the semantic development API.

## 2. Current repository baseline

The repository is still a conceptual/research project, not a complete language implementation. It contains useful bounded evidence and prototypes, but these do not yet form a coherent compiler/runtime/toolchain:

- Research describes the SPG and semantic identity direction, but a complete canonical SPG schema and stable hash/identity contract are not yet settled.
- There are dependency-analysis prototypes and a narrow formally checked relational-verification slice. Neither is a general LLMLang compiler or runtime.
- Package manifests and logical index/archive experiments exist, but they do not amount to a complete package manager and build system.
- RT-19 provides a transport-neutral Toolchain Server/API proposal and a narrow Python workspace prototype; it is not a production semantic server or MCP implementation.
- RT-20 proposes complete change-impact planning, caller migration classification, hash/reference propagation, and validation-gated commits; the full planner and commit gate are not implemented.
- The parser, general type checker, compiler IR/lowering, execution runtime, standard library, build/test orchestration, and self-hosting compiler are not available as one end-to-end language implementation.

This baseline is a repository-level assessment, not a claim that every individual prototype or research result has been exhaustively re-audited in this report.

## 3. Define the first target precisely

Three distinct goals must not be conflated:

1. **Tool development in LLMLang:** a useful tool is authored in LLMLang and can be built, tested, debugged, and versioned using the project toolchain.
2. **Toolchain development through LLMLang:** LLM/IDE/CLI clients make semantic changes through the LLMLang Toolchain API; the toolchain plans, validates, and records those changes.
3. **Compiler self-hosting:** the LLMLang compiler itself is implemented in LLMLang and can compile a subsequent version of itself.

Goal 1 does not require goal 3. Goal 2 does not require every server adapter or low-level host integration to be written in LLMLang. The recommended first milestone is goal 1 with a meaningful subset of goal 2; self-hosting is a later milestone.

## 4. Minimum implementation capabilities

| Capability | Minimum needed for first LLMLang tool | Why it is needed |
|---|---|---|
| Language semantic profile | Small, explicitly bounded and versioned subset | Compiler, runtime, tests, and tools need one stable meaning |
| Canonical semantic representation | Typed SPG/IR nodes, references, identity boundaries, canonical serialization | Tools must be represented and changed without depending on unstable syntax |
| Front end | Parser or structured authoring interface, name resolution, diagnostics | Source or generated semantic artifacts must enter the compiler deterministically |
| Type checking | Sound checks for the selected subset; explicit rejection of unsupported constructs | Prevent invalid programs from reaching execution |
| Compiler pipeline | Typed IR and at least one deterministic executable target | Build tool programs reproducibly |
| Runtime | Minimal execution model and standard primitives for collections, strings, errors, and filesystem/process access as required | A practical analyzer/validator must interact with repository data |
| Build and test | Reproducible builds, test runner, fixtures, exit status, CI integration | The tool must be verifiable and maintainable |
| Toolchain API | Workspaces, immutable snapshots/change sets, typed mutations, validation and export | LLM clients must modify semantic state rather than hand-editing derived artifacts |
| Dependency and impact analysis | At least sound dependency discovery for the supported semantic subset; conservative unknown handling | Changes must not silently leave stale callers or derived results |
| Change planning and commit gate | Initially scoped CIP and validation gates, progressively implementing RT-20 | The toolchain must know the full affected set before mutation/commit |

A full optimizing compiler, native backend, complete POSIX layer, distributed server, package registry, and complete self-hosting compiler are not prerequisites for the first tool.

## 5. Recommended bootstrap architecture

Use two layers rather than trying to eliminate the host language immediately.

### 5.1 Trusted bootstrap layer

Initially implemented in a mature host language (Rust is a candidate, not a settled decision):

- small compiler/front end for the initial LLMLang subset;
- minimal runtime and platform boundary;
- filesystem and process primitives needed by build/test;
- deterministic serialization and hashing primitives, once their contracts are specified;
- CI/bootstrap packaging.

Keep this layer small, auditable, and explicit. It is a bootstrap mechanism, not the place where all future development tools must live.

### 5.2 LLMLang development tools

Move project-specific and higher-level logic into LLMLang incrementally:

- SPG validator and semantic consistency checker;
- dependency analyzer and impact planner;
- package/index validator and build graph logic;
- test orchestration and repository-level checks;
- later, compiler front end, optimizer, and selected runtime/toolchain components.

The host layer should expose narrow capabilities. It should not silently become a second semantic authority.

## 6. Suggested implementation sequence

| Step | Deliverable | Exit condition |
|---|---|---|
| 0 | Freeze a minimal language profile for the first vertical slice | Syntax/structured representation, values, control flow, functions, modules, errors, and effects used by the slice have explicit semantics |
| 1 | Canonical SPG/IR and identity slice | Typed objects serialize deterministically; identity inputs and references are explicit; unsupported cases fail closed |
| 2 | Bootstrap compiler and minimal runtime | A small LLMLang program compiles and executes reproducibly |
| 3 | Build/test vertical slice | Tests run from the repository; failures are deterministic and visible in CI |
| 4 | First real LLMLang tool | A useful validator or dependency analyzer is implemented in LLMLang and used by the repository |
| 5 | Semantic Toolchain API integration | Tool can be inspected and changed through workspace/snapshot/change-set operations; export to Git is deterministic |
| 6 | RT-20 change planning integration | Caller discovery, per-call-site classification, hash propagation, complete plan execution, and validation-gated commit are implemented for the supported subset |
| 7 | Expand LLMLang ownership | More project tools and selected toolchain services migrate from the host layer |
| 8 | Self-hosting compiler | Bootstrap compiler builds compiler version N; compiler N builds N+1; outputs and tests satisfy a reproducible bootstrap policy |

The first tool candidate should be either an SPG validator or a dependency analyzer. The dependency analyzer is strategically attractive because it exercises the graph and impact model that the Toolchain itself needs. It should not be started against a moving, undefined SPG identity contract; first stabilize the minimum representation and identity slice.

## 7. Effort estimate

The following are coarse engineering estimates for one experienced engineer working mostly full-time. They are planning ranges, not commitments or statistically grounded forecasts.

| Work package | Preliminary estimate |
|---|---:|
| Minimal semantics, SPG and identity slice | 3–6 person-months |
| Parser/structured front end, type checker, typed IR | 3–5 person-months |
| Interpreter or minimal executable runtime | 2–4 person-months |
| Build/test system, libraries and CI vertical slice | 2–4 person-months |
| Production-grade Toolchain Server and semantic API | 3–6 person-months |
| MCP adapter and LLM integration | 1–2 person-months |
| RT-20 planner, validation and commit gate | 2–4 person-months |
| First useful LLMLang tool and migration | 1–3 person-months |
| **Indicative total to a first end-to-end LLMLang tool workflow** | **17–34 person-months** |
| Additional self-hosting compiler work | **6–12 person-months** |

The ranges overlap in places and assume reuse of existing research/prototypes. They exclude a full production-grade language, optimizing/native compiler, complete POSIX implementation, distributed collaboration, broad package ecosystem, and comprehensive formal verification. Actual effort may change substantially after the first vertical slice and a more precise semantic profile.

## 8. First milestone acceptance criteria

The **LLMLang Self-Development Milestone** should be considered achieved only when all of the following are demonstrated:

1. At least one useful repository tool is authored in LLMLang, not merely generated as a wrapper around a host-language implementation.
2. Its canonical semantic representation is stored in the repository and can be reconstructed from a clean clone.
3. The bootstrap compiler builds it reproducibly from the declared source/semantic inputs.
4. The LLMLang test runner executes its tests and reports deterministic pass/fail results.
5. CI runs the build and tests from a clean environment.
6. The Toolchain can inspect and modify the tool through semantic workspace/change-set operations.
7. Dependency and impact analysis identify the supported affected callers and derived artifacts; unknown/incomplete cases block acceptance rather than being treated as safe.
8. A scoped change plan is completed before mutation, and the validation gate prevents a Git commit when required checks fail.
9. The host-language bootstrap boundary and all unsupported LLMLang constructs are documented.

This milestone does not require a self-hosting compiler.

## 9. Risks and unresolved questions

- **Semantic churn:** implementing tools before the language subset and identity rules stabilize creates expensive migrations.
- **Bootstrap lock-in:** a broad host-language implementation can become a permanent parallel toolchain. Keep host APIs narrow and define migration boundaries.
- **Premature self-hosting:** writing the compiler in an immature language compounds debugging and trust problems; first establish an independently testable compiler/runtime.
- **False completeness in impact analysis:** incomplete caller discovery or hash propagation can leave stale semantic references. Unknown must fail closed.
- **Scope inflation:** a first useful tool does not need a complete general-purpose language or full POSIX environment.
- **Trust boundary:** compiler, runtime, build system, and semantic API must remain independently testable; an LLM-generated program is not evidence of its own correctness.

Open decisions include the initial language subset, canonical SPG/IR shape, identity/hash contract, bootstrap implementation language, first tool candidate, runtime capability boundary, and which RT-20 gates are mandatory for the first milestone.

## 10. Preliminary recommendation

Prioritize a small, coherent vertical slice over broad language implementation or immediate self-hosting:

1. Define the minimum semantic profile and canonical identity slice.
2. Build a small host-language bootstrap compiler/runtime.
3. Implement and test one genuinely useful tool in LLMLang.
4. Make that tool part of the repository's own CI and development loop.
5. Connect it to the semantic Toolchain API and progressively introduce RT-20 planning/commit gates.
6. Migrate additional tools and only then evaluate compiler self-hosting.

This is a research recommendation, not an accepted architecture decision. No ADR or language specification is changed by this report.
