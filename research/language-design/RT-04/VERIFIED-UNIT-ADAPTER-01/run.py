"""Check the Lean adapter theorem and replay directed executable controls."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
MAX_TICKS = 2 ** 32 - 1
SCALE = 1000
MAX_MILLIS = 4_294_967
LEAN_REVISION = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
RANGE = ("range", None, ())


def ideal(ticks):
    return ("armed", ticks, (("arm", ticks),))


def decode(observation):
    status, value, trace = observation
    if status != "armed":
        return observation
    return (status, value // SCALE, trace)


def reference(millis):
    ticks = millis * SCALE
    if ticks > MAX_TICKS:
        return RANGE
    return ("armed", millis, (("arm", ticks),))


def routes(millis):
    checked = decode(ideal(millis * SCALE)) if millis <= MAX_MILLIS else RANGE
    wrapped = decode(ideal((millis * SCALE) % (MAX_TICKS + 1)))
    status, value, trace = checked
    spurious_trace = trace + (("audit", None),) if status == "armed" else trace
    return {
        "checked": checked, "unchecked_u32_wrap": wrapped,
        "erase_trace": (status, value, ()), "wrong_input_scale": decode(ideal(millis)),
        "extra_provider_event": (status, value, spurious_trace),
    }


def replay(lean):
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert LEAN_REVISION in version
    checked = subprocess.run([lean, "-DwarningAsError=true", HERE / "Adapter.lean"],
                             check=True, capture_output=True, text=True, timeout=60)
    axioms = checked.stdout.splitlines()
    assert len(axioms) == 6 and all("sorryAx" not in line for line in axioms)
    inputs = sorted(set(range(0, 17)) | set(range(MAX_MILLIS - 16, MAX_MILLIS + 17))
                    | {2 ** exponent for exponent in range(8, 67, 4)})
    mismatches = Counter()
    observations = []
    for millis in inputs:
        expected = reference(millis)
        actual = routes(millis)
        assert actual["checked"] == expected
        mismatches.update(route for route, outcome in actual.items() if outcome != expected)
        observations.append({"millis": millis, "required": expected, "observations": actual})
    return {
        "schema": "rt04-verified-unit-adapter-v1",
        "python": platform.python_version(), "lean": version, "checked_axioms": axioms,
        "input_count": len(inputs), "accepted_inputs": sum(row["required"][0] == "armed" for row in observations),
        "mismatch_counts": {name: mismatches[name] for name in routes(0)},
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in ("Adapter.lean", "run.py")},
        "observations": observations,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.lean), indent=2, sort_keys=True))
