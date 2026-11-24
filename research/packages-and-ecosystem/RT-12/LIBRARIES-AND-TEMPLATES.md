# Libraries and Templates

**Status:** Proposed  
**Scope:** Conceptual design proposal for LLMLang. This document does not amend or silently override `LLMLang-CONCEPT.md` or other existing project decisions.

## 1. Summary

LLMLang should distinguish reusable semantic components from parameterized structures used to create new parts of a program.

- A **Package** is a distributable unit identified by the content hashes of its manifest, contents, and resolved dependencies.
- A **Library** is a package whose primary purpose is to provide reusable components.
- A **Template** is a parameterized description that can be instantiated into a program's Semantic Program Graph (SPG).

A package may contain libraries, templates, or both. A template may depend on libraries. These concepts should integrate with the Specification, Design, and Implementation layers of the SPG.

The central principle is that reuse should preserve semantics, contracts, traceability, and verification information—not merely copy source text.

## 2. Relationship to the Existing LLMLang Model

The proposal builds on the existing LLMLang concepts:

- **Semantic Program Graph (SPG):** reusable components and instantiated structures should be represented as typed, identifiable semantic objects with explicit relationships.
- **Specification Graph:** describes externally relevant behavior and guarantees of reusable components.
- **Design Graph:** describes their architecture and internal organization.
- **Implementation Graph:** describes executable implementation details.
- **Contracts and effects:** public interfaces should expose the guarantees and restrictions consumers need.
- **Independent verification:** claims about compatibility and correctness must be checked by tools, not accepted merely because an LLM asserts them.
- **Provenance and content addressing:** consumers should be able to identify the exact package, template, and immutable content hashes from which an object originated.

This document proposes how libraries and templates might use those concepts; it does not establish that every detail is already part of the language.

## 3. Packages and Libraries

### 3.1 Package

A Package is a distribution and dependency-management unit. It should have:

- a stable package identity;
- a content-addressed manifest/root identity;
- a manifest describing its contents;
- declared dependencies and compatibility constraints;
- integrity information for the distributed artifacts;
- optional publisher and signature metadata.

A package may contain one or more semantic components, templates, verification artifacts, documentation, or implementation artifacts.

**Open design question:** Is a Package itself a first-class SPG object, or is it a distribution-level container that references SPG objects? The latter keeps program semantics separate from packaging, while the former may simplify provenance and dependency navigation.

### 3.2 Library

A Library is a package, or a named component within a package, intended to be reused by other programs.

A library may provide three independently available layers:

| Layer | Typical contents | Consumer purpose |
|---|---|---|
| Specification | Public types, interfaces, contracts, invariants, effects, errors, state semantics | Understand and verify permitted use |
| Design | Components, architecture, internal relationships, design constraints | Inspect, extend, or audit structure |
| Implementation | Source, compiled representation, executable artifacts, implementation dependencies | Build or execute the library |

The layers should be independently content-addressable and independently identifiable. A consumer should not have to receive implementation details when the public specification and a suitable executable artifact are sufficient.

For example, a library may publish its Specification while keeping its Implementation private. This allows consumers to reason about the public contract without requiring access to source code. Such opacity limits what consumers can independently inspect, so the package must state exactly which claims can and cannot be verified from the published artifacts.

### 3.3 Public Interface

A LLMLang library interface should be richer than a list of function signatures. Where relevant, it should expose:

- public types and type constraints;
- preconditions and postconditions;
- invariants;
- effects and required capabilities;
- possible errors and failure semantics;
- state transitions and lifecycle constraints;
- concurrency and ownership constraints;
- compatibility guarantees.

Illustrative pseudo-declaration (not proposed as canonical LLMLang syntax):

```text
library Payment

interface PaymentService {
    operation authorize(request: PaymentRequest)
        requires request.amount > 0
        effects network, payment.write
        returns Authorization
        errors InvalidRequest, Declined, Unavailable
}
```

The exact syntax and the boundary between interface declarations and contracts remain open language-design questions.

## 4. Dependency Model

Dependencies should be explicit and typed. At least four useful categories can be distinguished:

1. **Interface dependency** — depends on a library's public specification and compatibility guarantees, not on a particular implementation.
2. **Implementation dependency** — depends on a particular implementation or implementation-level behavior. This is more restrictive and may reduce substitutability.
3. **Capability dependency** — requires an environmental capability, such as filesystem access, network access, cryptographic operations, or a particular runtime service.
4. **Development dependency** — needed only for development, testing, analysis, verification, or code generation, and not necessarily required by the deployed program.

