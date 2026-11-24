# Research Scenario 96B — Byte-View Bounds and Origin in LLVM

**Status** — Bounded differential experiment on Linux x86-64

**Baseline** — `main` at `a80d94e795d8d2b613d01c09687c181df592c7f5`

**Research areas** — RT-03 semantics · RT-07 evidence · RT-09 lowering · RT-13 targets

## Contract and method

Can LLVM preserve a source rule that distinguishes forming an end pointer from reading through it, even when the address also names a readable byte in another view? The test uses five logical views of one initialized six-byte allocation. The views include adjacent ranges, overlapping ranges, and an empty range at the end. Each view has an identity, base and length supplied together by the test harness.

Formation accepts a signed offset-plus-delta in the inclusive range `[0, length]`. Reading first checks the originating view against the expected view, then requires the sum to fit in `i64` and the index to be strictly less than the length. Both operations reject negative indices. The Python reference uses arbitrary-precision arithmetic. The generator emits LLVM signed-overflow checking followed by a bounds branch that dominates `getelementptr inbounds`. Only the read path emits a load. On rejection the caller's result slot keeps its sentinel. Pointer-to-integer conversion exposes the formed address for measurement on x86-64. The runner never reconstructs a pointer from that integer. [Executable probe](../PROTOTYPES/LLVM-PRESERVATION-01/llvm_view_probe.py) · [LLVM 19.1.7 GEP documentation](https://github.com/llvm/llvm-project/blob/llvmorg-19.1.7/llvm/docs/GetElementPtr.rst)

## Results

| Pipeline | Comparisons | Success | Bounds | Overflow | Wrong origin |
| --- | ---: | ---: | ---: | ---: | ---: |
| O0 | 9,800 | 580 | 4,100 | 1,200 | 3,920 |
| O3 | 9,800 | 580 | 4,100 | 1,200 | 3,920 |

All 19,600 comparisons match. Each pipeline runs both operations against every origin and expected-view pair and all pairs of 14 signed boundary operands. The left view's end and the right view's start both form the address at slab offset 3. Reading through the left view returns a bounds error. Reading through the right view returns byte 44.

Two verifier-accepted controls depart from the reference at both optimization levels. Allowing reads at the left view's end returns byte 44 from the adjacent view. Removing the origin check accepts a read from an overlapping view and returns byte 33 where the contract requires a wrong-origin error. Both witness loads remain inside the initialized physical allocation. They show that a physically valid LLVM load can violate logical bounds or origin. Either mismatch falsifies the corresponding lowering rule for this fixture.

## Reproduction and limits

```sh
python -B research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01/llvm_view_probe.py --opt /path/to/opt --llc /path/to/llc
```

The runner uses Debian LLVM 19.1.7, Python 3.12.14 and GCC 14.2.0 with GNU ld 2.44 on `x86_64-unknown-linux-gnu`. It reuses the verified O0/O3 pipelines and PIC configuration from Scenario 96A. The input IR SHA-256 is `ddb41ceb866c77e957df865cd2102f7a02d3a468150fc82f79c7a7fb2bf782d0`. [Integer baseline](RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md)

This experiment covers logical view identity within a single live allocation. General allocation provenance, stale pointers, forged descriptors, alignment beyond byte loads, and validation of a complete source-to-LLVM pipeline remain open. The result informs LL-020 without selecting a memory model or backend. [LL-020](../../../TODO.md#ll-020--define-llvm-backend-role-and-semantic-boundary)


## RT-00 reproducibility audit: experiment source revision

The `Baseline` above is the pre-experiment source baseline, not the commit containing the probe implementation. The exact experiment/report source commit is [`2a9b6e5072efc542e823c529cf3cdee838f9ad36`](https://github.com/aivibeflow/LLMLang/commit/2a9b6e5072efc542e823c529cf3cdee838f9ad36); it introduced this report together with `llvm_view_probe.py`. Keep the recorded baseline `a80d94e795d8d2b613d01c09687c181df592c7f5` unchanged as the prior experiment baseline.

The historical LLVM run is not invoked by required CI. Its recorded input IR hash, tool versions, commands, and limits remain the reproduction evidence; a fresh run on current main is not implied by the CI test results.
