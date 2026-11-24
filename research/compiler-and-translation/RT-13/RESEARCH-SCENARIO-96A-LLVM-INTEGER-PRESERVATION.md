# Research Scenario 96A — Integer Semantics in Generated LLVM IR

**Status** — Bounded source-to-LLVM experiment on Linux x86-64

**Research areas** — RT-03 execution · RT-07 evidence · RT-09 lowering · RT-13 target preservation

**Updated** — 2026-11-20

**Baseline** — `main` at `d58df1640caa72c1bed4e58f02ef78f89185bc7c`

## Question

Can an LLVM backend preserve wrapping arithmetic, recoverable errors, and ordered effects for a fixed-width source fragment at both low and high optimization? Scenario 96 specifies the hazards. This study runs the integer portion of its proposed corpus. [Scenario 96](RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md) · [Backend preservation brief](../../preparation/RT-07-09-10-13-EVIDENCE-AND-BACKEND-PRESERVATION.md)

## Source contract and lowering

Each program emits argument `a` before a conditional operation. The skipped branch returns `b`. Success emits and returns the value. A recoverable error exits after the first effect, with an error kind and no result value. The adapter checks the fixed source shape and lowers the chosen operation and its argument order. The reference evaluates the source rules with arbitrary-precision Python integers. The native target uses a C ABI callback to capture ordered effect payloads and a separate output slot for the value. [Source and reference](../PROTOTYPES/LLVM-PRESERVATION-01/integer_fixture.py) · [LLVM generator and runner](../PROTOTYPES/LLVM-PRESERVATION-01/llvm_integer_probe.py)

| Candidate source operation | Source outcome | Emitted LLVM rule |
|---|---|---|
| Wrapping add, subtract, multiply | Value modulo 2³² | Plain `add`, `sub` or `mul` with no overflow flags |
| Checked signed or unsigned add, subtract, multiply | Value in range or `overflow` | Matching `llvm.*.with.overflow.i32` intrinsic and explicit branch |
| Checked signed or unsigned division and remainder | `zero_divisor` at zero. Signed minimum by −1 returns `overflow` under this fixture contract. Division truncates toward zero. | Nonzero guard. Signed operation also checks the minimum/−1 pair before `sdiv` or `srem`. |
| Checked left, arithmetic right or logical right shift | Value for counts 0–31. All other counts return `shift_count`. Left shift wraps at 32 bits. | Compare the count as unsigned before the shift. No no-wrap or `exact` promise. |

These are tested candidate rules. For example, a source contract that defines signed minimum remaindered by −1 as zero would need a different guarded result. LLVM's rules for integer operations, overflow intrinsics, and poison are versioned inputs to this experiment. [LLVM 19.1.7 language reference](https://github.com/llvm/llvm-project/blob/llvmorg-19.1.7/llvm/docs/LangRef.rst)

## Method and results

The generator lowers 16 operations and one signed division fixture with swapped operands. Each program gets both branch outcomes for all 361 pairs over 19 boundary values and 256 additional 32-bit pairs from Python's `Random(134)`. Boundary values include signed and unsigned extrema, half-range multiplication thresholds, and counts around the 32-bit shift limit. This yields 1,234 inputs per program. The runner verifies the original IR, runs `default<O0>` or `default<O3>`, verifies again, and compiles and links a native library for the matching level. Each comparison includes the status, returned bits or absence of value, and every callback payload in order. The caller initializes the output slot to a sentinel and checks it on error.

| Profile | Native comparisons | Success | Overflow | Invalid shift count | Zero divisor | Mismatches |
|---|---:|---:|---:|---:|---:|---:|
| O0 | 20,978 | 17,552 | 1,765 | 1,566 | 95 | 0 |
| O3 | 20,978 | 17,552 | 1,765 | 1,566 | 95 | 0 |

The source checker rejects an unknown operation, a literal operand, and an effect expression outside the fixture. The LLVM verifier rejects a value used on an error edge that it does not dominate. A separate mutation replaces the signed-add overflow branch with unconditional success. That mutant remains structurally valid at both levels. For `2147483647 + 1`, the oracle expects overflow after one effect. Both mutant binaries return bits `0x80000000` and emit a second effect, so the differential test catches the semantic failure.

| Claim | Evidence and scope | Falsifier or missing evidence | Downstream impact |
|---|---|---|---|
| S96A-01. The candidate mappings preserve the checked observations for the generated inputs. | Experimental result. 41,956 comparisons across the specified fixture and LLVM 19.1.7 profiles. | A status, value, effect, or result-slot mismatch for an accepted input invalidates the tested lowering. Whole-domain proof and other targets remain open. | LL-020, RT-09, RT-13 |
| S96A-02. Structural verification accepts a lowering that loses the source overflow edge. | Experimental result. The defined, mutated program differs on the signed maximum witness at O0 and O3. | A stronger claim about what a validator can prove requires source-aware correspondence evidence. | LL-008, RT-07 |

## Reproduction and decision boundary

```sh
python -B research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01/llvm_integer_probe.py --opt /path/to/opt --llc /path/to/llc
```

The run used Debian LLVM `1:19.1.7-3+b1` and Python 3.12.14. The target is `x86_64-unknown-linux-gnu` with CPU `x86-64`, position-independent objects and GNU ld 2.44 via GCC 14.2.0. Python used libffi 3.4.8 and glibc 2.41. The runner gives every tool invocation at most 60 seconds. It prints result counts and the negative-control traces. The input IR SHA-256 is `c46111f6b77eb621a5c154b17645044e1d76c7cb2808fe80189a63f447dc173d`. The Debian tool archive SHA-256 is `0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb`, verified against the signed trixie package metadata.

Evidence applies to the fixed integer fragment, two optimization pipelines, and the declared target. The corpus exercises runtime values and skipped branches. Constant folding of source expressions, general provenance and memory access, floating point, traps and unwinding, ABI portability, and formal translation validation remain open. The numeric and backend choices remain candidates. [LL-020](../../../TODO.md#ll-020--define-llvm-backend-role-and-semantic-boundary) · [LL-008](../../../TODO.md#ll-008--define-compatibility-evidence-and-evidence-reuse-rules)


## RT-00 reproducibility audit: experiment source revision

The `Baseline` above is the pre-experiment source baseline, not the commit containing the probe implementation. The exact experiment/report source commit is [`a80d94e795d8d2b613d01c09687c181df592c7f5`](https://github.com/aivibeflow/LLMLang/commit/a80d94e795d8d2b613d01c09687c181df592c7f5); it introduced this report together with `integer_fixture.py` and `llvm_integer_probe.py`. Keep the recorded baseline `d58df1640caa72c1bed4e58f02ef78f89185bc7c` unchanged as the pre-experiment baseline.

The historical LLVM run is not invoked by required CI. Its recorded tool archive, input IR hash, compiler/tool versions, commands, and limits remain the reproduction evidence; a fresh run on current main is not implied by the CI test results.

The [whole-domain checked-add study](RT-13-LLVM-CHECKED-ADD-OBSERVATIONS-2026-11-24.md) checks the signed-add O0 and O3 IR artifacts against a source observation model over all inputs. It extends the missing-overflow control with reordered callbacks and an output-slot write on error.