A dependency declaration should identify the target package/component by Stable ID and Content Hash (or by a declared content-hash constraint), dependency kind, and any relevant capability or configuration requirements.

The system should distinguish dependencies that affect the program's public semantics from dependencies used only to build or verify it.

## 5. Content Addressing and Compatibility

Package, library, template, and SPG entity states SHOULD be identified by cryptographic content hashes rather than mutable or manually assigned semantic version numbers.

Each logical entity retains a **Stable ID**. Each immutable state has a **Content Hash** computed from:
- the entity kind and hash domain;
- canonical structured semantic content;
- sorted, typed references to hash-relevant dependencies, represented by their exact Content Hash values.

Hashes SHOULD be computed at the smallest useful SPG entity granularity: individual types, operations, contracts, effects, tests, proofs, and other semantic nodes. Module, library, template, package, and project identities can then be represented by root hashes that recursively commit to their reachable hash-relevant content.

The dependency edge kind determines propagation. An interface consumer commits to the provider's Specification hash, while an implementation consumer commits to the relevant Implementation hash. A change to an implementation that preserves the public Specification therefore need not change the hash of an interface-only consumer.

The canonical encoding MUST be deterministic. Presentation-only metadata such as names, paths, comments that have no semantic effect, timestamps, authorship, and provenance SHOULD be excluded from semantic hashes. Signatures and attestations SHOULD be attached separately to the exact hash they endorse. The initial algorithm may be SHA-256; the digest representation MUST identify its algorithm and permit future algorithm migration.

This hash identifies canonical graph content, not arbitrary behavioral equivalence. Compatibility is established by comparing specifications and, where possible, by independent verification that an implementation satisfies the required Specification.

A package registry SHOULD store immutable content-addressed objects and manifests. Dependency resolution SHOULD produce a lock record containing exact Stable ID + Content Hash references for all resolved dependencies. Broad version ranges are not required for correctness or reproducibility.

Semantic version labels SHOULD NOT be required for package identity, dependency resolution, compatibility, or build reproducibility. A project MAY attach optional human-readable release labels as metadata, but labels MUST NOT determine identity or override content hashes.

A content hash changes whenever the local canonical semantic content or a hash-relevant dependency changes. The change propagates recursively to dependents in the hash dependency DAG. Unchanged nodes and branches retain their hashes and can be deduplicated, cached, and reused.

Only the hash dependency relation must be acyclic. If the broader SPG contains cycles, those relations must either be excluded from recursive hashing or represented by an explicitly specified canonical group/root object.

## 5.1. Layer-specific hashes and compatibility

A package exposes separate Specification, Design, and Implementation root hashes. These layers may change independently:

- **Specification hash:** public contract and externally observable behavior.
- **Design hash:** internal architecture and structural organization.
- **Implementation hash:** concrete implementation and executable artifact.

Each layer hash commits to its own canonical nodes and hash-relevant dependencies. A separate build-artifact hash SHOULD include the implementation root hash, compiler/toolchain identity, build configuration, and target environment when these affect the produced artifact. Compatibility should be established by comparing the relevant specifications and, where possible, independently checking that a new implementation satisfies the required contract.

A useful compatibility question is:

> Does implementation version B satisfy the same public specification as implementation version A?

If this can be verified, consumers depending only on that specification may be able to adopt B without changing their own semantic dependencies.

The language and package tooling should distinguish:
- declared compatibility;
- compatibility inferred from structural comparison;
- compatibility supported by a verification result;
- compatibility that is unknown or not checked.

Unknown or unchecked compatibility must not be presented as proven.

## 6. Templates

### 6.1 Definition

A Template is a parameterized semantic description that can be instantiated into a program's SPG. Its immutable definition and each instantiated result are identified by content hashes, while the template's logical identity remains stable.

A template is not merely a text generator or a collection of source snippets. Its parameters and expansion describe semantic objects and relationships. Instantiation should create or connect typed SPG objects, preserve stable identity rules, and produce traceable results.

A template may declare:

- typed parameters;
- required capabilities;
- preconditions for instantiation;
- constraints and invariants;
- objects and relationships to create;
- generated contracts and tests;
- dependencies on libraries or other templates;
- postconditions that must hold after instantiation.

