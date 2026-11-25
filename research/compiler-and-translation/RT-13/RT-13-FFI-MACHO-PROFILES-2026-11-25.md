# Mach-O cross-build profiles for macOS and iOS

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

The experiment separately cross-builds a C ABI provider and consumer for macOS ARM64, macOS x86-64 and iOS ARM64 from Linux. Each profile builds a static archive, a provider dylib and two consumer dylibs. One consumer includes the static provider. The other has one load-time dependency with a relative install name. The runner audits Mach-O CPU type, deployment platform and minimum, SDK load-command field, export trie, dylib load commands, runtime search path and chained fixups.

The fixed 16-byte by-value record lowers as two scalar registers on macOS x86-64. Both ARM64 profiles use a pair-shaped aggregate carrier. The static consumers have no provider dylib dependency. The dynamic consumers have exactly one dependency on `@rpath/libspan.dylib`, with `@loader_path` in the runtime search path. The source code is freestanding and uses no Apple SDK. The SDK field in the load command is explicitly set by the linker.

| Provider mismatch | Observed linker and package results |
| --- | --- |
| ARM64 macOS with ARM64 iOS, in both directions | The linker refuses both platform mismatches. |
| macOS x86-64 consumer with macOS ARM64 dylib | The observed linker accepts without a warning and records the same dependency name in the x86-64 client. The package check refuses the provider CPU. |
| Matching CPU and platform, higher minimum OS | All three links succeed with warnings. The package check refuses each provider whose minimum exceeds the intended deployment baseline. |

The package check independently verifies the exact dependency artifact's architecture, platform, install name and deployment version. Successful linkage and a matching dependency name leave further evidence needed about the selected binary and runtime. The fixture records hashes for each admitted and higher-minimum provider.

Clang and LLD are LLVM 19.1.7. The fixed macOS minimum is 13.0 and the fixed iOS minimum is 16.0. Deterministic archives and binary load commands reproduce in two fresh Linux roots. The research covers cross-build artifact correspondence. Native loading, platform SDK closure, system library imports, deployment frameworks, signing policy and Apple runtime behavior remain open.

## Replay

Use CPython 3.12.14 and LLVM 19.1.7 Clang, ld64.lld, llvm-ar and llvm-objdump.

```sh
fixture=research/compiler-and-translation/RT-13/FFI-MACHO-PROFILES-01
python "$fixture/run.py" --clang /path/to/clang19 --output /tmp/rt13-ffi-macho.json
cmp "$fixture/evidence.json" /tmp/rt13-ffi-macho.json
```

The [ledger](FFI-MACHO-PROFILES-01/evidence.json) records the observed cross-build cells, exact artifacts and control outcomes.
