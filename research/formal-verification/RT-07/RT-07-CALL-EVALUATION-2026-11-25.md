# RT-07 — Effectful call evaluation and abrupt completion

This experiment turns the first four discriminators from [Scenario 77](../../language-design/RT-03/RESEARCH-SCENARIO-77-CALL-ARGUMENT-EVALUATION-ORDER.md#4-discriminating-fixtures-for-llmlang-research) into a shared executable corpus. It compares source-ordered operands with either sequential order for the arguments. The result informs [PLAN §2.1](../../../PLAN.md#21-formal-semantics-of-the-language) and [#293](https://github.com/aivibeflow/LLMLang/issues/293).

Both candidate models evaluate the target before either argument. Each operand reads or toggles one shared Boolean cell and records its stage, the prior cell and the new cell. The operand can finish normally or fail before the rest of the call. Failing after its cell change is a separate fixture, and the failed prefix retains its effects. The body records entry only after both arguments finish successfully. Argument values remain in their original parameter slots in both schedules.

| Candidate | Admitted argument schedules | Observable consequence |
| --- | --- | --- |
| Source order | Left, then right | The effect order and the first failing operand are fixed by the source. |
| Sequential with unspecified order | Left, then right or right, then left | Each operand completes before the other starts. Either trace, value or selected error can be admitted when the operands differ observably. |
| Guarded reordering | Source order unless a proof establishes agreement | Lean checks that swapping a total constant with no state change or trace cannot alter the complete observation, even when the other operand fails. |

The Python oracle enumerates all 128 combinations of initial cell and target/argument behaviors for each order. The orders differ for 64 complete observations. Tagged result and final cell distinguish 44 cases. Another 20 differ only in the ordered trace. When both arguments fail, the selected failure stage differs in 16 cases. A target failure records only the target prefix for both schedules.

The Rust fixture uses the `?` operator to return immediately from an operand failure. The C++ fixture throws an exception at that point and captures the failing stage in the caller. Each native invocation is compared with the permitted observations for its model. Source-ordered Rust 2021 is compared against the left-first oracle. Both C++20 builds are compared against membership in the two-order set. All checks passed.

| Compiler and profile | Rows per optimization level | Order on all 64 distinguishing cases |
| --- | ---: | --- |
| rustc 1.85.1, O0 and O2 | 128 | Left first |
| GCC 14.2.0, O0 and O2 | 128 | Right first |
| Clang 19.1.7, O0 and O2 | 128 | Left first |

The two C++ implementations exhibit different schedules under the same language mode. These observations apply to the recorded compiler builds and fixture. The Rust early return and C++ stack unwinding have matching observed prefixes here. Destructors and unwinding effects, implicit conversions, defaults, nested calls, scheduling, divergence and LLMLang source correspondence remain open. Lean checks prefix preservation on failure and the pure-operand rule against the model without additional axioms. The native runs supply separate observed behavior. Runtime and lowering depend on the explicit order and observation contract in [DEP-016 and DEP-018](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register).

## Reproduce

Use x86-64 Linux, CPython 3.12.14, rustc 1.85.1 at `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, GNU g++ Debian 14.2.0-19, Clang Debian 19.1.7 (3+b1), and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. With those compilers available, run the commands below from the repository root. Set `RUSTC`, `GXX` or `CLANGXX` to the corresponding executable if it is outside the path. The [ledger](CALL-EVALUATION-01/evidence.json) records each profile, counts, witnesses and native stdout digests.

```sh
set -eu
fixture=research/formal-verification/RT-07/CALL-EVALUATION-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Order.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
