# POSIX for LLMLang: Portable and Native Runtime Architecture

**Status:** Research proposal  
**Date:** 2026-11-17  
**Scope:** Standard system library, operating-system boundary, portable bootstrap implementation, native Linux implementation, and formal verification strategy.

> This document records an architectural proposal for discussion. It does not amend or silently establish normative requirements in `LLMLang-CONCEPT.md` or other project specifications.

## 1. Executive Summary

LLMLang should provide a standard POSIX-oriented system library so that application-level programs can be written before LLMLang has its own complete low-level runtime.

The library should have one public API and one normative semantic contract, with at least two interchangeable implementations:

1. **Portable POSIX Runtime** — an initial implementation backed by existing operating-system facilities and system libraries (typically libc and, where appropriate, other platform libraries).
2. **Native POSIX Runtime** — a progressively developed implementation written in LLMLang and operating directly over the Linux system-call ABI.

These must not become two independent interpretations of POSIX. Both implementations must satisfy the same LLMLang POSIX specification, contracts, error semantics, and observable behavior within an explicitly declared support profile.

The portable implementation enables early application development and bootstraps the ecosystem. The native implementation is a substantial systems-programming project and a proving ground for LLMLang's low-level capabilities and formal-verification architecture.

The intended relationship is:

```
Application programs written in LLMLang
                 |
                 v
       LLMLang POSIX API / contract
                 |
          POSIX Runtime interface
             /          \
            v            v
   Portable Runtime   Native Runtime
   libc / OS libs     LLMLang / Linux ABI
            \            /
             v          v
             Operating system
```

The public API should hide which runtime is selected. Runtime selection should normally happen at build, link, or deployment configuration time, rather than through application-specific branching.

## 2. Why Provide POSIX as a Standard Library

POSIX is a practical compatibility boundary between application programs and operating systems. It exposes widely understood abstractions such as file descriptors, files, processes, threads, synchronization, signals, and standard I/O.

Providing a POSIX-oriented standard library has several strategic benefits:

- **Application development can start early.** LLMLang programs do not need to wait for a complete native system library.
- **The language can be tested on realistic workloads.** Applications exercise the type system, effects, ownership/resource model, error handling, concurrency, compiler, and runtime.
- **The standard library becomes a meaningful systems-programming test.** Implementing substantial POSIX behavior is a stronger demonstration of LLMLang's capabilities than isolated examples.
- **The ecosystem can evolve incrementally.** Portable implementations can be replaced operation by operation as native implementations mature.
- **The OS boundary becomes explicit.** Effects, capabilities, resource lifetimes, and environmental assumptions can be represented in LLMLang contracts rather than hidden in ad hoc foreign-function calls.

POSIX should be treated as a standard compatibility library and one OS-facing abstraction, not as the semantic foundation of the LLMLang language itself.

## 3. One Contract, Multiple Implementations

### 3.1 Normative POSIX Specification

The central architectural rule is that there must be one LLMLang-level specification for each exposed operation and abstraction.

The specification should define, as applicable:

- public types, constants, and valid value domains;
- preconditions and postconditions;
- state transitions and invariants;
- externally observable behavior;
- resource ownership and lifetime rules;
- effects and required capabilities;
- success and failure outcomes;
- error codes and error-state behavior;
- blocking, interruption, and partial-completion behavior;
- concurrency and synchronization semantics;
- environmental assumptions and explicitly unsupported cases.

The specification should identify the POSIX edition and the precise supported profile or subset. "POSIX-compatible" without a declared scope is too vague to be a useful compatibility claim. Where LLMLang intentionally strengthens, restricts, or safely wraps a POSIX interface, the difference must be explicit and must not be presented as unmodified POSIX behavior.

The POSIX specification is the source of truth for both runtimes, generated tests, and formal models.

### 3.2 Portable POSIX Runtime

The initial runtime should adapt existing platform facilities. On Unix-like systems this will usually mean libc and other established system libraries.

Its purpose is to provide a usable implementation quickly, not to duplicate the operating system's implementation in LLMLang.

The portable runtime should:

- implement the common LLMLang POSIX API;
- translate platform types, return conventions, and errors into the LLMLang contract;
- isolate foreign-function interfaces and platform-specific details;
- declare the host platform and feature profile it supports;
- be replaceable without changing application code;
- provide a reference implementation for application development and differential testing.

