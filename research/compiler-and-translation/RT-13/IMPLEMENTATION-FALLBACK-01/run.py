"""Check the Lean fallback model and an independent exact-dispatch matrix."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Profile:
    operation: int = 1
    target: int = 2
    abi: int = 3
    runtime: int = 4
    capability_scope: int = 5
    policy: int = 6
    observations: int = 7


@dataclass(frozen=True)
class Receipt:
    profile: Profile
    artifact: int
    verdict: str


@dataclass(frozen=True)
class Implementation:
    profile: Profile
    artifact: int
    available: bool
    receipt: Receipt | None


PROFILE_FIELDS = ("operation", "target", "abi", "runtime", "capability_scope", "policy", "observations")
PROFILES = ("matching", *PROFILE_FIELDS)
RECEIPTS = ("verified", "absent", "wrong-runtime", "wrong-artifact", "unknown", "failed")
AVAILABILITY = ("materialized", "unavailable")
VARIANTS = tuple(product(PROFILES, RECEIPTS, AVAILABILITY))


def candidate(request, artifact, tags):
    shape, proof, available = tags
    profile = request if shape == "matching" else replace(request, **{shape: 99})
    correct = Receipt(request, artifact, "checked")
    receipts = {
        "verified": correct,
        "absent": None,
        "wrong-runtime": replace(correct, profile=replace(request, runtime=99)),
        "wrong-artifact": replace(correct, artifact=99),
        "unknown": replace(correct, verdict="unknown"),
        "failed": replace(correct, verdict="failed"),
    }
    return Implementation(profile, artifact, available == "materialized", receipts[proof])


def eligible(request, item):
    return (item.available and item.profile == request
            and item.receipt == Receipt(request, item.artifact, "checked"))


def choose(choices, accepted):
    return next((item.artifact for item in choices if accepted(item)), None)


def verify(lean):
    request = Profile()
    checked = ("matching", "verified", "materialized")
    counts = {mode: Counter() for mode in ("exact", "available-only", "abi-only")}
    outcome_digest = sha256()
    for preferred, reserve in product(VARIANTS, repeat=2):
        choices = (candidate(request, 10, preferred), candidate(request, 20, reserve))
        oracle_eligible = {artifact for artifact, tags in ((10, preferred), (20, reserve))
                           if tags == checked}
        expected = next((artifact for artifact in (10, 20) if artifact in oracle_eligible), None)
        decisions = {
            "exact": choose(choices, lambda item: eligible(request, item)),
            "available-only": choose(choices, lambda item: item.available),
            "abi-only": choose(choices, lambda item: item.available
                               and (item.profile.operation, item.profile.target, item.profile.abi)
                               == (request.operation, request.target, request.abi)),
        }
        if decisions["exact"] != expected:
            raise AssertionError((preferred, reserve, expected, decisions))
        for mode, selected in decisions.items():
            outcome = {None: "refused", 10: "preferred", 20: "reserve"}[selected]
            counts[mode][outcome] += 1
            counts[mode]["incorrect_dispatch"] += selected is not None and selected not in oracle_eligible
            counts[mode]["wrong_decision"] += selected != expected
            outcome_digest.update(bytes([selected or 0]))

    theorem_log = subprocess.run([lean, str(HERE / "Fallback.lean")], check=True,
                                 capture_output=True, text=True, timeout=60)
    if theorem_log.stderr:
        raise ValueError(theorem_log.stderr)
    names = [line.split("'")[1] for line in theorem_log.stdout.splitlines()]
    if names != ["selected_from_eligible", "no_selection_iff_none_eligible",
                 "selection_binds_exact_evidence", "eligible_preferred_stays_selected"]:
        raise ValueError(theorem_log.stdout)
    return {
        "lean": subprocess.check_output([lean, "--version"], text=True, timeout=10).strip(),
        "theorems": theorem_log.stdout.splitlines(),
        "candidate_variants": len(VARIANTS),
        "dispatch_cases": len(VARIANTS)**2,
        "decisions": {mode: dict(sorted(values.items())) for mode, values in counts.items()},
        "decision_stream_sha256": outcome_digest.hexdigest(),
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Fallback.lean", "run.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    print(json.dumps(verify(parser.parse_args().lean), indent=2))
