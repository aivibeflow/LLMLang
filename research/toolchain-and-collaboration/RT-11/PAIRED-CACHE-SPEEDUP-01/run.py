#!/usr/bin/env python3
"""Recompute the analytical cache table and analyze exact pairs from the timing ledger."""

from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import platform
from statistics import median
import subprocess

ROOT = Path(__file__).resolve().parents[4]
BASELINE = "bbfb97ac4e4cf659d8fdcedebe8279325ed7659f"
RT11 = "research/toolchain-and-collaboration/RT-11"
THEORY = f"{RT11}/COMPILATION-CACHE-SPEEDUP-ESTIMATE.md"
TIMINGS = f"{RT11}/COMPILE-CACHE-TIMINGS-01/evidence.json"
BASELINES = ("clean", "incremental")


def archive(path):
    command = ["git", "show", f"{BASELINE}:{path}"]
    return subprocess.run(command, cwd=ROOT, check=True, capture_output=True, timeout=20).stdout


def table(section):
    return [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in section.splitlines() if line.startswith("|")][2:]


def number(cell):
    return Decimal(cell.strip("*").removesuffix("%").removesuffix("×"))


def analytical(markdown):
    stages = table(markdown.split("## 3.", 1)[1].split("## 4.", 1)[0])
    weights = {name: number(weight) / 100 for name, weight in stages}
    if weights.pop("**Total**", None) != Decimal(1) or sum(weights.values()) != 1:
        raise AssertionError(weights)
    reuse = table(markdown.split("## 4.", 1)[1].split("## 5.", 1)[0])
    fractions = {row[0]: [number(value) / 100 for value in row[1:]] for row in reuse}
    if fractions.keys() != weights.keys() or any(len(values) != 3 for values in fractions.values()):
        raise AssertionError(fractions)
    assumptions = dict(zip(("Local edit", "Component edit", "Repeated identical build", "Cold build"),
                           [*(sum(weight * fractions[stage][index] for stage, weight in weights.items())
                              for index in range(3)), Decimal(0)]))
    printed = table(markdown.split("## 5.", 1)[1].split("## 6.", 1)[0])
    actual = {}
    for row in printed:
        scenario, avoided, *speedups = row
        work = assumptions[scenario]
        estimated = [(1 / (1 - work + Decimal(overhead) / 100)).quantize(Decimal(".01"))
                     for overhead in (1, 2, 4)]
        if work * 100 != number(avoided) or estimated != list(map(number, speedups)):
            raise AssertionError((scenario, work, estimated, row))
        actual[scenario] = {"avoided_work_percent": str((work * 100).quantize(Decimal(".01"))),
                            "speedups_at_1_2_4_percent_overhead": list(map(str, estimated))}
    if set(actual) != assumptions.keys():
        raise AssertionError(actual)
    return actual


def statistics(rows, field):
    values = [row[field] for row in rows]
    return {"median": median(values), "min": min(values), "max": max(values)}


def observed(timings):
    by_group = defaultdict(dict)
    for row in timings["samples"]:
        group = by_group[(row["stage"], row["trial"])]
        method = row["method"]
        if method in group:
            raise AssertionError("Duplicate method in one source timing block")
        group[method] = row
    results = {}
    units = timings["translation_units"]
    expected_pairs = timings["repetitions"]
    for stage in timings["input_shape"]:
        pairs = []
        for trial in range(expected_pairs):
            group = by_group[(stage, trial)]
            if set(group) != {"clean", "incremental", "content"}:
                raise AssertionError((stage, trial, group.keys()))
            if len({row["manifest_sha256"] for row in group.values()}) != 1:
                raise AssertionError((stage, trial, "Nonidentical build output"))
            if len({row["order"] for row in group.values()}) != 3:
                raise AssertionError((stage, trial, "Different methods should have different positions"))
            clean, content = group["clean"], group["content"]
            if clean["compiler_invocations"] != units or content["compiler_invocations"] + content["cache_hits"] != units:
                raise AssertionError((stage, trial, "Unexpected action count"))
            elapsed = {method: row["elapsed_ns"] for method, row in group.items()}
            actual_time = elapsed["content"]
            overhead = content["key_lookup_verify_materialize_ns"]
            if actual_time <= 0 or not 0 <= overhead <= actual_time:
                raise AssertionError((stage, trial, "Invalid measured time"))
            estimate = elapsed["clean"] * content["compiler_invocations"] / units + overhead
            pairs.append({
                "trial": trial, "elapsed_ns": elapsed,
                "speedup_vs_clean": elapsed["clean"] / actual_time,
                "speedup_vs_incremental": elapsed["incremental"] / actual_time,
                "fixed_cost_per_action_estimate_ns": estimate,
                "prediction_residual_ms": (estimate - actual_time) / 1e6,
                "manifest_sha256": content["manifest_sha256"],
            })
        summary = {}
        for baseline in BASELINES:
            field = f"speedup_vs_{baseline}"
            summary[baseline] = {
                **statistics(pairs, field),
                "slower": sum(row[field] < 1 for row in pairs),
                "faster": sum(row[field] > 1 for row in pairs),
            }
        results[stage] = {"comparisons": summary,
                          "prediction_residual_ms": statistics(pairs, "prediction_residual_ms"), "pairs": pairs}
    if len(by_group) != len(results) * expected_pairs:
        raise AssertionError("Unrecognized timing block")
    return results


def run():
    theory, timing_raw = map(archive, (THEORY, TIMINGS))
    timings = json.loads(timing_raw)
    return {
        "schema": "llmlang-paired-cache-speedup/1", "baseline": BASELINE, "python": platform.python_version(),
        "inputs_sha256": {THEORY: sha256(theory).hexdigest(), TIMINGS: sha256(timing_raw).hexdigest()},
        "toolchain": timings["toolchain"], "host": timings["host"], "trials_per_stage": timings["repetitions"],
        "analytical": analytical(theory.decode("utf-8")), "paired": observed(timings),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
