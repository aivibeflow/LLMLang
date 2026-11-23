# RT-11: Cache speedup model recheck

**Date:** 2026-11-23  
**Baseline:** `338c47aee8fc3c8f6780ef1b15b0d249ab0bf63f` (`main`)  
**Status:** reproducible action-count experiment; no elapsed-time benchmark  
**Question:** which implications of the analytical cache-speedup model are supported by the current executable binding experiment, and which remain unmeasured?

## Method and provenance

Ran the existing synthetic C experiment from `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python3 -B -m src.binding_build_benchmark --cc cc
```

Environment: CPython 3.12.14; `cc (Debian 14.2.0-19) 14.2.0`; target `x86_64-linux-gnu`. The program's clean-build oracle matched every incremental result. It tests exact-address and separate stable-symbol linkage, sixteen fixture callers, one body-visible caller group, one independent provider, compile/link/verification action counts, and a verification-key counterexample. SHA-256 at the baseline: `binding_build_benchmark.py` `8da49c2a49817ae429a4323b0aee02b8c866ea53cf796ab8c196cb191d745fe4`; `binding.py` `451fce52b0a01395339dab8f2d9c9901f155f1dac201a83efb588284e8187471`.

## Reproduced counts

Each cell is actions executed in that phase, with exact linkage first and separate linkage second. “Projected verification” keys the result to the selected binding row; “whole snapshot verification” keys it to the complete snapshot root.

| Change | Provider compiles | Caller compiles | Links | Projected verification | Whole-snapshot verification |
|---|---:|---:|---:|---:|---:|
| Cold | 2 / 2 | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 |
| Identical warm build | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Implementation changes, ABI/contract preserved | 1 / 1 | 12 / 4 | 12 / 12 | 12 / 12 | 16 / 16 |
| Contract tightens, C body/ABI unchanged | 1 / 0 | 8 / 0 | 8 / 0 | 12 / 12 | 16 / 16 |
| Binding snapshot parent changes only | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 16 / 16 |
| Compiler flags change | 2 / 2 | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 |

On separate linkage, changing the implementation recompiles four body-visible callers and none of the twelve prototype-only callers; all twelve linked executables and verification actions rerun. The fixture also holds a caller's compile-input digest constant while its executable output changes from `10 11 10 11` to `11 12 11 12`, so caller compilation identity alone is not a sound verification key. The whole-snapshot policy reruns all sixteen checks after a parent-only history change, while the directly projected key reuses them in this fixture.

## What this supports

- A warm identical build can have zero executed actions in this cache model.
- A stable separate-link boundary can preserve caller compilation across an implementation change when caller compilation does not consume the body.
- Verification has inputs beyond caller compilation and needs its own exact identity.
- Whole-snapshot keys are conservative and can over-invalidate relative to a verified selected-binding projection.
- Cold builds execute the full measured action set; the experiment does not establish whether initial cache population is a wall-time loss or gain.

These reproduce relationships between declared inputs and action counts. The count reduction does **not** validate the speedup estimate's 6–8× local-edit, 2.2–2.4× component-edit, or 17–34× warm-build numbers. No action durations, critical path, lookup/hash/dependency overhead, memory, artifact transfer, or representative Rust/Go/C++ project was measured. The synthetic C workload also does not model source-derived dependency discovery, toolchain changes beyond one fixed environment/flags case, remote caches, or parallel scheduling.

## Decision and remaining work

Keep the analytical ratios labeled as hypotheses and do not use them to select a production cache architecture. The executable experiment strengthens the action-reuse and verification-key arguments, while §3.4's main performance claim remains unvalidated. Next empirical work needs controlled repeated timings and distributions for cold, warm, local, component, and broad changes; hit rates and overhead by action; clean and conventional incremental baselines; and representative Rust, Go, and C++ workloads on declared hardware. Report neutral/slower cases and critical-path effects as well as action counts. Cache correctness and completeness gates from §3.2 must hold independently of any speedup result.
