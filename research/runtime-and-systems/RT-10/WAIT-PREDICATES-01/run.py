"""Check native condition-variable policies in coordinated, bounded schedules."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


EXPECTED = {
    "pulse-only": "empty-reported-as-work:false:false:false",
    "pulse-then-work": "work:false:false:true",
    "already-published": "work:false:false:false",
    "cancel-only": "cancelled:false:true:false",
    "both-cancel-first": "cancelled:true:true:false",
    "both-work-first": "work:false:true:false",
}


def study(compiler):
    source = Path(__file__).with_name("wait.rs")
    with TemporaryDirectory() as temporary:
        builds = {}
        for level in (0, 2):
            binary = Path(temporary) / "wait"
            subprocess.run(
                [compiler, "--edition=2021", "-Dwarnings", f"-Copt-level={level}", str(source),
                 "-o", str(binary)],
                check=True, timeout=30,
            )
            results = {}
            for scenario, expected in EXPECTED.items():
                outcome = subprocess.check_output([binary, scenario], text=True, timeout=10).strip()
                assert outcome == expected, (scenario, level, outcome)
                reason, pending, cancelled, rewait = outcome.split(":")
                results[scenario] = {
                    "outcome": reason, "item_remaining": pending == "true",
                    "cancelled": cancelled == "true", "observed_rewait_after_irrelevant_notification": rewait == "true",
                }
            builds[str(level)] = results
        assert builds["0"] == builds["2"]
    return {
        "python": platform.python_version(),
        "rustc": subprocess.check_output([compiler, "-Vv"], text=True).splitlines(),
        "builds": builds,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    print(json.dumps(study(parser.parse_args().rustc), indent=2, sort_keys=True))