"Portable" does not mean every POSIX function is available identically on every host. Availability and semantic differences must be surfaced through capability/profile declarations and checked during build or configuration.

### 3.3 Native POSIX Runtime

The second runtime should be written in LLMLang and implement the same public contracts using the Linux system-call ABI.

Its purpose is both practical and strategic:

- reduce dependence on libc for the covered functionality;
- exercise LLMLang's ability to implement low-level system infrastructure;
- provide a target for formal specification and progressive proof;
- clarify the boundary between LLMLang semantics and kernel-provided behavior;
- create a foundation for a more self-hosted runtime.

The native runtime should be introduced incrementally. It is not necessary or desirable to implement all of POSIX before it can be useful.

### 3.4 Why These Are Not Two Independent POSIX Implementations

If the two runtimes have separate specifications, they will eventually drift. Applications could then behave differently depending on which runtime is selected, and tests or proofs for one implementation would not establish anything about the other.

Instead:

- the public API is shared;
- the semantic contract is shared;
- platform adapters are implementation details;
- implementation-specific limitations are declared;
- the same conformance suite is run against both;
- formal claims are attached to a particular implementation and its assumptions.

The implementations may use very different internal algorithms while preserving the same externally observable contract.

## 4. Three Architectural Layers

The design should separate three layers.

### Layer 1 — POSIX Specification

Defines the LLMLang-facing API and its normative semantics:

- types and interfaces;
- contracts and invariants;
- errors and failure behavior;
- resource and state models;
- concurrency and effects;
- supported POSIX profile and documented deviations.

This layer must not depend on a particular backend's implementation details.

### Layer 2 — POSIX Runtime

Contains interchangeable implementations of the specification:

- Portable Runtime over libc and platform libraries;
- Native Runtime in LLMLang over the Linux syscall ABI;
- future runtimes for other operating systems where feasible.

Each runtime declares which specification items and profiles it implements, and what evidence supports that claim.

### Layer 3 — Operating-System Interface

Contains the actual boundary to the host:

- foreign-function calls into system libraries;
- system-call ABI transitions;
- architecture-specific calling conventions and low-level code;
- kernel-visible resources and state;
- OS-specific mechanisms required to implement higher-level POSIX behavior.

The distinction prevents application code from depending directly on Linux-specific syscall details and prevents the POSIX contract from being defined accidentally by one backend.

## 5. POSIX API Is Not the Linux Syscall ABI

A direct one-to-one mapping from POSIX functions to Linux system calls is not a sufficient implementation strategy.

For example:

- `open()` may be implemented using `openat()`, with flags, path resolution, errors, and semantics reconciled at the API boundary.
- `read()` must preserve partial-read, EOF, interruption, and error semantics.
- `pthread` abstractions generally require runtime logic and may involve multiple kernel facilities; they are not one syscall per API function.
- `stdio` includes buffering and stream state above the raw file-descriptor interface.
- `errno` and the system-call return convention must be translated correctly.
- `fork()` has process-state semantics that cannot be reduced to merely invoking a syscall wrapper.
- signals, thread cancellation, process lifecycle, and synchronization require higher-level runtime behavior.

Therefore, the Native Runtime must implement POSIX semantics, not merely rename Linux syscalls.

The Linux syscall ABI is an implementation boundary. It is not the specification of the LLMLang POSIX library.

## 6. Bootstrapping and Incremental Replacement

The portable runtime should be implemented first to unblock application development.

The intended development loop is:

1. Define a POSIX API operation and its LLMLang contract.
2. Implement it in the Portable Runtime using existing host facilities.
3. Write application programs against the common API.
4. Add the corresponding Native Runtime implementation in LLMLang.
5. Run the shared conformance tests against both implementations.
6. Add differential tests where equivalent initial conditions and observations can be established.
7. Develop formal models and proofs for the operation and its implementation.
8. Promote the native implementation only when its support and evidence status meet the project's acceptance criteria.

This permits a mixed maturity state: some operations may have a portable implementation only, others may have both, and some native operations may be formally verified while others are merely tested.

