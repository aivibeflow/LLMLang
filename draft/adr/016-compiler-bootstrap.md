# ADR-016 — Bootstrap the LLMLang compiler from source

- **Status** — Accepted
- **Accepted** — 2026-11-25
- **Date** — 2026-11-20
- **Decision owners** — LLMLang project
- **Related research** — [RT-21 — Self-Development, Bootstrap, and Migration Roadmap](../../research/toolchain-and-collaboration/RT-21/RT-21-LLMLANG-SELF-DEVELOPMENT-AND-BOOTSTRAP-ROADMAP.md)

## Context

A clean machine needs a way to build the compiler written in LLMLang without an installed LLMLang compiler. RT-21 proposes a small compiler and runtime built with an existing toolchain. It leaves the implementation language and the initial LLMLang subset open.

The bootstrap compiler needs a front end that validates a versioned subset of LLMLang and a backend that preserves its semantics. The language used to implement the bootstrap compiler and the format it emits are independent choices. Using the same language for both can reduce the toolchains needed for a clean build. LLVM IR is an output format and requires a host language for the front end.

## Decision

Prototype a small bootstrap compiler written in Rust that emits Rust source from a validated LLMLang representation. Build the bootstrap compiler with `cargo`, then use the same pinned Rust toolchain and the declared platform linker to compile the generated source. Keep the runtime support small and specify its observable behavior alongside the bootstrap profile. The profile should cover the LLMLang features used to implement the compiler and report unsupported constructs before code generation.

The clean-machine build proceeds in three stages:

1. **Stage 0** — Build the Rust bootstrap compiler from the checkout using the declared host tools and pinned dependencies. Provide a documented build command that can run without fetching dependencies once the declared inputs have been prepared.
2. **Stage 1** — Use stage 0 to translate the LLMLang compiler sources to Rust. Build the generated Rust and runtime to obtain the first compiler implemented in LLMLang.
3. **Stage 2** — Use stage 1 to build the same LLMLang compiler sources again. Compare stage 1 and stage 2 on the bootstrap conformance suite. Compile those sources with both compilers and compare the Rust they emit under identical inputs.

The initial self-hosted compiler also emits Rust, so `rustc` remains part of the build chain. Once the same-revision rebuild is verified, building a later compiler revision requires the new sources to stay within the preceding compiler's supported profile or to provide an explicit intermediate revision. The production backend and supported host platforms remain open decisions.

## Alternatives considered

| Candidate | Role in bootstrap | Benefits | Main costs |
| --- | --- | --- | --- |
| C | Host implementation, generated source, or both | Broad availability of compilers. Generated C can represent explicit layouts, control flow, and a small runtime interface. | The compiler and runtime must manage memory and keep generated code clear of undefined behavior, including overflow, alignment, and aliasing hazards. |
| C++ | Host implementation, generated source, or both | Standard containers and RAII help implement the front end and runtime. Native toolchains provide code generation and linking. | Generated code must account for C++ object lifetimes, implicit conversions, and exception behavior. ABI and standard-library choices add build inputs where they affect the runtime boundary. |
| Rust | Host implementation, generated source, or both | A single Rust toolchain can build the front end and generated program. Rust makes memory-safe implementation practical for much of the initial toolchain. | Code generation must express LLMLang ownership and aliasing correctly under Rust's borrow checker. Incompatible semantics may require explicit representations or runtime helpers. |
| Go | Host implementation, generated source, or both | Go's standard library, garbage collector, and build tools support a compact bootstrap front end and can simplify generation for a managed subset. | Generated Go carries the Go runtime. Resource cleanup, pointer behavior, and any explicit layout requirements need careful translation. |
| LLVM IR | Generated IR with a front end implemented in a host language | Existing LLVM tools provide optimization and native code generation. Explicit control over layout and calling conventions can help if the bootstrap profile needs low-level features. | The project must implement lowering for representation, control flow, ABI, and runtime calls. The build must pin a compatible LLVM toolchain, and generated IR must respect LLVM's rules for undefined behavior. |

Rust is the first prototype because one toolchain can build the bootstrap executable and compile the generated Rust. Test C as the next output target if ownership constraints make generated Rust require substantial compiler-specific workarounds. Revisit LLVM IR if the required layout or calling conventions are costly to express through a source backend.

## Consequences

- A source checkout and the declared build inputs are sufficient to start the chain. The bootstrap compiler and generated artifacts can be inspected independently.
- The bootstrap compiler still implements the LLMLang semantics for the supported subset. The Rust compiler verifies the generated Rust according to Rust's own rules. LLMLang conformance tests verify that translation preserves the specified behavior.
- The Rust toolchain, linker, bootstrap source, dependencies, and runtime are part of the bootstrap trust boundary. Rebuilding to a fixed point checks consistency within that chain.
- Changes to the bootstrap profile, runtime, or host toolchain require repeating the clean-machine build and conformance checks.

## Implementation validation

1. Document the supported LLMLang input form, language subset, runtime operations, host tools, and dependency versions. Demonstrate that the compiler sources fit the declared profile.
2. Run the full chain in clean CI with no LLMLang executable or cached build outputs. Once the declared inputs are available, run the build without network access.
3. Run the same positive and negative conformance cases through stage 0 and the self-hosted compiler. Cover observable behavior at the translation boundary, including integer overflow, aliasing and mutation, error handling, and resource lifetime where these features are part of the profile.
4. Verify that stage 1 and stage 2 emit identical Rust source for the same compiler inputs and target, with toolchain, flags, and environment fixed. Run the same compiler tests on both executables. Define any native binary reproducibility requirement separately, with its full build inputs documented.
