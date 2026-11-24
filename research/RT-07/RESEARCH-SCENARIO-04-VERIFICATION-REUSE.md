# Scenario Study 04: Reusing Verification Results Safely

**Date:** 2026-11-16  
**Status:** Research result / proposed design, not an accepted LLMLang decision  
**Scope:** Verification identity, cache keys, dependency closure, proof reuse, invalidation, and assurance status

## 1. Question

A semantic graph changes. Which previous test, static-analysis, contract-verification, or formal-proof results can LLMLang safely reuse?

The optimization goal is important: re-running every expensive verifier after every small change wastes time and tokens. But an unsound cache can silently report an old proof as evidence for a new program.

The governing rule should be:

**A verification result is reusable only when the exact proposition and all declared inputs on which it depends are unchanged, or when a trusted reuse rule proves that the old result applies to the new inputs.**

Stable ID alone is never sufficient.

## 2. Findings from related projects

### 2.1 Edict: structural per-function verification cache

Edict's contract verifier computes a SHA-256 verification hash over a function's parameters, contracts, body, return type, and effects. It recursively canonicalizes object keys and strips node `id` fields so that identity-only ID changes do not cause cache misses. It also incorporates hashes of callees with preconditions into the caller's hash.

The incremental checker computes changed definitions and transitive dependents, then limits expensive Z3 contract verification to affected functions. Structural validation, name resolution, type checking, complexity checking, and effect checking still run over the full module.

This is a useful practical pattern:
- keep mandatory cheap validation broad;
- narrow expensive verification to the dependency impact set;
- use a verification-specific structural fingerprint rather than a generic object identity;
- include relevant callee contracts so callers are invalidated when callee preconditions change.

Important limits visible in the inspected implementation:
- the cache is an in-memory process-local map;
- the hash is function-specific and does not visibly include a stable verifier/toolchain/configuration identity;
- the dependency map is built from discovered callee references, so soundness depends on the completeness of that dependency extraction;
- the implementation's own comment calls out transitive dependency hashes, but the inspected collector builds dependencies from call expressions in the function body; recursive closure completeness must be checked rather than assumed;
- the cache stores successful results (errors prevent caching), but skipped/unsupported diagnostics can accompany a cached success and must remain visible as coverage limits.

This is a good optimization prototype, not a complete portable proof-artifact identity model.

