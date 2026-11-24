# Research Scenario 93 — Cache Soundness, Result Envelopes, and Trust

**Status:** Comparative research; no LLMLang cache design selected  
**Date:** 2026-11-19  
**Scope:** LL-021 / RT-11: when a cached action result is reusable, what the result record must bind, and how integrity and producer trust differ.

## 1. Question and boundary

The existing [Semantic Compilation Cache proposal](SEMANTIC-COMPILATION-CACHE.md) already separates Semantic Hash, Action Key, and Artifact Hash; models compilation as a dependency graph; and proposes conservative handling of incomplete dependencies. This scenario focuses on the remaining correctness boundary: an exact key is only sound if it closes over every result-determining input, and retrieving bytes by digest does not establish that the action result is valid or trusted.

The specific questions are:

1. Which inputs and execution constraints belong in the Action Key, including output shape and resource limits?
2. What must an Action Result envelope say before a consumer may reuse it?
3. Which reuse classes can tolerate an inexact or prefix match?
4. How should dependency uncertainty, nondeterminism, poisoning, and evidence scope affect reuse?

This is prior-art analysis and a proposed discriminator set. It does not add a cache protocol, close LL-021, or select an option.

## 2. Evidence from existing systems

### 2.1 Bazel Remote Execution API: action result map plus content store

The REAPI has two distinct lookup relations. The Action Cache maps a digest of the encoded `Action` to an `ActionResult`; the CAS stores individual input/output blobs by their own content digests. The API explicitly describes Action Cache lookups as results of prior executions and CAS as storage addressed by each blob's content. [Remote Execution API](https://github.com/bazelbuild/remote-apis/blob/main/build/bazel/remote/execution/v2/remote_execution.proto)

The encoded action commits to the command, input-root directory, timeout, non-cacheable flag, cache salt, and platform requirements. The protocol says distinct timeouts are distinct Actions so a result from a long-timeout run cannot hide a too-short timeout; platform requirements are part of the action digest. Command environment variables and output paths are canonicalized for stable identity. The ActionResult separately records exit code and output files/directories and refers to their content digests. These are useful examples of a *result envelope*, not proof that an arbitrary action is deterministic or safe to share.

The API asks clients to make actions reproducible for cache correctness and permits an explicit `do_not_cache` control. This exposes a key design split: the key names the request; cacheability policy states whether identical requests can safely share a result.

### 2.2 Nix: declared inputs and sandbox are assumptions behind content addressing

