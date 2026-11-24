# RT-09/13 — Mutable byte views across LLVM and C++

**Date** · 2026-11-21  
**Baseline** · `017e64b87c87371309197a392165258b8b088dd1`  
**Status** · Bounded differential experiment for [Plan §6.2](../../../PLAN.md#62-backend-selection-and-cross-backend-validation) and [§6.3](../../../PLAN.md#63-llvm-backend)

## Source contract

[Scenario 96B](../RT-13/RESEARCH-SCENARIO-96B-LLVM-BYTE-VIEW-PRESERVATION.md) distinguishes view identity, logical bounds, and physical address for read-only accesses. This experiment asks whether mutable overlapping views preserve an observation across a store.

The candidate operation validates the write identity, signed offset-plus-delta and strict view bounds, then the read identity and strict probe bounds. The first failed check fixes the error. A rejected operation leaves both the bytes and output sentinel unchanged. On success it reads the probe byte, stores 201 through the write view, then reads the probe byte again. Logical view IDs may differ even when the read and write reach the same physical byte. The output records the before/after pair and the harness observes the entire six-byte slab. The word transactional here refers to validation before side effects in one sequential call.

## Lowering alternatives

| Approach | Required invariant and cost |
|---|---|
| Conservative aliasing with two pointer arguments | Both pointers can address the same underlying allocation. Keep the second read unless the target compiler can prove independence. No additional dispatch is needed. |
| One allocation descriptor and checked indexes | Can keep one provenance root explicit across lowering. Consumes descriptor information and still requires ordered loads and stores plus separate checks for logical view identity. This study leaves code generation for this option open. |
| Disjoint or exclusive access specialization | May enable eliminating a redundant read. Needs an established noninterference invariant, for example explicit nonoverlap or a proved restriction in the selected ownership model. Different view IDs alone supply no such invariant. |

The direct LLVM lowering uses checked addition, unsigned bounds tests that also reject negative offsets, and branches that dominate memory effects. The independently authored C++ realization uses GCC checked addition and explicit signed range guards. Python supplies the oracle with arbitrary-precision sums and slab indexes. The interfaces are fixed handwritten realizations of this operation. [LLVM 19.1.7 LangRef, parameter attributes](https://github.com/llvm/llvm-project/blob/llvmorg-19.1.7/llvm/docs/LangRef.rst#parameter-attributes) · [GCC overflow built-ins](https://gcc.gnu.org/onlinedocs/gcc/Integer-Overflow-Builtins.html)

## Results

All four LLVM and C++ builds agree with the Python oracle at O0 and O3. Each build covers the same 117,600 cases, combining 25 write/read view pairs, four identity-match combinations, all pairs of 14 signed boundary values, and six probe indexes. That yields 470,400 comparisons of status, output and final memory. Per build, 910 cases succeed, 43,790 return bounds, 12,000 return overflow, and 60,900 return wrong origin.

The negative control adds LLVM `noalias` to the write argument. The test deliberately supplies overlapping physical bytes through different legal source views. LLVM accepts the IR. At O0 the observed pair is `(33, 201)`. At O3 it is `(33, 33)`, while status and final memory still agree with the source contract. The supplied attribute is invalid for this execution. The O3 observation demonstrates why validating only the IR, error code, or final state would miss a broken lowering. It does not predict behavior for other inputs to the invalid IR.

Use the conservative lowering as the comparison baseline in this fixture. A specialized path needs a separate proof or checked predicate for its aliasing precondition. RT-03 defines the observation order, RT-04 constrains permissible overlap, RT-09 must carry those rules through the checked IR, and RT-13 compares target observations. Broader allocator provenance, lifetimes, concurrency, ownership, target coverage, and compiler selection remain open. [Dependency map](../../RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

Run on Linux x86-64 with CPython 3.12.14, Debian LLVM 19.1.7 (package `1:19.1.7-3+b1`), GCC/G++ 14.2.0, GNU ld 2.44, and glibc 2.41. The direct LLVM path uses the existing verified O0/O3 PIC pipelines. The executable archive SHA-256 is `0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb`.

```sh
python -B research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01/llvm_mutable_view_probe.py \
  --opt /path/to/opt --llc /path/to/llc --cc gcc --cxx g++
```

| Lowered input | SHA-256 |
|---|---|
| LLVM IR | `53b6326862c8993f1bf58d91d180dfd4dddab3578892942b5abfed90884780bf` |
| C++ source | `4ab706666777d9120d7b02a0f7c37dbab441dec2a1c554e1fe13776c462bccce` |

Scenario 96B was also rerun with the same tools and matched all 19,600 observations and its existing control witnesses. This new native probe was run locally and requires the LLVM tools above. [Executable experiment](../PROTOTYPES/LLVM-PRESERVATION-01/llvm_mutable_view_probe.py)
