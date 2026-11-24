# LLMLang: Semantic Compilation Cache and Incremental Build Graph

**Status:** Research proposal; not a normative LLMLang decision  
**Date:** 2026-11-17  
**Scope:** Content-addressed caching, incremental compilation, reusable analysis and verification results, and cache correctness.

> This document develops a consequence of LLMLang's semantic graph and immutable artifact model. It proposes a cache architecture, but does not yet define a normative cache format or promise that every compiler action is cacheable.

## 1. Central idea

Compilation should be modeled not as repeatedly compiling source files, but as evaluating a dependency graph of typed, deterministic (or explicitly non-cacheable) actions over immutable semantic inputs.

A cache hit is valid when the exact inputs that determine an action's result are unchanged and the action is known to be safely reusable. A cache miss requires computing the action and storing its result with enough metadata to justify future reuse.

The cache unit should therefore be a semantic computation, not necessarily a source file, module, or whole program.

This follows naturally from LLMLang's proposed foundations:

- immutable semantic objects and content identities;
- explicit typed dependencies;
- separation of operation, contract, and implementation identity;
- independently addressable tests, models, proofs, and generated artifacts;
- dependency-aware impact analysis;
- evidence bound to exact input versions and assumptions.

The intended outcome is broader than faster machine-code generation. The same architecture can reuse parsing, normalization, type checking, contract analysis, dependency analysis, code generation, tests, formal verification, and packaging results.

## 2. Three identities that must remain distinct

At least three hash roles are needed:

| Identity | What it addresses | Example |
|---|---|---|
| Semantic Hash | An immutable semantic object | OpHash, ContractHash, TypeHash, ImplementationHash |
| Action Key | One computation with exact inputs, tool identity, and relevant configuration | Lowering a particular implementation for a particular target |
| Artifact Hash | The exact output bytes or canonical output object | LLVM bitcode, object file, proof certificate, test report |

An Operation Hash must not be used as a compiled-artifact cache key. The same operation semantics may have several implementations; the same implementation may be compiled for multiple targets or toolchains.

Likewise, an Action Key is not the identity of the output. Two independent actions may produce byte-identical artifacts, and one action may produce different artifacts if an untracked input or nondeterministic source is present.

A conceptual action key is:

```text
ActionKey = H(
  domain,
  action_kind,
  action_implementation_identity,
  ordered_or_canonical_input_refs,
  relevant_configuration,
  relevant_environment_identity
)
```

The output is stored separately:

```text
ActionKey -> ResultRecord -> ArtifactHash(es)
```

The exact encoding, ordering rules, digest algorithm, and treatment of optional inputs remain open design work.

## 3. The compilation process as a graph of actions

A possible graph for one operation:

```text
Operation / Contract / Types / Dependencies
                    |
                    v
          Semantic normalization
                    |
                    v
        Type and contract validation
                    |
                    v
       Target capability analysis
                    |
                    v
            Target lowering
                    |
                    v
              LLVM IR
                    |
                    v
         LLVM optimization pipeline
                    |
                    v
          Object code generation
                    |
                    v
            Link / package
```

Each stage is a separate action with explicit input references and outputs. The graph is not required to be a simple linear pipeline: independent functions, modules, proofs, and tests can be evaluated in parallel, and shared dependencies can be computed once.

A cached intermediate result can be reused by any consumer whose action key references that exact result and whose compatibility constraints are satisfied.

## 4. Granularity: cache semantic units, not arbitrary fragments

The useful cache boundary is an independently meaningful unit whose inputs can be enumerated.

Candidate units include:

- normalized semantic operation;
- type and layout computation;
- contract well-formedness result;
- target capability report;
- lowered function or module;
- generated LLVM IR module;
- optimized IR artifact;
- object file;
- test execution result;
- proof or verification result;
- package/link result.

The model should not force every expression or basic block into a global artifact. Excessive fragmentation increases metadata, lookup, graph traversal, and storage overhead. Conversely, caching only whole files/programs loses reuse when independent semantic entities change separately.

The granularity should be selected per action and justified by stable semantic boundaries, meaningful reuse, and measurable cost.

## 5. Dependency closure and invalidation

A cache entry is reusable only if all result-determining inputs are represented in its Action Key or in immutable objects referenced by that key.

For each action, the system needs a declared input/dependency set. Changing a hash-relevant input creates a different identity for the affected immutable semantic object (for an implementation, a different `ImplHash`). Any action whose exact inputs include that identity consequently receives a different `ActionKey`. Reverse dependency edges are used to find affected actions and their new keys; they are not a separate source-change or dirty-flag mechanism.

Example:

