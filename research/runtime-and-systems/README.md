# Runtime, resources, embedded and operating systems

[Research index](../README.md) · [Research taxonomy](../research-management/RESEARCH-TAXONOMY.md) · [Dependency map](../research-management/RESEARCH-DEPENDENCY-MAP.md)

This direction groups related research studies without changing their RT identifiers, research status, or accepted decisions.

## Browse by topic

- [Execution and POSIX](execution-and-posix/README.md) · RT-10
- [Memory and resource accounting](memory-and-resource-accounting/README.md) · RT-25, RT-26
- [Embedded systems and operating-system kernels](embedded-and-kernels/README.md) · RT-37, RT-38

## Studies

| ID | Scope |
|---|---|
| [RT-10](RT-10/) | Runtime and execution model |
| [RT-25](RT-25/) | Runtime memory allocators and allocation strategy |
| [RT-26](RT-26/) | Hierarchical resource accounting and real-time enforcement |
| [RT-37](RT-37/) | Freestanding, embedded and real-time firmware |
| [RT-38](RT-38/) | Operating-system kernels and verified microkernel feasibility |

## Recent bounded rechecks

- [RT-37 Cortex-M3 NVIC pending clear](RT-37/RT-37-CORTEX-M3-NVIC-PENDING-CLEAR-2026-11-25.md) checks exact write-one-to-clear and read-modify-write effects.
- [RT-37 Cortex-M3 nested exception stack](RT-37/RT-37-CORTEX-M3-NESTED-EXCEPTION-STACK-2026-11-25.md) compares priority, masking and observed frame displacement.
- [RT-37 Cortex-M3 startup RAM retention](RT-37/RT-37-CORTEX-M3-STARTUP-RETENTION-2026-11-25.md) checks exact copy and clear intervals during software re-entry.
- [RT-10 POSIX read continuation proof](RT-10/RT-10-POSIX-READ-CONTINUATION-PROOF-2026-11-25.md) checks abstract prefix conservation and audits concrete premises.
- [RT-10 POSIX umask context](RT-10/RT-10-POSIX-UMASK-CONTEXT-2026-11-25.md) compares temporary ambient masks with scoped creation modes.
- [RT-10 libc error carriers](RT-10/RT-10-LIBC-ERROR-CARRIERS-2026-11-25.md) compares return-carried errors and scoped errno capture.
- [RT-10 Linux syscall architectures](RT-10/RT-10-LINUX-SYSCALL-ARCHITECTURES-2026-11-25.md) compares freestanding adapters on native x86-64 and emulated AArch64.
- [RT-10 POSIX startup and file I/O slice](RT-10/RT-10-POSIX-STARTUP-IO-SLICE-2026-11-25.md) composes process startup, typed errors and regular-file progress.
- [RT-10 POSIX profile evidence](RT-10/RT-10-POSIX-PROFILE-EVIDENCE-2026-11-25.md) checks exact scope, availability and runtime claim coverage.
- [RT-10 libc and syscall cancellation](RT-10/RT-10-LIBC-SYSCALL-CANCELLATION-2026-11-25.md) distinguishes a cancelled join from byte settlement.
- [RT-10 typed readv progress](RT-10/RT-10-POSIX-READV-TYPED-PROGRESS-2026-11-25.md) distinguishes zero requests, EOF, would-block and vector continuation.
- [RT-10 POSIX edition descriptors](RT-10/RT-10-POSIX-EDITION-DESCRIPTORS-2026-11-25.md) compares edition requests, descriptor declarations and native flags.
- [RT-10 native wait predicates](RT-10/RT-10-WAIT-PREDICATES-AND-CANCELLATION-2026-11-25.md) compares notification, work readiness and cancellation.
- [RT-10 release sequence membership](RT-10/RT-10-RELEASE-SEQUENCE-MEMBERSHIP-2026-11-25.md) checks version-specific synchronization under explicit read-from edges.
- [RT-26 delegated quota reclamation](RT-26/RT-26-DELEGATED-QUOTA-RECLAMATION-2026-11-25.md) checks conservation and safe reuse after child usage.
- [RT-10 native byte and text values](RT-10/RT-10-NATIVE-BYTE-AND-TEXT-VALUES-2026-11-25.md) observes exact spans, C string prefixes and UTF-8 validation.
- [RT-10 exact native call closure](RT-10/RT-10-EXACT-NATIVE-CALL-CLOSURE-2026-11-25.md) compares wrapper identity, resolved helper identity and observed behavior.
- [RT-10 stack VM fuel correspondence](RT-10/RT-10-STACK-VM-FUEL-CORRESPONDENCE-2026-11-25.md) compares source charges, opcode costs and partial effect traces.
- [RT-25 four-provider allocator replay](RT-25/RT-25-FOUR-PROVIDER-ALLOCATOR-REPLAY-2026-11-25.md) — checks the same Rust probe and graph with glibc, jemalloc, TCMalloc minimal and mimalloc.
- [RT-25 workload-fit recheck](RT-25/RT-25-WORKLOAD-FIT-RECHECK-2026-11-24.md) maps current allocator evidence to the RT-01 workload catalog and RT-25 gates. Existing evidence covers one compatible Linux glibc/jemalloc probe and one synthetic graph workload; actual cache/package/concurrent service workloads, other mandatory candidates, and supported-target FFI coverage remain open.

## Dedicated research artifacts

- [PROTOTYPES](PROTOTYPES/)

## Cross-direction evidence

- [RT-25 modern Google TCMalloc](RT-25/RT-25-MODERN-GOOGLE-TCMALLOC-2026-11-25.md) checks the pinned native build, process-wide Rust allocation and a head-to-head graph workload.
See [shared executable research prototypes](../PROTOTYPES/README.md) for integrated experiments that are used across directions.
