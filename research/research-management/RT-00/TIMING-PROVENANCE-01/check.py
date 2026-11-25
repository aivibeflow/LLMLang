"""Audit timing units and provenance from immutable Git evidence, without retiming."""

from collections import defaultdict
import csv
from hashlib import sha256
from io import StringIO
import json
from statistics import median, quantiles
import subprocess


REVISION = "f02265dd33de654ebeca57e57646ad267f0bd2f5"
SEMANTIC = "research/semantic-representation"
CORE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src"
RT11 = "research/toolchain-and-collaboration/RT-11"
RT13 = "research/compiler-and-translation/RT-13"
RT25 = "research/runtime-and-systems/RT-25"


def read(path, revision=REVISION):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"])


def obj(path, revision=REVISION):
    return json.loads(read(path, revision))


def sample_csv(path):
    raw = read(path)
    return list(csv.DictReader(StringIO(raw.decode()))), sha256(raw).hexdigest()


def sources(identities, paths, revision=REVISION):
    assert identities.keys() == paths.keys()
    for label, path in paths.items():
        assert sha256(read(path, revision)).hexdigest() == identities[label], path
    return len(paths)


def stats(values):
    p10, *_, p90 = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": p10, "p90": p90}


def grouped(rows, keys):
    result = defaultdict(list)
    for row in rows:
        result["/".join(str(row[key]) for key in keys)].append(row)
    return result


def semantic_csv(section, study, profile_fields, keys, normalize=None):
    path = f"{SEMANTIC}/{section}/{study}"
    config = obj(f"{path}/evidence/config.json")
    summary = obj(f"{path}/evidence/summary.json")
    raw, digest = sample_csv(f"{path}/evidence/samples.csv")
    assert digest == summary["samples_sha256"]
    paths = {name: (f"{path}/{name}" if name == "measure.py" else f"{CORE}/{name}")
             for name in config["source_sha256"]}
    identity_count = sources(config["source_sha256"], paths)
    groups = grouped(raw, profile_fields)
    assert len(groups) == 6 and groups.keys() == summary["profiles"].keys()
    assert config.get("cpu_counter_delta", config.get("counter_delta"))["nr_throttled"] == 0
    for profile, trial in groups.items():
        assert len(trial) == config["trials"] == 10
        recorded = summary["profiles"][profile]
        if normalize:
            assert {int(row[normalize]) for row in trial} == {recorded[normalize]} == {64}
            recorded = recorded["phase_ns_per_object"]
        for key in keys:
            values = [int(row[f"{key}_ns"]) / int(row[normalize]) if normalize else int(row[key])
                      for row in trial]
            assert min(values) > 0
            assert recorded[key] == {**stats(values), "n": len(values)}
    return {"rows": len(raw), "compared_series": len(groups) * len(keys), "source_digests": identity_count,
            "reported_denominator": 64 if normalize else 1,
            "reported_unit": "ns per object" if normalize else "ns per phase",
            "host": [config[key] for key in ("cpu", "cpu_model", "kernel", "python")]}


def dispatch():
    path = f"{RT13}/DISPATCH-TIMING-01"
    e = obj(f"{path}/evidence.json")
    raw, digest = sample_csv(f"{path}/samples.csv")
    sources_count = sources(e["source_sha256"], {path: path for path in e["source_sha256"]})
    profiles = grouped(raw, ("workload", "adapter"))
    assert len(profiles) == 10
    for series in profiles.values():
        assert {int(row["trial"]) for row in series} == set(range(1, 8))
        for row in series:
            assert int(row["elapsed_ns"]) > 0 and int(row["calls"]) == e["calls_per_trial"]
            assert int(row["checksum"]) == e["checked_workloads"][row["workload"]]["timed_checksum"]
    assert e["calls_per_trial"] == 524288 and e["warmup_calls"] == 16384
    assert e["clock"] in read(f"{path}/measure.c").decode() and e["gomaxprocs"] == 1
    return {"rows": len(raw), "source_digests": sources_count, "sample_digest": digest,
            "calls_per_timed_interval": e["calls_per_trial"], "reported_unit": "ns per call",
            "host": {key: e[key] for key in ("cpu", "cpu_name", "machine", "kernel", "clock")},
            "toolchain": e["toolchain"], "runner_python_archived": "python" in e}


