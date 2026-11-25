# Stage 7 scalability measurements and uncertainty

The eight committed benchmark ledgers provide bounded measurements of memory, latency, throughput and cache reuse. Each row below retains the exact workload and phase from its own ledger. The reducer verifies each raw sample hash against its study summary. Rates divide the reported amount of work by the timed interval in the same trial. Ratios use both paired measurements from each trial.

The intervals are deterministic 95% percentile bootstrap intervals for the median of the recorded profile, with 5,000 resamples and seed 332. A trial is the resampling unit. Individual requests or worker threads inside a trial stay together. Each timing or resource estimate uses seven or ten trials. Small samples give limited resolution, and the intervals describe within-profile variability on the recorded runner. Hardware, repository and workload variation require additional measurement. The source studies retain p10–p90 and their figures for each profile, while this report uses a table to compare distinct units.

| Measurement and exact profile | Median | Within-profile 95% interval |
| --- | ---: | ---: |
| Extra retained reverse-index allocations, layered 8,192-node graph | 5.82 MiB | 5.82–5.82 MiB |
| Repeated-query speedup including index build, same graph and six queries | 3.60× | 3.19–4.13× |
| Canonical encoding of a 512-entry nested payload | 461.78 µs/object | 438.88–576.54 µs/object |
| Canonical encoding throughput, same nested profile | 2,167 objects/s | 1,734–2,279 objects/s |
| Grouped planning for a hot callee with 1,024 active callers | 18.95 ms | 17.47–21.54 ms |
| Fresh build-cache process with all exact artifacts restored | 47.05 ms | 45.37–53.14 ms |
| Peak Lean child RSS for the mapping and IPC proof route | 305.05 MiB | 302.66–311.78 MiB |
| Peak Python RSS for that package's finite oracle | 13.50 MiB | 13.50–13.50 MiB |
| SQLite indexed retained-root collection at 8,192 objects | 109,073 removed objects/s | 101,811–112,338 removed objects/s |
| Verification and decode of the 32-dependency Git graph | 5.97 million edges/s | 4.41–6.62 million edges/s |
| Exact projection publication, eight independent writers | 98.03 commits/s | 97.36–98.46 commits/s |

Python live allocation estimates and process peak RSS measure different quantities. The two proof and finite-oracle values also refer to different work and coverage. Graph verification throughput includes container checks and parsing. Publication throughput counts accepted edits within the measured batch boundary. These denominators make the values usable as inputs to scoped scheduling and storage estimates.

The persistent-cache fixture observed 0 hits in 100 cold action requests, 100 in 100 requests across fresh restorations, and 90 in 100 following the verification-policy change. These are exact fixture frequencies over repeated fixed actions. Estimating a production hit rate requires a workload distribution. [Persistent build cache](../toolchain-and-collaboration/RT-11/RT-11-PERSISTENT-BUILD-CACHE-BENCHMARK-2026-11-25.md)

[Graph traversal](../semantic-representation/RT-05/RT-05-REVERSE-TRAVERSAL-BENCHMARK-2026-11-25.md) · [Canonical encoding](../semantic-representation/RT-05/RT-05-CANONICAL-HASH-COST-2026-11-25.md) · [Impact planning](../semantic-representation/RT-06/RT-06-IMPACT-PLANNING-BENCHMARK-2026-11-25.md) · [Proof and test costs](../formal-verification/PROOF-OBLIGATION-BENCHMARK/PROOF-AND-TEST-COST-2026-11-25.md) · [SQLite retention](../toolchain-and-collaboration/RT-27/RT-27-SQLITE-RETENTION-BENCHMARK-2026-11-25.md) · [Large Git graph](../toolchain-and-collaboration/RT-27/RT-27-LARGE-GIT-GRAPH-BENCHMARK-2026-11-25.md) · [Concurrent publication](../toolchain-and-collaboration/RT-24/RT-24-CONCURRENT-PUBLICATION-COST-2026-11-25.md)

## Reproduction

Use CPython 3.12.14. This replays the statistics over committed measurements. Each source report records how to collect fresh samples.

```sh
study=research/research-management/SCALABILITY-METRICS-01
build=$(mktemp -d)
for seed in 37 75; do
  LC_ALL=C PYTHONHASHSEED="$seed" python "$study/run.py" --output "$build/result-$seed.json"
done
cmp "$build/result-37.json" "$build/result-75.json"
cmp "$build/result-37.json" "$study/evidence.json"
```

[Reducer](SCALABILITY-METRICS-01/run.py) · [Pinned sources and exact statistics](SCALABILITY-METRICS-01/evidence.json)
