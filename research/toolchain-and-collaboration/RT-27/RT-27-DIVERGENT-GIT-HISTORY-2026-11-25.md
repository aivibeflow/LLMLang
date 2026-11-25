# RT-27 variable-size Git storage over divergent histories

**Date** 2026-11-25 · **Plan** §4.2 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

The synthetic typed graph starts with 401 reachable objects. Leaves carry varying expression lengths and one to four contract edges, with object sizes from 68 to 25,784 bytes including the snapshot root. Each history has an initial commit, 20 shared edits, six divergent edits on each arm, and a compaction commit. Edits replace one to five selections, with periodic deletion and insertion at new positions. Both arms use `research/all` in separate repositories. The alternate tip is fetched by an explicit tag into the source fixture so both histories stay reachable for measurement.

Stable shards partition records into eight bounded buckets by semantic slot. Immutable segments append new addressed records and select the active inventory through the manifest. Content-defined chunks use ordered records, a hash anchor and 16–64 record bounds. All layouts use the same reachable graphs. Each run fetches both arms into a clean Git clone, verifies Git objects, disconnects the sources, and reconstructs every retained commit with its complete exact graph and no KV database.

| Metric | Stable shards | Immutable segments | Content-defined chunks |
| --- | ---: | ---: | ---: |
| Pack and index after common commits, bytes | 108,148 | 109,058 | 208,909 |
| Pack and index before compaction, bytes | 161,196 | 129,922 | 290,273 |
| Pack and index after compaction, bytes | 161,385 | 139,130 | 290,465 |
| Packed bytes of delta entries after compaction | 104,999 | 51,693 | 228,291 |
| Maximum delta depth after compaction | 22 | 26 | 18 |
| Maximum tracked record paths before compaction | 8 | 27 | 11 |
| Active payload bytes before compaction | 760,629 | 1,599,462 | 760,629 |
| Active payload bytes after compaction | 760,629 | 760,629 | 760,629 |

Segment compaction removes 838,833 active payload bytes while adding 9,208 retained pack and index bytes. It retains the smallest final pack in this workload, and uses the largest peak traced reconstruction allocation. Stable shards use eight record files at each stage and occupy less pack space than the content-defined chunks at all three checkpoints.

The nine measured histories use Git 2.52.0, a single pack thread, window 10, depth 50 and compression level six. Commands run with CPU affinity to core 4 of a shared Linux x86-64 AMD EPYC host. The table gives median wall and CPU milliseconds from three runs in the form wall / CPU. The log contains each measured command's Linux `wait4` peak RSS. Python traced allocation is measured on a separate reconstruction call.

| Operation | Stable shards | Immutable segments | Content-defined chunks |
| --- | ---: | ---: | ---: |
| Clone | 68.629 / 66.497 | 36.514 / 33.718 | 61.085 / 55.376 |
| Fetch both retained arms | 97.471 / 96.834 | 56.095 / 55.211 | 106.093 / 105.542 |
| Checkout compacted tip | 7.589 / 7.444 | 7.699 / 7.564 | 8.523 / 8.305 |
| Read compacted Git archive | 2.974 / 2.520 | 3.710 / 3.245 | 4.602 / 3.824 |
| Reconstruct exact graph | 10.605 / 10.605 | 12.901 / 12.904 | 12.468 / 12.472 |
| Repack after compaction | 7.919 / 6.315 | 26.155 / 24.418 | 9.951 / 8.461 |
| Maximum observed Git RSS over sampled commands, KiB | 6,016 | 5,700 | 4,908 |
| Maximum Python traced reconstruction bytes | 919,544 | 1,570,963 | 887,569 |

All 306 commit reconstructions in the timed batch match the intended graph. A separate fresh three-layout run agrees on identities and pack statistics. This local benchmark uses synthetic graph payloads, small edits, one shaped divergence and a shared host. Larger realistic SPG distributions, mixed toolchains and repository servers, metadata-only reads, alternative Git pack settings, and production layout selection remain open.

Reproduce with CPython 3.12.14, GCC and Git 2.52.0 on Linux from the repository root. The exact output and raw resource samples are separate.

```bash
study=research/toolchain-and-collaboration/RT-27/DIVERGENT-GIT-HISTORY-01
taskset -c 4 python "$study/run.py" --trials 1 --exact /tmp/llmlang-git-history.json
cmp "$study/evidence.json" /tmp/llmlang-git-history.json
```
