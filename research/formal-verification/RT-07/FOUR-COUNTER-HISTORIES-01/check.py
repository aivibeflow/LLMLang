"""Compare all four-participant complete histories for one C11 increment contract."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ORIGINAL = HERE.parent / "DAFNY-CONCURRENT-FRAME-HISTORY-01"
BASE = "95a2a64c38b217f97874c0712a196fa2466894e6"
ACTORS = 4
VALUES = (0, 1, (1 << 32) - 1 - ACTORS)


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def pinned_fixtures():
    inputs = {}
    for name in ("run.py", "counter.c"):
        path = ORIGINAL / name
        relative = str(path.relative_to(REPO))
        blob = git("rev-parse", f"{BASE}:{relative}")
        if git("hash-object", relative) != blob:
            raise ValueError(f"Changed pinned source: {relative}")
        inputs[relative] = blob
    return inputs


def load():
    spec = importlib.util.spec_from_file_location("previous_counter", ORIGINAL / "run.py")
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    return model


def interval_witness(base, events, state, observed):
    """Use each reply's unique sequential rank and check interval precedence."""
    if state != base + ACTORS or len(observed) != ACTORS:
        return None
    if any(old + 1 != reply for old, reply in observed):
        return None
    ranks = [reply - base - 1 for _, reply in observed]
    if set(ranks) != set(range(ACTORS)):
        return None
    positions = {event: index for index, event in enumerate(events)}
    if any(positions[2 * left + 1] < positions[2 * right] and ranks[left] > ranks[right]
           for left, right in product(range(ACTORS), repeat=2)):
        return None
    return sorted(range(ACTORS), key=ranks.__getitem__)


def controls():
    events = tuple(range(2 * ACTORS))
    valid = [(i, i + 1) for i in range(ACTORS)]
    assert interval_witness(0, events, ACTORS, valid) == list(range(ACTORS))
    outcomes = {
        "same_final_swapped_nonoverlapping_calls": [valid[1], valid[0], *valid[2:]],
        "same_final_duplicate_rank": [valid[0], valid[0], *valid[2:]],
        "same_final_forged_prior_value": [(1, valid[0][1]), *valid[1:]],
    }
    assert all(interval_witness(0, events, ACTORS, record) is None for record in outcomes.values())
    return {name: {"same_final": ACTORS, "observed_pairs": record, "refused": True}
            for name, record in outcomes.items()}


def audit(work):
    pin = pinned_fixtures()
    baseline = load()
    source = (ORIGINAL / "counter.c").read_text()
    assert source.count("MAX_ACTORS = 3") == 1
    adapted = source.replace("MAX_ACTORS = 3", "MAX_ACTORS = 4")
    path = work / "counter.c"
    path.write_text(adapted)
    orders = baseline.orders(ACTORS)
    assert len(orders) == 2520
    cases = list(product(VALUES, orders))
    request = "".join(" ".join(map(str, (ACTORS, value, *events))) + "\n" for value, events in cases)
    gcc = Path(shutil.which("gcc")).resolve()
    options = ("-std=c11", "-Wall", "-Wextra", "-Werror", "-pthread")
    profiles = {}
    for optimization in ("-O0", "-O2"):
        baseline.run(work, gcc, *options, optimization, "counter.c", "-o", "counter")
        results = {}
        for route in ("split", "rmw"):
            process = baseline.run(work, "./counter", route, data=request)
            counts = {value: Counter() for value in VALUES}
            witnesses = {}
            for (value, events), row in zip(cases, process.stdout.splitlines(), strict=True):
                final, *items = map(int, row.split())
                assert len(items) == 2 * ACTORS
                pairs = list(zip(items[::2], items[1::2], strict=True))
                outcome = {"state": final, "prior_values": items[::2], "replies": items[1::2]}
                assert outcome == baseline.simulate(value, ACTORS, events, route)
                witness = interval_witness(value, events, final, pairs)
                assert witness == baseline.serial_witness(value, ACTORS, events, outcome)
                row_counts = counts[value]
                row_counts["linearizable" if witness is not None else "refused"] += 1
                row_counts["correct_final" if final == value + ACTORS else "wrong_final"] += 1
                if witness is None and str(value) not in witnesses:
                    witnesses[str(value)] = {"events": events, "final": final, "per_actor": pairs}
            expected = {"linearizable": 2520, "correct_final": 2520} if route == "rmw" else {
                "linearizable": 24, "refused": 2496, "correct_final": 24, "wrong_final": 2496,
            }
            assert all(count == expected for count in counts.values())
            results[route] = {"counts_by_base": counts, "first_refusal_by_base": witnesses,
                              "native_output_sha256": sha256(process.stdout.encode()).hexdigest()}
        profiles[optimization] = results
    assert profiles["-O0"] == profiles["-O2"]
    return {
        "base": BASE, "source_blobs": pin, "compiler": baseline.run(work, gcc, "--version").stdout.splitlines()[0],
        "compiler_sha256": baseline.sha(gcc), "python": sys.version.split()[0],
        "host": {"machine": platform.machine(), "kernel": platform.release(),
                 "libc": subprocess.check_output(["getconf", "GNU_LIBC_VERSION"], text=True).strip()},
        "flags": options, "adapted_c_sha256": baseline.sha(path), "initial_values": VALUES,
        "schedules_per_initial_value": len(orders), "input_count_per_route_and_optimization": len(cases),
        "total_histories": len(cases) * len(profiles) * 2, "profiles": profiles,
        "request_sha256": sha256(request.encode()).hexdigest(), "controls": controls(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-counter-history-") as directory:
        evidence = audit(Path(directory))
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