def allocator():
    path = f"{RT25}/ALLOCATOR-CONCURRENT-01"
    e = obj(f"{path}/evidence.json")
    sources_count = sources(e["sources_sha256"], {
        "compatibility_probe": "research/runtime-and-systems/PROTOTYPES/ALLOCATOR-COMPAT-01/probe.rs",
        "probe.rs": f"{path}/probe.rs", "run.py": f"{path}/run.py",
    })
    groups = grouped(e["samples"], ("provider", "producers"))
    assert len(groups) == 10 and groups.keys() == e["summary"].keys()
    assert e["counter_delta_churn_only"]["nr_throttled"] == 0
    assert "start.elapsed().as_nanos()" in read(f"{path}/probe.rs").decode()
    for profile, rows in groups.items():
        assert len(rows) == e["trials"] == 10
        assert all(row["count"] == 1024 * row["producers"] for row in rows)
        for metric in ("elapsed_ns", "peak_kib", "after_drop_kib"):
            values = [row[metric] for row in rows]
            assert e["summary"][profile][metric] == {**stats(values), "n": len(values)}
    return {"rows": len(e["samples"]), "compared_series": 3 * len(groups), "source_digests": sources_count,
            "packets_per_interval": sorted({row["count"] for row in e["samples"]}),
            "reported_unit": "µs per completed packet",
            "host": [e[key] for key in ("cpu", "cpu_model", "kernel", "python")], "rustc": e["rustc"]}


def channels():
    base = f"{SEMANTIC}/RT-35"
    path = f"{base}/CHANNEL-COST-01"
    e = obj(f"{path}/evidence.json")
    source_count = sources(e["sources"], {"fixture": f"{base}/SCOPED-RETRIEVAL-01/run.py",
                                         "measure.py": f"{path}/measure.py"})
    runner = read(f"{path}/measure.py").decode()
    assert "queries = exact_queries" in runner and 'append(elapsed / 200)' in runner
    count = 0
    for channel, profiles in e["raw_samples"].items():
        for metric, values in profiles.items():
            assert len(values) == e["blocks"] and e["summary"][channel][metric] == stats(values)
            count += len(values)
    return {"rows": count, "compared_series": 2 * len(e["raw_samples"]), "source_digests": source_count,
            "queries_per_batch": e["query_count"], "updates_per_average": 200,
            "host": [e[key] for key in ("cpu", "cpu_model", "kernel", "python")],
            "cgroup_throttle_archived": "cpu_counter_delta" in e}


def cache():
    path = f"{RT11}/PAIRED-CACHE-SPEEDUP-01"
    e = obj(f"{path}/evidence.json")
    source_path = f"{RT11}/COMPILE-CACHE-TIMINGS-01"
    producer = read(f"{source_path}/run.py", e["baseline"]).decode()
    t = obj(f"{source_path}/evidence.json", e["baseline"])
    source_count = sources(e["inputs_sha256"], {p: p for p in e["inputs_sha256"]}, e["baseline"])
    assert e["host"] == t["host"] and e["toolchain"] == t["toolchain"]
    assert '"logical_cpu": os.cpu_count()' in producer and "os.sched_setaffinity" not in producer
    assert '"affinity": sorted(os.sched_getaffinity(0))' in producer
    raw = grouped(t["samples"], ("stage", "trial"))
    assert len(raw) == 35
    for stage, data in e["paired"].items():
        assert len(data["pairs"]) == e["trials_per_stage"] == t["repetitions"]
        for pair in data["pairs"]:
            source = raw[f"{stage}/{pair['trial']}"]
            elapsed = {row["method"]: row["elapsed_ns"] for row in source}
            assert len(source) == 3 and pair["elapsed_ns"] == elapsed
            for reference in ("clean", "incremental"):
                assert pair[f"speedup_vs_{reference}"] == elapsed[reference] / elapsed["content"]
    return {"rows": len(t["samples"]), "paired_blocks": len(raw), "baseline": e["baseline"],
            "source_digests": source_count, "host": e["host"], "toolchain": e["toolchain"],
            "logical_cpu_meaning": "os.cpu_count() reported count", "cpu_pinned_by_runner": False}


def run():
    return {"revision": REVISION, "studies": {
        "RT-05": semantic_csv("RT-05", "CANONICAL-HASH-COST-01", ("shape", "entries_per_object"),
                              ("encode", "hash", "encode_hash", "retained_hash"), "invocations_per_scope"),
        "RT-06": semantic_csv("RT-06", "IMPACT-PLANNING-BENCHMARK-01", ("shape", "active_callers"),
                              ("discovery_ns", "audit_ns", "bind_ns", "baseline_plan_ns", "grouped_plan_ns")),
        "RT-11": cache(), "RT-13": dispatch(), "RT-25": allocator(), "RT-35": channels(),
    }}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, ensure_ascii=False))
