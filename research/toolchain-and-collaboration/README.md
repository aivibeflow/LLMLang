# Toolchain, build, storage and collaboration

[Research index](../README.md) · [Research taxonomy](../research-management/RESEARCH-TAXONOMY.md) · [Dependency map](../research-management/RESEARCH-DEPENDENCY-MAP.md)

This direction groups related research studies without changing their RT identifiers, research status, or accepted decisions.

## Studies

| ID | Scope |
|---|---|
| [RT-11](RT-11/) | Build, incremental computation, and caching |
| [RT-14](RT-14/) | AI-native authoring and change protocol |
| [RT-15](RT-15/) | Collaboration, version control, and semantic merge |
| [RT-17](RT-17/) | Developer experience and diagnostics |
| [RT-19](RT-19/) | Toolchain Server and semantic development API |
| [RT-20](RT-20/) | LLM patch planning, caller migration, hash propagation, and verified commit |
| [RT-21](RT-21/) | LLMLang self-development and bootstrap |
| [RT-22](RT-22/) | LLMLang Git repository and worktree MCP surface |
| [RT-23](RT-23/) | Single-instance Toolchain and incremental multi-worktree file views |
| [RT-24](RT-24/) | Canonical semantic representation, semantic diff, and three-way merge |
| [RT-27](RT-27/) | SPG repository storage format and Git-efficient persistence |

## Recent bounded rechecks

- [RT-19 transaction/recovery protocol comparison](RT-19/RT-19-TRANSACTION-RECOVERY-PROTOCOL-COMPARISON-2026-11-24.md) compares a single embedded DB coordinator, separate immutable object plus workspace journal/outbox contracts, and Git commit as acceptance. It favors testing the separated logical contracts in one DB transaction, with Git as reconstructible authority; it does not claim crash recovery or select a production backend.
- [RT-19 multi-file publication boundary recheck](RT-19/RT-19-MULTIFILE-PUBLICATION-BOUNDARY-RECHECK-2026-11-24.md) compares per-file replacement, immutable generation publication, and exact Git-tree/ref publication. It favors validating a private complete tree before Git ref publication as the next experiment; no implementation or production format is selected.

## Dedicated research artifacts

- [PROTOTYPES](PROTOTYPES/)
- [benchmarks](benchmarks/)

## Cross-direction evidence

See [shared executable research prototypes](../PROTOTYPES/README.md) for integrated experiments that are used across directions.
