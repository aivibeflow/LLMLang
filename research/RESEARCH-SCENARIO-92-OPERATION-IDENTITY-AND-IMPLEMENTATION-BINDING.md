# Research Scenario 92 — Operation Identity and Implementation Binding

**Status:** Evidence-linked architecture comparison; no OpHash envelope or binding rule selected
**Research areas:** RT-03 semantics, RT-04 interfaces/effects, RT-05 identity, RT-07 evidence, RT-11 cache keys, RT-12 libraries
**Updated:** 2026-11-19

## 1. Question and relation to existing work

What exactly does an `OpHash` promise to a caller: a versioned interface/contract, a particular implementation behavior, or a resolved call binding that joins a semantic operation to a concrete implementation and target?

[LL-001](../TODO.md#ll-001--define-the-canonical-ophash-envelope) asks which canonical semantic data belongs in an OpHash. [Global Semantic Artifact Store §3.6](GLOBAL-SEMANTIC-ARTIFACT-STORE.md#36-operation-identity-and-call-address) already proposes distinct Operation Stable ID, OpHash, and Implementation Hash, and says implementations may serve an OpHash only with compatibility evidence. It also explicitly leaves the envelope and its relationship to Interface, Contract, and Target Profile unspecified. [Scenario 91](RESEARCH-SCENARIO-91-VERSIONED-CONTENT-ADDRESSES-AND-DIGEST-MIGRATION.md) separates digest suite, representation, domain, lineage, and trust; this report focuses on which semantic artifacts should be referenced by the operation identity.

The important ambiguity is the word “exact.” A contract normally constrains allowed behavior; it need not select one unique implementation trace or result. If a call records only an OpHash for such a contract, its precise behavior can still depend on which compatible implementation is bound. Conversely, including the implementation body makes the operation address precise but couples call identity to implementation changes and makes transparent replacement impossible even when behavior is preserved. The project must state which guarantee is intended before fixing fields in the envelope.

## 2. Prior-art comparison

### WebAssembly Component Model WIT: typed import/export contract

WIT describes imports and exports to a component. Its interface is a collection of functions and types and is an interoperable unit consumed from a host or implemented by a component. Package/interface names and optional semantic versions identify the public naming/versioning layer. This is an interface and ABI contract; it does not, by itself, prove or hash a unique function behavior.

**Implication:** an interface artifact can be stable and language-neutral while leaving implementation choice to a separate binding. A function signature alone cannot substantiate an OpHash promise of exact behavior.

Source: [WebAssembly Component Model — WIT](https://github.com/WebAssembly/component-model/blob/main/design/mvp/WIT.md), especially “WIT Interfaces” and package/interface references.

### Bazel Remote Execution API: action identity for cacheable execution

The Remote Execution API models an `Action` with a command digest, input-root digest, timeout, optional cache-suppression flag and salt, and platform requirements. It makes timeout part of the action identity: differing timeouts must not share a cache result because a longer execution might otherwise hide that a shorter timeout is insufficient. Platform properties are also part of the action digest, and equivalent platform properties must be put in a canonical sorted order.

**Implication:** an Action digest answers “which execution request and environment should produce this result?” It includes operational inputs that should not automatically become part of a language-level callable operation's semantic identity. A semantic operation, executable binding, and compiler/test/proof action need distinct identities.

Source: [Bazel Remote Execution API `Action` and `Platform` messages](https://github.com/bazelbuild/remote-apis/blob/main/build/bazel/remote/execution/v2/remote_execution.proto), particularly the `Action` and `Platform` definitions.

### Nix derivations: address of how an output was made versus what it contains

Nix input-addressed outputs derive their store path from the derivation that produced them, not just the output bytes. Thus identical contents produced in different ways can receive different store paths. Nix documents quotient hashing as a way to ignore selected derivation differences where that prevents unnecessary rebuilds, such as fetching details that do not change the fixed output.

**Implication:** the recipe/provenance identity and the output content identity serve different purposes. A LLMLang implementation hash, Action Key, and output Artifact Hash should not be collapsed into OpHash. A controlled equivalence/quotient rule can recover reuse, but only where its soundness conditions are stated.

Source: [Nix Reference Manual — Input-addressing derivation outputs](https://nix.dev/manual/nix/2.35/store/derivation/outputs/input-address).

### OCI descriptors: exact byte content with type and verification metadata

An OCI descriptor combines a media type, a digest of raw content bytes, and a byte size. It permits independent verification of the targeted bytes and lets artifact type vary independently from digest algorithm in appropriate uses. This is a content-addressing contract, not a behavioral or callable contract.

**Implication:** artifact type/domain and digest identify what kind of bytes are addressed, but an implementation digest alone does not establish conformance to an operation's contract.

Source: [OCI Image Specification — Content Descriptors and Digests](https://github.com/opencontainers/image-spec/blob/main/descriptor.md).

## 3. Identity layers and claims

| Identity/evidence object | Claim it can make | Must not be inferred from it |
|---|---|---|
| Operation Stable ID | These immutable operation versions belong to one declared logical lineage. | That the versions have equal behavior, same interface, or same implementation. |
| Interface Hash | These versions expose the same canonical callable shape and ABI-relevant interface. | That their contracts or behaviors match. |
| Contract Hash | These versions use the same canonical pre/postconditions, invariants, declared effects, and other contract clauses. | That a contract is complete, satisfiable, or uniquely determines behavior. |
| OpHash | A versioned operation-definition envelope with an explicit semantic claim and immutable references. | Which implementation is selected, or that the claim is proven, unless the envelope explicitly states it and evidence supports it. |
| Implementation Hash | These are the same canonical implementation artifact and dependencies. | That it satisfies an operation contract or behaves the same as another implementation. |
| Binding Hash | This exact operation/implementation/target/evidence association was selected. | That its evidence is sound unless verifier, assumptions, toolchain, and trust are validated. |
| Action Key | This exact build/test/proof/analyzer request and its result-determining inputs are the same. | That the output is semantically correct or that the operation identity is unchanged. |
| Artifact Hash | These output bytes are the same under a named digest suite. | That the bytes are correct, trusted, or semantically equivalent. |

This decomposition extends, rather than replaces, the distinctions already proposed in the semantic artifact store and semantic compilation cache. Names, descriptions, authors, timestamps, registry locations, licences, and signatures remain metadata/attestations unless the language explicitly gives one semantic force.

## 4. Candidate OpHash models

| Candidate | Envelope claim | Effect of implementation change | Effect of target change | Main advantage | Main risk / required condition |
|---|---|---|---|---|---|
| **O-A Contract-addressed operation** | Typed references to canonical interface and contract, plus semantic context that changes the contract's interpretation. | OpHash remains if the declared operation contract is unchanged; Implementation Hash and Binding Hash change. | Only semantic/ABI-relevant target facts affect OpHash; deployment compatibility stays in a binding. | Separates callable obligation from replaceable implementation; supports multiple realizations. | “Exact operation semantics” means an allowed-behavior contract, not one exact trace. Call semantics rely on a valid explicit binding and complete contract. |
| **O-B Definition includes exact body** | Interface, contract, effects, and canonical implementation/semantic body are committed together. | Any body change makes a new OpHash, even if an equivalence proof shows behavior unchanged. | Target-specific lowering belongs in the hash only if it is part of the semantic body/ABI. | A call pinned to the hash names one body-level operation version. | Redundant coupling of contract and implementation; can impede independent implementations, library reuse, and separate linking. A body hash still requires stable semantics and dependency closure. |
| **O-C Operation plus explicit binding identity** | OpHash identifies interface/contract obligation; Binding Hash identifies the chosen implementation, target profile, and compatibility evidence. A reproducible executable/call site pins both. | Semantic callers may retain OpHash while selected implementation binding changes explicitly. | Binding changes when target selection or ABI realization changes; OpHash changes only when operation meaning does. | Makes abstract call meaning and concrete realization reviewable separately. | More identity and resolution machinery; APIs must distinguish contract-level reasoning from exact-build reproducibility. |
| **O-D Versioned tuple without an envelope object** | Call stores typed tuple `(InterfaceHash, ContractHash, SemanticContextHash)`. | Same as O-A, with tuple components independently visible. | Same semantic-context qualification. | Simple to inspect and normalize. | Tuple evolution and domain/version ambiguity are harder to centralize; duplicate tuple semantics can drift. A typed canonical envelope may be needed at serialization boundaries anyway. |

O-A and O-C can coexist: O-A defines operation meaning and O-C defines how a concrete program or deployment pins its realization. O-B is useful only if the project intends OpHash itself to identify exact implementation-level semantics; it conflicts with an architecture that allows independent implementations behind one operation contract.

## 5. Field inclusion test

For any proposed OpHash field `x`, ask:

1. Can changing `x` alter the meaning a conforming caller is entitled to rely on, under the chosen semantic observation model?
2. Is `x` already represented by an immutable typed artifact reference? If so, should the envelope reference it rather than duplicate it?
3. Is `x` only needed to select/build/test/prove an implementation? If yes, it likely belongs in Binding Hash, Action Key, or evidence input rather than OpHash.
4. If `x` is omitted, can two operations with different externally observable behavior still receive the same OpHash while both conform to their contracts? If yes, either the contract-level claim is intentionally broad, or the envelope is missing a semantic discriminator.
5. If `x` is included, does an irrelevant edit force a new call identity, compatibility proof, or rebuild? If yes, it may be over-scoped.

Candidate dimensions and provisional classification:

| Dimension | OpHash candidate? | Separate identity/evidence concern |
|---|---|---|
| Parameter/result types, labels if call semantics observe them, error/cancellation outcomes | Usually yes through Interface/Contract artifacts. | Source-level spelling/aliases can remain metadata if canonical resolution is unchanged. |
| Preconditions, postconditions, invariants, declared behavioral guarantees | Yes through Contract Hash, with logic/profile/version identified. | Proof that implementation satisfies them belongs to evidence bound to exact inputs. |
| Effects and capability requirements | Include semantic effect/authority *requirements* if they constrain call meaning or admissible observations. | Concrete capability grants, handles, credentials, and runtime host selection belong to bindings/authority tokens. |
| Evaluation, state, concurrency, ordering, divergence, and failure interpretation | Include the relevant semantic profile or contract reference if changing it changes what a caller may observe. | Runtime/toolchain versions are action inputs unless they change source interpretation; evidence and target conformance are separate. |
| ABI/calling convention | Include in the operation interface when it is part of the callable boundary and affects caller/callee compatibility. | Architecture-specific lowering choice belongs in binding/target profile unless ABI is itself a public semantic commitment. |
| Target architecture, OS, libc/kernel, feature flags | Include only a semantic-profile reference where those differences change the specified operation meaning. | Exact worker, sysroot, ABI implementation, and configuration belong to binding/action/evidence. |
| Implementation body and dependency closure | Not required by a contract-addressed OpHash; required by O-B. | Always needs a separate Implementation Hash for implementation-addressing and cache invalidation. |
| Human name, source location, owner, history, prose docs, signature, registry URI | No, unless language gives it semantic meaning. | Metadata, lineage, or attestation. |

“Include” here means be committed through the canonical envelope or immutable reference closure, not necessarily inline bytes.

## 6. Minimal discriminator fixture set

No LLMLang compiler/runtime experiment was run. Future cross-vector fixtures should hold all unrelated fields constant and record OpHash, implementation hash, binding hash, action key, selected behavior/trace, and evidence inputs.

| Edit/intervention | Contract-addressed expectation to test | Definition/body-addressed expectation to test |
|---|---|---|
| Rename operation or source file; edit prose docs | OpHash unchanged; Stable ID/history metadata may record the edit. | OpHash unchanged unless names are language-observable/imported ABI. |
| Change parameter/result type, error set, effect bound, or public ABI | New interface/contract reference and new OpHash when callable meaning changes. | New OpHash. |
| Change implementation but preserve contract; prove refinement/equivalence | Same OpHash, new Implementation Hash and Binding Hash; evidence tied to exact tuple. | New OpHash even if behaviorally equivalent. |
| Change implementation to another valid but observably different realization under a permissive contract | Same OpHash is legal only if it is explicitly a contract-level abstract call and binding selection is visible/allowed; otherwise contract is too weak or O-A is unsuitable. | New OpHash. |
| Change compiler, optimizer, target worker, or timeout | OpHash unchanged unless source semantics/ABI interpretation changes; Action Key changes when result can change. | Body OpHash still must not silently absorb build-execution details; a separate Action Key is needed. |
| Change capability grant/credential/provider | OpHash stable if requirement is unchanged; binding/authority context changes. | Same unless exact provider implementation is defined as part of the operation body/meaning. |
| Change declared semantic version (overflow, memory, concurrency, error profile) | New OpHash if interpretation of the contract changes. | New OpHash. |
| Use an implementation with incomplete/unknown dependency extraction | No compatibility claim or transparent binding; mark unknown/fail closed. | No trustworthy identity closure without complete canonical body/dependencies. |

These cases discriminate the meaning of “exact”; they do not decide it. A useful follow-up is an inline counterexample where two bodies satisfy the same contract but return different results, then compare a call bound only by OpHash with a call that also pins Binding Hash. Existing finite witnesses in [the call-site refactoring experiment](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md) and [COR-09](RT-03-04-SHARED-SEMANTICS-CORPUS.md#7-cor-09--typed-calls-and-private-local-state) provide starting points, not complete OpHash validation.

## 7. Provisional synthesis and unresolved gates

Prior art supports keeping interface/contract identity separate from implementation, binding, action-cache, and output-content identities. It does not settle whether LLMLang OpHash denotes an abstract operation contract or an exact executable behavior version. If it denotes the former, the specification must say that multiple outputs/traces may be permitted and must make implementation binding explicit wherever reproducibility or an exact trace matters. If it denotes the latter, it must define canonical implementation closure and the cost of changing call identity on body edits.

The apparent direction O-A + O-C is consistent with the current Global Semantic Artifact Store and TODO recommendation, but is not selected here. Before normative adoption, resolve:

1. **LL-001:** define “exact semantics” as either contract-level allowed behavior or body-level behavior; version and type the envelope.
2. **LL-002:** define explicit lineage independently of OpHash; split/merge and equivalent-but-independent operations need lifecycle rules.
3. **LL-003:** discovery may find candidates, but acceptance requires evidence against exact OpHash and required target/binding.
4. **LL-004/005:** the envelope needs canonical encoding, domain/version tags, and a rule for hash-relevant references/cycles.
5. **LL-007/008:** classify semantic target dimensions versus binding constraints; bind evidence to exact operation, implementation, assumptions, target, and verifier/toolchain.
6. **LL-021:** an Action Key must include result-determining toolchain, target, inputs, config and execution details without contaminating OpHash.

No option is accepted, no TODO is resolved, and no behavior or conformance tests are claimed.

## 8. References

- [WebAssembly Component Model — WIT format](https://github.com/WebAssembly/component-model/blob/main/design/mvp/WIT.md)
- [Bazel Remote Execution API — remote_execution.proto](https://github.com/bazelbuild/remote-apis/blob/main/build/bazel/remote/execution/v2/remote_execution.proto)
- [Nix Reference Manual — Input-addressing derivation outputs](https://nix.dev/manual/nix/2.35/store/derivation/outputs/input-address)
- [OCI Image Specification — Content Descriptors and Digests](https://github.com/opencontainers/image-spec/blob/main/descriptor.md)
- [LL-001 — canonical OpHash envelope](../TODO.md#ll-001--define-the-canonical-ophash-envelope)
- [Global Semantic Artifact Store §3.6](GLOBAL-SEMANTIC-ARTIFACT-STORE.md#36-operation-identity-and-call-address)
- [Scenario 91 — versioned content addresses](RESEARCH-SCENARIO-91-VERSIONED-CONTENT-ADDRESSES-AND-DIGEST-MIGRATION.md)
- [RT-05 / RT-20 call-site refactoring experiment](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md)

## Public-interface integration (2026-11-24; proposed)

Add the public-name/catalog revision as a separate resolution layer to the identity vectors. Distinguish an exact operation revision from a stable external selector and exact provider binding. A public contract may admit different traces, so OpHash pinning alone does not imply deterministic exact execution across providers. Pin the chosen provider and execution context for reproducibility; compare static resolution, explicit separately linked provider selection, and runtime admission as distinct research alternatives. Preserve the existing WIT/type-shape comparison without treating signature matching as contract refinement.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
