# ADR-015: Toolchain Server and semantic development API

- **Status:** Proposed; validation required before acceptance
- **Date:** 2026-11-18
- **Decision owners:** LLMLang project
- **Related research:** [RT-19 — Toolchain Server and Semantic Development API](../../research/RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md)
- **Related architecture:** [RFC — LLMLang Development Engine](../../research/RT-14/RFC-DEVELOPMENT-ENGINE.md)
- **Related repository decision:** [ADR-014 — Git repository representation and semantic merge](014-git-semantic-merge.md)
- **Related agent interchange decision:** [ADR-017 — Default object format for agent interaction through MCP](017-mcp-agent-object-format.md)

> This ADR records a proposed architectural direction for research and prototype evaluation. Its status is not Accepted. It does not authorize implementation to bypass the current semantic, identity, or repository constraints.

## Context

LLMLang is intended to let agents author programs through structured semantic operations rather than by directly editing source files. The Development Engine RFC already establishes the SPG, isolated Change proposals, deterministic validation, independent verification, and a model-agnostic Machine API. It permits MCP as an adapter but does not define the operational Toolchain API, workspace lifecycle, storage contract, concurrency model, or synchronization with the Git repository.

An implementation that exposes only file read/write tools would leave agents responsible for textual placement, formatting, cross-file edits, and source-level bookkeeping. That is inconsistent with the intended semantic authoring model.

At the same time, making an external database the only authoritative copy of program meaning would conflict with ADR-014's proposed Git-portability boundary.

## Proposed direction

1. **Introduce a transport-neutral Toolchain API.** Domain operations and error semantics are independent of MCP, JSON-RPC, CLI, IDE, or CI transports.
2. **Provide MCP as an adapter.** MCP Tools expose bounded semantic actions; Resources expose read-only semantic views and reports; Prompts are optional task templates. MCP session/connection identity is not durable workspace identity.
3. **Make structured semantic changes the normal agent authoring path.** Mutations use typed operation envelopes, explicit target identities, expected Content Hash preconditions, provenance, and idempotency keys. Raw text import remains an interoperability path and must pass through parsing, semantic diff, validation, and conflict checks.
4. **Use explicit Workspace and Change Set handles.** A Workspace is an isolated working view rooted at an immutable base snapshot. A Change Set groups proposed operations and evidence. Neither may mutate an accepted snapshot in place.
5. **Publish immutable snapshots.** Acceptance creates a new immutable semantic snapshot only after required validation, verification, and policy checks. Semantic acceptance is distinct from filesystem export, Git commit, and push.
6. **Use optimistic concurrency by default.** Mutations compare expected object/workspace hashes. Stale writes and conflicting changes fail explicitly; last-writer-wins is prohibited for semantic entities.
7. **Keep Git-visible repository inputs sufficient for reconstruction.** In line with Proposed ADR-014, local SPG databases, workflow stores, indexes, and caches are derived/reconstructible. No external database becomes the sole authoritative source of accepted program meaning.
8. **Separate logical storage responsibilities.** Immutable semantic objects, mutable workspace/change records, evidence/audit records, indexes, and disposable caches have distinct contracts even if they initially share one physical database.
9. **Start as a modular monolith.** Do not introduce a distributed server or remote shared database until measured requirements justify the operational complexity.
10. **Synchronize deterministically.** Import constructs a candidate graph and validates it before publication. Export serializes an exact snapshot canonically, detects external edits, and publishes a consistent file generation. Neither direction silently overwrites concurrent changes.
11. **Enforce authority outside the model.** Authentication, per-operation authorization, review policy, acceptance, commit, and publication are enforced by the Toolchain and policy layer, not by model-generated claims.

## Explicit non-decisions

This ADR does not select:
- a canonical SPG schema or final semantic mutation vocabulary;
- a database engine or final on-disk storage format;
- the canonical repository/on-disk serialization or digest algorithm; the scoped MCP-facing SPG object format is decided separately by [ADR-017](017-mcp-agent-object-format.md);
- an MCP transport/version profile or exhaustive Tool list;
- distributed collaboration, remote workspaces, or a hosted Toolchain service;
- automatic acceptance, commit, push, or package publication;
- a final source-file layout or language syntax.

These require RT-19 experiments and consistency with RT-05, RT-14, RT-15, and RT-16.

## Alternatives considered

### Agents edit textual files directly

Retained as an interoperability and human-editing path, but not selected as the primary agent interface. It forces agents to manage syntax, file placement, formatting, and cross-file edits, and makes semantic preconditions and provenance harder to enforce.

### MCP as the internal domain API

Not selected. It couples core semantics and lifecycle to one protocol, complicates reuse by CLI/CI/IDE, and risks treating connection/session details as durable state. MCP should adapt the domain API.

### In-memory-only Toolchain

Useful for the first prototype and tests, but insufficient as the only operational profile when workspaces must survive process restarts. The API should allow a persistent backend without changing domain semantics.

### External database as sole source of truth

Not selected because a normal Git checkout would no longer be sufficient to reconstruct accepted program meaning. This would add availability, backup, replication, and consistency dependencies.

### Distributed Toolchain service from the outset

Deferred. A modular monolith can establish semantics, transaction boundaries, and measurements before adding network and distributed-systems complexity.

## Consequences

### Expected benefits

- Agents manipulate semantic entities rather than source-file layout.
- One domain API can serve MCP, CLI, IDE, and CI clients.
- Stale edits and conflicts are detected using explicit identities and preconditions.
- Workspace state can survive reconnection and, with a persistent backend, process restarts.
- Git remains the portable history and source-distribution boundary.
- Semantic acceptance, export, commit, and push become independently observable and auditable.

### Costs and risks

- The semantic mutation API depends on a sufficiently stable SPG schema.
- Atomicity across semantic storage and filesystem/Git boundaries requires explicit recovery design.
- A persistent workspace store adds migrations, locking, backup, and corruption-handling requirements.
- A large Tool surface can overwhelm agents; operations must remain coarse-grained and context-bounded.
- MCP compatibility and authorization behavior must be tested independently.
- The design may be more complex than file editing for very small or syntax-oriented tasks.

## Validation required before acceptance

The proposal must pass the RT-19 exit criteria, including:
- typed mutations against exact baselines;
- immutable accepted snapshots;
- deterministic import/export round trips;
- stale-write and concurrent-workspace conflict tests;
- crash/restart and interrupted-export recovery;
- external IDE edit detection;
- MCP adapter tests from an independent client;
- authorization and audit tests;
- comparison against direct source-file editing for correctness, review effort, latency, and context cost.

Until that evidence exists, this ADR remains Proposed and must not be cited as an accepted architecture.
