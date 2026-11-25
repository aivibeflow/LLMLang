"""Recompute selected scalability metrics from committed trial ledgers."""

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from statistics import median, quantiles


HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[1]
RESAMPLES = 5000
SEED = 332
SOURCES = {
    "graph": "semantic-representation/RT-05/REVERSE-TRAVERSAL-01",
    "encoding": "semantic-representation/RT-05/CANONICAL-HASH-COST-01",
    "impact": "semantic-representation/RT-06/IMPACT-PLANNING-BENCHMARK-01",
    "build": "toolchain-and-collaboration/RT-11/PERSISTENT-BUILD-CACHE-01",
    "proof": "formal-verification/PROOF-OBLIGATION-BENCHMARK/PROOF-AND-TEST-COST-01",
    "gc": "toolchain-and-collaboration/RT-27/SQLITE-RETENTION-BENCHMARK-01",
    "large": "toolchain-and-collaboration/RT-27/LARGE-GIT-GRAPH-BENCHMARK-01",
    "publication": "toolchain-and-collaboration/RT-24/CONCURRENT-PUBLICATION-BENCHMARK-01",
}
BYTES_PER_MIB = 1024 * 1024


def read_ledger(source):
    evidence = RESEARCH / source / "evidence"
    path = evidence / "samples.csv"
    digest = sha256(path.read_bytes()).hexdigest()
    summary = json.loads((evidence / "summary.json").read_text())
    if digest != summary.get("samples_sha256", summary.get("sample_sha256")):
        raise ValueError(f"samples are detached from the study summary: {source}")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    config = json.loads((evidence / "config.json").read_text())
    return rows, {
        "samples": str(path.relative_to(RESEARCH)), "samples_sha256": digest,
        "config_sha256": sha256((evidence / "config.json").read_bytes()).hexdigest(),
        "summary_sha256": sha256((evidence / "summary.json").read_bytes()).hexdigest(),
        "trials_per_profile": config["trials"], "rows": len(rows),
        "cpu_model": config["cpu_model"], "kernel": config["kernel"],
    }


def select(rows, **conditions):
    chosen = [row for row in rows if all(row[key] == str(value) for key, value in conditions.items())]
    if len(chosen) < 2:
        raise ValueError(f"missing repeated samples for {conditions}")
    return chosen


def metric(rows, value, unit, random):
    samples = [value(row) for row in rows]
    if any(sample <= 0 for sample in samples):
        raise ValueError((unit, samples))
    draws = [median(random.choices(samples, k=len(samples))) for _ in range(RESAMPLES)]
    interval = quantiles(draws, n=40, method="inclusive")
    deciles = quantiles(samples, n=10, method="inclusive")
    return {
        "unit": unit, "n": len(samples), "median": median(samples),
        "p10_p90": [deciles[0], deciles[-1]],
        "median_bootstrap_95_interval": [interval[0], interval[-1]],
    }


def integer(row, field):
    return int(row[field])


def collect():
    sources = {name: read_ledger(path) for name, path in SOURCES.items()}
    graph = select(sources["graph"][0], shape="layered-eight", nodes=8192)
    encoding = select(sources["encoding"][0], shape="nested", entries_per_object=512)
    impact = select(sources["impact"][0], shape="hot", active_callers=1024)
    build = select(sources["build"][0], phase="restored")
    proof = select(sources["proof"][0], profile="mapping-ipc", mode="proof")
    tests = select(sources["proof"][0], profile="mapping-ipc", mode="test")
    gc = select(sources["gc"][0], variant="indexed", objects=8192)
    git = select(sources["large"][0], degree=32)
    publication = select(sources["publication"][0], writers=8, shape="independent", policy="exact-projection")
    rng = Random(SEED)
    metrics = {
        "graph_retained_index_memory": metric(graph, lambda r: integer(r, "live_index_bytes") / BYTES_PER_MIB, "MiB", rng),
        "graph_query_speedup_including_index": metric(graph, lambda r: integer(r, "rebuild_batch_ns") /
            (integer(r, "retained_batch_ns") + integer(r, "index_ns")), "ratio", rng),
        "nested_payload_encode_latency": metric(encoding, lambda r: integer(r, "encode_ns") /
            integer(r, "invocations_per_scope") / 1000, "us/object", rng),
        "nested_payload_encode_rate": metric(encoding, lambda r: 1e9 * integer(r, "invocations_per_scope") /
            integer(r, "encode_ns"), "objects/s", rng),
        "grouped_impact_plan_latency": metric(impact, lambda r: integer(r, "grouped_plan_ns") / 1e6, "ms", rng),
        "restored_build_process_latency": metric(build, lambda r: integer(r, "process_ns") / 1e6, "ms", rng),
        "proof_child_peak_rss": metric(proof, lambda r: integer(r, "peak_kib") / 1024, "MiB", rng),
        "finite_oracle_peak_rss": metric(tests, lambda r: integer(r, "peak_kib") / 1024, "MiB", rng),
        "indexed_collection_rate": metric(gc, lambda r: 1e9 * integer(r, "removed") /
            integer(r, "collect_ns"), "removed objects/s", rng),
        "dense_graph_verification_rate": metric(git, lambda r: 1e9 * integer(r, "edges") /
            integer(r, "verify_ns"), "decoded edges/s", rng),
        "eight_writer_publication_rate": metric(publication, lambda r: 1e9 * integer(r, "commits") /
            integer(r, "batch_ns"), "commits/s", rng),
    }
    cache_counts = {}
    for phase in ("cold", "restored", "policy-changed"):
        rows = select(sources["build"][0], phase=phase)
        hits = sum(integer(row, "hits") for row in rows)
        actions = 10 * len(rows)
        cache_counts[phase] = {"trials": len(rows), "hits": hits, "actions": actions, "fraction": hits / actions}
    if [row["fraction"] for row in cache_counts.values()] != [0.0, 1.0, 0.9]:
        raise ValueError("cache counts do not match the pinned action model")
    return {
        "sources": {source: archive for source, (_, archive) in sources.items()},
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "bootstrap": {"seed": SEED, "resamples": RESAMPLES, "unit": "recorded trial within one profile"},
        "metrics": metrics, "exact_observed_cache_counts": cache_counts,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(), indent=2, sort_keys=True) + "\n")
