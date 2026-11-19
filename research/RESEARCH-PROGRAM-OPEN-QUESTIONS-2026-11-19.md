# Research Program for Open LLMLang Questions — 2026-11-19

**Status:** Scope inventory and sequencing plan; not a design decision
**Scope rule:** “Open” means every unresolved design item in `TODO.md` plus the unresolved research gates recorded by the RT taxonomy and evidence state. Existing reports count as evidence, not as closure, unless a question's decision gates are met and the project records a decision.

## 1. Snapshot and completeness boundary

At this snapshot, the TODO register contains 24 unique questions after correcting a duplicate stable ID: 6 P0, 14 P1, and 4 P2. They span operation identity, canonical representation/dependencies, package/library distribution, POSIX/runtime, LLVM, caching, Toolchain Server, and LLM change planning. The project also has open research gates in all 23 taxonomy areas. Some topics have substantial analytical reports and bounded prototypes; none of that alone selects a coherent integrated language design.

This inventory is the control sheet for the requested exhaustive research. It makes the scope auditable and prevents a focused report from being mistaken for completion. The work is necessarily incremental: each research batch must be committed and cross-checked against current `TODO.md`, taxonomy, dependency map, option matrix, and CI. “Exhaustive” for this stage means every remaining question receives at least a scoped prior-art comparison, candidate vectors, compatibility conditions, falsifiers, and concrete validation gates. It does not mean every candidate is implemented or independently proven.

## 2. Open-question inventory

| ID | Priority | Research cluster | Main unresolved discriminator / evidence still needed |
|---|---:|---|---|
| LL-001 | P0 | Operation identity | Whether OpHash denotes contract-permitted behavior or one exact implementation behavior; canonical typed envelope, effects, ABI and semantic-context boundary. Scenario 92 begins the comparison; no envelope chosen. |
| LL-002 | P1 | Operation identity | Creation and authenticated continuation of Stable ID; rename, split, merge, deprecation, recreation, independent-equivalent operations, branch import/merge. |
| LL-003 | P1 | Operation identity / libraries | Candidate discovery versus acceptance; exact-contract matching, refinement/equivalence proof, adapters, target-specific implementation binding and failure behavior. |
| LL-004 | P0 | Content identity | Typed canonical bytes, domain/schema version, digest suite, dual-address migration and representation evolution. Scenarios 90–91 add prior art; canonical fixture and migration evidence remain open. |
| LL-005 | P0 | Content identity / dependencies | Hash-relevant edge taxonomy, transitive closure, recursion/SCC policy, and effects on callers, symmetry, merge and cache invalidation. Bounded group experiment exists; graph-wide rule remains open. |
| LL-006 | P1 | Artifact model | Minimal independently addressable units for specification, interface, contract, implementation, dependencies, tests, proofs, and package roots; cost of over-fragmentation. |
| LL-007 | P1 | Targets / identity | Which target facts alter semantic interpretation, public ABI, implementation binding, execution action, or only deployment selection; validate against POSIX and multiple backends. |
| LL-008 | P1 | Evidence | Evidence claims and reuse relation for tests, proofs, refinement checks, and conformance; assumptions, provenance, verifier/compiler identity, stale input invalidation, UNKNOWN. |
| LL-009 | P2 | Registry / trust | Publication and mirror trust, signatures/attestations, licensing, revocation, retention, cache policy, and garbage collection. Content integrity must remain separate. |
| LL-010 | P1 | Packages / SPG | Package as semantic graph object versus distribution container; test whether requirements, dependency resolution, or execution semantics require package-level nodes. |
| LL-011 | P1 | Libraries | Library as package subtype or semantic role; minimum public machine-readable contract, opaque implementation limits, compatibility and verification disclosures. |
| LL-012 | P2 | Templates | Instance representation, provenance, customization/detachment states, update/migration semantics, merge and generated-source correspondence. |
| LL-013 | P1 | POSIX profile | Initial POSIX edition and mandatory/optional/implementation-defined subset; choose only after workload and target constraints are explicit. |
| LL-014 | P1 | POSIX API | Direct POSIX surface versus typed façade; ownership, error, capability and behavioral mapping across concrete file/process examples. |
| LL-015 | P1 | Runtime vertical slice | Smallest shared portable/native slice that exercises startup, I/O, errors, resource lifetime, ABI and reference semantics end-to-end. |
| LL-016 | P2 | Native targets | Initial Linux architecture(s), syscall ABI isolation, portability cost, emulation/cross-build and target-specific test coverage. |
| LL-017 | P1 | Trusted runtime | Trusted assembly/intrinsics/external code boundary, primitive contracts, proof limits, auditing and alternative implementation strategy. |
| LL-018 | P2 | POSIX concurrency | Language memory model, POSIX thread/signal/blocking behavior, Linux ordering, scheduling, interruption and environment-dependent semantics. |
| LL-019 | P1 | Conformance / proofs | Feature-scoped POSIX conformance claims, optional and implementation-defined behavior, assumptions, unsupported cases and proof scope. |
| LL-020 | P1 | LLVM backend | Initial/optional/replaceable role; supported IR subset and preservation contract for poison/UB, overflow, pointers, floats, atomics, ABI and optimization. |
| LL-021 | P0 | Build/cache | Action DAG, exact Action Key inputs and closure, nondeterminism, cache layers, output/evidence identity, language/toolchain versions, remote trust and conservative UNKNOWN handling. Scenarios 92–93 refine the identity and reuse/trust boundaries; schema, prototype and falsification remain open. |
| LL-022 | P1 | Package distribution | Manifest/index schemas, binary blocks/compression/sparse lookup, static versus provider-built archives, dependency closure and measured resource bounds. Prototype exists; format and adapter validation remain. |
| LL-023 | P0 | Change planning | Complete caller/reference discovery, edge-specific migrate/preserve/adapt/fork, contract/hash propagation, shared-caller split, plan approval/revision and exact-tree commit gates. |
| LL-024 | P0 | Toolchain Server | Transport-neutral API, durable snapshots/workspaces, Change Sets, storage/recovery, concurrency, filesystem/Git synchronization and authorization. This ID replaces the duplicate LL-022 label; wording and question are unchanged. |

