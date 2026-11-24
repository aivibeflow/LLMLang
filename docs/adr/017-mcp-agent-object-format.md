# ADR-017 — Default object format for agent interaction through MCP

- **Status** — Accepted
- **Date** — 2026-11-23
- **Decision owners** — LLMLang project
- **Related architecture** — [ADR-015 — Toolchain Server and semantic development API](015-toolchain-server-semantic-api.md)
- **Related research** — [RT-19 — Toolchain Server and Semantic Development API](../../research/toolchain-and-collaboration/RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md)

## Context

LLMLang agents interact with the Semantic Program Graph (SPG) through the Toolchain API exposed by MCP. The API must provide a predictable textual representation that agents can generate, inspect, and modify, and that Toolchain implementations can parse consistently.

The choice concerns the representation of SPG objects exchanged with agents. It does not select MCP's protocol framing, the canonical repository representation, an internal storage encoding, or the Content Hash algorithm.

## Decision

**JSON is the default format for representing SPG objects exchanged with agents through MCP.**

The following rules apply:

1. Each independently addressable SPG graph object is represented as one JSON value/serialization element. Nested structures belonging to that object remain nested within that value.
2. References between independently addressable graph objects are represented using their SPG IDs, not by embedding duplicate object definitions or introducing a second in-document graph-reference mechanism.
3. MCP-facing Tools and Resources that expose or accept SPG object representations use JSON by default.
4. Support for other textual formats is permitted when justified by a concrete interoperability or implementation need, but such support is not a priority and must not fragment the default agent workflow.
5. An alternative format must preserve the same SPG semantics and must not create a separate semantic model.

This decision is about the object representation carried through MCP-facing API operations. It does not redefine MCP's JSON-RPC protocol messages.

## Explicit scope exclusions

This decision does not determine:

- the canonical textual representation of the Git repository;
- the on-disk or in-memory representation of SPG objects;
- the canonicalization profile for repository serialization;
- the Content Hash or graph-hashing algorithm;
- the complete JSON schema, Toolchain operation schemas, or MCP capability/version profile.

Those concerns require their own specifications and decisions. In particular, choosing JSON for agent-facing exchange does not imply that RFC 8785/JCS is automatically the canonicalization algorithm for SPG.

## Consequences

- Agents can use the widely supported JSON ecosystem as the default representation for SPG objects.
- Rust, Go, and C++ clients can use mature JSON libraries without requiring Ion-specific support.
- The Toolchain must define and validate the JSON schemas for each exposed object/operation.
- The project should avoid introducing alternative formats without a demonstrated need and cross-language conformance tests.
- Repository canonicalization and Content Hash remain separate design decisions.
