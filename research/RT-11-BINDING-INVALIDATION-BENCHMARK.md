# RT-11 Binding Invalidation Benchmark

**Status:** Executable compiler experiment in a synthetic workload

## 1. Question

The recursive identity experiment makes a group of implementations and all exact callers depend on one group version. This benchmark asks which compile, link, and verification work can survive a change when the caller instead uses a stable ABI and the build binds the implementation separately. [Recursive identity experiment](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md) · [Binding Snapshot study](RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md)

The distinction is consistent with prior work on the inputs consumed by an action. GHC uses interface fingerprints for recompilation checks. The build systems literature distinguishes evaluating dependencies from deciding whether the consuming action needs to run. [GHC recompilation checker](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/separate_compilation.html#the-recompilation-checker) · [Build Systems à la Carte](https://eprints.ncl.ac.uk/249855)

## 2. Workload and comparison

Two providers each contain a pair of mutually recursive C functions. Sixteen callers are independent executable targets. Eight call the edited provider through a C prototype, four of its callers compile with the provider body visible, and four call an independent provider. The benchmark generates C and invokes a real compiler and linker.

- **Exact linkage.** An external caller uses a symbol derived from the selected implementation address. A replacement changes the symbol even when the ABI is unchanged.
- **Separate linkage.** An external caller uses a stable symbol. The linker receives the compiled object for the implementation selected in the immutable Binding Snapshot.
- **Body-visible callers.** In both modes the caller receives the implementation source. This models a compile action that consumes the body, whether or not the optimizer eventually inlines the function.

The compile key uses generated source, flags, and toolchain identity in one fixed local environment. Link keys include the ordered object byte digests. Verification runs the executable with four fixture inputs and checks the complete output tuple against the permitted outcomes for those inputs. Its key includes the executable bytes, contract, input set, and verifier/toolchain domain. One variant also commits to the entire Binding Snapshot root, and the other keys on the one binding row this fixture reads. Each stage counts cache misses independently.

The cases are measured sequentially within each linkage mode. Each case is also built from an empty cache in a separate directory and its observed outputs compared against the incremental run and the other linkage mode. Those oracle actions are excluded from the incremental counts. These are executed action counts on a synthetic C workload, with no wall-time estimate for an LLMLang compiler. The fixture keeps one local compiler, SDK, environment, and target fixed. Production dependency discovery, runtime input tracing, and toolchain attestation remain separate requirements.

## 3. Results

The run used Python 3.12.14 and Apple Clang 21.0.0 on `arm64-apple-darwin27.0.0`. All outputs agreed with the clean build for every phase and linkage mode. The count pair in a cell gives exact linkage first and separate linkage second.

| Edit | Provider compilations | Caller compilations | Links | Verification, selected binding | Verification, whole Snapshot |
|---|---:|---:|---:|---:|---:|
| Cold | 2 / 2 | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 |
| Identical warm | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Change one implementation, preserving its ABI and contract | 1 / 1 | 12 / 4 | 12 / 12 | 12 / 12 | 16 / 16 |
| Tighten that contract, keeping its ABI and C body | 1 / 0 | 8 / 0 | 8 / 0 | 12 / 12 | 16 / 16 |
| Change only the Binding Snapshot parent | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 16 / 16 |
| Change compiler flags from `-O0` to `-O2` | 2 / 2 | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 |

With a stable ABI the implementation change saves recompiling eight callers, while the same twelve executable targets still link and undergo verification. The four callers that consume the body must recompile in both models. In the separate linkage mode, one caller keeps the same compile inputs while its observed output changes from `10 11 10 11` to `11 12 11 12`. Its old result would be stale if verification used the compile inputs as its key. Both acceptable outputs fit the unchanged contract.

The contract-only edit in separate linkage requires verification but no C compile or link actions for this fixture. With exact linkage, this edit changes the address embedded in the generated external symbol and therefore recompiles eight callers. History-only changes distinguish root-based evidence from a projected key. The root-based policy reruns checks even when all rows are unchanged.

## 4. Consequences for the RFC

The data supports measuring a separately linked ABI boundary where caller compilation does not consume the selected body. It also shows why concrete execution evidence and caller compilation need different keys. An optimization that reads an implementation or assumes one of its properties must track that input. The language still needs an explicit rule for which checked semantic properties a caller may assume from a contract.

The projection is safe for the benchmark's fixed, directly declared one-row dependency. Before using a projected key in the general Toolchain Server, the design needs evidence about all bindings and conditions used by the action, including negative or fallback lookups that can change resolution. A root-based key remains a conservative candidate where that read set cannot be established. This run does not establish performance or trust for remote caches, an ABI design for LLMLang, or general behavioral conformance.

## 5. Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01` with Python 3.10 or later and a local C compiler:

```sh
python -B -m src.binding_build_benchmark --cc /usr/bin/cc
```

The benchmark prints per-stage counts and a witness showing why the caller's compile inputs cannot serve as its executable verification key. The recorded run used repository base `72822973f7cc9fd33ede66aad05e844bf25d5bd3` plus this working tree experiment. [Executable benchmark](PROTOTYPES/DEPENDENCY-GRAPH-01/src/binding_build_benchmark.py)

## Public-interface integration (2026-11-24; proposed)

Follow-up test plan: retain the separate-linkage workload and add independent public contract, provider contract, catalog and binding revisions. Compare modular caller proof reuse, compile action reuse, conformance-proof revalidation and link/whole-execution verification under body-only changes, incompatible contracts and public alias changes. The existing C benchmark demonstrates limited compile/link behavior, not a theorem of LLMLang interface substitution or proof reuse.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This follow-up does not change earlier results or accepted rules.
