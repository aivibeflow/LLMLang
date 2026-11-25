# ADR-019 — Bidirectional native library interoperability

- **Status** — Accepted
- **Accepted** — 2026-11-25
- **Date** — 2026-11-25
- **Decision owners** — LLMLang project
- **Scope** — Importing OS and third-party native libraries and compiling LLMLang libraries for external callers
- **Related work** — [Platform matrix and conformance gates](../../PLAN.md#66-cross-platform-native-interoperability-and-bidirectional-ffi-cross-cutting) · [RT-13 aggregate calling conventions](../../research/compiler-and-translation/RT-13/RT-13-FFI-AGGREGATE-CROSS-ABI-2026-11-25.md)

## Context

LLMLang programs need to call platform APIs exposed by native libraries and reuse existing native code. External programs must also be able to link to or load libraries compiled from LLMLang. An application binary interface (ABI) defines how binaries call one another, including symbol names, calling conventions, and data layout. ABI compatibility and conformance to a behavioral contract require separate checks.

## Decision

1. **Import native libraries.** The Toolchain must resolve imported declarations to symbols in OS or third-party libraries for the selected target. Imported declarations must identify the provider, ABI, and linking mode. Where a symbol version is relevant, include it in the binding. Model foreign behavior through explicit contracts or assumptions. A header supplies declarations and layout information.
2. **Compile and export native libraries.** The Toolchain must compile explicitly exported LLMLang interfaces into artifacts that independently built callers can link to or load. Produce static archives and shared libraries for the modes supported by the target profile, with public declarations such as C headers and the link and runtime requirements needed by consumers. Export only ABI-representable types or provide explicit adapters.
3. **Bind both directions to a target profile.** A profile identifies the OS, architecture, ABI, binary format, and applicable SDK, toolchain, and deployment constraints. Start with the platform C ABI as the common interoperability baseline. Add platform-specific adapters where needed. Publish support per target, direction, and linking mode.
4. **Validate the boundary.** Check the exported or imported symbols, calling convention, sizes, alignment, layouts, and argument and return representations. Make ownership, allocator pairing, lifetimes, error handling, and callback rules explicit when applicable. Reject unsupported signatures and incompatible target or ABI selections with diagnostics. Define how panics or exceptions are contained or translated at the boundary.
5. **Identify implementations independently of their public names.** Match native calls through the ABI declarations and symbols. Record the exact provider and artifact identity in build and verification evidence. ABI checks establish binary interoperability. Behavioral claims require evidence for the corresponding contract and assumptions.

## Boundaries and consequences

A common C ABI surface lets consumers use their own toolchains. Each artifact targets a declared profile. Support for C++ or managed-runtime ABIs, version-to-version ABI guarantees, and runtime loading on platforms with deployment restrictions require separate validation and decisions. The same-version compatibility guarantee in ADR-023 applies to LLMLang builds. This ADR specifies an explicit foreign binary boundary for the profiles and artifacts tested.

Native adapters may require a runtime or wrapper. Publish those dependencies and their initialization and cleanup requirements. Direct emission and generated adapters remain implementation options. [ADR-023](023-immutable-components-and-toolchain-compatibility.md)

## Validation required before claiming support

- Build a LLMLang program that calls an actual OS-provided library on the declared target and a controlled native library that exercises the supported boundary.
- Independently build a C consumer that calls a compiled LLMLang library. Exercise static and shared variants wherever the profile claims both, including the platform loader for shared artifacts.
- Inspect the exact artifacts and compare observed calls against the declared ABI and contract. Include negative cases for mismatched calling conventions or layouts, missing symbols, and invalid ownership transfers where supported.
- Record the target, SDK, toolchain, artifact identity, and results in the [support and evidence matrix](../../PLAN.md#66-cross-platform-native-interoperability-and-bidirectional-ffi-cross-cutting).
