# ADR-020 — Immutable semantic objects and calls pinned by ImplHash

- **Status** — Accepted
- **Accepted** — 2026-11-25
- **Date** — 2026-11-25
- **Decision owners** — LLMLang project
- **Scope** — Published semantic objects, direct implementation calls, and bindings to concrete implementations
- **Related decisions** — [ADR-023 on immutable components](023-immutable-components-and-toolchain-compatibility.md) · [ADR-019 on native library interoperability](019-bidirectional-native-library-abi.md)

## Context

A public interface gives callers a stable qualified name. A resolved binding must identify the implementation selected for the build so that the same call cannot silently acquire a different body or behavioral specification. This proposal applies the existing implementation identity model to semantic objects and call bindings. [Glossary](../GLOSSARY.md#implementation-hash-implhash) · [Public interface research](../../research/semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md)

## Decision

1. **Publish immutable semantic objects.** A published object retains its content under its identity. Changing that content creates a new object. A catalog or branch head may advance to a new object. Existing references continue to identify their original objects.
2. **Use `ImplHash` for concrete implementation identity.** Compute it from the canonical implementation, its provided behavioral specification or exact reference to it, and all hash-relevant semantic dependencies. Changing the body, specified behavior, or a hash-relevant dependency changes the implementation identity. The caller retains its required Contract reference. The implementation owns the provided Contract reference.
3. **Pin direct calls.** A direct call identifies the exact callee by `ImplHash` in the resolved semantic representation. Source syntax may use a name resolved by the Toolchain. A public interface is bound by qualified name in a pinned catalog or snapshot. When that binding selects a concrete provider, record its exact `ImplHash` in the resolved binding. Native code may lower the call to a symbol or address while preserving the selected callee.
4. **Keep the public Contract and the provided Contract separate.** Each immutable public interface revision references the public Contract that callers may rely on. The concrete implementation owns its own provided Contract reference. When binding or rebinding a public interface, the Toolchain checks the callable signature and verifies that the provided Contract refines the public Contract for the applicable profile and assumptions. The provider must accept every input and state admitted by the public Contract and preserve its guarantees, including applicable effects. Establish separately that the implementation satisfies its provided Contract. Accept the binding only when the required evidence applies to the exact interface revision, both Contracts, and the selected `ImplHash`.
5. **Make rebinding explicit.** A call pinned to one implementation keeps that binding when another version is published. Selecting a different implementation requires a new binding and verification against the caller's requirements. If the pin is part of the caller's canonical body, changing it creates a new caller identity and propagates through hash-relevant references. If the pin is in a separate binding, publish a new binding revision and revalidate dependent evidence. Preserve the previous snapshot and its bindings.
6. **Validate exact references.** The Toolchain must reject an unresolved or mismatched pin and verify callable compatibility and applicable behavioral obligations. Evidence may be reused when its subject and assumptions still apply to the exact binding. A missing object must not trigger substitution by name or by similarity.

## Boundaries and consequences

`ImplHash` identifies a concrete implementation. Operation and Contract identities retain their separate roles. A hash pin allows a caller to retain an earlier implementation, provided the required object remains available. This ADR leaves canonical encoding, digest algorithms, recursive-group identity, retention policy, and the rules for abstract calls and dynamic dispatch to their respective specifications. External callers use the native ABI boundary defined by ADR-019.

## Implementation validation

- Publish a replacement with the same public name and a changed body or behavioral specification. Verify that it gets a distinct `ImplHash` and that the previous snapshot still resolves to the original implementation.
- Bind two implementations with different provided Contracts that both refine the same public Contract. Reject an implementation with a matching signature that strengthens a public precondition or weakens a public guarantee. Check identity propagation for a direct pin and evidence invalidation for a separate binding.
- Reject missing or mismatched pins and stale evidence. Verify that lowering preserves the selected callee.
