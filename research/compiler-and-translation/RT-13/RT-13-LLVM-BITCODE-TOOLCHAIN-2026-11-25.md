# Exact LLVM bitcode producer and consumer compatibility

[GitHub #330](https://github.com/aivibeflow/LLMLang/issues/330) · 2026-11-25

The fixture tests Clang and LLD 19.1.7, 22.1.4 and 23.1.1 on x86-64 Linux. Each compiler emits LLVM bitcode for two independent C source contracts. One takes a 32-bit value, while the other reads it from an explicitly supplied pointer. The fixed-width transform and its independent Python oracle are identical. Each linker produces a freestanding shared object using its LTO pipeline. Native validation calls the exact artifact for 261 unsigned input values.

## Observed support matrix

All nine scalar pairs link and pass. The pointer input distinguishes two additional incompatible pairs.

| Pointer bitcode producer | LLD 19.1.7 | LLD 22.1.4 | LLD 23.1.1 |
| --- | --- | --- | --- |
| Clang 19.1.7 | Tested | Tested | Tested |
| Clang 22.1.4 | Refused | Tested | Tested |
| Clang 23.1.1 | Refused | Tested | Tested |

The two LLD 19 refusals report `Unknown attribute kind (102)`. Clang 19 emits `nocapture` on the pointer. Newer producers emit `captures(none)`. A directed control removes only the capture annotation from each newer textual module, assembles the resulting IR under its original producer, and links it with LLD 19. Both such artifacts pass all 261 native calls, isolating the incompatible attribute in these fixtures. The original failed link cells remain refused.

The 16 admitted baseline cells cover 4,176 native observations, and the annotation controls add 522. A final control retains the same Clang and LLD, successfully links under the same symbol, and changes the transform constant. All 261 native observations diverge from the source contract. A successful link establishes artifact admission. Behavioral validation determines whether that artifact satisfies the contract.

## Candidate version policy

Record producer and consumer binary identities, versions, target triple, link mode, profile and exact input bitcode. Reuse a prior claim only for its exact scope. Admit other combinations after independently replaying both link and native semantics. The observed evidence does not extend across all modules carrying the same LLVM major number. The recorded binary digests cover the direct executables; complete distribution, shared tool dependencies and supported production profiles require separate inventories.

Two independent temporary roots reproduce bitcode, textual IR, successful ELF files, diagnostics and native trace digests. [Evidence ledger](LLVM-BITCODE-TOOLCHAIN-01/evidence.json)

## Replay

Use CPython 3.12.14, GNU readelf and pinned Clang and LLD executables for each tested version. The newer distributions are those bundled with Lean 4.34.0 and 4.36.0.

```sh
fixture=research/compiler-and-translation/RT-13/LLVM-BITCODE-TOOLCHAIN-01
python "$fixture/run.py" --clang19 /path/to/clang19 --lld19 /path/to/lld19 \
  --clang22 /path/to/clang22 --lld22 /path/to/lld22 \
  --clang23 /path/to/clang23 --lld23 /path/to/lld23 \
  --output /tmp/rt13-llvm-bitcode.json
cmp "$fixture/evidence.json" /tmp/rt13-llvm-bitcode.json
```