**Stable-ID correction:** `TODO.md` previously assigned `LL-022` to both package distribution and Toolchain Server. The package question keeps LL-022 because it is the earlier register entry; Toolchain Server is now LL-024. Searchable references must use the unique ID. This corrects a tracking collision and does not resolve either design question.

## 3. Taxonomy-wide unresolved areas

| Area | Open research gates at this snapshot |
|---|---|
| RT-01 Product goals/workloads | Workload weighting, user/agent usability, complexity and performance criteria; the host CLI pilot does not measure LLMLang. |
| RT-02 Intent/requirements | Ambiguity handling, traceability, requirement evolution and source acceptance at scale. |
| RT-03 Core semantics | One coherent operational/observational semantics for state, errors, effects, recursion, concurrency and modules; no semantic profile chosen. |
| RT-04 Type/effects/ownership | Complete type/resource/capability model and cross-feature soundness beyond the limited checker. |
| RT-05 Representation/identity | Canonical SPG and identity envelope, lifecycle, cyclic groups, import/merge completeness. |
| RT-06 Dependencies | Sound complete reverse-reference extraction and UNKNOWN handling across full programs. |
| RT-07 Formal semantics | Supported language fragment, projection correspondence, proof obligations and trusted computing base. |
| RT-08 Testing/evidence | Reusable evidence classes, conformance corpus, model/property testing and exact invalidation rules. |
| RT-09 Compiler/IR | Comparative pipeline/IR boundaries, diagnostics, optimization trust and executable semantic-preservation evidence. |
| RT-10 Runtime | Interpreter/VM/native contract, resource and OS behavior, sandboxing and target-specific semantics. |
| RT-11 Build/cache | Sound action keys, dependency closure, deterministic outputs and cache trust at scale. |
| RT-12 Packages/libraries | Identity/publication, exact dependency closure, provider composition and scalable index/archive formats. |
| RT-13 Targets/interoperability | Multiple backends and FFI vertical slices with explicit semantic-preservation guarantees. |
| RT-14 AI authoring | Model-neutral structured edits, provenance, scope containment, authorization and agent failure recovery. |
| RT-15 Collaboration/merge | Repository representation and semantic merge prototypes; identity/schema assumptions and end-to-end merge remain coupled to RT-05/20/24. |
| RT-16 Security/trust | Persistent service threat validation, sandbox boundary, producer authenticity, supply-chain policy, revocation and recovery. |
| RT-17 DX/diagnostics | Comparative human/agent studies, debugging, explanation and feedback behavior. |
| RT-18 Evolution/conformance | Versioning and migration fixtures across language, package, target, Unicode and runtime profiles. |
| RT-19 Toolchain API | Prototype validates only a subset; persistence/recovery, adapter, concurrency and Git synchronization gates remain. |
| RT-20 Patch planning | Completeness audit and mandatory plan execution against real source graphs and changed callees. |
| RT-21 Self-development | Bootstrap boundary, minimum self-hosting profile and staged migration have preliminary analysis only. |
| RT-22 Repository/worktrees | Durable repository/worktree operations, recovery and workflow authorization need end-to-end validation. |
| RT-23 Multi-worktree server | Shared semantic store versus per-worktree mappings, event reconciliation, race/recovery behavior and resource bounds need prototype validation. |

