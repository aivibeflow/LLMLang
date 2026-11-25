# LLVM freeze and source-level choice correlation

[GitHub #330](https://github.com/aivibeflow/LLMLang/issues/330) · 2026-11-25

The source contract observes one Boolean twice. When the input is known, both observations equal the low bit of the supplied word. Otherwise either Boolean is allowed, provided both observations see the same choice. An independent C realization chooses false for unknown input. This is one valid deterministic refinement of the source contract.

## LLVM subset and definedness

The LLVM implementation selects a concrete bit or a deferred value. One `freeze i1` produces a concrete representative used for both arguments to an observation function. Both arguments are extended to `i32` before crossing the native callback boundary and satisfy its `noundef` obligations. The modeled instruction subset contains an integer comparison, truncation, select, freeze, zero extension and an explicit call. A negative control adds an XOR to invert the second use.

| IR choice | Allowed observations for unknown input | Source admission |
| --- | --- | --- |
| One freeze of undef or poison, used twice | 00, 11 | Admitted |
| Two freezes of the same undef or poison | 00, 01, 10, 11 | Can violate correlation |
| Invert the second use of a single frozen value | 01, 10 | Refused |
| Pass undef or poison directly to the `noundef` observer | Outside the defined call domain | Withheld from execution |

The model follows LLVM's distinction between stable uses of one frozen result and different freeze instructions that may choose differently. The source contract owns the allowed observation relation. [LLVM LangRef](https://llvm.org/docs/LangRef.html#freeze-instruction) · [LLVM IR undefined behavior manual](https://llvm.org/docs/UndefinedBehavior.html)

## Optimization and native evidence

The runner checks the emitted IR with LLVM 19.1.7 at `default<O0>`, `default<O2>` and `default<O3>` using pass verification. It compiles and links the exact optimized modules and runs 520 vectors per fully admissible route. Each optimizer pipeline executes 3,120 native calls and withholds 520 calls where the unsafe controls violate a parameter premise. The independent GCC C route adds 520 calls. The source oracle identifies valid outcomes independently of either lowering.

Both single-freeze variants match the source contract in all 520 calls per optimizer pipeline. The portable C route matches as well. Two separate freezes happen to produce correlated samples in every tested build, although the instruction model permits the mismatched pairs. The defined inverted control exposes the mismatch on all 520 rows per pipeline. The optimized module retains two freeze instructions at O2 and O3, compared with seven at O0. Native agreement and exact textual IR are observations with different scope.

Five Lean 4.36.0 theorems audit the Boolean relation without axioms. They prove single-choice admission, the independent-choice counterexample, rejection of inversion and the exact known and unknown observation relations. The theorems cover the finite source model. The Python relation for the LLVM subset is a stated model of these instructions. General source-to-IR correspondence and optimization correctness remain open.

## Replay

Use CPython 3.12.14, GCC 14.2.0, Clang and opt 19.1.7, and Lean 4.36.0 on Linux x86-64.

```sh
fixture=research/compiler-and-translation/RT-13/LLVM-CORRELATED-FREEZE-01
python "$fixture/run.py" --clang /path/to/clang19 --opt /path/to/opt19 \
  --output /tmp/rt13-llvm-choice.json
cmp "$fixture/evidence.json" /tmp/rt13-llvm-choice.json
```

Two complete replays produced identical [evidence ledgers](LLVM-CORRELATED-FREEZE-01/evidence.json).
