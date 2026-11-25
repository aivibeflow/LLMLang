# RT-11 delivery of optional package-cache results

**Date** 2026-11-25 · **Plan** §3.3 · **Issue** [#300](https://github.com/aivibeflow/LLMLang/issues/300)

The fixture combines the existing package verifier and versioned cache-index validator with five concrete outputs. It verifies the package, builds a GCC object, obtains a GNU readelf symbol analysis, records three native test observations and checks a separate integer proposition in Lean. The five action records bind the package root, exact action-family inputs and expected result digests. The action envelope uses fixture profiles and a supplied local trust map. The native object and Lean theorem are separate subjects in this delivery experiment. The theorem does not establish native compiler correctness.

The package-only consumer verifies the same core archive with every carrier and fetches zero detached bytes. The other profiles request compilation only or all five results. The table counts whole initial ZIP bytes, detached file bytes and detached reads. The transport uses uncompressed ZIP members and file-backed delivery with no pre-existing mirror.

| Optional index and payload layout | Initial package bytes | Compile only, additional bytes / reads | All five, additional bytes / reads | Offline hits out of five |
| --- | ---: | ---: | ---: | ---: |
| Omitted | 2,512 | 0 / 0 | 0 / 0 | 0 |
| Both embedded | 11,188 | 0 / 0 | 0 / 0 | 5 |
| Embedded index | 8,065 | 1,080 / 1 | 1,943 / 5 | 0 |
| Embedded payloads | 5,635 | 5,445 / 1 | 5,445 / 1 | 0 |
| Both detached | 2,512 | 6,525 / 2 | 7,388 / 6 | 0 |

All four cache-bearing layouts recover all five selected results online. Each of five altered payloads is refused by hashing actual bytes. Each of five structurally valid records that points across action families is refused before reading that payload. The other four records still hit in every fault control. All 20 layout/profile combinations and ten faults preserve the logical package and the exact inner archive.

Use an independently optional cache index and content-addressed payloads. The detached pair is the candidate default for ordinary package delivery so a package-only consumer incurs no cache bytes and a selective consumer can request only applicable result payloads. A self-contained export for disconnected operation can embed both the index and the requested payload closure. An embedded index with detached results is a usable option when the consumer is expected to query the index and can reach the result store. Embedding only the payloads adds carrier bytes without providing disconnected use when the index is unavailable. Package validation stays independent of every hint. Exact action, result authority and byte verification gate reuse for all five families. Missing or refused cache data falls back to executing the corresponding action under its ordinary policy.

This experiment measures bytes and reads rather than latency. Production wire encoding, request batching, package distribution protocols, remote trust, compressor choice, fallback execution and realistic hit profiles remain open. The fixture supplies deterministic delivery artifacts and a separate trust map for testing admission.

Reproduce with GCC, GNU readelf, Lean 4.36.0 and Python from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-11/PACKAGE-CACHE-DELIVERY-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh builds and five-family replays produced byte-identical ledgers.
