# LLMLang: LLVM Backend Architecture

**Status:** Research proposal; not a normative LLMLang decision  
**Date:** 2026-11-17  
**Scope:** Using LLVM IR, LLVM bitcode, optimization passes, and target code generation as one possible compilation backend for LLMLang.

> This document records an architectural direction for investigation. It does not make LLVM mandatory, define the canonical LLMLang IR, or establish that LLVM-generated output is formally verified.

## 1. Summary

LLMLang can use LLVM as a code-generation backend while keeping its own semantic model independent of LLVM.

The proposed boundary is:

- LLMLang owns source-language meaning, the Semantic Program Graph (SPG), contracts, types, effects, operation identities, and semantic validation.
- An LLMLang compiler performs semantic analysis and lowers validated program fragments into a representation accepted by a backend.
- An LLVM backend translates a supported subset into LLVM IR.
- LLVM performs target-oriented optimization and machine-code generation.
- LLMLang retains responsibility for describing what was checked and for not overstating the correctness of generated artifacts.

LLVM IR should be treated as a backend-facing intermediate representation, not as the canonical semantic representation of LLMLang.

## 2. Terminology

The word *bytecode* is sometimes used informally for LLVM bitcode, but the distinctions matter:

| Artifact | Meaning |
|---|---|
| LLMLang SPG | Canonical semantic program representation |
| LLMLang normalized/lowered IR | Optional LLMLang-controlled representation prepared for code generation |
| LLVM IR | Typed, target-independent (within LLVM's model) compiler IR |
| LLVM bitcode | Serialized bitcode representation of LLVM IR |
| Object code | Target-specific relocatable machine code |
| Executable | Linked output for a target platform |
| JIT code | Machine code generated for execution at runtime |

LLVM bitcode is not a language-independent virtual-machine bytecode with a stable execution semantics. It is a serialized form of LLVM IR intended for LLVM toolchain processing. LLVM IR itself has its own defined semantics and version/toolchain compatibility considerations.

## 3. Proposed compilation pipeline

```text
LLMLang source / structured graph mutations
                  |
                  v
        Semantic Program Graph
                  |
                  v
   LLMLang semantic analysis and validation
                  |
                  v
   Canonicalization / optional normalized LLMLang IR
                  |
                  v
        Target capability analysis
                  |
                  v
       LLVM-specific lowering
                  |
                  v
               LLVM IR
                  |
                  v
       LLVM optimization pipeline
                  |
                  v
       LLVM target code generator
                  |
          +-------+--------+
          |                |
          v                v
      Object code      JIT machine code
          |
          v
   Link / package / executable
```

A separate interpreter, reference evaluator, or alternative backend may consume the same canonical semantic model. LLVM is therefore replaceable and is not a prerequisite for defining LLMLang semantics.

## 4. Responsibilities and trust boundary

### 4.1 LLMLang responsibilities

Before LLVM lowering, LLMLang should establish all properties that belong to LLMLang semantics, including as applicable:

- type correctness and refinement constraints;
- contract well-formedness and applicable preconditions;
- evaluation order and observable effects;
- integer overflow, division, and conversion semantics;
- ownership, lifetime, and resource rules;
- concurrency and memory-ordering requirements;
- error and cancellation behavior;
- capability and target requirements.

The lowering must preserve these properties or reject the translation, or report a precisely scoped restriction. It must not silently weaken a contract to fit LLVM.

### 4.2 LLVM responsibilities

LLVM may provide:

- instruction selection and target-specific lowering;
- register allocation;
- target-specific instruction scheduling and machine code generation;
- optimization passes;
- object-file emission;
- JIT compilation infrastructure.

These capabilities make LLVM a strong implementation backend, but they do not transfer ownership of LLMLang's language semantics to LLVM.

### 4.3 Verification boundary

Successful LLVM verification, optimization, compilation, or object emission does not prove that the generated program satisfies its LLMLang contract.

Evidence should distinguish at least:

1. LLMLang semantic validation before lowering;
2. validity of generated LLVM IR under the selected LLVM version;
3. correctness of the LLMLang-to-LLVM lowering;
4. behavior of LLVM optimization and target code generation;
5. correctness of linking, runtime support, and platform assumptions;
6. end-to-end conformance of the executable to the source contract.

Any formal claim must identify the exact source semantic hashes, generated IR hashes, LLVM version and configuration, target triple/data layout, runtime dependencies, assumptions, and proof/test scope.

## 5. LLVM semantic hazards

LLVM IR is not a neutral container for arbitrary source-language operations. Its semantics include concepts and optimization assumptions that may differ from LLMLang's eventual semantics.

Particular care is required for:

- `undef`, `poison`, and `freeze`;
- `inbounds` pointer arithmetic;
- `nsw` and `nuw` integer flags;
- fast-math flags and floating-point contraction;
- pointer provenance, aliasing, and memory access rules;
- atomic operations and memory ordering;
- lifetime and alignment assumptions;
- undefined behavior and optimizer assumptions.

A backend must not emit stronger LLVM promises than the LLMLang source semantics justify. For example, an overflow flag must not be added merely because it enables optimization if LLMLang semantics permit that overflow. Likewise, fast-math assumptions must not be introduced unless the source contract explicitly permits the corresponding numerical relaxation.

The mapping should be conservative: if the LLVM construct's preconditions cannot be established, use a safer lowering or reject that optimization.

## 6. Target and runtime model

LLVM's target machinery can generate code for multiple architectures, but each generated artifact remains tied to a concrete target configuration.

The backend should explicitly track relevant values such as:

- target triple;
- CPU and feature set;
- data layout;
- ABI and calling convention;
- object format and relocation model;
- code model;
- relevant LLVM version and backend configuration;
- LLMLang runtime/support-library identity.

These values should be included in implementation/build provenance and in hashes wherever they affect artifact interpretation or behavior. They should not be indiscriminately added to the semantic identity of the source operation.

LLVM does not by itself supply the complete operating-system runtime or guarantee POSIX behavior. LLMLang runtime libraries, system interfaces, linking, and deployment remain separate concerns.

## 7. Multiple backends

The architecture should permit LLVM to coexist with other execution and compilation paths:

- an interpreter/reference evaluator for development and semantic comparison;
- an LLVM backend for optimized native code;
- a direct native backend if a use case requires control beyond LLVM's abstractions;
- a WebAssembly backend, whether implemented through LLVM or another toolchain;
- future target-specific backends.

All backends must implement the same LLMLang semantic source of truth. Differential tests can compare their observable behavior, but agreement between backends is evidence rather than a proof unless the test space and assumptions justify that claim.

## 8. Proposed initial strategy

A cautious implementation sequence would be:

1. Define a small, explicit LLMLang executable semantic subset.
2. Implement a reference evaluator or interpreter for that subset.
3. Define the lowering contract from LLMLang semantics to LLVM IR.
4. Implement a minimal LLVM backend without aggressive optimization.
5. Validate generated IR and compile/run a small set of examples.
6. Compare executable behavior against the reference evaluator using shared scenarios.
7. Add optimization passes incrementally, with regression and differential tests.
8. Record exact toolchain, target, runtime, and evidence metadata for every build artifact.

The initial subset should avoid relying on LLVM features whose semantic correspondence has not yet been specified.

## 9. Open design questions

The following issues remain unresolved and are tracked in the project TODO register:

- Is LLVM the first native backend, one of several equal backends, or merely an optional implementation?
- What is the canonical boundary between SPG, normalized LLMLang IR, and LLVM IR?
- Which LLVM version and compatibility policy should be supported?
- Which LLVM IR constructs are permitted in the initial backend profile?
- How are poison/undefined behavior, overflow, floating-point modes, pointer provenance, and concurrency mapped?
- Which optimization passes are allowed under each LLMLang semantic profile?
- What evidence is required to trust lowering, optimization, and code generation?
- Which targets and runtime combinations form the initial support matrix?

## 10. Current conclusion

LLVM appears to be a practical candidate for native code generation and optimization. The recommended architectural constraint is to keep LLVM behind a replaceable backend boundary and preserve LLMLang's own canonical semantics.

This is a research recommendation only. It does not yet select LLVM as a mandatory backend or settle the compiler IR architecture.
