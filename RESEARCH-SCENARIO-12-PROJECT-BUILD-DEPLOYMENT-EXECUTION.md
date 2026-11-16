# Research Scenario 12: Project, Build, Deployment, and Execution Identity

**Status:** Research / exploratory; not normative.  
**Date:** 2026-11-16  
**Predecessors:** Scenarios 09–11 and Dependency Graph Prototype 01.

## Executive conclusion

Do not put every operational choice into the semantic ProjectSnapshot. A project, a configured build, a deployment, and an individual execution are different immutable states with different change rates and different reproducibility requirements.

Recommended separation:

- **ProjectSnapshot** — selected semantic program state: contracts, implementations, callers, and other source-level semantic values.
- **BuildSnapshot** — exact project root plus build-time bindings, target/execution platforms, toolchains, dependency lock, and build configuration. It identifies the declared build inputs, not the produced bytes.
- **BuildArtifact** — exact output artifact hash plus the BuildSnapshot root, builder identity, and provenance root. This distinction matters because identical declared inputs do not, by themselves, prove that two executions emitted identical outputs.
- **DeploymentSnapshot** — exact build result (not merely build recipe) plus runtime bindings, runtime image, deployment configuration, and infrastructure identity.
- **ExecutionSnapshot** — exact deployment plus request-level resolved bindings, input identity, external-effect transcript, deterministic runtime inputs, and outputs.
- **ReleaseManifest** — immutable join that states which project, build, and deployment belong together for a published release.
- **Channel head** — mutable pointer to a ReleaseManifest, advanced with compare-and-swap (CAS), not part of the immutable manifest hash.

This permits one semantic project root to have several builds (platforms/toolchains), one build to have several deployments (production/staging/canary), and one deployment to have many executions.

## 1. Why one root is insufficient

If all choices are folded into one project root, changing a compiler, target platform, production binding, runtime image, or request-specific provider changes the apparent project identity. That creates unnecessary semantic churn and makes branch history noisy.

If all choices are excluded from identity, a build or execution can silently change while the project hash remains constant. That breaks reproducibility and invalidates cache/evidence assumptions.

The solution is layered roots with explicit references, not one universal root.

## 2. Proposed identity graph

```
ProjectSnapshot
      |
      +---- BuildSnapshot A (target platform / toolchain / build bindings)\n      |\n      +---- BuildArtifact (output digest + provenance)
      |             |
      |             +---- DeploymentSnapshot production
      |             |            +---- ExecutionSnapshot #1
      |             |            +---- ExecutionSnapshot #2
      |             |
      |             +---- DeploymentSnapshot staging
      |
      +---- BuildSnapshot B (other target platform / toolchain)
                    |
                    +---- DeploymentSnapshot canary

ReleaseManifest -> exact ProjectSnapshot + BuildSnapshot + DeploymentSnapshot
ReleaseChannelHead -> mutable pointer to ReleaseManifest (CAS)
```

The graph is a DAG of immutable objects. The mutable channel pointer is a separate coordination primitive.

## 3. Identity boundaries

### ProjectSnapshot

Contains semantic selections and their exact content hashes. It answers: "Which program semantics and source-level artifacts are selected?"

It does not contain environment-specific implementation selection, compiler/toolchain resolution, runtime image, deployment parameters, or request-specific routing unless those are explicitly part of the program's business semantics.

### BuildSnapshot

Includes:
- ProjectSnapshot root;
- build-time BindingSnapshot root (for code generators, compiler plugins, linkers, macro providers, build-time service implementations);
- target platform;
- execution platform;
- exact toolchain root;
- dependency lock root;
- build configuration hash.

Bazel is a useful precedent: toolchain resolution consumes required toolchain types, target platform, execution platforms, and available toolchains, and produces a concrete execution platform and toolchain map. The order of candidates matters; deterministic selection must be captured, not re-run against a mutable registry during replay. See https://bazel.build/docs/toolchains.

### DeploymentSnapshot

Includes:
- exact BuildSnapshot root;
- runtime BindingSnapshot root;
- runtime image/artifact digest;
- deployment configuration hash;
- infrastructure/configuration identity.

A runtime binding change should create a new DeploymentSnapshot, not a new ProjectSnapshot or necessarily a new BuildSnapshot.

Kubernetes distinguishes mutable image tags from immutable content digests: tags can move, while digests identify fixed image content. LLMLang should pin runtime artifacts by digest, not rely on mutable tags. See https://kubernetes.io/docs/concepts/containers/images/.

### ExecutionSnapshot

Includes:
- exact DeploymentSnapshot root;
- resolved request/session binding root;
- input root/digest;
- external event/effect transcript root;
- deterministic runtime inputs (clock, random seed, locale, feature flags where relevant);
- output root/digest.

A timestamp for audit display is metadata, not necessarily semantic identity. If time affects behavior, the effective clock value or time input must be included as an execution input. Likewise, external responses must be captured or the execution cannot claim deterministic replay.

### ReleaseManifest and channel head

The release manifest is an immutable join over exact roots. It prevents a release from accidentally pairing a build from project A with a deployment from build B.

The channel head is mutable and updated with compare-and-swap against the observed prior root. Concurrent publishers can create independent immutable candidates; only one wins the channel update. A stale publisher must reread, rebase/revalidate, and retry. The prototype models CAS as a pure operation; real atomicity must be provided by the persistence backend.

## 4. Branching and concurrency scenarios

### Two source branches

Two branches diverge from ProjectSnapshot P0 and produce P1 and P2. Each can independently produce builds and deployments. Their release manifests coexist. No global mutable binding is consulted when reconstructing either release.