The application-facing API should not change merely because an operation moves from the portable to the native runtime.

Runtime choice may be controlled by target configuration, link-time selection, or an explicit runtime profile. The exact mechanism remains a language/toolchain design question.

## 7. Formal Verification Strategy

The Native Runtime should be treated as a major formal-verification target, not merely as a hand-written replacement for libc.

The existing LLMLang principle of one canonical semantic description should apply:

- operation semantics are represented once in LLMLang's canonical semantic model;
- executable implementations and formal models are derived from or explicitly related to that model;
- proofs are tied to exact source/semantic hashes, tool versions, backend versions, and assumptions;
- changes invalidate dependent evidence;
- no LLM-generated assertion is accepted as proof without independent checking.

### 7.1 Operation-Level Proof Obligations

For each operation, distinguish at least:

1. **Contract correctness:** the intended POSIX-facing behavior is specified precisely.
2. **Algorithm correctness:** the LLMLang implementation satisfies that contract under stated assumptions.
3. **Syscall-boundary correctness:** the low-level ABI adapter passes arguments, interprets results, and handles errors correctly.
4. **Translation correctness:** generated machine code preserves the LLMLang implementation's semantics.
5. **Composition correctness:** callers may rely on the operation's contract only to the extent that the implementation evidence or explicit assumptions justify it.

For example, proving `read()` requires more than proving that bytes are copied. The model must account for the applicable cases such as EOF, partial reads, interruption, errors, file-descriptor state, and relevant environmental behavior.

### 7.2 Verification Levels

The following levels are a proposed way to report the scope of evidence. They are not a claim that all levels are already implementable.

| Level | Claim being checked |
|---|---|
| L1 | The operation's algorithm satisfies its POSIX-facing LLMLang contract. |
| L2 | The syscall/OS adapter correctly implements the declared low-level boundary under explicit ABI and kernel assumptions. |
| L3 | Compilation or translation preserves the relevant LLMLang semantics. |
| L4 | Composition of multiple system-library operations preserves their contracts and state invariants. |
| L5 | An application-level property follows from the application contracts and the system-library guarantees it uses. |

A proof at one level does not automatically establish the higher levels. In particular, proving an algorithm does not prove the correctness of the compiler, syscall ABI, Linux kernel, hardware, or all environmental assumptions.

### 7.3 Trusted Computing Base and Guarantee Boundaries

The project must explicitly identify the Trusted Computing Base (TCB) for each claim.

Potential trusted or assumed components include:

- Linux kernel behavior and the system-call ABI;
- CPU architecture and privilege-transition behavior;
- small architecture-specific syscall stubs;
- compiler and code generator components not yet verified;
- proof checker and formalization infrastructure;
- external system libraries used by the Portable Runtime;
- filesystem, device, scheduler, and other environmental behavior.

The long-term goal should be to minimize and progressively verify the TCB, not to pretend it can be eliminated immediately.

A proof of Native Runtime code can establish a conditional guarantee relative to the kernel and ABI assumptions. It does not prove that the kernel itself is correct.

A concrete proposed application-level example is [CF-008 — Linux pipe transfer](../../formal-verification/CONTRACT-FORMALIZATION-CORPUS/cases/CF-008-linux-pipe-transfer.md). It derives exact ordered transfer and failure-suffix guarantees from scoped blocking byte-stream read/write assumptions and explicit ABI, memory and environment correspondence. Safety does not imply termination or delivery to the peer. This is an analytical example, not new runtime conformance evidence.

### 7.4 Evidence Must Be Distinguished

For each function and property, report evidence precisely. At minimum, distinguish:

- **POSIX-compatible** — claimed to satisfy a declared POSIX profile;
- **POSIX-tested** — passed a declared test suite;
- **POSIX-verified** — conformance to the stated contract has been formally established within declared assumptions and proof boundaries.

These labels are not interchangeable. Testing, fuzzing, runtime monitoring, and finite-state exploration are valuable evidence but are not universal mathematical proofs.

A function may be tested but not verified. A verified algorithm may still depend on an unverified syscall boundary. These distinctions must remain visible to consumers and in composed proof results.

## 8. Conformance Testing and Differential Testing

Formal verification and testing should reinforce each other.

### 8.1 Shared Conformance Suite

