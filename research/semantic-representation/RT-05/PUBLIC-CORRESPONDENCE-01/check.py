"""Compare two provider interpreters against a separate finite public contract."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "provider.c"
PROFILES = ("plus-one", "plus-two", "order-control", "resource-control", "authority-control")
SCENARIOS = tuple(product(range(len(PROFILES)), (0, 1), range(4), range(-2, 6)))
TRACES = {0: (), 1: ("reserve",), 2: ("reserve", "commit"), 3: ("commit", "reserve")}
OUTCOMES = ("ok", "denied", "budget", "domain")


def source_semantics(profile, grant, fuel, units):
    path = []
    if grant or PROFILES[profile] == "authority-control":
        if fuel >= 2:
            path.append("reserve")
            if units < 0:
                return "domain", 0, tuple(path), len(path)
            path.append("commit")
            if PROFILES[profile] == "order-control":
                path.reverse()
            delta = 2 if PROFILES[profile] == "plus-two" else 1
            work = len(path) * (2 if PROFILES[profile] == "resource-control" else 1)
            return "ok", units + delta, tuple(path), work
        return "budget", 0, (), 0
    return "denied", 0, (), 0


def belongs(inputs, observation, max_work=2):
    _, grant, fuel, units = inputs
    outcome, answer, trace, work = observation
    permitted_failures = {
        "denied": (grant == 0, (0, (), 0)),
        "budget": (grant == 1 and fuel in {0, 1}, (0, (), 0)),
        "domain": (grant == 1 and fuel in {2, 3} and units < 0, (0, ("reserve",), 1)),
    }
    if outcome != "ok":
        active, exact = permitted_failures[outcome]
        return active and (answer, trace, work) == exact
    return (
        grant == 1 and fuel in {2, 3} and units >= 0
        and answer - units in {1, 2} and trace == ("reserve", "commit") and 0 <= work <= max_work
    )


def native(compilation, directory):
    binary = directory / "provider"
    subprocess.run(["gcc", "-std=c11", compilation, "-Wall", "-Wextra", "-Werror",
                    SOURCE, "-o", binary], check=True, timeout=15)
    raw = subprocess.check_output([binary], timeout=10)
    observations = {}
    for line in raw.decode("ascii").splitlines():
        profile, grant, fuel, units, status, result, trace, work = map(int, line.split())
        key = (profile, grant, fuel, units)
        if key in observations:
            raise ValueError("duplicate native input")
        observations[key] = (OUTCOMES[status], result, TRACES[trace], work)
    return observations, sha256(raw).hexdigest()


def run():
    source = {case: source_semantics(*case) for case in SCENARIOS}
    assert len(SCENARIOS) == len(source)
    conformance = Counter()
    for case, observation in source.items():
        if not belongs(case, observation):
            conformance[PROFILES[case[0]]] += 1
    assert dict(conformance) == {
        "order-control": 12, "resource-control": 12, "authority-control": 32,
    }
    outputs = {}
    with TemporaryDirectory() as work:
        for opt in ("-O0", "-O3"):
            actual, digest = native(opt, Path(work))
            assert actual == source
            assert all(belongs(case, actual[case]) == belongs(case, source[case]) for case in source)
            outputs[opt] = {"observations": len(actual), "output_sha256": digest}
    return {
        "python": platform.python_version(), "gcc": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
        "sources": {path.name: sha256(path.read_bytes()).hexdigest() for path in (Path(__file__), SOURCE)},
        "domain": {"profiles": PROFILES, "grant": (0, 1), "fuel": tuple(range(4)), "units": tuple(range(-2, 6))},
        "source_observations": len(source), "backend_observations": outputs,
        "public_refutations": {name: conformance[name] for name in PROFILES},
        "records": [{"input": case, "observation": received, "public_conformance": belongs(case, received)}
                    for case, received in source.items()],
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
