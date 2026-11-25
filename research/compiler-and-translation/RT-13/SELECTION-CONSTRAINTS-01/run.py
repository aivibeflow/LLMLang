"""Compare typed selection constraints and deliberately weaker gates."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
PLATFORM = ("x86_64-sse2", "sysv-elf", "glibc-profile-1", "hosted-image-A")
GRANTS = {"file-read", "clock-read"}
REQUIRED = {"ordered-effects"}
ARTIFACT = "linked-artifact-A"
AUTHORITY = "checked-policy-A"
PROFILE = "fixture/config-A"
METRIC = "certain-upper-bound-us"
MAXIMUM = 20


def failed_constraints(platform, needed, offered, evidence, demand, measurement):
    failed = set()
    if platform != PLATFORM:
        failed.add("platform")
    if not needed <= GRANTS:
        failed.add("capabilities")
    if not REQUIRED <= offered:
        failed.add("features")
    if evidence != (ARTIFACT, AUTHORITY, True):
        failed.add("attestation")
    if demand:
        if (measurement is None or measurement[:3] != (ARTIFACT, PROFILE, METRIC)
                or measurement[3] > MAXIMUM):
            failed.add("performance")
    return failed


def matrix():
    variants = {
        "platform": {
            "exact": PLATFORM, "target": ("aarch64", *PLATFORM[1:]),
            "abi": (PLATFORM[0], "win64", *PLATFORM[2:]),
            "runtime": (*PLATFORM[:2], "musl-profile-1", PLATFORM[3]),
            "deployment": (*PLATFORM[:3], "hosted-image-B"),
        },
        "needed": {"strict-subset": {"file-read"}, "equal": GRANTS, "disjoint": {"net"},
                   "overlap-with-extra": {"file-read", "net"}, "empty": set()},
        "offered": {"equal": REQUIRED, "superset": REQUIRED | {"trace"}, "missing": {"trace"}},
        "evidence": {
            "exact": (ARTIFACT, AUTHORITY, True), "other-artifact": ("linked-artifact-B", AUTHORITY, True),
            "other-authority": (ARTIFACT, "other-policy", True), "unchecked": (ARTIFACT, AUTHORITY, False),
        },
        "demand": {"optional": False, "mandatory": True},
        "measurement": {
            "below": (ARTIFACT, PROFILE, METRIC, 19), "exactly": (ARTIFACT, PROFILE, METRIC, 20),
            "above": (ARTIFACT, PROFILE, METRIC, 21), "missing": None,
            "other-artifact": ("linked-artifact-B", PROFILE, METRIC, 19),
            "other-profile": (ARTIFACT, "fixture/config-B", METRIC, 19),
            "wrong-metric": (ARTIFACT, PROFILE, "sample-median-us", 19),
        },
    }
    counts = Counter()
    examples = {}
    for labels in product(*(variants[field] for field in variants)):
        selected = [variants[field][label] for field, label in zip(variants, labels, strict=True)]
        platform, needed, offered, evidence, demand, measurement = labels
        expected = set()
        if platform != "exact":
            expected.add("platform")
        if needed in {"disjoint", "overlap-with-extra"}:
            expected.add("capabilities")
        if offered == "missing":
            expected.add("features")
        if evidence != "exact":
            expected.add("attestation")
        if demand == "mandatory" and measurement not in {"below", "exactly"}:
            expected.add("performance")
        actual = failed_constraints(*selected)
        if actual != expected:
            raise ValueError((labels, actual, expected))
        counts["cases"] += 1
        counts["admissible" if not actual else "refused"] += 1
        if actual == {"capabilities"} and selected[1] & GRANTS:
            counts["false_accept_by_capability_overlap"] += 1
        if not actual and selected[1] != GRANTS:
            counts["false_refusal_by_capability_equality"] += 1
        if actual == {"performance"} and measurement in {"other-artifact", "other-profile", "wrong-metric"}:
            counts["false_accept_by_performance_number_only"] += 1
        if platform == "exact" and needed == "strict-subset" and offered == "superset" and evidence == "exact":
            examples[f"{demand}/{measurement}"] = sorted(actual)
    return dict(counts), examples


def lean_check(lean):
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    result = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Constraints.lean")],
                            check=True, text=True, capture_output=True, timeout=30)
    theorems = ("capability_grant_widening_preserves_eligibility",
                "required_performance_needs_matching_receipt", "admitted_constraints_are_conjunctive")
    lines = result.stdout.splitlines()
    if result.stderr or lines != [f"'{name}' does not depend on any axioms" for name in theorems]:
        raise ValueError((result.stdout, result.stderr))
    return {"version": version, "axioms": lines}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    comparisons, examples = matrix()
    value = {
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Constraints.lean", "run.py")},
        "lean": lean_check(args.lean), "comparisons": comparisons, "examples": examples,
    }
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