Both runtimes should run the same tests derived from the shared specification. Tests should cover:

- normal behavior;
- boundary values;
- invalid arguments;
- error conditions;
- partial completion;
- resource lifecycle;
- state transitions;
- concurrency and ordering where relevant;
- platform/profile-specific behavior.

One test may cover multiple related contract properties, but traceability must identify which properties it checks.

### 8.2 Differential Testing

Where both runtimes can be placed in equivalent initial conditions, run equivalent operation sequences and compare their observable behavior.

The comparison should include more than return values where relevant:

- output values and bytes;
- error outcomes;
- resulting resource and process state;
- externally observable side effects;
- ordering and concurrency properties within the test's defined model.

Differential testing can expose implementation drift, but it is not a substitute for a proof. It also requires care: host environments may differ, and not every operation admits a deterministic comparison without controlled fixtures.

### 8.3 Fail-Closed Evidence

A missing test, unsupported behavior, inconclusive proof, or unmodeled environmental dependency must not be interpreted as success.

Evidence should be versioned and bound to the exact contract, implementation, configuration, and relevant dependencies.

## 9. Suggested Implementation Scope and Order

The following is a pragmatic sequence, not a claim about the normative ordering or mandatory structure of POSIX.

### Stage 1 — POSIX Core

Start with foundational interfaces such as:

- fundamental types and constants;
- error representation and error mapping;
- file descriptors;
- `open`, `close`, `read`, `write`, `lseek`;
- basic file metadata operations such as `stat`.

This provides enough functionality for useful file-oriented applications and establishes the resource and error models.

### Stage 2 — Memory and Process

Investigate and incrementally implement:

- memory allocation and mapping, including `mmap` where appropriate;
- process creation and lifecycle;
- `fork`, `exec`, and `wait`;
- process identifiers and relevant process state.

These features have complex semantics and should not be treated as trivial syscall wrappers.

### Stage 3 — Concurrency

Implement and verify the necessary parts of:

- threads;
- mutexes;
- condition variables;
- atomic operations;
- synchronization and memory-ordering constraints.

The exact boundary between POSIX thread abstractions, LLMLang's own concurrency model, and kernel mechanisms requires explicit design.

### Stage 4 — Advanced I/O and IPC

Consider:

- pipes;
- sockets;
- signals;
- `select`/`poll`;
- additional IPC facilities.

These features should be added according to application needs and the declared POSIX profile.

### Stage 5 — Higher-Level Libraries

Add higher-level facilities such as:

- `stdio`;
- buffered streams;
- higher-level filesystem operations;
- additional POSIX library interfaces.

These should build on the lower-level contracts where appropriate, without assuming that every higher-level function is a direct syscall wrapper.

### Stage 6 — Shell and Utilities

Treat POSIX Shell and Utilities as a distinct, substantial scope. It is not necessary to implement the shell and utility ecosystem before LLMLang can support application-level programs.

## 10. Portability Beyond Linux

Linux is the proposed first target for the Native Runtime because the direct syscall ABI provides a concrete low-level implementation target.

The architecture should not make Linux syscall semantics part of the public POSIX contract.

Future implementations may include native runtimes for other operating systems, such as FreeBSD, if justified by project goals and resources. They should implement the same LLMLang-facing specification, while declaring platform-specific support and limitations.

This is another reason to keep the POSIX Specification, Runtime, and OS Interface layers separate.

## 11. Relationship to the Existing LLMLang Architecture

The proposal should reuse, rather than bypass, existing LLMLang architectural principles:

- **Semantic Program Graph:** API operations, contracts, effects, resources, and implementations should be typed semantic entities.
- **Specification / Design / Implementation layers:** public behavior should remain distinguishable from internal runtime design and concrete implementation.
- **Canonical semantics:** formal models and executable implementations must be connected to one semantic source; independently maintained duplicate algorithms are not the default.
- **Content addressing:** contracts, implementations, generated artifacts, tests, and proofs should be bound to exact content hashes and typed dependencies.
- **Dependency-driven invalidation:** changing an operation's contract or implementation should invalidate only the evidence that depends on the changed semantic content.
- **Explicit effects and capabilities:** filesystem, process, memory, signal, and network access should be visible in contracts and required capabilities.
- **Independent validation:** generated code, tests, and proof artifacts must be checked by tools independent of the LLM that proposed them.

