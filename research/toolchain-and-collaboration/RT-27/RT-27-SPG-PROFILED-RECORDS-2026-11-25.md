# RT-27 cache-first Git records for the typed SPG prototype

**Date** 2026-11-25 · **Plan** §4.2, R-STORE-001–004 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

The existing dependency-graph prototype produces two typed SPG snapshots from its dispatch fixture. The second selects an alternate provider and binds the first snapshot as its parent. Each Git revision contains 18 semantic values in four uncompressed record buckets, plus a manifest, exact locations and reverse index. The manifest preserves selected identities, parent roots, persistence schema and relation rows. Physical record locations are bound to exact canonical bytes and each semantic Content Hash.

| Acquisition case | Cache hits | Record reads and decodes | Physical record bytes |
| --- | ---: | ---: | ---: |
| Cold restoration of either revision | 0 | 18 | 7,748 |
| Second revision with first revision cached | 17 | 1 | 419 |
| Either revision with exact complete cache | 18 | 0 | 0 |

Both revisions cold-restore from a clean Git clone with its origin removed and no external database. The prototype's existing persistence validator checks reconstructed contents and the SPG admission checker verifies selected objects. The checked storage separately reproduces exact reverse occurrences and live late-binding observations. The three retained return values change from `[-2, 1, 8]` to `[-1, 2, 9]` when the provider changes. Two snapshots each fit in seven tracked files with a fixed four-container bound.

The acquisition reader compares metadata with the exact Git blobs for a pinned commit before checking cache coverage. It checks cached object representations against the record digest and the semantic address. A miss seeks to the recorded offset, checks raw bytes, and decodes that object. A full hit succeeds even after the working-tree copy of every payload bucket is removed. Stale location metadata, a wrong cached object and a corrupt payload on a cold read are refused. The cache path covers acquisition of existing decoded records. The separate cold validator reconstructs and decodes the complete prototype persistence document.

Physical output is byte-identical across one, two and four serializer threads and repeated Python hash seeds. The fixture pins one uncompressed serialization profile. Its fixed buckets and clean clone establish scoped R-STORE-001–004 evidence for these actual prototype snapshots. Authenticity of the Git commit pin is a caller premise. Production schema, compression profiles, untrusted commit approval and broader corpus measurement remain open.

Reproduce with CPython 3.12.14 and Git 2.52.0 from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-27/SPG-PROFILED-RECORDS-01
PYTHONHASHSEED=2 python "$study/run.py" | cmp "$study/evidence.json" -
```
