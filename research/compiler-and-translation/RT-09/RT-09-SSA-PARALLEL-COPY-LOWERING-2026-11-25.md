# RT-09 — Preserve parallel SSA updates during sequential lowering

Can a lowering replace multiple incoming phi selections with sequential assignments while preserving each loop-state observation? This fixture compares native execution of LLVM phis, a generated copy schedule using temporaries, and direct in-place assignment. The branch baseline is `b986d2287eec56628438feea9f0564cc19aa88d7`. [Ordered SPG lowering](RT-09-ORDERED-SPG-LOWERING.md) · [LLVM phi instruction](https://llvm.org/docs/LangRef.html#phi-instruction)

The bounded loop has three mutable logical slots. A back edge selects one old slot as the next value for each destination. The pure reference computes all three selections from a fresh copy of the preceding state. The LLVM generator expresses each selection as one phi input on the back edge. The scheduled C lowering emits a copy only when the copy's destination value is no longer needed as a source. If no copy is ready, it saves one old value to a temporary and updates its outstanding uses. The control writes the destinations in place in their listed order.

Across 27 mappings, 27 initial tuples and zero through four iterations, the harness compares all 3,645 traces and checks that the target writes only the expected output prefix. Each trace contains the initial state and every successor. The native versions are compiled at optimization levels 0 and 2. [Generators, copy schedules and native checks](SSA-PARALLEL-COPIES-01/run.py) · [Machine-readable results](SSA-PARALLEL-COPIES-01/evidence.json)

| Lowering | Intermediate or final trace mismatches | Final state mismatches |
|---|---:|---:|
| LLVM phi selections | 0 | 0 |
| Dependency-scheduled copies | 0 | 0 |
| Direct sequential copies | 1,050 | 888 |

The direct sequential version can overwrite a value that a later copy still needs. In a three-slot rotation, assigning the first destination before retaining its previous value makes the last destination select the wrong value. A final-state check misses 162 cases where the trace already diverged. The two optimizer levels agree on all dispositions.

This result supports placing an explicit parallel-copy preservation obligation at the SSA-to-sequential boundary. It covers three integer slots with exact edge selection and ordinary local copies. General control-flow graphs, critical-edge placement, memory aliasing, target-specific moves and a proof for arbitrary-size scheduling remain open. [Translation architecture issue](https://github.com/aivibeflow/LLMLang/issues/327)

## Reproduction

Use CPython 3.12.14 and Clang 23.1.1 at LLVM revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689` on x86-64 Linux. The runner generates and compiles both IR and C. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/compiler-and-translation/RT-09/SSA-PARALLEL-COPIES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang > /tmp/llmlang-rt09-ssa-parallel.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt09-ssa-parallel.json
```
