# Versioned public C export with six independent consumers

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

The fixture generates a C header, implementation source and ELF version map from a restricted public declaration. Its contract adds seven to an unsigned 64-bit value when enabled, passes the value through when disabled, and returns an explicit overflow status while preserving the caller's initialized output slot. Interface version, source contract digest, ABI descriptor, provider bytes and scope of each observation are recorded separately.

The runner builds a static archive and a shared library exporting `checked_add@@LLM_CHECKED_1`. Independent C and C++ clients cover both archive and shared linking. Rust and Go cgo use shared linking. CPython `ctypes` and Java 21's preview Foreign Function and Memory API use an exact library path. The six language clients use independent argument and output-slot representations and compare unsigned output bits on the same 72 inputs.

| Provider revision | Evidence |
| --- | --- |
| Baseline range-check implementation | All eight consumer routes match. |
| Compatible implementation using compiler overflow detection | All six shared routes match. The ABI and trace are unchanged and the provider ELF identity changes. |
| Same ABI and versioned symbol, addition changed from seven to eight | The 33 changed rows per language reject compatibility. |
| Same exported symbol, output pointee narrowed from 64 to 32 bits | Generated ABI metadata differs. A native compiler check refuses the original client and the fixture withholds calls. |

All 1,008 preserving native and hosted foreign-call observations agree. The behavior control adds 432 comparisons, with 198 divergences. The dynamically loaded paths are independently observed in glibc loader diagnostics, and the checked trace receipt binds the exact selected artifact and consumer profile. Even the compatible revision requires a fresh receipt because the ELF changed. The candidate witness uses an exact local manifest. It leaves signature trust, dynamic dual-version policy, other native platforms and general source export open.

The replay pins Linux x86-64 SysV LP64, GCC/G++ 14.2.0, Go 1.27.4, Rust 1.85.1, CPython 3.12.14 and OpenJDK 21.0.13. Java requires the preview API and native-access flag for this profile. Go uses cgo in a local module with dependency downloads disabled.

## Replay

```sh
fixture=research/compiler-and-translation/RT-13/FFI-SIX-LANGUAGE-EXPORT-01
scratch=$(mktemp -d)
python "$fixture/run.py" --go /path/to/go1.27.4 --go-cache "$scratch/go-cache" \
  --output "$scratch/evidence.json"
cmp "$fixture/evidence.json" "$scratch/evidence.json"
```

Two complete replays produced identical [evidence ledgers](FFI-SIX-LANGUAGE-EXPORT-01/evidence.json).
