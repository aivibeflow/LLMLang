# Research Preparation — RT-11/12 Package, Cache and Trust Validation

**Status:** Prepared; not executed.  
**Priority:** P1 with P0 dependencies.  
**Related open questions:** LL-009, LL-010, LL-011, LL-021, LL-022; RT-11, RT-12, RT-16 and RT-18.

## 1. Objective

Turn the existing package-manifest, index and disk-backed traversal prototypes into a measurable validation programme. Keep semantic identity, package/archive identity, provider discovery, build Action Keys, output Artifact Hashes and trust/provenance distinct.

## 2. Existing material

Read:
- [TODO.md](../../TODO.md), especially LL-009–012 and LL-021/022
- [Draft Glossary](../../draft/GLOSSARY.md)
- [Scenario 90 — runtime hashing](../RESEARCH-SCENARIO-90-RUNTIME-HASHING-DETERMINISM-AND-PERSISTENT-IDENTITY.md)
- [Scenario 91 — versioned content addresses](../RESEARCH-SCENARIO-91-VERSIONED-CONTENT-ADDRESSES-AND-DIGEST-MIGRATION.md)
- [Scenario 92 — operation/implementation identity](../RESEARCH-SCENARIO-92-OPERATION-IDENTITY-AND-IMPLEMENTATION-BINDING.md)
- [Scenario 93 — cache soundness and trust](../RESEARCH-SCENARIO-93-CACHE-SOUNDNESS-RESULT-ENVELOPES-AND-TRUST.md)
- [Research State](../RESEARCH-STATE-2026-11-19.md), Gate C and Wave C
- Existing package and semantic-store prototype documentation linked from LL-022

## 3. Questions

### Package and distribution
- Which package contents are semantic graph objects, distribution payloads, indexes or provider metadata?
- How are required, optional and conditional dependencies represented and selected?
- How are cycles, shared dependencies, missing objects and substituted content handled?
- What is the minimum public package/library contract?
- Should package indexes and result payloads be embedded, block-addressed or fetched separately?
- Which fields are necessary for sparse lookup and bounded streaming?

### Cache correctness
- What exact inputs belong to an Action Key?
- How is the full dependency closure established and bound?
- Which data is a cached result, restored build material, or output Artifact Hash?
- How are nondeterministic actions, runtime/environment inputs and tool identity handled?
- What happens when dependency completeness, provenance or trust is UNKNOWN?
- What are the cache writer/reader trust boundaries, poisoning defenses, revocation and eviction rules?

### Measurement
- What are the resource costs for traversal, indexes, archives and validation?
- How does performance change with package size, dependency depth, fan-out, sharing and sparse access?
- What is the memory cost of archive central directories and index decoding?
- Which archive/container or block format is viable under measured constraints?

## 4. Fixture and benchmark preparation

Generate deterministic corpora with:
- small, medium and large manifests;
- deep chains, wide fan-out, shared dependencies and SCCs;
- required/optional/conditional edges;
- absent, substituted, corrupted and unreachable objects;
- negative/fallback provider discovery;
- stale indexes and schema/digest migration;
- warm/cold cache and partial dependency invalidation;
- tampered provenance, untrusted writer, revoked publisher and restored cache.

Pin workload generation seeds and publish dataset manifests separately from results.

## 5. Proposed method

1. Define the package, index, Action Key, result and artifact schemas as candidates only.
2. Build an immutable Content Store adapter against a pinned snapshot.
3. Verify exact dependency closure and index included flags against an independent traversal.
4. Exercise disk-backed queue/visited/dependency tables and streaming archive output.
5. Measure peak RSS, CPU, wall time, bytes read/written, query count, index decode and archive finalization separately.
6. Compare candidate archive/index representations only against those measurements.
7. Inject interrupted publication, missing content, stale cache entries and malicious provenance.
8. Keep semantic integrity (content address), authentication (who published/verified) and policy (who may consume/publish) as separate claims.

## 6. Exit criteria

- The production-like store adapter is bound to an immutable snapshot.
- Required/optional/conditional dependency closure is reproducible and independently checked.
- Missing, substituted, incomplete or untrusted data fails closed.
- Index and archive resource bounds are measured on documented corpus sizes.
- Cache reuse is tied to exact Action Key inputs and complete dependency closure.
- Negative lookup and fallback provider results participate in invalidation where relevant.
- A format recommendation is supported by measured cost and migration evidence, not preference alone.

Do not select ZIP, binary blocks, compression, sparse lookup, provider construction or remote-cache policy before the corresponding contracts and measurements exist.
