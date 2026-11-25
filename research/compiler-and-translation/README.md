# Compilers, backends and translation

[Research index](../README.md) · [Research taxonomy](../research-management/RESEARCH-TAXONOMY.md) · [Dependency map](../research-management/RESEARCH-DEPENDENCY-MAP.md)

This direction groups related research studies without changing their RT identifiers, research status, or accepted decisions.

## Studies

| ID | Scope |
|---|---|
| [RT-09](RT-09/) | Compiler architecture and intermediate representations |
| [RT-13](RT-13/) | Target backends and interoperability |
| [RT-28](RT-28/) | Incremental polyglot migration and semantic mirroring |
| [RT-29](RT-29/) | Rust capability and implementation foundation |
| [RT-30](RT-30/) | Bidirectional semantic translation across LLMLang, C, C++, Go, and Rust |

## Dedicated research artifacts

- [RT-13 rule proof and translation validation](RT-13/RT-13-RULE-PROOF-AND-TRANSLATION-VALIDATION-2026-11-25.md) — compares a checked store swap with validation of an exact emitted target.
- [RT-13 state/Result mutation coverage](RT-13/RT-13-STATE-RESULT-MUTATION-COVERAGE-2026-11-25.md) — checks which generators and projections expose seeded rewrite faults.
- [PROTOTYPES](PROTOTYPES/)

## Cross-direction evidence

- [RT-13 Rust optional ABI](RT-13/RT-13-RUST-NONZERO-OPTIONAL-ABI-2026-11-25.md) checks the documented nonzero niche and a tagged FFI carrier.
- [RT-13 C++ destructor ABI](RT-13/RT-13-CPP-DESTRUCTOR-ABI-2026-11-25.md) checks equal record layouts with different by-value return carriers.
- [RT-13 Go deferred resource capture](RT-13/RT-13-GO-DEFERRED-RESOURCE-CAPTURE-2026-11-25.md) checks exact handle identity under versioned loop binding.
- [RT-13 common subset backend receipts](RT-13/RT-13-COMMON-SUBSET-BACKEND-RECEIPTS-2026-11-25.md) verifies the implemented scalar backend gate across archived profiles.
- [RT-13 Java cleanup occurrences](RT-13/RT-13-JAVA-CLEANUP-OCCURRENCES-2026-11-25.md) compares automatic suppression with separate typed failure occurrences.
- [RT-09 static link artifact identity](RT-09/RT-09-STATIC-LINK-ARTIFACT-IDENTITY-2026-11-25.md) compares archive order, selected native members and exact executable bytes.
- [RT-09 translation outcome closure](RT-09/RT-09-TRANSLATION-OUTCOME-CLOSURE-2026-11-25.md) composes scoped region decisions and required target evidence.
- [RT-09 SSA parallel-copy lowering](RT-09/RT-09-SSA-PARALLEL-COPY-LOWERING-2026-11-25.md) checks scheduled sequential assignments against native LLVM phi traces.
See [shared executable research prototypes](../PROTOTYPES/README.md) for integrated experiments that are used across directions.