### 6.2 Possible Template Categories

The following categories describe intended use cases. They need not become separate language-level entity types; one general Template mechanism with different constraints may be sufficient.

| Category | Purpose | Example |
|---|---|---|
| Structural Template | Creates a reusable structural pattern | CRUD module, REST API, repository structure |
| Behavioral Template | Defines reusable behavior or a state machine | Retry policy, approval workflow, lifecycle |
| Specification Template | Adds a reusable set of requirements or contracts | Authorization rules, audit requirements |
| Project Template | Establishes a larger initial program or subsystem structure | Service skeleton, application architecture |

A template may combine several categories. For example, a service template may create specification requirements, design components, implementation placeholders, and test scenarios together.

### 6.3 Instantiation

Instantiation should be an explicit semantic operation.

A conceptual process:

1. Resolve the exact template Content Hash and the exact hashes of its dependencies.
2. Collect and type-check required parameters.
3. Check template preconditions and required capabilities.
4. Construct the proposed semantic objects and relationships.
5. Check template postconditions and validate the resulting graph.
6. Produce a traceable instantiation result that can be reviewed and, where required, accepted as a Change Set.

If required parameters are missing or constraints cannot be satisfied, instantiation should fail with structured diagnostics or request clarification. It should not silently invent business decisions.

### 6.4 Result of Instantiation

The instantiated objects should become part of the consumer program's SPG and should be independently identifiable and editable according to normal language rules.

The result should retain provenance links to:
- the source template Stable ID and exact Content Hash;
- the instantiation parameters;
- the resulting objects;
- any subsequent modifications;
- verification results associated with the instantiated structure.

This makes it possible to understand where an object came from without making the running program depend on a mutable template definition.

## 7. Template Updates and Customization

Changing a template must not silently rewrite existing instances.

A template update should instead make available an explicit migration or update proposal. Such a proposal should identify:

- the source and target template Content Hashes;
- the affected instantiated objects;
- the semantic differences;
- conflicts with local modifications;
- required parameter changes;
- verification work that must be repeated.

The consumer should be able to review and selectively adopt the update. Applying it should produce a normal, traceable Change Set.

A template instance may contain:
- generated objects that remain aligned with the template;
- locally customized objects;
- objects that have been detached from template management.

The exact mechanism for representing these distinctions is an open design question. Any mechanism should avoid overwriting user changes or obscuring their provenance.

## 8. Relationship Between Packages, Libraries, and Templates

The proposed conceptual relationship is:

- A **Package** is the distribution and content-addressing unit.
- A **Library** is a reusable semantic component or package role.
- A **Template** is a parameterized semantic construction mechanism.
- A package may contain libraries and templates.
- A template may depend on one or more libraries.
- A library may expose templates as part of its reusable contents.

These are different responsibilities and should not be conflated. In particular, a template is not simply a library with parameters: a library provides reusable behavior or capabilities, while a template creates a new semantic structure from parameterized definitions.

## 9. LLM and Tooling Workflow

The library/template model should support a context-efficient workflow:

1. The tooling provides a compact package catalog with names, content hashes, summaries, and public interface metadata.
2. The LLM identifies the relevant package or template without loading every implementation.
3. The tooling retrieves only the required specification, contracts, parameters, and dependency metadata.
4. The LLM proposes a template instantiation or library integration as structured semantic changes.
5. The system validates types, dependencies, capabilities, preconditions, and graph invariants.
6. A human reviews business-significant decisions and the semantic diff where approval is required.
7. Accepted changes are committed with provenance and exact dependency Content Hash values.
8. Independent verification checks the resulting program and records results against exact input Content Hash values.

This follows the token-efficiency principle of retrieving the minimum relevant context, using stable references, and exchanging structured changes rather than repeatedly transmitting entire source documents.

The LLM should not be trusted to assert that a package is safe, compatible, correctly signed, or verified. These claims must be checked by the relevant tooling.

## 10. Registry, Locking, and Reproducibility

A package ecosystem will likely need:

- one or more package registries;
- immutable content-addressed package and component artifacts;
- exact content-hash dependency references and optional policy constraints;
- a lockfile or equivalent resolved-dependency record;
- integrity hashes;
- optional publisher signatures and attestations;
- reproducible build metadata where applicable.