```text
A -> C -> E
B -> C -> E
D ------> E

If A changes:
  recompute C
  recompute E
  reuse B and D
```

This is more precise than invalidating every artifact in a containing file or package.

The key safety condition is dependency completeness. If the compiler reads an undeclared file, environment variable, system header, toolchain component, clock value, network response, or ambient configuration that can affect output, a key based only on declared inputs is unsound.

The system should therefore distinguish:

- **Complete dependency record:** all result-determining inputs are captured; reuse may be allowed.
- **Incomplete/unknown dependency record:** the result may be retained for diagnostics or provenance, but must not be treated as safely reusable.
- **Explicitly non-cacheable action:** the action has nondeterministic or external behavior that cannot be captured or normalized adequately.

When dependency discovery is uncertain, invalidation should be conservative (fail closed), not optimistic.

### 5.1 Content-addressed invalidation through `ImplHash`

For implementation changes, the implementation identity is the invalidation signal. If a semantic change affects an implementation's canonical body or any hash-relevant semantic dependency, its `ImplHash` changes. Every downstream action that consumes that implementation identity (directly or through another changed immutable input) therefore has a different `ActionKey`.

No additional mechanism is needed to track that the implementation's source or semantic node changed: the new content identity makes the old action result inapplicable to the new input. The build planner recomputes the affected action keys and reuses entries whose keys still match. Reverse dependency edges may accelerate impact traversal and scheduling, but separate dirty flags, timestamps, or source-change invalidation records are not authoritative.

This principle is sound only if `ImplHash` and downstream `ActionKey` values cover every result-determining semantic input. An omitted dependency can leave an identity unchanged when the result should change; that is a dependency-completeness defect, not a reason to add an independent invalidation mechanism. Unknown or incomplete dependencies must therefore prevent safe reuse (fail closed).

The principle does not mean every caller must be rebuilt whenever a callee's `ImplHash` changes. A caller is affected only if its action's actual inputs include the changed implementation identity or a derived artifact. For example, a stable separately linked call boundary may leave the caller's own compiled artifact reusable, while inlining or body-dependent optimization makes the caller's action depend on the callee implementation.

## 6. Environment and toolchain identity

Compilation outputs depend on more than source semantics. A target-specific action may depend on:

- compiler and backend implementation version;
- compiler flags and optimization pipeline;
- LLVM version and relevant pass configuration;
- target triple, CPU features, and data layout;
- ABI and calling convention;
- runtime/support-library versions;
- linker and object format;
- relevant system headers, SDKs, sysroots, and external libraries;
- environment variables or configuration that affect the result.

Only result-determining properties need to enter a given action key. A host detail that cannot affect a cross-compiled artifact should not perturb its key. Conversely, a relevant toolchain or ABI change must not be omitted merely to improve cache hit rate.

This leads to a useful distinction:

- semantic identity describes what the LLMLang object means;
- action identity describes how a particular toolchain computes a result from exact inputs;
- build provenance records the actual tools, environment, and configuration used.

A change in compiler version may require a new action result without changing the source OpHash or ContractHash.

## 7. Reuse beyond machine-code compilation

The same action-cache model applies to the entire LLMLang toolchain.

| Action | Reusable output |
|---|---|
| Parsing / graph construction | Canonical parsed graph |
| Semantic normalization | Normalized semantic artifact |
| Type checking | Type-check result and diagnostics |
| Contract analysis | Contract validity / analysis result |
| Dependency analysis | Typed dependency graph and completeness evidence |
| Target capability analysis | Target support report |
| Lowering | Target/backend IR |
| Optimization | Optimized IR |
| Code generation | Object or executable artifacts |
| Testing | Test result tied to exact inputs and environment |
| Formal verification | Proof/certificate and verification result |
| Packaging | Package artifact and manifest |

Diagnostics can also be cached, but they must be tied to exact inputs and tool versions just like successful results. A stale error must not be reported as current after the relevant inputs change.

Failed computations may be cached only when the failure is deterministic and all inputs that determine it are captured. Transient infrastructure failures, timeouts, unavailable services, and resource exhaustion must not be mistaken for stable semantic results.

## 8. Verification evidence is a first-class cached result

A proof or test result is not merely a log file. It is an evidence artifact with exact applicability conditions.

A verification result should bind at least:

- the exact semantic object or implementation hashes checked;
- the exact contract and requirement hashes;
- transitive dependencies relevant to the property;
- assumptions and target/environment profile;
- test corpus or formal model identity;
- verifier, solver, compiler, or test-runner identity and configuration;
- result status and scope;
- evidence artifact hash.

