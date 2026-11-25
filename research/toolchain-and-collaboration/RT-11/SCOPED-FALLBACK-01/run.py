#!/usr/bin/env python3
"""Compare dependency-unknown fallback policies in a finite action graph."""

from collections import Counter
from itertools import product
import json
from pathlib import Path
import platform
from hashlib import sha256

SIDES = ("left", "right")
EVIDENCE = ("complete", "stale", "unknown")
POLICIES = ("optimistic", "whole_graph", "scoped")
BASE_VALUES = {"left": (5, 0), "right": (10, 0)}
NODES = ("left-body", "left-analysis", "left-emit", "right-body", "right-analysis", "right-emit", "package")


def baseline():
    cache = {}
    for side, (source, environment) in BASE_VALUES.items():
        body = source + environment
        analysis = body % 3
        cache[f"{side}-body"] = ((source, environment), body)
        cache[f"{side}-analysis"] = ((body,), analysis)
        cache[f"{side}-emit"] = ((analysis,), analysis + 20)
    emitted = cache["left-emit"][1], cache["right-emit"][1]
    cache["package"] = (emitted, emitted)
    return cache


def oracle(inputs):
    left = inputs["left"][0] + inputs["left"][1]
    right = inputs["right"][0] + inputs["right"][1]
    return {
        "left-body": left, "left-analysis": left % 3, "left-emit": 20 + (left % 3),
        "right-body": right, "right-analysis": right % 3, "right-emit": 20 + (right % 3),
        "package": (20 + (left % 3), 20 + (right % 3)),
    }


def required_certificate(side):
    return ("extractor/2", f"{side}-body", ("source", "environment"))


def certificates_for(labels):
    records = {}
    for side, label in zip(SIDES, labels, strict=True):
        required = required_certificate(side)
        records[side] = {
            "complete": required,
            "stale": ("extractor/1", required[1], ("source",)),
            "unknown": None,
        }[label]
    return records


def actions(inputs, certificates, can_execute, policy, cache):
    complete = {side: certificates[side] == required_certificate(side) for side in SIDES}
    force_all = policy == "whole_graph" and not all(complete.values())
    results = {}
    decisions = {}

    def derived(name, dependencies, transform):
        args = tuple(results[dependency] for dependency in dependencies)
        if None in args:
            results[name] = None
            decisions[name] = "blocked"
        elif not force_all and args == cache[name][0]:
            results[name] = cache[name][1]
            decisions[name] = "reuse"
        else:
            results[name] = transform(*args)
            decisions[name] = "compute"

    for side in SIDES:
        body = f"{side}-body"
        source, environment = inputs[side]
        old_dependencies, old_value = cache[body]
        if not force_all and complete[side] and (source, environment) == old_dependencies:
            results[body] = old_value
            decisions[body] = "reuse"
        elif policy == "optimistic" and not complete[side] and source == old_dependencies[0]:
            results[body] = old_value
            decisions[body] = "reuse_without_evidence"
        elif not can_execute[side]:
            results[body] = None
            decisions[body] = "blocked"
        else:
            results[body] = source + environment
            decisions[body] = "compute" if complete[side] else "compute_ephemeral"

        analysis = f"{side}-analysis"
        derived(analysis, (body,), lambda value: value % 3)
        derived(f"{side}-emit", (analysis,), lambda value: value + 20)
    derived("package", ("left-emit", "right-emit"), lambda left, right: (left, right))
    return results, decisions


def compare():
    cache = baseline()
    totals = {policy: Counter() for policy in POLICIES}
    witnesses = {}
    case_count = 0
    for left, right in product(product((0, 1), repeat=2), repeat=2):
        inputs = {
            "left": (BASE_VALUES["left"][0] + left[0], -left[1]),
            "right": (BASE_VALUES["right"][0] + right[0], -right[1]),
        }
        expected = oracle(inputs)
        for status in product(EVIDENCE, repeat=2):
            certificates = certificates_for(status)
            evidence_labels = dict(zip(SIDES, status, strict=True))
            for available in product((False, True), repeat=2):
                can_execute = dict(zip(SIDES, available, strict=True))
                case_count += 1
                outcomes = {policy: actions(inputs, certificates, can_execute, policy, cache) for policy in POLICIES}
                for policy, (values, decisions) in outcomes.items():
                    counters = totals[policy]
                    counters.update(decisions.values())
                    counters["stale_results"] += sum(values[node] is not None and values[node] != expected[node]
                                                     for node in NODES)
                    counters["packages_admitted"] += values["package"] is not None
                    counters["stale_packages"] += values["package"] is not None and values["package"] != expected["package"]
                    if policy != "optimistic":
                        for side in SIDES:
                            # Independently classify permission to produce the upstream result.
                            key_matches = inputs[side] == BASE_VALUES[side]
                            all_current = all(item == "complete" for item in status)
                            proved_hit = evidence_labels[side] == "complete" and key_matches
                            if policy == "whole_graph":
                                proved_hit = proved_hit and all_current
                            required_body = expected[f"{side}-body"] if can_execute[side] or proved_hit else None
                            for operation in ("body", "analysis", "emit"):
                                node = f"{side}-{operation}"
                                required = expected[node] if required_body is not None else None
                                if values[node] != required:
                                    raise AssertionError(f"Unexpected permission or blocking for {policy}, {node}")
                        package = expected["package"] if all(values[f"{side}-body"] is not None for side in SIDES) else None
                        if values["package"] != package:
                            raise AssertionError(f"Incorrect join admission for {policy}")
                optimistic, scoped = (outcomes[name] for name in ("optimistic", "scoped"))
                if optimistic[0]["package"] is not None and optimistic[0]["package"] != expected["package"]:
                    witnesses.setdefault("stale_package", (inputs, certificates, can_execute, optimistic, scoped))
                if (scoped[1]["left-body"] == "compute_ephemeral"
                        and scoped[1]["left-analysis"] == "reuse"
                        and inputs["left"] != BASE_VALUES["left"]
                        and scoped[0]["package"] == expected["package"]):
                    witnesses.setdefault("fresh_identical_input", (inputs, certificates, can_execute, scoped))
                if scoped[0]["left-body"] is None and scoped[1]["right-emit"] == "reuse":
                    witnesses.setdefault("unavailable_left_complete_right", (inputs, certificates, can_execute, scoped))
    if any(totals[policy]["stale_results"] for policy in ("whole_graph", "scoped")):
        raise AssertionError("A conservative policy produced a stale result")
    if len(witnesses) != 3:
        raise AssertionError("Did not observe all fallback discriminator cases")
    return {
        "schema": "llmlang-scoped-fallback/1", "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "case_count": case_count, "nodes": NODES, "baseline": cache,
        "required_certificates": {side: required_certificate(side) for side in SIDES},
        "policies": totals, "witnesses": witnesses,
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