A lockfile (or equivalent resolution record) should record the exact Stable ID + Content Hash references of every resolved package, component, template, and build input. It must not rely on mutable tags or broad version ranges to identify build inputs. This supports repeatable builds, auditability, and meaningful verification results.

Registry trust, publisher identity, signing policy, and offline distribution are separate policy questions and should not be inferred solely from package availability.

## 11. Verification and Trust Boundaries

Libraries and templates should carry machine-readable claims and, where available, verification artifacts. Examples include:

- interface conformance results;
- contract verification results;
- test and scenario results;
- dependency and capability analysis;
- reproducible build attestations;
- artifact integrity and publisher signatures.

Verification evidence must identify the exact Content Hash values of all relevant inputs. A result for one implementation or specification Content Hash must not automatically be treated as evidence for a different version.

The system should preserve distinctions such as PROVEN, DISPROVEN, UNKNOWN, and NOT_CHECKED where those statuses are used by the broader LLMLang verification model. An opaque implementation may support contract-level reasoning while leaving implementation-level properties unknown.

Licensing and provenance also matter: the tooling should make package origin and declared license information discoverable, while the precise enforcement model remains a policy decision.

## 12. Design Questions Requiring Further Decisions

The following questions remain open and should be resolved before treating this proposal as normative:

1. Is Package a first-class SPG object or a distribution-level container?
2. Is Library strictly a kind of Package, a semantic role, or both?
3. Must every published library provide a Specification? What minimum contract is required for opaque binaries?
4. Are Specification, Design, and Implementation root hashes independently addressable, and what canonical encoding do they use?
5. Which dependency categories are mandatory in the initial design?
6. Are Templates first-class language constructs, package artifacts, compiler/tooling constructs, or a combination?
7. Does instantiation create copies of semantic objects, parameterized references, or a hybrid?
8. How should template migrations handle local modifications and partial adoption?
9. Which parameter kinds are supported: values, types, capabilities, contracts, policies, or requirements?
10. How are generated, customized, and detached objects represented?
11. Which verification artifacts are required for publication, and which are optional?
12. What are the registry, lockfile, signing, and trust policies, including hash algorithm migration?
13. How should licensing metadata and license compatibility be represented and checked?

## 13. Suggested Initial Direction

As a starting point for further discussion, the following direction appears coherent with the existing LLMLang architecture:

- Keep Package as a distribution/identity concept unless a concrete need justifies making it part of the program's semantic graph.
- Treat Library as a reusable component role, not as a fundamentally separate semantic model.
- Require a machine-readable public Specification for libraries intended for semantic integration; allow opaque implementations when their verification limits are explicit.
- Make Templates semantic, parameterized constructs whose instantiation creates ordinary SPG objects.
- Preserve template provenance, but never propagate template changes to existing instances implicitly.
- Represent dependency kinds explicitly.
- Resolve dependencies to exact immutable Content Hashes for reproducible builds.
- Treat compatibility and verification as evidence-backed claims, not naming conventions.

These are recommendations for discussion, not accepted project decisions.

## 14. Conclusion

Libraries should let LLMLang programs reuse components through explicit, machine-readable contracts. Templates should let programs create new semantic structures through typed, validated instantiation. Packages should make these artifacts content-addressable, distributable, and reproducible.

Together, these mechanisms can provide reuse without sacrificing the properties central to LLMLang: explicit semantics, stable identity, traceability, independent verification, and controlled change.

## Public-interface integration (2026-11-24; proposed)

Extend the existing Public Interface section: the stable qualified export name is resolved to an immutable public operation revision and contract; a library or build binding selects a concrete immutable provider. Providers declare their own contracts; both body correctness and contract refinement are checked under exact target assumptions. Templates generating a new export or adapter must establish the same obligations for each instantiated revision. A library may publish interface-only design material, but an executable closure needs admitted providers. Distinguish package export namespace, semantic operation identity, provider binding and external ABI symbol.

Related: [Public interfaces and verified contract refinement](../RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## Explicit assumptions and conditional verification (RT-36; proposed)

Opaque binaries may supply typed contract premises for conditional caller proofs. Pin provider artifacts, ABI and transitive dependencies; keep authorization, bounded evidence and proof separate. Publication and runtime selection must not silently convert declared contract to proved conformance. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](../RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This is a candidate follow-up, not an adopted rule or new experimental result.
