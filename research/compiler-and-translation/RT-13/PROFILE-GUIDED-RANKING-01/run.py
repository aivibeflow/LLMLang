"""Check bounded, profile-specific cost ranking against exhaustive cost scenarios."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCOPE = ("checked-add/v1", "linux-x86_64-sysv", "host-A", "elapsed-us")
BUCKETS = ("short", "long")
MARGIN = 2


@dataclass(frozen=True)
class Receipt:
    artifact: str
    scope: tuple[str, ...]
    costs: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Candidate:
    name: str
    artifact: str
    eligible: bool
    switch: int
    receipt: Receipt | None


BASELINE = Candidate("baseline", "artifact-B", True, 0, Receipt("artifact-B", SCOPE, ((7, 9), (10, 13))))
SHORT = Candidate("short-specialized", "artifact-S", True, 5, Receipt("artifact-S", SCOPE, ((3, 4), (13, 15))))
LONG = Candidate("long-specialized", "artifact-L", True, 9, Receipt("artifact-L", SCOPE, ((8, 10), (4, 6))))


def cost_range(candidate, weights):
    receipt = candidate.receipt
    if receipt is None or (receipt.artifact, receipt.scope) != (candidate.artifact, SCOPE):
        return None
    if len(receipt.costs) != len(weights) or any(lo < 0 or hi < lo for lo, hi in receipt.costs):
        return None
    lo = sum(weight * bound[0] for weight, bound in zip(weights, receipt.costs, strict=True))
    hi = sum(weight * bound[1] for weight, bound in zip(weights, receipt.costs, strict=True))
    return lo + candidate.switch, hi + candidate.switch


def choose(baseline, candidates, weights):
    if len(weights) != len(BUCKETS) or not any(weights) or any(weight < 0 for weight in weights):
        return "invalid-workload-mix", None
    if not baseline.eligible:
        return "no-eligible-baseline", None
    current = cost_range(baseline, weights)
    if current is None:
        return "baseline-missing-comparable-cost", baseline.name
    ranked = []
    for candidate in candidates:
        if not candidate.eligible:
            continue
        predicted = cost_range(candidate, weights)
        if predicted is not None and predicted[1] + MARGIN < current[0]:
            ranked.append((predicted[1], candidate.artifact, candidate.name))
    if not ranked:
        return "baseline-retained", baseline.name
    return "bounded-improvement", min(ranked)[2]


def realized(receipt, weights):
    return {sum(w * n for w, n in zip(weights, point, strict=True)) for point in product(*receipt.costs)}


def oracle(baseline, candidates, weights, states):
    if states[0] == "ineligible":
        return "no-eligible-baseline", None
    if states[0] == "missing":
        return "baseline-missing-comparable-cost", baseline.name
    current = realized(baseline.receipt, weights)
    improves = []
    for candidate, state in zip(candidates, states[1:], strict=True):
        if state == "exact":
            scenarios = {cost + candidate.switch for cost in realized(candidate.receipt, weights)}
            if all(new + MARGIN < old for old, new in product(current, scenarios)):
                improves.append((max(scenarios), candidate.artifact, candidate.name))
    if not improves:
        return "baseline-retained", baseline.name
    return "bounded-improvement", min(improves)[2]


def edit(candidate, kind):
    if kind == "exact":
        return candidate
    if kind == "missing":
        return replace(candidate, receipt=None)
    if kind == "ineligible":
        return replace(candidate, eligible=False)
    if kind == "other-artifact":
        return replace(candidate, receipt=replace(candidate.receipt, artifact="stale-artifact"))
    if kind == "malformed":
        return replace(candidate, receipt=replace(candidate.receipt, costs=((4, 3), (5, 2))))
    return replace(candidate, receipt=replace(candidate.receipt, scope=(*SCOPE[:2], "host-B", SCOPE[-1])))


def matrix():
    counts = Counter()
    examples = {}
    options = ("exact", "missing", "ineligible", "other-artifact", "other-scope", "malformed")
    mixes = [(short, long) for short, long in product((0, 1, 4, 16, 64), repeat=2) if short or long]
    for mix, baseline_state, short_state, long_state in product(mixes, options[:3], options, options):
        states = (baseline_state, short_state, long_state)
        baseline, short, long = [edit(candidate, state) for candidate, state in
                                 zip((BASELINE, SHORT, LONG), states, strict=True)]
        expected = oracle(baseline, (short, long), mix, states)
        observed = choose(baseline, (short, long), mix)
        if observed != expected:
            raise ValueError((mix, states, observed, expected))
        if choose(baseline, (long, short), mix) != observed:
            raise ValueError("ranking depended on enumeration order")
        outcome, chosen = observed
        counts["cases"] += 1
        counts[outcome] += 1
        if chosen is not None:
            counts[chosen] += 1
        if states == ("exact", "exact", "exact"):
            examples[f"{mix[0]}/{mix[1]}"] = {
                "selected": chosen,
                "bounds_with_switch_cost": {
                    candidate.name: cost_range(candidate, mix) for candidate in (baseline, short, long)
                },
            }
    tie_a, tie_b = [replace(SHORT, name=name, artifact=artifact,
                           receipt=replace(SHORT.receipt, artifact=artifact))
                    for name, artifact in (("a", "second"), ("b", "first"))]
    tie = choose(BASELINE, (tie_b, tie_a), (16, 0))
    if tie != ("bounded-improvement", "b") or choose(BASELINE, (tie_a, tie_b), (16, 0)) != tie:
        raise ValueError("tie was not resolved by stable identity")
    invalid = [choose(BASELINE, (SHORT, LONG), mix) for mix in ((), (0, 0), (-1, 1))]
    if invalid != [("invalid-workload-mix", None)] * 3:
        raise ValueError("an invalid workload mix was accepted")
    return dict(counts), examples, {"stable_tie": tie, "invalid_weights": invalid}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    counts, examples, controls = matrix()
    receipt = {
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "cost_data_kind": "synthetic interval estimates", "scope": SCOPE, "buckets": BUCKETS,
        "margin": MARGIN, "counts": counts, "mix_examples": examples, "controls": controls,
    }
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
