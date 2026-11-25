"""Measure cleanup event order and terminal states in separately compiled Rust profiles."""

import argparse
from itertools import product
import json
from pathlib import Path
import platform
import resource
import signal
import subprocess
from tempfile import TemporaryDirectory


def expected_implicit(strategy, body, fails):
    events = [f"body-{body}"]
    if body == "panic":
        events.append("hook-body")
        if strategy == "abort":
            return -signal.SIGABRT, events

    events.append("inner-drop")
    if fails:
        events.append("hook-close")
        if strategy == "abort" or body == "panic":
            return -signal.SIGABRT, events

    events.append("outer-drop")
    if fails or body == "panic":
        events.append("caught-panic")
    else:
        events.append("result-ok" if body == "ok" else "result-body-error")
    return 0, events


def expected_explicit(body, fails):
    outcomes = {
        ("ok", False): "ok",
        ("ok", True): "close-error",
        ("error", False): "body-error",
        ("error", True): "both-errors:body-error+close-error",
    }
    return 0, [f"body-{body}", "close-error" if fails else "close-ok", "outer-drop",
               f"result-{outcomes[body, fails]}"]


def check_build(binary, strategy, cwd):
    cases = [
        (mode, body, fails)
        for mode, bodies in (("implicit", ("ok", "error", "panic")), ("explicit", ("ok", "error")))
        for body, fails in product(bodies, (False, True))
    ]
    rows = []
    for mode, body, fails in cases:
        result = subprocess.run(
            [binary, mode, body, "failure" if fails else "success"],
            cwd=cwd, capture_output=True, check=False, text=True, timeout=10,
        )
        observed = result.returncode, result.stdout.splitlines()
        expected = expected_implicit(strategy, body, fails) if mode == "implicit" else expected_explicit(body, fails)
        assert observed == expected, (mode, strategy, body, fails, observed, result.stderr)
        rows.append({
            "mode": mode, "body": body, "cleanup_fails": fails,
            "returncode": observed[0], "events": observed[1],
        })
    return rows


def study(compiler):
    source = Path(__file__).with_name("cleanup.rs").resolve()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    builds = {}
    with TemporaryDirectory() as temporary:
        for strategy in ("unwind", "abort"):
            observations = []
            for level in (0, 2):
                binary = Path(temporary) / f"cleanup-{strategy}-{level}"
                subprocess.run(
                    [compiler, "--edition=2021", "-Dwarnings", f"-Cpanic={strategy}",
                     f"-Copt-level={level}", str(source), "-o", str(binary)],
                    check=True, timeout=30,
                )
                observations.append(check_build(binary, strategy, temporary))
            assert observations[0] == observations[1]
            builds[strategy] = observations[0]
    return {
        "python": platform.python_version(),
        "rustc": subprocess.check_output([compiler, "-Vv"], text=True).splitlines(),
        "matching_optimization_levels": [0, 2],
        "cases_per_build": len(builds["unwind"]),
        "builds": builds,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    print(json.dumps(study(parser.parse_args().rustc), indent=2, sort_keys=True))
