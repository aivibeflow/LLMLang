# Git binary SPG storage benchmark

This directory contains a reproducible reference harness for the add/remove-only immutable-object workload described in the [research report](../../GIT-BINARY-SPG-STORAGE-EFFICIENCY.md).

## Provenance note

The measurements previously mentioned in the research report (30,000 × 192-byte records) came from an exploratory run whose original source code, fixture, exact commands, and raw logs were not retained. **This harness is a new reference implementation; it does not claim to reproduce those historical numbers byte-for-byte.** It provides a reproducible baseline for future measurements.

## Requirements

- Python 3.10 or newer
- Git installed and available on PATH
- No third-party Python packages

Record the environment before comparing results:

    python3 --version
    git --version
    git config --show-origin --get-regexp '^(core\.bigFileThreshold|pack\.(window|depth|compression))$' || true

The harness sets the listed repository-local Git configuration explicitly. When `--workdir` is supplied, it must be fresh or empty; the harness rejects existing scenario directories instead of accidentally reusing stale repositories.

## Quick start

Run from the repository root:

    python3 research/benchmarks/git_binary_spg/run_benchmark.py \
      --objects 30000 \
      --record-size 192 \
      --change-ratio 0.01 \
      --seed 20261123 \
      --output research/benchmarks/git_binary_spg/results.json

The command creates five independent temporary Git repositories:

1. mutable_append — rewrite one bounded container with appended records;
2. mutable_delete_compact — rewrite one container without deleted records;
3. mutable_delete_tombstones — retain immutable payload bytes and write a separate tombstone index;
4. segments_append — add an immutable segment and update its manifest;
5. segments_delete_tombstones — retain the segment and write tombstones.

Each repository contains a baseline commit and one changed-state commit. The harness runs git gc --aggressive --prune=now, measures pack and index sizes, and collects git verify-pack -v and git count-objects -v output.

## Scaling and parameter sweeps

Run each ratio separately so every output is independently attributable:

    for ratio in 0.0001 0.01 0.10; do
      python3 research/benchmarks/git_binary_spg/run_benchmark.py \
        --objects 1000000 \
        --record-size 192 \
        --change-ratio "$ratio" \
        --seed 20261123 \
        --output "results-${ratio}.json"
    done

Vary object count and record size to explore different container sizes. This initial harness is a controlled microbenchmark, not a complete production-topology benchmark.

## Retain repositories for inspection

Temporary repositories are removed by default. To retain them:

    python3 research/benchmarks/git_binary_spg/run_benchmark.py \
      --objects 30000 --record-size 192 --change-ratio 0.01 \
      --output results.json --keep-workdirs --workdir ./benchmark-work

Inspect a scenario:

    git -C benchmark-work/mutable_append count-objects -v
    git -C benchmark-work/mutable_append log --oneline --stat
    git -C benchmark-work/mutable_append verify-pack -v \
      benchmark-work/mutable_append/.git/objects/pack/*.idx

## Executed reference baseline (2026-11-23)

The committed harness was executed five times with the same fixed-size fixture:

- Git 2.47.3; Python 3.13.5; Linux x86_64.
- 30,000 records × 192 bytes (5,760,000 payload bytes), 300 additions/deletions (1%).
- Seed 20261123; `core.bigFileThreshold=512m`, `pack.window=10`, `pack.depth=50`, `pack.compression=6`.
- Each repetition used five fresh repositories, two commits per repository, and `git gc --aggressive --prune=now`.

Median pack + index bytes across five repetitions:

| Scenario | Median pack + index | Median delta representation bytes |
|---|---:|---:|
| mutable_append | 5,693,362 | 241 |
| mutable_delete_compact | 5,638,292 | 1,557 |
| mutable_delete_tombstones | 5,637,671 | 85 |
| segments_append | 5,693,602 | 85 |
| segments_delete_tombstones | 5,637,823 | 100 |

The append layouts differ by only 240 bytes; deletion alternatives differ by at most 621 bytes in this fixture. These differences are negligible relative to a roughly 5.6 MB pack and do not establish a preferred layout. The fixture is high-entropy, fixed-size, single-container/segment, and only two commits deep. It is a smoke-level baseline, not representative SPG evidence. Full per-scenario ranges and run metadata are stored in [results-2026-11-23.json](results-2026-11-23.json).

The retained final run passed `git fsck --full` in all five scenario repositories. A small CLI smoke test, Python bytecode compilation, and rejection of a reused non-empty `--workdir` were also checked. This does not validate semantic SPG reconstruction, reference integrity, clone/fetch costs, long histories, or branch merges.

## Output interpretation

The JSON report records:

- Python, platform, and Git versions;
- repository-local pack configuration;
- fixture dimensions, deterministic seed, and add/delete counts;
- baseline and changed commit IDs;
- worktree payload size;
- pack, index, and combined pack/index bytes;
- object and delta counts parsed from verify-pack;
- count-objects output;
- commit and aggressive-GC wall-clock times.

The reported delta representation byte count sums the packed-size field for delta entries from verify-pack. It is not a semantic measure of how many SPG bytes changed. Compare it alongside total pack size and delta depth. The harness does not measure network fetch traffic or peak memory.

## Reproducibility protocol

For publishable comparisons:

1. Pin Git/Python versions, OS, filesystem, CPU, and benchmark arguments.
2. Run each configuration at least five times in fresh work directories.
3. Preserve every JSON result and exact command line.
4. Compare medians and tail values, not one run.
5. Keep fixture seed, record count, record size, and change ratio identical across layouts.
6. Extend the fixture with realistic SPG payload distributions and cross-object references before making an architecture decision.
7. Add long histories, branch divergence, compaction cycles, clone/fetch measurements, and clean-clone SPG reconstruction as separate phases.
8. Validate the logical active object set after every scenario; packfile size alone does not establish correctness.

The fixture uses deterministic fixed-size records and deterministic pseudorandom payloads. It is a storage microbenchmark, not a complete SPG serializer, index, semantic merge implementation, or production workload simulator.

## Scenario semantics

Object payloads are immutable. Tombstones are stored separately as repository metadata. The harness does not interpret tombstones or perform graph-level reference validation; those belong to the semantic SPG layer. The compact-delete scenario rewrites the current container without deleted records, while Git history retains the earlier commit's blob.

## Limitations and next extensions

- The current version tests one changed commit after the baseline.
- It uses one container or one segment stream per scenario; bounded multi-shard placement and shard skew remain to be implemented.
- It does not model realistic variable-size SPG objects, dependency graphs, or semantic merge.
- It does not measure clone/fetch network bytes, checkout latency, random object lookup, or peak RSS.
- Aggressive repack is one controlled measurement mode; repeat with ordinary git gc and production-representative configurations.
- Compression modes and chunking strategies should be added as separate controlled factors.
