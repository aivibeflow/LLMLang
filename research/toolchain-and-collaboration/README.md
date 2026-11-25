# Toolchain, build, storage and collaboration

[Research index](../README.md) · [Research taxonomy](../research-management/RESEARCH-TAXONOMY.md) · [Dependency map](../research-management/RESEARCH-DEPENDENCY-MAP.md)

This direction groups related research studies without changing their RT identifiers, research status, or accepted decisions.

## Browse by topic

- [Build, cache and bootstrap](build-and-bootstrap/README.md) · RT-11, RT-21
- [Git, worktrees and semantic storage](git-and-storage/README.md) · RT-15, RT-22, RT-23, RT-24, RT-27
- [Toolchain API, diagnostics and agent workflows](api-and-workflows/README.md) · RT-14, RT-17, RT-19, RT-20

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

- [RT-24 effective merge attributes](RT-24/RT-24-EFFECTIVE-MERGE-ATTRIBUTES-2026-11-25.md) distinguishes the tracked fallback, effective Git rule and whole-graph outcome.
- [RT-24 team Git workflow](RT-24/RT-24-TEAM-GIT-WORKFLOW-2026-11-25.md) documents candidate inspection, recovery and publication boundaries.
- [RT-24 merge validation audit replay](RT-24/RT-24-MERGE-VALIDATION-AUDIT-REPLAY-2026-11-25.md) checks exact validation decisions across equal candidate results.
- [RT-27 Git journal compaction](RT-27/RT-27-GIT-JOURNAL-COMPACTION-2026-11-25.md) checks exact logical deletion and index recovery from Git.
- [RT-11 scoped dependency fallback](RT-11/RT-11-SCOPED-UNKNOWN-DEPENDENCY-FALLBACK-2026-11-25.md) — compares conservative recomputation with mixed completeness receipts.
- [RT-11 semantic impact and proof freshness](RT-11/RT-11-SEMANTIC-IMPACT-AND-PROOF-FRESHNESS-2026-11-25.md) — compares source revisions, checker keys and archived proof artifacts.
- [RT-11 native source metadata reuse](RT-11/RT-11-NATIVE-SOURCE-METADATA-REUSE-2026-11-25.md) — separates exact objects, source locations and observed execution after edits.
- [RT-11 layered cache lookup](RT-11/RT-11-LAYERED-CACHE-LOOKUP-2026-11-25.md) — compares view completeness, verified bytes and offline promotion.
- [RT-11 cache artifact lifetime](RT-11/RT-11-CACHE-ARTIFACT-LIFETIME-2026-11-25.md) — checks use of verified bytes across native maintenance and eviction.
- [RT-11 multi-action cache hits](RT-11/RT-11-MULTI-ACTION-CACHE-HITS-2026-11-25.md) — checks action-type reuse, exact native bytes and a verifier-policy counterexample.
- [RT-11 build phase overhead](RT-11/RT-11-BUILD-PHASE-OVERHEAD-2026-11-25.md) — measures discovery, hashing, scheduling, recovery of cached bytes and verification separately.
- [RT-11 paired cache speedups](RT-11/RT-11-PAIRED-CACHE-SPEEDUP-2026-11-25.md) — recomputes the analytical estimate and compares paired speedups against forced and incremental builds.
- [RT-11 upstream build baselines](RT-11/RT-11-UPSTREAM-BUILD-BASELINES-2026-11-25.md) — measures clean, warm and edited builds of pinned Rust, Go and C++ libraries.
- [RT-11 upstream content cache](RT-11/RT-11-UPSTREAM-CONTENT-CACHE-2026-11-25.md) — compares whole-project executable reuse with both conventional baselines and retains slower cases.
- [RT-11 five-stage build replay](RT-11/RT-11-BUILD-STAGE-REPLAY-2026-11-25.md) — independently reproduces exact artifacts and action counts for the five native build stages.
- [RT-19 transaction/recovery protocol comparison](RT-19/RT-19-TRANSACTION-RECOVERY-PROTOCOL-COMPARISON-2026-11-24.md) compares a single embedded DB coordinator, separate immutable object plus workspace journal/outbox contracts, and Git commit as acceptance. It favors testing the separated logical contracts in one DB transaction, with Git as reconstructible authority; it does not claim crash recovery or select a production backend.
- [RT-19 multi-file publication boundary recheck](RT-19/RT-19-MULTIFILE-PUBLICATION-BOUNDARY-RECHECK-2026-11-24.md) compares per-file replacement, immutable generation publication, and exact Git-tree/ref publication. It favors validating a private complete tree before Git ref publication as the next experiment; no implementation or production format is selected.
- [RT-19 concurrent workspace CAS recheck](RT-19/RT-19-CONCURRENT-WORKSPACE-CAS-RECHECK-2026-11-24.md) checks same-base concurrent acceptance and Change Set retry behavior. Local CAS is confined to one workspace; shared-head conflict control and durable idempotency remain unresolved.

