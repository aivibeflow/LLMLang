#!/usr/bin/env python3
"""Compare two-pass evidence admission with direct endpoint preservation."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
PROGRAMS = {
    "source": ((0, ("read", "write")), (1, ("write",))),
    "equivalent_copy": ((0, ("read", "write")), (1, ("write",))),
    "reorder": ((0, ("write", "read")), (1, ("write",))),
    "wrong_result": ((0, ("read", "write")), (0, ("write",))),
    "undefined_last": ((0, ("read", "write")), None),
    "undefined_first": (None, (1, ("write",))),
    "extra_effect": ((0, ("read", "write")), (1, ("write", "read"))),
    "both_different": ((1, ("write", "read")), (0, ("write", "read"))),
}
ARTIFACT_IDS = {
    key: sha256(json.dumps([key, observations], separators=(",", ":")).encode()).hexdigest()
    for key, observations in PROGRAMS.items()
}
DOMAINS = range(1, 4)
PROFILES = ("return_only", "complete")


def preserves(source, target, domain, profile):
    for input_index in range(2):
        if not domain & (1 << input_index):
            continue
        left, right = PROGRAMS[source][input_index], PROGRAMS[target][input_index]
        if left is None or right is None:
            return False
        if profile == "return_only":
            left, right = left[0], right[0]
        if left != right:
            return False
    return True


def compare():
    truths = {
        args: preserves(*args) for args in product(PROGRAMS, PROGRAMS, DOMAINS, PROFILES)
    }
    counts = Counter()
    witnesses = {}
    for source, first_mid, second_mid, target in product(PROGRAMS, repeat=4):
        for left_dom, right_dom, left_profile, right_profile in product(
            DOMAINS, DOMAINS, PROFILES, PROFILES
        ):
            if not (truths[source, first_mid, left_dom, left_profile] and
                    truths[second_mid, target, right_dom, right_profile]):
                continue
            for requested in DOMAINS:
                identity = ARTIFACT_IDS[first_mid] == ARTIFACT_IDS[second_mid]
                guard = requested & ~(left_dom & right_dom) == 0
                scope = left_profile == right_profile == "complete"
                bridge = truths[first_mid, second_mid, requested, "complete"]
                exact = truths[source, target, requested, "complete"]
                routes = {
                    "exact_chain": identity and guard and scope,
                    "checked_bridge": bridge and guard and scope,
                    "ignore_midpoint": guard and scope,
                    "ignore_guard": identity and scope,
                    "ignore_scope": identity and guard,
                    "locally_valid_only": True,
                }

                counts["locally_valid_chains"] += 1
                for route, accepts in routes.items():
                    counts[f"{route}_admitted"] += accepts
                    counts[f"{route}_false_admissions"] += accepts and not exact
                    if accepts and not exact:
                        witnesses.setdefault(route, {
                            "artifacts": [source, first_mid, second_mid, target],
                            "receipt_domains": [left_dom, right_dom], "requested": requested,
                            "receipt_profiles": [left_profile, right_profile],
                            "excluded_by": [name for name, holds in (
                                ("identity", identity), ("guard", guard), ("scope", scope)) if not holds],
                        })
                counts["valid_bridge_with_distinct_identity"] += routes["checked_bridge"] and not identity
    assert counts["exact_chain_false_admissions"] == counts["checked_bridge_false_admissions"] == 0
    assert witnesses.keys() == {"ignore_midpoint", "ignore_guard", "ignore_scope", "locally_valid_only"}
    return counts, witnesses


if __name__ == "__main__":
    counts, witnesses = compare()
    print(json.dumps({
        "schema": "llmlang-compiler-pass-composition/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Chain.lean", "axioms.txt")},
        "artifacts": {key: {"observations": observations,
                            "sha256": ARTIFACT_IDS[key]}
                      for key, observations in PROGRAMS.items()},
        "counts": counts, "first_witnesses": witnesses,
    }, indent=2))
