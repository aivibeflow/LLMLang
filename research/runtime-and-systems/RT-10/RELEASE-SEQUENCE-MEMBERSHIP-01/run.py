"""Derive release-sequence membership for a closed set of flag modifications."""

from itertools import permutations
import json
import platform


RELEASE = "writer-release"
SAME_STORE = "writer-relaxed"
OTHER_STORE = "other-relaxed"
RELAYS = ("relay-a-rmw", "relay-b-rmw")
WRITES = (RELEASE, SAME_STORE, OTHER_STORE, *RELAYS)


def scan(order, legacy):
    members = set()
    live = False
    flag_values = {}
    flag = 0
    for event in order:
        if event == RELEASE:
            live = True
        elif event not in RELAYS and not (legacy and event == SAME_STORE):
            live = False
        # The three stores write one. Each RMW adds zero to its immediate predecessor.
        if event not in RELAYS:
            flag = 1
        flag_values[event] = flag
        if live:
            members.add(event)
    return members, flag_values


def includes(order, read, legacy):
    if read == "init":
        return False
    head = order.index(RELEASE)
    tail = order.index(read)
    if tail < head:
        return False
    intervening = order[head + 1:tail + 1]
    candidates = set(RELAYS)
    if legacy:
        candidates.add(SAME_STORE)
    return set(intervening) <= candidates


def study():
    totals = {
        "orders": 0,
        "read_from_cases": 0,
        "edge_cpp17": 0,
        "edge_cpp20": 0,
        "edge_changes": 0,
        "numeric_false_positives_cpp17": 0,
        "numeric_false_positives_cpp20": 0,
    }
    controls = {}
    sequences = {
        "rmw_with_no_interrupt": ((RELEASE, *RELAYS, SAME_STORE, OTHER_STORE), RELAYS[1]),
        "same_writer_store_then_rmw": ((RELEASE, SAME_STORE, *RELAYS, OTHER_STORE), RELAYS[1]),
        "foreign_store_then_rmw": ((RELEASE, OTHER_STORE, *RELAYS, SAME_STORE), RELAYS[1]),
        "read_release_directly": ((OTHER_STORE, RELEASE, SAME_STORE, *RELAYS), RELEASE),
    }
    for order in permutations(WRITES):
        if order.index(RELEASE) > order.index(SAME_STORE):
            continue
        totals["orders"] += 1
        older_members, values = scan(order, legacy=True)
        newer_members, _ = scan(order, legacy=False)
        for read in ("init", *order):
            before = read in older_members
            after = read in newer_members
            assert before == includes(order, read, legacy=True)
            assert after == includes(order, read, legacy=False)
            value = values.get(read, 0)
            totals["read_from_cases"] += 1
            totals["edge_cpp17"] += before
            totals["edge_cpp20"] += after
            totals["edge_changes"] += before != after
            totals["numeric_false_positives_cpp17"] += value == 1 and not before
            totals["numeric_false_positives_cpp20"] += value == 1 and not after
            assert not after or before
            for case, selection in sequences.items():
                if (order, read) == selection:
                    controls[case] = {
                        "order": order,
                        "read_from": read,
                        "flag": value,
                        "edge_cpp17": before,
                        "edge_cpp20": after,
                        "payload_cpp17": [1] if before else [0, 1],
                        "payload_cpp20": [1] if after else [0, 1],
                    }

    assert totals["orders"] == 60 and totals["read_from_cases"] == 360
    assert len(controls) == len(sequences)
    assert controls["rmw_with_no_interrupt"]["edge_cpp20"]
    assert controls["same_writer_store_then_rmw"]["edge_cpp17"]
    assert not controls["same_writer_store_then_rmw"]["edge_cpp20"]
    assert not controls["foreign_store_then_rmw"]["edge_cpp17"]
    assert controls["read_release_directly"]["edge_cpp20"]
    assert all(row["flag"] == 1 for row in controls.values())
    return {"runtime": platform.python_version(), "totals": totals, "controls": controls}


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