If a relevant dependency changes, only properties whose evidence depends on it need invalidation. Independent proofs and tests can remain reusable.

This is property-specific invalidation, not a global “everything is dirty” rule. It also means a cached result must never be promoted to a broader claim than the original evidence established.

## 9. Determinism and reproducibility

Content-addressed caching works best when actions are deterministic for a fixed Action Key.

For deterministic actions:

```text
same Action Key => same logical result
```

For byte-reproducible actions, the stronger property is:

```text
same Action Key => identical output bytes
```

These are not the same guarantee. An action may be semantically deterministic but emit timestamps, unstable symbol ordering, random identifiers, or other irrelevant byte differences.

The system should classify actions as:

- **Byte-deterministic:** same key must produce identical bytes.
- **Semantically deterministic:** output bytes may differ, but canonicalized semantic output must match.
- **Nondeterministic/non-cacheable:** result cannot safely be reused under the current input model.

Sources of nondeterminism should be eliminated, normalized, or made explicit inputs (for example, a fixed build timestamp or seed). Hidden ambient inputs invalidate the cache-soundness claim.

## 10. Local, shared, and remote caches

The logical cache model should not depend on one physical deployment.

Possible layers:

1. **Process-local cache:** short-lived results within one compiler process.
2. **Workspace cache:** artifacts reusable across builds in one checkout.
3. **Machine-local cache:** shared across workspaces on one machine.
4. **Team/remote cache:** shared across developers and CI.
5. **Global semantic artifact store:** globally addressable immutable artifacts and reusable implementations.

The global store and build cache are related but not identical. The artifact store answers “what immutable object is this?” The action cache answers “has this exact computation already been performed, and what result did it produce?”

A cache may be evicted without changing semantic identity. A globally stored artifact may remain addressable even when a local action-cache entry is removed.

## 11. Trust, integrity, and cache poisoning

A cache hit is a reuse decision, not a correctness proof.

At minimum:

- verify artifact bytes against Artifact Hash on retrieval;
- bind result records to exact Action Keys;
- authenticate trusted producers where trust policy requires it;
- keep provenance and license metadata separate from content identity;
- do not accept an artifact merely because its filename or claimed hash matches;
- isolate untrusted cache namespaces or verify outputs before use;
- preserve the distinction between “reproduced,” “verified,” and “trusted producer.”

A malicious or faulty cache can return an artifact that does not correspond to the requested action. Integrity checks detect byte substitution relative to a claimed digest, but trust in the producer and correctness of the computation require additional evidence or independent recomputation.

## 12. LLM workflow and token efficiency

The same architecture can reduce LLM context and repeated reasoning.

Instead of sending an LLM the entire project on every task, tooling can provide:

- the changed semantic subgraph;
- its exact direct and transitive dependencies relevant to the task;
- affected contracts and requirements;
- cached analyses and verification evidence that remain applicable;
- only the diagnostics for actions that actually ran.

The LLM proposes a typed change set. Deterministic tooling computes the impact closure, reuses unaffected results, and returns a compact explanation of what changed, what was recomputed, what was reused, and what remains unresolved.

This is not simply prompt caching. It is reuse of structured semantic work, with the LLM receiving the smallest context sufficient for the current mutation.

## 13. Worked example: changing one implementation

Suppose a program contains operations A, B, and C. A and B are independent; C calls A. All three have contracts and cached tests. All are compiled for x86-64 and ARM64.

If only A's implementation changes while its OpHash and contract remain unchanged:

- A receives a new `ImplHash`; this identity change is the invalidation signal.
- Actions that consume A's old `ImplHash` receive new `ActionKey` values and must be recomputed; actions whose keys remain unchanged are reusable.
- No separate dirty flag or source-node change tracker is required.
- C's source and contract identities do not automatically change.
- C's compiled artifact may be reusable if its generated code does not embed or otherwise depend on A's implementation body (for example, if it calls A through a stable separately linked interface).
- If C was inlined with A, statically linked with A, or optimized using A's body, the relevant downstream action keys change and C must be rebuilt.
- B and its evidence remain reusable if no dependency path connects them to the changed inputs.
- A's previous proof/test results remain valid only for the exact old implementation hash; new evidence is needed for the new implementation where required.

This example shows why dependency edges must describe actual result-determining relationships, including code-generation and optimization dependencies, rather than only source-level calls.

## 14. Proposed build result record

A conceptual result record:

```text
ActionResult {
  action_key
  action_kind
  action_implementation
  language_version
  language_component_registry_digest
  toolchain_identity
  input_refs[]
  relevant_configuration
  environment_identity
  status
  output_artifact_refs[]
  diagnostics_ref?
  provenance_ref
  determinism_class
}
```