The taxonomy is a coverage map rather than 23 independent decisions. Research should follow the dependency map: semantic observation and type/resource rules constrain identity, evidence, compiler/runtime behavior, cache keys, merge and security.

## 4. Research sequence and completion gates

### Wave A — semantic and identity foundations

Research RT-01–08 together: workload criteria; observables and core profiles; type/effect/ownership/capability boundaries; typed identity envelopes; dependency completeness; formal correspondence; evidence/reuse. Deliver matched scenarios where only one semantic dimension changes, and explicitly state which claim each hash/proof/test supports.

### Wave B — compilation, runtime and target preservation

Research RT-09–13 and LL-013–020. Compare interpreter/reference semantics, bytecode VM, LLVM and portable/native POSIX candidates against the same bounded vertical slice. Record unsupported programs, ABI and OS assumptions, effects, resource cleanup, diagnostics, code size, runtime and target-specific evidence. No backend is selected by architecture prose alone.

### Wave C — packages, caching and ecosystem trust

Research LL-009–012, LL-021–022 and RT-11/12/16/18. Extend package prototypes to a real immutable-store adapter and representative large indexes; define which identity is semantic, archival, provider, cache-action, output-artifact or trust metadata. Exercise interrupted migration, missing dependencies, tampered provenance, remote cache poisoning, revocation and GC.

### Wave D — toolchain and AI change protocol

Research LL-023–024 and RT-14/17/19/20/22/23 as one transactional workflow. Validate plan-before-mutation, optimistic concurrency, complete impact closure, scoped authorization, durable recovery, multi-worktree reconciliation, exact Git tree staging, validation gates and failure injection. Keep push authorization separate from local commit creation.

### Whole-specification synthesis gate

Before writing the language RFC, each candidate vector needs: a precise claim; primary-source references; tested discriminators or an explicit reason evidence is analytical only; assumptions; failure/UNKNOWN behavior; cost and migration analysis; dependency/compatibility links; a falsifier; and a normalized row in the option matrix. Then construct only internally compatible integrated candidates, score against agreed workload weights, run sensitivity analysis, and record unresolved risks. Do not turn a recommendation into an accepted decision without project review.

## 5. Progress recorded

- [Scenario 92](RESEARCH-SCENARIO-92-OPERATION-IDENTITY-AND-IMPLEMENTATION-BINDING.md) compares interface contracts, operation identity, implementation bindings, execution action keys and output artifact hashes for LL-001/002/003/007/008/021. It leaves the OpHash meaning open.
- [Scenario 93](RESEARCH-SCENARIO-93-CACHE-SOUNDNESS-RESULT-ENVELOPES-AND-TRUST.md) compares exact Action Result reuse with material-cache restoration and trust-domain controls for LL-021/RT-11/12/16. It leaves the result schema, validation policy, and trust model open.
- [Scenario 91](RESEARCH-SCENARIO-91-VERSIONED-CONTENT-ADDRESSES-AND-DIGEST-MIGRATION.md) compares digest migration prior art for LL-004/005; it leaves the canonical envelope and migration mechanism open.
- Existing bounded prototypes and reports remain evidence at their documented scope. The open register still controls decisions; this work does not mark open questions resolved.
