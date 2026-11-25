"""Audit Java resource cleanup failure occurrences in two HotSpot profiles."""

import argparse
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


STAGES = ("body", "inner", "outer")


def expected(modes):
    primary = "-"
    suppressed = []
    cause = "-"
    occurrences = []
    for stage, mode in zip(STAGES, modes, strict=True):
        if mode == "ok":
            continue
        tag = "shared" if mode == "shared" else stage
        occurrences.append(f"{stage}:{tag}")
        if primary == "-":
            primary = tag
        elif primary == tag:
            primary, suppressed, cause = "self-suppression", [], tag
        else:
            suppressed.append(tag)
    return {
        "automatic_events": list(STAGES), "automatic_primary": primary,
        "automatic_suppressed": suppressed, "automatic_cause": cause,
        "explicit_events": list(STAGES), "explicit_occurrences": occurrences,
    }


def records(output):
    observations = {}
    for row in output.splitlines():
        if not row.startswith("case="):
            continue
        key, events, primary, suppressed, cause, explicit_events, occurrences = row[5:].split("|")
        assert key not in observations
        observations[key] = {
            "automatic_events": events.split(","), "automatic_primary": primary,
            "automatic_suppressed": suppressed.split(",") if suppressed else [], "automatic_cause": cause,
            "explicit_events": explicit_events.split(","),
            "explicit_occurrences": occurrences.split(",") if occurrences else [],
        }
    return observations


def study(java):
    source = Path(__file__).with_name("Fixture.java")
    fixtures = {",".join(modes): expected(modes) for modes in product(("ok", "own", "shared"), repeat=3)}
    with TemporaryDirectory() as temporary:
        subprocess.run(
            [java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-Xlint:all", "-Werror", "-source", "21", "-target", "21",
             "-d", temporary, str(source)],
            check=True, timeout=30,
        )
        policies = {
            "interpreted": ["-Xint"],
            "compiled": [
                "-Xcomp", "-XX:-TieredCompilation", "-XX:+PrintCompilation",
                "-XX:CompileCommand=compileonly,Fixture::automatic",
                "-XX:CompileCommand=compileonly,Fixture::explicit",
            ],
        }
        for profile, flags in policies.items():
            output = subprocess.check_output([java, *flags, "-cp", temporary, "Fixture"], text=True, timeout=30)
            if profile == "compiled":
                for method in ("automatic", "explicit"):
                    assert any(f"Fixture::{method} (" in line for line in output.splitlines()), output
            actual = records(output)
            assert actual == fixtures, (profile, [key for key in fixtures if fixtures[key] != actual.get(key)])
    version = subprocess.run([java, "-version"], check=True, capture_output=True, text=True, timeout=10)
    self_suppressed = [key for key, record in fixtures.items() if record["automatic_primary"] == "self-suppression"]
    assert len(self_suppressed) == 6
    return {
        "python": platform.python_version(),
        "jvm": version.stderr.splitlines(),
        "profiles": sorted(policies),
        "same_throwable_replacements": self_suppressed,
        "fixtures": fixtures,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default="java")
    print(json.dumps(study(parser.parse_args().java), indent=2, sort_keys=True))
