# RT-27 Git pack deltas over typed prototype SPG records

**Date** 2026-11-25 · **Plan** §4.2 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

This cohort produces objects with the existing typed SPG compiler and dispatcher fixture. It instantiates independent modules, updates provider implementations and bindings, and adds and removes entire modules. The 15 distinct selections contain 172–186 semantic values, with canonical prototype record sizes between 143 and 638 bytes. The harness preserves exact dependency references and both the prototype semantic root and the storage transport root. Independent persistence and typed admission checks restore each prototype snapshot and replay declared observations.

Three layouts use the same prototype records and graph history. The eight stable buckets use a projection of the immutable prototype address. Immutable segments retain existing exact rows and append new addresses. Content-defined chunks use an ordered projection and exact anchored boundaries. Every update adds and retires immutable addresses. Three edits add 19 and retire five, and three remove 19 while adding five. Compaction switches physical selection while retaining the graph.

| Final pack metric | Stable shards | Immutable segments | Content-defined chunks |
| --- | ---: | ---: | ---: |
| Pack and index before final compaction, bytes | 92,985 | 92,946 | 158,507 |
| Pack and index after final compaction, bytes | 93,092 | 103,009 | 158,615 |
| Packed delta bytes after final compaction | 56,961 | 41,581 | 115,490 |
| Number of delta entries | 111 | 44 | 92 |
| Maximum delta depth | 7 | 6 | 7 |
| Active record bytes before compaction | 163,282 | 493,629 | 163,282 |
| Active record bytes after compaction | 163,282 | 163,282 | 163,282 |

Clones fetch divergent history, disconnect from their sources and reconstruct all 16 retained commits in each layout, including the compaction commit. This gives 48 exact restore checks. The current cohort's stable shards have the smallest final pack. The [longer synthetic cohort](RT-27-DIVERGENT-GIT-HISTORY-2026-11-25.md) instead has the smallest final pack for immutable segments. Layout comparisons depend on record shape, retention and compaction.

This workload carries real prototype records and typed edges from generated variants of one project fixture. It complements the longer synthetic history, which supplies measured resource distributions. A production LLMLang corpus, authority and canonical shard or layout choice remain open. The runner retains one Git object format and one fixed Git compression profile.

Reproduce with CPython 3.12.14, Git 2.52.0 and GCC from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-27/PROTOTYPE-SPG-PACKS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two separate runs reproduced every selected identity and pack statistic.
