# RT-15: Prior-art comparison for semantic identity and storage

**Date:** 2026-11-23  
**Baseline:** `b10edf42486bb91791af5489c2bf581d6250d8b6` (`main`)  
**Scope:** PLAN §1.5. This is a comparative primary-source review, not a compatibility test, architecture decision, or endorsement of any project's whole model. Official documentation was reviewed on 2026-11-23 alongside current LLMLang research.

## Comparison

| System | What its identity / model is good at | Boundary for LLMLang |
|---|---|---|
| [Unison hashes](https://www.unison-lang.org/docs/language-reference/hashes/) and [codebase model](https://www.unison-lang.org/docs/the-big-idea/) | Definitions get a hash of internal syntax structure excluding names; cycles have an explicit canonical ordering. Names can be remapped separately. The codebase stores processed definitions and typecheck results. This is a strong precedent for separating immutable definition identity from human names and for attaching derived cache state to immutable definitions. | Unison's hash unit and source-language assumptions are language-specific. LLMLang still needs separate identities for operation contract, concrete implementation/binding, action, output artifact, and evidence; a syntax-tree hash does not settle those distinctions or dependency completeness. |
| [Git data model](https://git-scm.com/docs/gitdatamodel) | Typed immutable objects are content-addressed; trees map paths/modes to objects; commits add a snapshot tree, parent links, author/committer metadata and message. Reuse of unchanged blobs makes it an effective history/transport and branch graph. | Git object identity commits to the physical object's type/content and tree paths; commit identity also changes with history/metadata. It is not a canonical identity for a language-level operation or its contract. Use Git for repository state/history/transport, not as the semantic hash authority. |
| [LLVM IR](https://llvm.org/docs/LangRef.html) and [bitcode encoding](https://llvm.org/docs/BitCodeFormat.html) | LLVM provides typed SSA IR for compiler analyses/transforms and equivalent in-memory, textual and bitcode representations. A verifier checks LLVM well-formedness. Bitcode is an efficient target/toolchain interchange artifact. | The representation is deliberately low-level and backend-oriented. Parser acceptance/well-formedness does not prove source-language correctness. The serialization is an encoding of LLVM IR, not a stable LLMLang semantic identity or cross-version canonical form. Key backend artifacts to exact toolchain/target inputs and validate source correspondence independently. |
| [Nix store paths](https://releases.nixos.org/nix/nix-2.22.3/manual/store/store-path.html) | Store objects use digest-bearing opaque paths with a readable name; reference closure and store context are explicit. This demonstrates a useful artifact-store model and highlights that relocation/reference context can affect reproducibility. | A store path is an artifact locator/build-store identity, not necessarily a semantic operation identity. Names and store-directory context have their own behavior; do not copy its path identity as LLMLang's portable OpHash. |
| [Bazel remote cache](https://bazel.googlesource.com/bazel/%2B/23b0b8a45a103f78d37f9338f0e80caffa076d6f/site/docs/remote-caching.md) | Separates Action Cache metadata (action hash → result metadata) from CAS output blobs; declared action inputs/outputs enable reuse; supports local/remote read and write policy. This directly matches LLMLang's needed separation among computation identity, result record and artifact bytes. | Soundness depends on the action's declared inputs and reproducibility. Remote-cache access control and poisoning recovery are operational policy. The cache does not define LLMLang semantics or prove the dependency declaration complete. |
| [OCI image manifests and digests](https://docs.docker.com/reference/api/registry/latest/) and [digest-bound signing](https://docs.docker.com/learn/content/prove-where-your-image-came-from/) | A manifest references digest-addressed config/layer blobs; tags are movable names; signatures/attestations can reference an exact digest without changing the artifact. Good precedent for immutable distribution references, alias separation and provenance as a separate association. | Container image identity is a package/artifact identity. Its digest does not establish semantic correctness, compatibility, or trust without an authenticated attestation and policy. |
| [Maven repository layout](https://maven.apache.org/pom.html#Repositories) | Human/package coordinates, versioned path layout, local-first retrieval, remote repositories and update/checksum policies provide discoverability and established package delivery. | Coordinates and mutable snapshot metadata are resolution names/policy, not immutable semantic identity. Checksums detect byte mismatch only relative to the checksum source; they do not prove publisher authority or behavior. |

## Cross-system comparison

The useful choices are composable layers, not mutually exclusive complete architectures:

1. **Semantic definitions:** Unison supplies the closest precedent for immutable typed definitions with names outside identity. LLMLang must enrich this with explicit interface/contract, implementation binding, dependency, and provenance boundaries.
2. **Repository history and collaboration:** Git supplies snapshots, branches, ancestry, and interoperable transport. Its object IDs remain repository-object identities.
3. **Backend and build results:** LLVM defines a target-facing IR/artifact boundary; Bazel illustrates that action-result metadata and output CAS objects are distinct. LLMLang's ActionKey and ArtifactHash should therefore remain distinct from semantic hashes.
4. **Distribution and discovery:** Nix/OCI illustrate digest references and artifact closure; Maven illustrates named coordinates and repository policy. LLMLang can provide immutable content references and readable aliases without making aliases the authority.
5. **Trust:** digests detect identity/byte mismatch; authenticated signatures/attestations and explicit verifier/publisher policy answer who asserted what. Neither substitutes for semantic validation.

## Candidate synthesis and decision boundary

For further LLMLang experiments, retain a candidate layered model:

```text
reviewable source / explicit semantic graph
  -> typed semantic object identity and dependency references
  -> Git commit/tree for repository history and interchange
  -> ActionKey for a declared toolchain computation
  -> ArtifactHash-addressed result bytes
  -> optional signed evidence/provenance attached to exact subjects
```

This synthesis preserves the strongest separations found in the sources and in LLMLang's existing proposals. It does **not** settle canonical SPG structure, hash payloads/algorithms, identity propagation through recursive definitions, a mandatory repository representation, cache formats, package registry semantics, or trusted-producer policy. Those remain dependencies in PLAN §§1.1–1.3, 3.1–3.3, and 7.4. No implementation is selected by this prior-art comparison.

## Review limits

This review compares official project documentation, not full implementations or performance. It does not validate the sources' claims experimentally, survey every content-addressed store or package registry, or establish compatibility with LLMLang requirements. The next architecture decision requires the unresolved semantic identity and dependency rules to be specified and independently tested first.
