#!/usr/bin/env python3
"""Replay partial writes through a real pipe and compare declared observations."""

from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
MESSAGE = bytes.fromhex("4100ff4a20")


def attempt_model(length, boundaries, budget, limit, interrupt, drop_short):
    end_points = [i for i in range(1, length) if boundaries & (1 << (i - 1))]
    end_points.append(length)
    sent = bytearray()
    calls = []
    start = 0
    for end in end_points:
        offset = start
        while offset < end:
            requested = end - offset
            if interrupt:
                calls.append(f"{requested}:eintr")
                interrupt = False
                continue
            if budget == 0:
                calls.append(f"{requested}:eio")
                return "eio", bytes(sent), calls
            accepted = min(requested, limit, budget)
            calls.append(f"{requested}:{accepted}")
            sent.extend(MESSAGE[offset:offset + accepted])
            budget -= accepted
            if drop_short:
                break
            offset += accepted
        start = end
    return "ok", bytes(sent), calls


def execute(args, *, stdin=None):
    return subprocess.run(args, input=stdin, check=True, capture_output=True,
                          text=True, timeout=40).stdout


def check():
    rows = {}
    for length in range(len(MESSAGE) + 1):
        axes = (range(1 << max(0, length - 1)), range(length + 2), (1, 2, 3), (0, 1), (0, 1))
        for remaining in product(*axes):
            profile = (length, *remaining)
            rows[profile] = attempt_model(*profile)
    ordered_input = "".join(" ".join(map(str, profile)) + "\n" for profile in rows)
    oracle = "".join(" ".join([status, data.hex() or "-", *calls]) + "\n"
                     for status, data, calls in rows.values())
    native_hashes = {}
    with TemporaryDirectory(prefix="llmlang-output-") as tmp:
        executable = Path(tmp) / "probe"
        for optimization in ("-O0", "-O2"):
            execute(["gcc", optimization, "-std=c17", "-Wall", "-Wextra", "-Werror",
                     str(HERE / "probe.c"), "-o", str(executable)])
            observed = execute([str(executable)], stdin=ordered_input)
            if observed != oracle:
                first = next((i for i, (a, b) in enumerate(zip(observed.splitlines(), oracle.splitlines()))
                              if a != b), None)
                raise AssertionError(f"Native and reference rows differ at {optimization}: {first}")
            native_hashes[optimization] = sha256(observed.encode("ascii")).hexdigest()

    counts = dict(robust_rows=0, split_pairs=0, split_pairs_differing_in_calls=0,
                  short_drop_differences=0, short_drop_false_success=0)
    witnesses = {}
    for profile, observation in rows.items():
        length, boundaries, budget, limit, interrupt, drop_short = profile
        if drop_short:
            continue
        counts["robust_rows"] += 1
        status, data, _ = observation
        if (status, data) != ("eio" if budget < length else "ok", MESSAGE[:min(length, budget)]):
            raise AssertionError(f"Robust writer disagrees with the accepted-prefix model: {profile}")
        coalesced = rows[(length, 0, budget, limit, interrupt, 0)]
        if boundaries:
            counts["split_pairs"] += 1
            if observation[:2] != coalesced[:2]:
                raise AssertionError(f"Coalescing changed bytes or status: {profile}")
            if observation[2] != coalesced[2]:
                counts["split_pairs_differing_in_calls"] += 1
                witnesses.setdefault("call_trace", (profile, observation, coalesced))
        dropped = rows[(*profile[:-1], 1)]
        if observation[:2] != dropped[:2]:
            counts["short_drop_differences"] += 1
        if dropped[0] == "ok" and len(dropped[1]) < length:
            counts["short_drop_false_success"] += 1
            witnesses.setdefault("false_success", (profile, observation, dropped))
    return {
        "schema": "llmlang-partial-output/1",
        "gcc": execute(["gcc", "--version"]).splitlines()[0],
        "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Prefix.lean", "axioms.txt", "probe.c")},
        "native_observations_per_optimization": len(rows),
        "native_rows_sha256": native_hashes,
        "counts": counts,
        "witnesses": witnesses,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, default=bytes.hex))