Sources:
- [Edict contract verifier](https://github.com/Sowiedu/Edict/blob/main/src/contracts/verify.ts)
- [Edict verification hash](https://github.com/Sowiedu/Edict/blob/main/src/contracts/hash.ts)
- [Edict incremental checker](https://github.com/Sowiedu/Edict/blob/main/src/incremental/check.ts)
- [Edict dependency graph](https://github.com/Sowiedu/Edict/blob/main/src/incremental/dep-graph.ts)

### 2.2 LLMLang's current baseline

The LLMLang concept already proposes fine-grained Content Hashes and a Merkle DAG, while the Development Engine RFC proposes incremental verification and cache reuse by exact input identities. The Request/Change RFC requires verification evidence to become stale when relevant inputs change.

The missing definition is the complete identity of a verification proposition and its execution environment, including how the result records coverage and limitations.

## 3. Separate semantic state identity from verification identity

A node Content Hash identifies a canonical semantic graph state. It does not identify a verification run.

A verification record should identify at least:

| Input | Why it matters |
|---|---|
| Proposition/obligation hash | Exactly what is being proved or tested |
| Specification/contract hashes | The required behavior being checked |
| Design hashes (if relevant) | Assumptions and architecture boundaries |
| Implementation hashes in scope | The candidate realization |
| Test/property/proof artifact hash | The actual verification procedure |
| Dependency closure hash | All semantic dependencies used by the check |
| Verifier identity/version | Solver, compiler, analyzer, test runner, or proof kernel |
| Verifier configuration hash | Options, timeouts, bounds, feature flags, warning policy |
| Assumption/environment hash | Target architecture, runtime, libraries, external models, environment |
| Input/toolchain artifact hashes | Compiler/tool binaries or immutable container/toolchain image |
| Policy hash | Required assurance level and acceptance rules |

A result key can be modeled as:

```text
VerificationKey =
    H(
      domain = "LLMLang.Verification.v1",
      obligation_hash,
      exact_input_root_hashes,
      dependency_closure_hash,
      verifier_identity,
      verifier_config_hash,
      assumptions_hash,
      environment_hash,
      policy_hash
    )
```

The result record is separate from the key. It includes the outcome, logs/diagnostics, coverage, resource limits, execution metadata, provenance, and evidence artifact locations.

## 4. Results are not all equally reusable

Different verification classes have different semantics.

| Verification kind | Reuse condition | Important caveat |
|---|---|---|
| Parsing/schema validation | Exact input bytes or canonical schema hash and validator version | A changed schema invalidates prior result |
| Name resolution/type checking | Exact relevant graph closure and compiler/type-system version | Changed imports, scopes, traits, or overload sets may affect distant consumers |
| Effect/capability checking | Exact effect declarations, call/dependency closure, and policy | Dynamic or unresolved calls require conservative invalidation |
| Unit test execution | Exact executable, test, fixtures, runtime, environment, and external dependencies | Nondeterminism and external services complicate identity |
| Property-based testing | Same code/test/generator/seed/config/environment | A finite run is evidence, not a universal proof |
| SMT contract proof | Same logical obligation, assumptions, translation semantics, solver identity/configuration | Solver UNKNOWN/timeout is not PROVEN |
| Interactive theorem proof | Same proposition and proof term accepted by the trusted kernel | Kernel/version and imported theorem identities matter |
| API compatibility check | Exact before/after public interface and compatibility policy | Internal implementation changes may be irrelevant |
| Performance benchmark | Exact workload, binary, hardware/runtime configuration, measurement method | Often noisy; cache reuse should be stricter or statistical |

The engine must not treat every successful command as the same assurance level. A passing test is not a formal proof, and a skipped unsupported proof obligation is not a pass.

## 5. Dependency closure and Merkle DAG

### 5.1 Verification-specific dependency closure

A verification run should declare which SPG nodes and external artifacts it consumed. The verifier adapter may provide this set, and the engine should compare it with the dependency graph derived by semantic analysis.

The closure should include:
- the obligation itself;
- all referenced contracts/types/effects;
- all relevant callee contracts and implementations;
- imported declarations and configuration;
- assumptions and external models;
- verifier semantics and toolchain identity.

If the verifier cannot expose exact dependencies, the engine must use a conservative declared scope or mark the result non-portable/non-cacheable.

### 5.2 Hashing

The Merkle DAG can make closure hashing efficient. A verification key can reference layer/subgraph roots rather than serializing every dependency into the request.

However:
- the root must commit to the complete required closure;
- dependency edges must be typed and hash-relevant;
- the verifier/config/environment identities must be included outside or alongside the semantic graph root;
- cache entries must be keyed by domain-separated hashes to prevent cross-kind collisions;
- a hash match establishes identical declared inputs, not correctness of the verifier.

### 5.3 Negative results and UNKNOWN

Caching failures is possible but requires care. A counterexample may be reusable for the same exact proposition and inputs. A timeout or solver UNKNOWN may be transient and should not be treated as a durable semantic verdict.

Suggested policy:
- PROVEN: cache as reusable evidence when all inputs are pinned.
- DISPROVEN: cache the counterexample/result as a diagnostic for the exact inputs; it is not evidence of current failure after inputs change.
- UNKNOWN: retain the run record, but do not treat it as reusable success; retry policy may schedule another attempt.
- NOT_CHECKED: record absence of execution, never cache as success.
- ERROR/TOOL_FAILURE: preserve diagnostics; retry only according to a typed failure policy.

## 6. Proof reuse across changed inputs

Exact-key equality is the default safe reuse rule. More advanced reuse can be allowed only through a separately verified transformation.

Examples:
- A comment or formatting change excluded from semantic hashes may preserve a proof key.
- A change to an unrelated module may preserve a proof if the dependency closure is demonstrably disjoint.
- A renamed symbol may preserve a proof only if the proof representation is identity-based or a trusted normalization proves the proposition equivalent.
- A strengthened assumption may invalidate a proof of a postcondition unless the proof's logical context and implication direction justify reuse.
- A weakened requirement changes the proposition; the old proof may still imply the new one, but the implication must be checked by a trusted proof mechanism, not inferred by the LLM.

A Proof Reuse record should identify:
- source verification record;
- target verification key;
- transformation/implication being claimed;
- trusted checker and result;
- exact proof artifact;
- accepted status and provenance.

Without such a record, the engine should rerun verification.

## 7. Incremental invalidation algorithm

1. Receive a new candidate graph snapshot.
2. Determine changed semantic node hashes and changed external input identities.
3. For each verification record, compare its declared dependency closure with the changed set.
4. If no dependency intersects and verifier/config/policy/environment identities match, retain the evidence as current.
5. If dependencies intersect, attempt a declared sound reuse rule if one exists.
6. If no sound reuse rule applies, mark the evidence STALE and schedule verification.
7. Recompute affected dependency closures if graph structure or dependency extraction changed.
8. Keep coverage gaps and unsupported constructs visible.
9. Publish new verification records only against the exact candidate snapshot and key.
10. Never allow an old result to overwrite a newer result for a different key.

If the dependency graph is incomplete or extraction is stale, the system should conservatively invalidate the relevant scope rather than report unaffected.

## 8. Persistence, determinism, and reproducibility

A cache entry should be an immutable artifact, not only an in-memory boolean.

It should retain:
- verification key;
- verifier result and status;
- full declared input manifest;
- verifier/toolchain identity;
- normalized diagnostics and raw log/artifact references;
- coverage and unsupported-scope declarations;
- execution timestamp and duration;
- resource limits and exit reason;
- provenance and signature/attestation if required.

Reproducibility is stronger than cache reuse. A result may be safely reused based on a trusted immutable attestation even if rerunning is expensive, but reproducibility requires that the execution can be replayed and produce the expected result under the pinned environment.

## 9. Required invariants

Proposed invariants for a future RFC:

1. Stable ID is never a verification cache key by itself.
2. Every verification result is bound to a canonical proposition and exact declared inputs.
3. Verifier identity, configuration, assumptions, and relevant environment are part of verification identity.
4. Incomplete dependency discovery prevents an unqualified cache-valid claim.
5. Exact-key cache hits preserve the original outcome and coverage limitations.
6. UNKNOWN, NOT_CHECKED, skipped, and tool failure are never promoted to PROVEN.
7. A changed obligation invalidates evidence unless a trusted reuse proof establishes applicability.
8. A result for one snapshot cannot be attached to another snapshot solely because the entity Stable IDs match.
9. Reuse and invalidation decisions are auditable and explainable.
10. Cache entries are immutable and content-addressed.
11. Cache misses affect performance, not correctness; cache hits must not weaken correctness.
12. The trusted verification kernel/tool adapter is responsible for attesting the result, not the LLM that requested it.

## 10. Open questions

1. Which verification kinds should share one generic record schema, and which require specialized evidence schemas?
2. Should tool binaries be identified by content hash, signed release identity, container digest, or all three?
3. How should hardware and runtime environment be represented for nondeterministic performance or concurrency tests?
4. What is the trust model for external solvers and compiler plugins?
5. Can proof artifacts be checked by a small trusted kernel independent of the original prover?
6. Which result classes may be persisted/shared across machines or projects?
7. How should flaky tests and probabilistic tests represent repeatability and confidence without conflating them with proof?
8. What is the minimal dependency manifest a verifier must return before its result is eligible for persistent caching?

## 11. Preliminary conclusion

Edict demonstrates a practical first step: structural verification fingerprints, dependency-aware invalidation, and incremental execution of expensive contract checks. Its implementation also illustrates the limits of an in-process cache and why dependency and tool identity need explicit treatment.

LLMLang's Merkle DAG can provide an efficient basis for exact semantic input identity, but it cannot replace a verification-specific manifest. The verifier, options, assumptions, environment, and obligation must also be pinned.

**Preliminary recommendation:** define verification records and cache keys as first-class content-addressed artifacts. Make exact-input reuse the default. Permit cross-input proof reuse only through a separately checked implication/equivalence transformation. Preserve UNKNOWN, NOT_CHECKED, and coverage limitations without upgrading them to success.

This is a research conclusion, not an accepted change to LLMLang's concept or RFCs.

## Sources

- [Edict contract verifier](https://github.com/Sowiedu/Edict/blob/main/src/contracts/verify.ts)
- [Edict verification hash](https://github.com/Sowiedu/Edict/blob/main/src/contracts/hash.ts)
- [Edict incremental checker](https://github.com/Sowiedu/Edict/blob/main/src/incremental/check.ts)
- [Edict dependency graph](https://github.com/Sowiedu/Edict/blob/main/src/incremental/dep-graph.ts)
- LLMLang internal baseline: `LLMLang-CONCEPT.md`, `RFC-DEVELOPMENT-ENGINE.md`, `RFC-REQUEST-CHANGE.md`, `RESEARCH-DEEP-COMPARISON.md`

## RT-36 follow-up: explicit assumptions (proposed)

Reuse a checked abstract caller theorem only under identical/compatible premise context; rebind exact provider evidence and recompute closure and admission after relevant assumption or authorization changes. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
