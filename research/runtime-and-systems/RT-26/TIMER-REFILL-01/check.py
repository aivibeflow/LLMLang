"""Check timer read windows and finite serialized two-child refill behavior."""
import argparse
import csv
from itertools import product
import json
from pathlib import Path


def formula(caps, current, ticks, demands):
    tokens = [min(cap, initial + ticks) for cap, initial in zip(caps, current)]
    return allocate(tokens, demands)


def allocate(tokens, demands):
    parent, first, second = tokens
    first_grant = min(parent, first, demands[0])
    second_grant = min(parent - first_grant, second, demands[1])
    return first_grant, second_grant


def reference(caps, current, ticks, demands):
    pools = [[None] * amount for amount in current]
    for _ in range(ticks):
        for pool, cap in zip(pools, caps):
            if len(pool) < cap:
                pool.append(None)
    grants = [0, 0]
    for index, demand in enumerate(demands):
        for _ in range(demand):
            child = pools[index + 1]
            if not pools[0] or not child:
                break
            pools[0].pop()
            child.pop()
            grants[index] += 1
    return tuple(grants)


def model():
    counts = {"states": 0, "collapsed_mismatches": 0, "uncapped_mismatches": 0}
    states = [(cap, initial) for cap in range(1, 4) for initial in range(cap + 1)]
    for parent, a, b in product(states, repeat=3):
        caps = (parent[0], a[0], b[0])
        current = (parent[1], a[1], b[1])
        for ticks, demand_a, demand_b in product(range(8), range(3), range(3)):
            candidates = ((caps, current, (demand_a, demand_b)),
                          ((caps[0], caps[2], caps[1]), (current[0], current[2], current[1]),
                           (demand_b, demand_a)))
            for limits, balances, demands in candidates:
                expected = reference(limits, balances, ticks, demands)
                actual = formula(limits, balances, ticks, demands)
                assert actual == expected
                assert sum(actual) <= limits[0]
                assert all(grant <= limit for grant, limit in zip(actual, limits[1:]))
                collapsed = formula(limits, balances, int(ticks > 0), demands)
                uncapped = allocate([initial + ticks for initial in balances], demands)
                counts["states"] += 1
                counts["collapsed_mismatches"] += collapsed != expected
                counts["uncapped_mismatches"] += uncapped != expected
    assert counts["states"] == 104_976
    assert counts["collapsed_mismatches"] > 0 and counts["uncapped_mismatches"] > 0
    return counts


def check_samples(path):
    counts = {}
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    seen = set()
    for row in rows:
        item = {key: int(value) for key, value in row.items()}
        repetition, target = item["repetition"], item["target_ticks"]
        assert (repetition, target) not in seen
        seen.add((repetition, target))
        period = item["period_ns"]
        before, after = item["before_read_ns"], item["after_read_ns"]
        ticks = item["expirations"]
        assert period == 20_000_000 and before <= after
        lower = max(0, 1 + before // period)
        upper = max(0, 1 + after // period)
        assert target <= lower <= ticks <= upper, item
        expected = reference((3, 2, 3), (0, 0, 0), ticks, (16, 16))
        capped = formula((3, 2, 3), (0, 0, 0), ticks, (16, 16))
        assert expected == capped
        naive = formula((3, 2, 3), (0, 0, 0), int(ticks > 0), (16, 16))
        uncapped = allocate([ticks] * 3, (16, 16))
        bucket = counts.setdefault(target, {"observations": 0, "seen_counts": set(),
                                            "collapsed_mismatches": 0, "uncapped_mismatches": 0})
        bucket["observations"] += 1
        bucket["seen_counts"].add(ticks)
        bucket["collapsed_mismatches"] += naive != expected
        bucket["uncapped_mismatches"] += uncapped != expected
    assert seen == set(product(range(1, 7), (1, 3, 6)))
    for bucket in counts.values():
        bucket["seen_counts"] = sorted(bucket["seen_counts"])
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timer_samples", type=Path)
    parser.add_argument("model_output", type=Path)
    args = parser.parse_args()
    print(json.dumps(check_samples(args.timer_samples), indent=2))
    args.model_output.write_text(json.dumps(model(), indent=2) + "\n")


if __name__ == "__main__":
    main()