### Same project, different target platforms

P0 produces BuildSnapshot B-linux and B-windows. The project root is shared; platform/toolchain/dependency differences are represented in each build root.

### Same build, production and staging

B0 can be deployed with runtime binding S-prod and S-stage, producing distinct DeploymentSnapshots D-prod and D-stage. The build is not duplicated merely because runtime provider selection differs.

### Concurrent deployment changes

Two operators create D-canary and D-prod-v2 from the same build. Both are immutable. A release channel CAS decides which manifest becomes current. The losing update is not silently overwritten.

### Rollback

Rollback means advancing a channel pointer to a previously accepted ReleaseManifest (or publishing a new manifest that intentionally references previous roots), subject to current policy. It does not mutate or erase the old release.

## 5. Reproducibility levels

| Level | Required pinned identities | What can be claimed |
|---|---|---|
| Source reconstruction | ProjectSnapshot root | Exact selected semantic source graph |
| Build reconstruction | Project + build bindings + platforms + toolchains + dependency lock + build config | Same declared build inputs; bit-identical output only if the build is hermetic/reproducible |
| Deployment reconstruction | Build + runtime bindings + runtime artifact digest + deployment/infrastructure config | Same declared deployment configuration |
| Execution replay | Deployment + request bindings + inputs + clock/random + external-effect transcript + runtime | Replayable execution to the extent all nondeterministic/external inputs are captured |

Nix flakes provide a precedent for locking exact dependency inputs. This is necessary but not sufficient for bit-for-bit reproducibility: the build must also avoid undeclared inputs and nondeterminism. See https://nix.dev/concepts/flakes.html.

SLSA provenance similarly emphasizes identifying the output artifact, builder, source, entry point, parameters, and dependencies. This supports recording build provenance separately from the semantic project identity. See https://slsa.dev/spec/v1.0/provenance.

## 6. Secrets and mutable external systems

Never put secret plaintext into content-addressed manifests. A hash of a low-entropy secret may enable guessing attacks. Instead record a secret reference plus immutable version identifier or a protected opaque commitment supplied by the secret manager; access-control and audit metadata remain separate.

A URL is not an immutable external dependency. For external services, record a provider/version identity, contract, configuration identity, and—when replay is required—the observed request/response transcript or a deterministic simulator. If this is impossible, classify the execution as non-replayable rather than pretending the environment is pinned.

## 7. Prototype 01 extension

Added `src/execution.py` with immutable:
- BuildSnapshot;
- DeploymentSnapshot;
- ExecutionSnapshot;
- ReleaseManifest.

It includes constructors with digest validation, consistency checks between project/build/deployment roots, and a pure compare-and-swap function for a mutable release channel head.

Tests cover:
1. runtime binding changes do not change project/build roots;\n2. identical build inputs may have distinct BuildArtifact records if outputs differ;
2. toolchain changes do not change project root but do change build root;
3. multiple deployments can share a project and build;
4. crossed project/build/deployment references are rejected;
5. execution identity pins request bindings, inputs, external events, outputs, and runtime;
6. execution identity changes when deployment changes;
7. CAS accepts current head and rejects stale writers;
8. malformed digests are rejected.

This prototype is a model, not a durable distributed CAS implementation. It does not yet include a real release registry, signatures, authorization, secret manager, build engine, deployment engine, or execution recorder.

## 8. Important correction to Scenario 11

A single checksummed persistence envelope is a storage-integrity boundary, not a semantic identity boundary and not a transaction protocol. It can store several independent immutable roots together, but it must not imply that ProjectSnapshot and BindingSnapshot are the same state.

The project-state serializer's newline terminator was also corrected from a literal backslash-n sequence to an actual newline. The envelope remains deterministic JSON with nested integrity validation.

## 9. Preliminary recommendation

Research direction, not normative:

1. Keep ProjectSnapshot semantic and environment-independent.
2. Model build-time bindings as inputs to BuildSnapshot.
3. Model runtime bindings and deployment configuration as inputs to DeploymentSnapshot.
4. Model request/session bindings and nondeterministic/external inputs in ExecutionSnapshot.
5. Join exact roots in an immutable ReleaseManifest.
6. Keep mutable branch/channel heads outside content-addressed objects and update them using atomic CAS.
7. Distinguish source reconstruction, build reconstruction, deployment reconstruction, and execution replay; do not promise a stronger level than captured inputs justify.
8. Keep secrets out of public content-addressed records; record protected version references instead.

**The project says what program is selected. The build says how that program was materialized. The deployment says what was installed and wired. The execution says what actually ran with which inputs and effects. The release manifest binds the exact states together.**

## References

1. Bazel toolchain resolution: https://bazel.build/docs/toolchains
2. Kubernetes image digests: https://kubernetes.io/docs/concepts/containers/images/
3. Nix flakes and locked inputs: https://nix.dev/concepts/flakes.html
4. SLSA provenance v1.0: https://slsa.dev/spec/v1.0/provenance


### Additional refinement: build recipe versus build result

The prototype now distinguishes `BuildSnapshot` from `BuildArtifact`. A BuildSnapshot hashes declared inputs and configuration; it does not assert that execution of the build was deterministic. BuildArtifact binds the resulting output digest to the exact build root, builder identity, and provenance root. DeploymentSnapshot references both the build root and the exact artifact. Thus two builds with identical declared inputs but different outputs cannot be silently treated as the same deployed artifact. Bit-for-bit reproducibility is an independently checkable claim comparing output digests under equivalent pinned inputs.