The record is illustrative, not a settled schema. The exact representation should itself be typed, canonical, versioned, and content-addressable.

## 15. Implementation strategy

A staged research/prototype path:

1. Define a minimal action graph for a small LLMLang semantic subset.
2. Define canonical Action Key inputs and distinguish them from Semantic Hashes.
3. Implement an in-process cache for deterministic semantic analysis.
4. Add dependency-aware invalidation and reverse dependency queries.
5. Add a compiler/backend action with explicit toolchain and target inputs.
6. Demonstrate that an unrelated semantic change reuses previous outputs.
7. Add test and proof result records bound to exact inputs.
8. Add workspace and remote cache layers only after correctness is demonstrated.
9. Add adversarial tests for undeclared dependencies, stale evidence, corrupted artifacts, and cache poisoning.

The first milestone should prioritize soundness and explainability over maximum hit rate.

## 16. Open questions

- What is the canonical Action Key schema and domain separation?
- How are action implementations and toolchain versions identified?
- What constitutes a complete dependency record?
- How are dynamic dependencies discovered and stabilized?
- Which actions are byte-deterministic, semantically deterministic, or non-cacheable?
- How should action graphs represent generated inputs, cycles, and multi-output actions?
- Which verification results can be reused under property-specific dependency changes?
- What trust policy applies to local, team, CI, and global caches?
- How should cache eviction, retention, and garbage collection interact with the global artifact store?
- What is the smallest useful cache granularity for the first prototype?

## 17. Current conclusion

Compilation caching is not an incidental performance feature for LLMLang. It is a direct operational consequence of representing programs as immutable semantic objects connected by explicit dependencies.

The strongest design is a content-addressed action graph in which semantic objects, computations, and outputs have distinct identities; dependency completeness controls safe reuse; and verification evidence is cached with exact applicability conditions.

This can unify incremental compilation, build caching, analysis reuse, test reuse, proof reuse, and reduced LLM context under one coherent model.

This remains a research proposal. It does not yet settle the canonical Action Key format, cache trust policy, or mandatory implementation behavior.


## 18. Package-distributed cache indexes

The package system may optionally distribute indexes of action results alongside semantic object indexes. Typical results include semantic validation, type/contract analysis, target-specific compilation, tests, and formal verification.

The cache index is keyed by **Action Key**, not a bare Semantic Hash or Content Hash. The key covers exact semantic inputs and relevant dependency closure, action kind and implementation, composite LanguageVersion, the digest of the append-only language component registry used to interpret it, ToolchainIdentity, target, configuration, and other result-determining inputs. The result record points to Artifact Hash values and records status, scope, determinism/dependency completeness, and provenance.

Every record states LanguageVersion, LanguageComponentRegistryDigest, and ToolchainIdentity separately. The registry digest identifies the exact ordered component list used to interpret the composite version; the registry file itself contains no versions and is append-only. Reuse across a different relevant language version, registry snapshot, or toolchain identity is a cache miss unless an explicit compatibility rule is validated. A language-version match alone never authorizes reuse across behavior-changing toolchain builds.

A package may carry cache-index metadata only, with result payloads fetched from another cache/store, or both metadata and selected payloads. Missing or evicted payloads are ordinary cache misses. Cache indexes are optional and evictable; they do not change semantic object hashes or logical package identity. A cache hit is not itself proof of correctness: artifact integrity, evidence applicability, and producer trust remain separate checks.

Cache indexes reuse compact-index techniques (canonical sort, binary search, streaming merge, optional block compression and sparse lookup) but remain logically separate from package Object/Symbol/Dependency indexes. This extends `research/PACKAGE-SYSTEM.md` and does not introduce a second Action Key scheme.

## Public-interface integration (2026-11-24; proposed)

Use different dependency closures for name resolution, modular caller proof, caller compilation, provider proof, conformance proof, link and executable verification. A compatible provider replacement can reuse an interface-only proof if all proof inputs and assumptions are unchanged; caller machine code is reusable only across a stable non-inlined boundary with unchanged ABI and compile inputs. Exact selected provider and runtime context affect executable/link and closed-system evidence; do not key them by public name or OpHash alone. Changes to a provider contract invalidate its refinement evidence even if body bytes remain equal. Cache misses, unsupported proof fragments and incomplete resolution remain distinct from verified results.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## RT-36 follow-up: explicit assumptions (proposed)

Research separate cache keys for local theorem, transitive proof closure and policy admission. Changes to provider, premise, correspondence or authorization invalidate relevant derived claims; preserve historical and reusable abstract theorem artifacts. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
