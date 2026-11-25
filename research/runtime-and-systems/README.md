# Runtime, resources, embedded and operating systems

[Research index](../README.md) · [Research taxonomy](../research-management/RESEARCH-TAXONOMY.md) · [Dependency map](../research-management/RESEARCH-DEPENDENCY-MAP.md)

This direction groups related research studies without changing their RT identifiers, research status, or accepted decisions.

## Studies

| ID | Scope |
|---|---|
| [RT-10](RT-10/) | Runtime and execution model |
| [RT-25](RT-25/) | Runtime memory allocators and allocation strategy |
| [RT-26](RT-26/) | Hierarchical resource accounting and real-time enforcement |
| [RT-37](RT-37/) | Freestanding, embedded and real-time firmware |
| [RT-38](RT-38/) | Operating-system kernels and verified microkernel feasibility |

## Recent bounded rechecks

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

See [shared executable research prototypes](../PROTOTYPES/README.md) for integrated experiments that are used across directions.
