# Ordered commit and rollback across hosted backends

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

The fixture evaluates a checked byte write with an explicit primary error, cleanup error bits, optional result, final state, remaining ownership and ordered effects. It varies acquisition, write, rollback and release outcomes independently. A failed write may change state before it reports failure. The caller then attempts rollback and still attempts release. A failed release leaves the ownership obligation visible.

The emitter instantiates C++, Go, Rust, Java and Python templates from one declared range, error and event encoding. A separate Python evaluator implements the contract using explicit transition records and computes the expected observations without executing any generated code. The runner exercises 784 inputs, including range boundaries and every combination of four outcome flags.

| Target profile | Complete observations |
| --- | ---: |
| GCC C++20, O0 and O2 | 784 per profile |
| Clang C++20 lowered through a retained LLVM IR file and linked by Clang | 784 |
| Go standalone, `GOAMD64=v1`, cgo disabled | 784 |
| Rust 2021, O2 with overflow checking | 784 |
| Java 21, interpreter and default HotSpot mode | 784 per profile |
| CPython 3.12 | 784 |

All eight profiles produce the same full trace digest in 6,272 comparisons. The LLVM route consumes a real intermediate file generated from the C++ template. Java default execution is recorded as a runtime configuration. The existing scalar fixture separately confirms compiled entry methods.

Three executable C++ controls isolate omissions that can survive narrower comparisons.

| Changed behavior | Incorrect observations | What would miss the change |
| --- | ---: | --- |
| Omit the release effect | 392 | All scalar fields, including the error pair and final state, still agree. |
| Omit the release error bit | 196 | The primary result, ownership, state and ordered effects still agree. |
| Skip restoration after a successful rollback disposition | 40 | The error pair, ownership and ordered effects still agree. |

The reported finite contract models provider dispositions with inputs. Go, Rust and C++ match that hosted contract under the recorded builds. This evidence complements their separate native ABI, ownership and runtime studies. Real external provider failures, exception and unwind semantics, concurrent interference, broader platform coverage and the initial target selection remain open.

## Replay

Use CPython 3.12.14, GCC/G++ 14.2.0, Clang 19.1.7, Go 1.27.4, Rust 1.85.1 and OpenJDK 21.0.13. The runner builds in a fresh directory and compares every status, result, post-state and event against the oracle.

```sh
fixture=research/compiler-and-translation/RT-13/ORDERED-ROLLBACK-CROSS-BACKEND-01
scratch=$(mktemp -d)
python "$fixture/run.py" --clang /path/to/clang19 --go /path/to/go1.27.4 \
  --go-cache "$scratch/go-cache" --output "$scratch/evidence.json"
cmp "$fixture/evidence.json" "$scratch/evidence.json"
```

Two complete replays produced identical [evidence ledgers](ORDERED-ROLLBACK-CROSS-BACKEND-01/evidence.json).