## Historical scenarios and proposals

- [Scenario 02 — Concurrent changes](RT-14/RESEARCH-SCENARIO-02-CONCURRENT-CHANGES.md)
- [RFC proposal — Request and Change Set](RT-14/RFC-REQUEST-CHANGE.md)

## Dedicated research artifacts

- [PROTOTYPES](PROTOTYPES/)
- [benchmarks](benchmarks/)

## Cross-direction evidence

- [RT-24 identity lineage and caller rebinds](RT-24/RT-24-IDENTITY-LINEAGE-AND-REBIND-2026-11-25.md) checks exact identity and call-site scope across rename, split and merge.
- [RT-24 optimistic edit retries](RT-24/RT-24-OPTIMISTIC-RETRY-AND-RECEIPTS-2026-11-25.md) checks durable receipts and optimistic retry across native SQLite process exits.
- [RT-24 concurrent publication costs](RT-24/RT-24-CONCURRENT-PUBLICATION-COST-2026-11-25.md) measures wait, retry and outcome scopes for live SQLite writers.
- [RT-27 large Git graph benchmark](RT-27/RT-27-LARGE-GIT-GRAPH-BENCHMARK-2026-11-25.md) compares Git pack size, verified checkout and reachability at two edge densities.
- [RT-27 SQLite retention benchmark](RT-27/RT-27-SQLITE-RETENTION-BENCHMARK-2026-11-25.md) compares reverse index, marked reachability and physical compaction costs under exact retained roots.
- [RT-11 persistent build cache](RT-11/RT-11-PERSISTENT-BUILD-CACHE-BENCHMARK-2026-11-25.md) checks exact compile, archive, link and verification restoration across fresh processes.
See [shared executable research prototypes](../PROTOTYPES/README.md) for integrated experiments that are used across directions.
- [RT-11 composed non-interference](RT-11/RT-11-COMPOSED-NONINTERFERENCE-2026-11-25.md) — distinguishes separate edit checks from applicable evidence about their composed result.
- [RT-11 typed pipeline invalidation](RT-11/RT-11-TYPED-PIPELINE-INVALIDATION-2026-11-25.md) — compares precise consumed inputs and reusable outputs across six pipeline actions.
- [Six-stage native propagation](RT-11/RT-11-SIX-STAGE-PROPAGATION-2026-11-25.md) — exact native artifacts and proof freshness after implementation edits.
- [Typed action receipts](RT-11/RT-11-TYPED-ACTION-RECEIPTS-2026-11-25.md) — actual native and Lean outputs with role and proof-subject checks.
- [Native runtime closure](RT-11/RT-11-NATIVE-RUNTIME-CLOSURE-2026-11-25.md) — loader-order, transitive runtime bytes, missing inputs and policy controls.
- [ELF metadata reuse](RT-11/RT-11-ELF-METADATA-REUSE-2026-11-25.md) — loads, exact artifacts and runtime self-inspection.
- [Negative header dependencies](RT-11/RT-11-HEADER-LOOKUP-FALLBACK-2026-11-25.md) — exact positive and absent inputs in ordered compiler search.
- [Native edit locality](RT-11/RT-11-NATIVE-EDIT-LOCALITY-2026-11-25.md) — paired action counts, artifact equality and exploratory rebuild time.
- [Three-edit non-interference](RT-11/RT-11-THREE-EDIT-INTERFERENCE-2026-11-25.md) — pairwise controls and composition at exact intermediate states.
- [RT-11 debug column reuse](RT-11/RT-11-DEBUG-COLUMN-REUSE-2026-11-25.md) — tests exact DWARF column evidence when code and line/address observations remain equal.
- [RT-11 cross-toolchain cache compatibility](RT-11/RT-11-CROSS-TOOLCHAIN-CACHE-COMPATIBILITY-2026-11-25.md) — tests exact artifact identity and finite compatibility evidence under different native compilers.