A caller should not be described as unconditionally verified merely because it relies on a verified contract if the actual callee implementation has not been shown to satisfy that contract. Such a caller proof is conditional and must preserve the assumption. This is especially important for system-library operations because their behavior affects large portions of the application call graph.

## 12. Proposed Acceptance Criteria

The architecture should be considered established only when the following can be demonstrated for a declared initial profile:

1. An application can call the LLMLang POSIX API without depending on a particular runtime implementation.
2. The Portable Runtime implements the declared subset and runs on at least one supported host configuration.
3. The Native Runtime implements at least one useful vertical slice in LLMLang over the Linux syscall ABI.
4. Both runtimes are checked against the same operation contracts and shared conformance tests.
5. The build/runtime selection mechanism does not require application source changes.
6. Platform-specific behavior and unsupported features are explicitly declared.
7. At least one operation has a formal model tied to its canonical LLMLang semantics.
8. The project can state exactly which parts of the operation implementation and syscall boundary are proven, tested, assumed, or unverified.
9. Differential testing can compare the two implementations for a suitable deterministic subset.
10. Changes to hash-relevant contracts or implementations invalidate dependent tests/proofs and preserve unaffected evidence where safe.

These criteria are staged: they do not require full POSIX coverage or a fully verified runtime before the first useful release.

## 13. Open Design Questions

The following questions remain unresolved and should be answered through subsequent design work:

1. Which exact POSIX edition and initial functional profile should LLMLang target?
2. Should the LLMLang API expose the POSIX surface as directly as possible, or provide a safer typed façade that makes ownership, errors, and capabilities explicit while preserving a documented mapping to POSIX?
3. Which functions belong in the initial portable bootstrap profile?
4. What is the minimum Native Runtime vertical slice that exercises the compiler, resource model, error handling, and syscall ABI?
5. How should runtime selection be represented in package manifests, target configuration, and dependency hashes?
6. Which Linux architectures should be supported first, and how should architecture-specific syscall stubs be isolated?
7. How should LLMLang's concurrency and memory models relate to POSIX threads and the Linux kernel's memory-ordering guarantees?
8. Which parts of the runtime should be implemented in LLMLang immediately, and which tiny low-level pieces may initially remain trusted assembly or compiler intrinsics?
9. What formal models are appropriate for blocking I/O, signals, scheduling, and other environment-dependent behavior?
10. How should conformance claims be scoped when POSIX permits implementation-defined or optional behavior?

## 14. Recommendation

Adopt the two-runtime, one-contract architecture as the preferred direction for LLMLang's standard system library:

- build a Portable POSIX Runtime first to enable application development;
- develop a Native POSIX Runtime in LLMLang over the Linux syscall ABI in parallel and incrementally;
- keep one normative LLMLang-facing POSIX specification;
- test both implementations against shared contracts and conformance tests;
- use differential testing to discover mismatches;
- formally verify the native implementation progressively;
- publish explicit evidence and trust boundaries rather than making blanket claims of verification;
- preserve the possibility of additional OS runtimes.

The Native POSIX Runtime should be treated as one of the first substantial real-world systems projects for validating LLMLang's ability to produce useful, low-level, formally verifiable software.

The portable implementation should not be postponed until that work is complete. Its role is to let application development and language validation proceed immediately, while the native implementation matures.


## RT-04 type/effect/ownership dependency

The API contract requirements above are inputs to the comparative [RT-04 type/effect/ownership/capability research](../../language-design/RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md). In particular, POSIX resource lifetimes, partial completion, interruption, error outcomes, capabilities, and concurrency/memory ordering are scenario sources for that study. Neither this runtime proposal nor RT-04 selects the final LLMLang type or ownership model.

## Explicit assumptions and conditional verification (RT-36; proposed)

Model OS/kernel/runtime and syscall guarantees as explicitly scoped premises when unproved, separate foundational TCB from contingent environment assumptions, pin target and profile, and propagate only justified property dependencies. Runtime conformance observations cannot discharge universal premises. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](../../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This is a candidate follow-up, not an adopted rule or new experimental result.
