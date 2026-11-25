"""Check the summary and exact effects of typed local recovery on a finite model."""

import argparse
from ctypes import CDLL, c_uint32
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


OPERATIONS = ("read", "audit", "repair")
OUTCOMES = ("found", "missing", "io-error", "denied", "recovered")


def planned(fetch, enabled):
    if fetch == "missing" and enabled:
        return OPERATIONS, "recovered"
    return ("read",), fetch


def expected(fetch, enabled, granted):
    effects, completed = planned(fetch, enabled)
    for position, requirement in enumerate(effects):
        if requirement not in granted:
            return "denied", effects[:position]
    return completed, effects


def unpack(number):
    result = OUTCOMES[number >> 8]
    remainder = number & 0xff
    trace = []
    while remainder:
        effect = remainder % 4
        assert 1 <= effect <= 3
        trace.append(OPERATIONS[effect - 1])
        remainder //= 4
    return result, tuple(reversed(trace))


def observe(library):
    evaluate = CDLL(str(library)).evaluate
    evaluate.argtypes = [c_uint32] * 3
    evaluate.restype = c_uint32
    rows = []
    for fetch, enabled, grants in product(range(3), range(2), range(8)):
        granted = {operation for bit, operation in enumerate(OPERATIONS) if grants & (1 << bit)}
        expected_result = expected(OUTCOMES[fetch], enabled, granted)
        result, trace = unpack(evaluate(fetch, enabled, grants))
        assert (result, trace) == expected_result
        read_only_admission = "read" in granted
        path_admission = set(planned(OUTCOMES[fetch], enabled)[0]) <= granted
        assert path_admission == (result != "denied")
        assert set(trace) <= granted
        assert not enabled or result != "missing"
        rows.append({
            "fetch": OUTCOMES[fetch], "handler_enabled": bool(enabled), "grants": sorted(granted),
            "outcome": result, "effects": trace, "read_only_admission": read_only_admission,
            "path_admission": path_admission,
        })
    return rows


def study(compilers):
    source = Path(__file__).with_name("recover.c")
    observations = []
    toolchains = {}
    with TemporaryDirectory() as temporary:
        for name, compiler in compilers.items():
            toolchains[name] = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
            for level in ("-O0", "-O2"):
                library = Path(temporary) / f"{name}{level}.so"
                subprocess.run(
                    [compiler, "-std=c11", "-Wall", "-Wextra", "-Wconversion", "-Werror",
                     "-shared", "-fPIC", level, str(source), "-o", str(library)],
                    check=True, timeout=30,
                )
                observations.append(observe(library))
    baseline = observations[0]
    assert all(baseline == result for result in observations)
    false_admissions = [row for row in baseline if row["read_only_admission"] and not row["path_admission"]]
    retained_audits = [row for row in false_admissions if "audit" in row["effects"]]
    assert len(false_admissions) == 3 and len(retained_audits) == 1
    return {
        "python": platform.python_version(),
        "toolchains": toolchains,
        "matching_builds": len(observations),
        "read_only_false_admissions": len(false_admissions),
        "failed_recovery_with_completed_audit": len(retained_audits),
        "cases": baseline,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--clang", default="clang")
    options = parser.parse_args()
    print(json.dumps(study({"gcc": options.gcc, "clang": options.clang}), indent=2, sort_keys=True))
