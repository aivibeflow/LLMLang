# RT-27 bounded active segments through ordinary Git transport

**Date** 2026-11-25 · **Plan** §4.2, R-STORE-009–012 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

The writer represents each update by exact added and retired content addresses. The active manifest commits the complete reachable graph. Immutable physical segments may retain retired addresses until the next compaction. The runner sets a fixture compaction rule at 105% of live encoded payload bytes. Crossing that threshold rewrites the active segment files from the current live inventory, preserves the semantic root, and leaves historical commits reachable.

The 21 committed selections include ten compactions. Every selected graph recovers exactly after each physical rewrite. The highest active-to-live payload ratio after publication is 1.0446. The largest individual compaction removes 70,375 active bytes. The bound applies to selected record payloads. It excludes metadata, repository pack growth and temporary staging.

The writer uses an ordinary local bare upstream, with a seeded branch named `research/all`. An independently cloned observer fetches the fast-forward branch and a historical tag, then disconnects its origin. A second writer offers a divergent update from the older head and normal Git rejects the non-fast-forward push. The observer's branch retains exactly the 21 accepted Git commits. Its historical tag identifies the exact revision that omits the derived reverse index. Rebuilding the index from that commit's closed graph reproduces the independently expected reverse rows. The other 20 commits verify their tracked index against the graph.

This is evidence for immutable add/update/delete semantics, candidate active compaction, recoverable indexes and ordinary ref transport over one shaped history. Derived metadata can be reconstructed from the graph under the declared projection. The fixture leaves long-term pack growth, standard project workload coverage, hosting and production compaction policy open.

Reproduce with CPython 3.12.14 and Git 2.52.0.

```bash
study=research/toolchain-and-collaboration/RT-27/SEGMENTED-GIT-TRANSPORT-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh repository runs reproduced the commit sequence, roots, compaction and tag results byte for byte.