Nix describes derivations as processes that run in a sandbox whose reads are limited to declared store inputs and whose writes are captured as designated outputs. Its content-addressed derivation discussion conditions repeatable output addresses on complete sandboxing or on residual impurities being irrelevant to behavior. [Nix glossary](https://nix.dev/manual/nix/2.35/glossary), [content-addressed derivation outputs](https://nix.dev/manual/nix/2.31/store/derivation/outputs/content-address.html)

This is a soundness precondition: a digest cannot repair an incomplete input model. If network, clock, host files, undeclared environment, or ambient tool state affect output, either capture/control that input, normalize it with a specified equivalence, or decline reuse.

### 2.3 GitHub Actions: dependency-cache hints and writer boundaries

GitHub Actions dependency caching allows a requested key plus `restore-keys`; a prefix match can yield a usable restored dependency cache even when the exact key was absent. The documentation exposes `cache-hit` specifically to distinguish exact match. This mechanism is for restoring dependencies and must not be treated as a proof that a compiler/test/proof action's exact result is valid. Low-trust workflows are read-only in the default-branch cache scope to reduce cache poisoning; the docs also warn that untrusted workflows may read sensitive cache contents and poisoned caches can execute code in trusted workflows. [Dependency caching reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching), [security concepts](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching)

This comparison suggests separating *candidate material reuse* from *authoritative result reuse*. A prefix-restored package directory may be an optimization hint followed by exact dependency verification; it cannot stand in for an exact Action Key match and result validation.

## 3. Candidate result envelope

The following envelope is a research candidate, not a normative schema:

```text
ActionResultEnvelope {
  action_key
  action_schema_and_kind
  declared_input_root_and_dependency_closure
  action_implementation_and_toolchain_identity
  language_version_and_component_registry_digest
  target_platform_and_result_determining_configuration
  execution_constraints                 // e.g. timeout if semantically relevant
  dependency_completeness               // complete | unknown + reason/evidence
  determinism_class                     // byte | canonical-semantic | non-cacheable
  termination_status                    // success | deterministic failure | incomplete
  declared_output_manifest[] { path, kind, artifact_hash }
  diagnostics_or_standard_streams?      // only if consumer-visible result
  applicability_claims[]                // property, subjects, assumptions, scope
  provenance_ref                        // producer/executor identity and policy data
  validation_or_attestation_refs[]?
}
```

The envelope has several logically independent claims:

| Claim | Evidence required | Does not establish |
|---|---|---|
| Request identity | Exact canonical Action Key | That inputs were complete or execution correct |
| Output integrity | Recomputed Artifact Hash matches retrieved bytes/tree | That the producer ran the requested action |
| Applicability | Exact subjects, assumptions, target, property and evidence scope match current request | Producer authorization or proof soundness |
| Producer provenance | Authenticated producer/executor record and policy | That its software is correct |
| Correctness | Trusted verifier, reproducible independent recomputation, or explicit bounded validation | Broad claims beyond the validated property |

Successful build artifacts, diagnostics, deterministic failures, tests, and proof results are not interchangeable result kinds. A failure can be reused only if it is a stable action result (not timeout, worker loss, cancellation, quota exhaustion, or transient service failure) and the consumer asks for the same failure semantics. A test/proof result is evidence whose subject and assumptions must match; it cannot be widened by packaging it as a generic cache hit.

## 4. Reuse candidate policies

| Candidate | Rule | Benefit | Main risk / discriminator |
|---|---|---|---|
| **C-A Exact-action result reuse** | Reuse only on exact canonical Action Key, complete declared closure, permitted determinism class, output-manifest verification and applicable trust policy. Unknown closure fails closed. | Strong correspondence between result and request; supports remote execution and evidence reuse. | Key omission or unsound declared inputs still breaks soundness; trust policy is separate. |
| **C-B Material cache with validation** | Prefix or approximate match may restore candidate dependencies/intermediates; validate every object, manifest, content digest and semantic compatibility, then run the normal action/evidence gates. | Fast warm starts and package dependency reuse. | Accidentally treating restoration as a valid execution result; validation cost may erase benefit. |
| **C-C Recompute on every trust boundary** | Exact results are usable locally; crossing workspace/team/CI/global trust domains requires verification or recomputation. | Clear trust model with reduced shared-cache attack surface. | Cost and duplicated work; verification strength must be specified. |
| **C-D Attested shared result** | Shared exact-key results carry signed producer, executor, policy, and validation claims; consumers accept only configured authorities and claim scopes. | Efficient federation and auditable provenance. | Signatures authenticate claims, not correctness; revocation, key rotation and compromised builders remain. |

These candidates can compose: C-A may define semantic validity, C-B materializes data, and C-C/C-D provide deployment-specific trust policies.

## 5. Conservative reuse gate (candidate)

For an action result to be reusable, test each condition independently:

1. **Exact action identity:** canonical key agrees over kind/schema, command/implementation, exact declared input closure, relevant configuration, target, toolchain, and any constraints that affect whether an outcome is acceptable.
2. **Dependency completeness:** every result-determining input is represented directly or through immutable references. If extraction is incomplete or unknown, use only as untrusted material, or recompute; do not reuse as an authoritative result.
3. **Environment control:** ambient inputs are either forbidden, modeled in the key, or normalized under a documented semantic equivalence. “Same source hash” alone is insufficient.
4. **Cacheability:** action declares byte-deterministic, canonical-semantic, or non-cacheable behavior. Nondeterministic actions cannot be converted to reusable results merely by recording their first output.
5. **Result completeness:** required outputs are present; paths/types/metadata satisfy the declared manifest; all blob/tree hashes verify; status is terminal and not a transient infrastructure outcome.
6. **Evidence applicability:** test/proof claims name the exact subjects, property, assumptions, target, corpus/model, and verifier identity required by the consumer.
7. **Trust authorization:** producer or cache namespace meets the consumer's policy; content hash alone is integrity, not source authentication or computational correctness.

The system may still keep a failed/partial/unknown record for audit and debugging. Retention does not imply cache eligibility.

## 6. Discriminating fixtures and falsifiers

| Intervention | Required observation to test | Failure exposed |
|---|---|---|
| Change an undeclared environment variable that alters output | Key changes or action marked incomplete/non-cacheable; old result rejected | Hidden dependency / unsound key |
| Change target libc, SDK, CPU feature, sysroot, backend, or registry interpretation | Only result-determining dimensions alter relevant action key; artifact/evidence is not cross-targeted implicitly | Under- or over-keying |
| Change timeout/resource budget for a possibly failing action | A prior unconstrained/long-budget success does not hide a shorter-budget failure if budget is part of requested semantics | Wrong result-class reuse |
| Omit or ambiguously resolve one transitive dependency | Dependency completeness becomes unknown; authoritative hit rejected | Optimistic closure handling |
| Run same key twice with differing output bytes or canonical semantics | Detect violation; disable cache or refine key/classification and investigate | False determinism claim |
| Restore a prefix key for dependency material | Material is verified and action re-runs unless exact result identity is established | Approximate match treated as exact |
| Upload a forged result with correct-looking key but wrong blob bytes | Digest validation rejects bytes; provenance/authorization policy rejects unauthorized writer | Integrity/provenance conflation |
| Upload internally consistent bytes from an untrusted but authorized-to-write branch | Trust policy isolates, rejects, or independently validates before privileged use | Cache poisoning across domains |
| Change one test assumption or proof corpus/verifier version | Evidence key or applicability predicate changes as required | Stale evidence reuse |
| Return timeout, cancellation, worker loss, quota error or service outage | Classified as incomplete/transient; not reused as stable semantic failure | Infrastructure failure cached as language result |
| Remove a required output while returning success | Manifest validation rejects incomplete ActionResult | Success status mistaken for complete result |

Falsify the strong exact-action model if a counterexample with fully captured inputs and deterministic action produces an accepted different result, or if the same valid result must be reused under a materially different observable contract and no explicit compatibility relation exists. Falsify blanket cache disabling at every trust boundary if independent verification yields adequate, cheaper evidence under the project's threat model.

## 7. Cross-area consequences and open decisions

- **LL-001/004/005:** preserve distinct typed identities and canonical inputs; the Action Key's dependency closure depends on the identity and cycle rules selected there.
- **LL-007/013–020:** target, ABI, runtime, backend, and OS dimensions must be classified by whether they affect the action output or evidence claim.
- **LL-008:** evidence is property-specific and must retain its exact assumptions, subjects and producer/verifier scope.
- **LL-009/016/017/022:** publication trust, remote builders, binary distribution, revocation and licenses are policies around artifacts/results, not content identity.
- **LL-021:** still needs a schema and conformance prototype for key canonicalization, closure completeness, output result records, exact versus material caches, deterministic failure, and trust-domain transitions.
- **RT-11/12/16:** performance, package indexes, signatures and poisoning resistance need workload measurements and threat validation.

No candidate policy is chosen, no LL-021 TODO item is closed, and no LLMLang cache implementation or behavior test is claimed.

## 8. References

- [Bazel Remote Execution API — `remote_execution.proto`](https://github.com/bazelbuild/remote-apis/blob/main/build/bazel/remote/execution/v2/remote_execution.proto)
- [Nix 2.35 glossary — store object and sandbox](https://nix.dev/manual/nix/2.35/glossary)
- [Nix 2.31 content-addressed derivation outputs](https://nix.dev/manual/nix/2.31/store/derivation/outputs/content-address.html)
- [GitHub Actions dependency caching reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)
- [GitHub Actions dependency caching security concepts](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching)
- [Scenario 92 — Operation Identity and Implementation Binding](../RT-05/RESEARCH-SCENARIO-92-OPERATION-IDENTITY-AND-IMPLEMENTATION-BINDING.md)
- [Semantic Compilation Cache proposal](SEMANTIC-COMPILATION-CACHE.md)
- [LL-021](../../TODO.md#ll-021--define-semantic-action-caching-and-incremental-compilation)
