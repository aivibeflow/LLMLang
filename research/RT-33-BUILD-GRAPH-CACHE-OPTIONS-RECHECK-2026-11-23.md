# RT-33: Build graph and cache distribution options recheck

**Date:** 2026-11-23  
**Baseline:** `1fd75fe3f9d6973b8a3a1ecab726fe948725de50` (`main`)  
**Scope:** compare candidate cache-index/result placement and deployment layers for PLAN §3.3 using current package and cache prototypes. No production cache or remote service is implemented.

## Candidate comparison

| Option | Benefits | Costs and risks | Evidence / disposition |
|---|---|---|---|
| Put cache records and result payloads inside the immutable package archive | Single transport unit; package root can enumerate optional data | Couples release publication to rebuildable/evictable results; large archives and every cache update create a new delivery artifact; stale cache data can look like package content | Package identity proposal explicitly excludes optional cache fields from Package Content Root Hash and treats missing cache data as a miss. Do not make cache payloads mandatory package members. |
| Package carries an optional cache-index reference; immutable result payloads live in a separate CAS | Separates semantic package identity from derived results; index can be omitted/rebuilt and payloads can be shared by digest | Requires safe locator/authentication policy and independent availability/eviction; reference schema and merge behavior are open | Closest to existing proposal: package manifest may reference optional cache indexes, while content store/archive handles immutable objects. Candidate for later protocol design, not validated end to end. |
| Local/workspace cache only, with a local derived index | Simplest trust and failure boundary; supports early action-key experiments without a service | No cross-workspace sharing; cleanup/concurrency and persistent index format still matter | Existing package index and SQLite content-store prototypes exercise immutable snapshots, streaming and local persistence, not action-result cache integration. Suitable as first deployment slice after key/completeness contracts. |
| Team/remote cache as the initial authority | Cross-developer and CI sharing; potentially high warm reuse | Authentication, producer trust, poisoning, network/eviction policy, reproducibility, availability and failure fallback all become correctness-critical | Existing cache proposal lists this as a later layer; no remote cache experiment or trust protocol is in current evidence. Defer until local soundness and provenance are demonstrated. |

Across every option, keep Semantic Hash, Action Key, and Artifact Hash distinct. The cache-record prototype binds action kind/implementation, declared input hashes, language version and registry digest, toolchain, target, configuration, runtime, determinism, status, and a completeness flag. It rejects incomplete dependencies and transient/non-cacheable outcomes. This supplies a testable candidate record, but not proof that production dependency extraction is complete or that the record schema is canonical.

## Focused validation

On CPython 3.12.14, ran the cache-record/version tests, package logical-index tests, and SQLite content-store snapshot tests:

```text
Ran 36 tests; 0 failures, 0 errors, 0 skipped.
```

These tests cover declared Action Key inputs (including toolchain identity), version/registry checks, package index invariants, and local immutable snapshot behavior. They do not exercise cache-index merge/conflict resolution, remote result fetch, evictions, authenticated provenance, or action execution/reuse through a compiler.

SHA-256 at baseline:
- `PACKAGE-IDENTITY-01/cache_index.py`: `2662ffa87450e05f075218b5593222262ff724e785ce512436bfa40443329b3b`
- `PACKAGE-IDENTITY-01/test_language_version_cache_index.py`: `d6576e10e9a1a0fdf674751f18602eabbee81c9cb732177c092a7cfdd7688a6f`
- `PACKAGE-INDEX-01/package_index.py`: `e03e977aef9a7dd9764854468bf0c43875236dae700bcdc498b2286e1de6ae3c`

## Candidate direction and unresolved dependencies

Evidence supports a staged separation: compute and validate deterministic actions locally first; keep optional package cache metadata outside semantic package identity; treat result payloads as independently addressable immutable artifacts; consider workspace/machine sharing after sound local reuse. Remote/team distribution remains conditional on authenticated producer policy, integrity validation, complete dependencies, cache miss/failure fallback, eviction and availability rules. No wire format, merge policy, authority model, or cache layer is selected by this recheck. Those choices require source-derived dependency completeness, the production Action Key contract, representative workload and transfer measurements, and trust/security review.
