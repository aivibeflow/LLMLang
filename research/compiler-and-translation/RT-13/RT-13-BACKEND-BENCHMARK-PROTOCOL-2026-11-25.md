# RT-13 backend benchmark protocol and shared corpus

Backend comparison needs the same semantic input and the same measurement boundary. A cached edit, one in-process JIT compilation and a process launched from scratch answer different questions. Optimized and debug configurations each need independent conformance before their performance results can be compared. The protocol below defines those boundaries and pins an executable starting corpus for LLVM, Cranelift and applicable alternatives. It leaves benchmark execution and production configuration selection as separate plan items.

```mermaid
flowchart LR
    A["Pinned workload, inputs, oracle and target"] --> B["Build candidates under the same intent"]
    B --> C["Check exact artifacts and adversarial controls"]
    C --> D["Match timed boundary, cache state and edit"]
    D --> E["Record paired raw samples and per-workload distributions"]
```

## Common workload inventory

| Workload | Observations | Executed backend routes |
| --- | --- | --- |
| Checked addition with ordered effects | Status, stored bits, callback order, overflow and bypass | LLVM ORC and Cranelift host JIT |
| Native callback with generated code on the stack | Return, callback count, frame registration lifetime, source origin | LLVM ORC and Cranelift host JIT |
| Strict dynamic rounding in one leaf | Result bits, sticky flags and inspected machine code | LLVM x86-64 and a scoped direct assembly control |
| Read-only Wasm memory64 byte view | Bounds, return or rejection, traps and host admission | LLVM wasm64 and WABT-assembled WAT |

The manifest pins source, runners and result artifacts by SHA-256. `observed` means an executable route has a checked fixture. A `scoped-control` can refute a claim about a particular lowering while wider backend coverage remains incomplete. `missing` records a comparison cell without an executable route. A completed compiler benchmark needs larger inputs in at least three separate workload families, shared modules with a deterministic edit and invalidation chain, repeated computation that exercises the runtime and optimizer, and an effectful workload that crosses an ABI and observes cleanup. Use frozen source and input hashes, retain cold and warm configurations, and specify the narrow output, effect and error equivalences for each. The four registered fixtures provide boundary and adversarial coverage. Representative application workloads and the selected measurement hardware remain a separate gate. [Executable corpus](BACKEND-BENCHMARK-PROTOCOL-01/corpus.json)

## Collection boundaries

| Measure | Start and end | Record |
| --- | --- | --- |
| Clean build latency and throughput | Launch a build with an empty build and backend cache. Stop when the final callable artifact and required metadata are available. Also time frontend, lowering, backend and link phases individually where observable. | Input size, wall and CPU time, job count, units built per second and observed filesystem cache condition |
| Incremental rebuild | Start from an identical successful build. Apply the pinned edit, start the timer on invocation and stop at the next checked artifact. Use separate local, interface, dependency and no-op edits. | Exact edit, invalidated units, accepted reuse, recomputation and wall time |
| Host JIT | Record process-to-first-call-ready and in-process module-enabled-to-call-ready separately. Keep first materialization, repeated new modules and cache hit distinct. | Startup, materialization, number of modules, allocation and registration included in the boundary |
| Debug and Release runtime | Prepare a checked artifact before timing. Time a fixed input batch through the selected observable effects. Record startup separately and warm-up by predeclared policy. | Nanoseconds per operation, operations per second, batch size and optimization intent |
| Artifact size and compiler memory | Inspect like-kind artifacts. Measure compiler peak process-tree memory from launch through the end of the selected phase. Run sequential and parallel builds as separate cells. | Bytes for text/debug/full object or executable, peak bytes, process-tree accounting and tool |
| Debug and diagnostic quality | Use pinned success and error scenarios for stack traversal, source origins, stepping, and unsupported operations. | Expected and observed dispositions, exact source ranges and settings, debugger version and false attribution |
| Target coverage and integration | Perform each matrix stage using the same demanded ABI, runtime and support policy. | Code emission, link, native versus emulated execution, conformance, required components, setup commands and supported profile |

A clean build empties build caches. Treat the operating system page cache as a separate observed or controlled variable. A fresh process can reuse shared-library pages. A source edit can change semantics, dependencies or both. Record before/after input digests, expected semantics and the precise edit category. Peak RSS for one process and peak aggregate memory of a process tree are different measures, so identify the exact metric.

Run each comparison pair on one pinned target, CPU affinity, runner, resource limit, and workload profile. Record CPU/ISA, kernel, OS, filesystem, cache policy, toolchain versions and flags, linker, runtime, container quotas, codegen worker count and background load or throttling counters. Randomize backend order using a recorded seed within at least 30 paired independent process-level batches for the initial timing run. A predeclared diagnostic can justify more batches, while a smaller pilot retains its limited scope. Hold failed observations in the ledger. Report median, p10, p90, sample size and raw samples per workload and build profile. When including paired uncertainty, bootstrap the independent batches rather than individual measurements from the same process. Separate trials with observed contention, and compare size and portability directly alongside timing. Retain environment metadata, reference receipts, raw samples and a reproducible chart per measured quantity. [Example materialization study](RT-13-JIT-MATERIALIZATION-LATENCY-2026-11-24.md)

Receipts bind workload, inputs, oracle, target, environment, optimization intent, boundary, cache state, edit identity, measured unit and exact checked and timed artifacts. Record per-backend toolchain, options and output identity so that LLVM O0 and Cranelift `none` can share a comparison intent without asserting identical optimization passes. Candidate ranking requires passing the common reference oracle and detecting its adversarial outcomes. The matching prototype checks recorded field equality and applicability on supplied receipt data. A production collector also needs to bind the observation to the measured process and artifact at collection time.

## Verification

The executable inventory verifies 22 artifact pins for four workloads. Sixteen synthetic receipt controls include an accepted LLVM/Cranelift pair, differences in input and oracle identity, a target outside the workload profile, incompatible boundaries and units, an unavailable route and changes to a checked artifact. A stale inventory hash is separately refused. These checks establish inventory consistency and the behavior of the comparison rules. They do not add timing observations. [Checker](BACKEND-BENCHMARK-PROTOCOL-01/run.py) · [Evidence](BACKEND-BENCHMARK-PROTOCOL-01/evidence.json)

Run with CPython 3.12.14 from the repository root.

```sh
study=research/compiler-and-translation/RT-13/BACKEND-BENCHMARK-PROTOCOL-01
build=$(mktemp -d)
for seed in 37 75; do
  LC_ALL=C PYTHONHASHSEED="$seed" python "$study/run.py" --output "$build/result-$seed.json"
done
cmp "$build/result-37.json" "$build/result-75.json"
cmp "$build/result-37.json" "$study/evidence.json"
```
