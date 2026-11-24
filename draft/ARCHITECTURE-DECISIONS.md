# Architecture Decision — Immutable Components and Single-Version Toolchain Compatibility

**Status:** Accepted project architecture decision  
**Date:** 2026-11-20  
**Scope:** Component immutability and caller/callee compatibility at build time  
**Related:** [RT-20 contract identity and compatibility](../research/RT-20/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md), [Scenarios 109–111](../research/README.md#core-semantic-and-type-research), [Scenario 134](../research/RT-18/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md)

## Decision

1. Published LLMLang components are immutable/read-only. A component version is not edited in place; a change produces a distinct component version.
2. Compatibility is required within a build performed by one coherent version of the LLMLang toolchain. This decision does not require arbitrary components built by different toolchain versions to interoperate.
3. The toolchain checks each caller-to-callee binding during that build. The caller's call arguments and the callee's declared callable prototype must satisfy the language's static typing and call-compatibility rules, as in a statically typed language.
4. A mismatch in callable shape or types is a build-time error; it is not deferred to runtime wire-schema negotiation or migration.
5. The current architecture makes no promise of cross-version wire compatibility, automatic schema evolution, persisted-message migration, schema-registry negotiation, or unknown-field forwarding between independently versioned components.

## Boundaries and non-decisions

- This decision concerns component immutability and compatibility for calls in one toolchain-version build. It does not select a serialization format or require Protobuf, Avro, CBOR, JSON, or a custom wire format.
- Callable prototype/type compatibility must not be conflated with behavioral Contract refinement. The exact semantics of behavioral contracts, proof obligations, and any distinction between exact Contract identity and refinement remain governed by separate contract/identity work; this decision does not silently resolve them.
- It does not define ABI compatibility across toolchain versions, separately compiled binary plugin compatibility, dynamic loading, external RPC, persistence formats, or cross-process protocols. If any such capability is later introduced, its compatibility requirements must be decided explicitly.
- It does not alter the existing storage relation: caller retains its required Contract reference; callee owns the single provided Contract reference, resolved through the caller-to-callee relation.

## Consequences

- Cross-format wire-schema evolution research is not a prerequisite for the current caller/callee architecture.
- Scenarios 109–111 remain bounded serialization experiments and Scenario 134 remains prior-art/reference material. They do not establish an LLMLang wire protocol or a requirement to implement one.
- Do not start the proposed Protobuf/Avro/CBOR runtime conformance matrix for the current architecture unless a new requirement introduces an external, persistent, independently versioned, or cross-toolchain data boundary.
- The relevant current build-time work is to specify and validate callable prototype/type rules and the exact caller/callee contract relation.

## Reconsideration trigger

Reopen this decision only if LLMLang adopts independently built component exchange, cross-toolchain-version linking, dynamic component loading, external RPC, persisted serialized messages that outlive a build, or a separately versioned binary/plugin ABI.

## Related research (not an amendment to the decision)

The [public interfaces proposal](../research/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md) investigates stable names resolving to immutable operation revisions and separate verified provider bindings. It is consistent with immutable published components and does not adopt cross-toolchain ABI/wire compatibility or runtime negotiation. Behavioral refinement remains a separate open question; the accepted decision above is unchanged.
