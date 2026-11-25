"""Compare witnessed, upper-bound and exact absence evidence by query scope."""

import argparse
import hashlib
import json
import platform
import subprocess
from collections import Counter
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = "d7874b9547b58ca44a741f5cf98158c871592f21"
PROVIDERS = ("a", "b", "c")
PROGRAMS = tuple(product((None, "a", "b"), repeat=2))
SCOPES = ((False,), (True,), (False, True))
SAMPLES = ((), *SCOPES)
SCHEMA = "closed-boolean-dispatch/1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return digest(json.dumps(value, separators=(",", ":")).encode())


def query(program, scope, target):
    return {"snapshot": identity(program), "scope": scope, "target": target, "schema": SCHEMA}


def observe(program, flag, changed=None):
    # Each positive call is observable as provider identity and selected version.
    provider = program[1] if flag else program[0]
    return (provider, "replacement" if provider == changed else "original") if provider else None


def issue_absence(program, scope, target):
    return {"query": query(program, scope, target),
            "input_rows": tuple(observe(program, flag) for flag in scope),
            "absent": all(observe(program, flag) != (target, "original") for flag in scope)}


def admissible_absence(receipt, program, scope, target, complete):
    return complete and receipt == issue_absence(program, scope, target) and receipt["absent"]


def compare():
    counts = {name: Counter() for name in ("sample-only", "closed-upper-bound", "exact-scope")}
    exact_categories = Counter()
    for program, scope, samples, target, complete in product(PROGRAMS, SCOPES, SAMPLES, PROVIDERS, (False, True)):
        changed = any(observe(program, flag, target) != observe(program, flag) for flag in scope)
        witnessed = any(observe(program, flag) == (target, "original") for flag in samples if flag in scope)
        static_upper_bound = set(program) - {None}
        receipt = issue_absence(program, scope, target)
        routes = {
            "sample-only": not witnessed,
            "closed-upper-bound": complete and target not in static_upper_bound,
            "exact-scope": admissible_absence(receipt, program, scope, target, complete),
        }
        assert receipt["absent"] == (not changed)
        for name, admits_reuse in routes.items():
            counts[name]["cases"] += 1
            counts[name]["safe_reuses"] += admits_reuse and not changed
            counts[name]["stale_reuses"] += admits_reuse and changed
            counts[name]["safe_cases_held"] += not admits_reuse and not changed
        if witnessed:
            assert changed
            exact_categories["witnessed_edge"] += 1
        elif not complete:
            exact_categories["unresolved"] += 1
        elif routes["exact-scope"]:
            exact_categories["checked_absence"] += 1
        else:
            exact_categories["reachable_after_complete_replay"] += 1
    return counts, exact_categories


def controls():
    program = ("a", "b")
    scope = (False,)
    old = issue_absence(program, scope, "b")
    assert admissible_absence(old, program, scope, "b", True)
    assert not admissible_absence(old, program, (False, True), "b", True)
    assert not admissible_absence(old, ("b", "b"), scope, "b", True)
    assert not admissible_absence(old, program, scope, "b", False)
    altered = old | {"input_rows": (None,)}
    assert not admissible_absence(altered, program, scope, "b", True)
    return {
        "valid_scope": old["query"], "broadened_scope_rejected": True, "rebound_source_rejected": True,
        "source_coverage_missing_rejected": True, "altered_observation_rows_rejected": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    args = parser.parse_args()
    lean = args.lean.resolve(strict=True)
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    source = HERE / "Coverage.lean"
    axioms = subprocess.check_output([lean, "-DwarningAsError=true", source], text=True, timeout=30).splitlines()
    assert len(axioms) == 3 and all("does not depend on any axioms" in line for line in axioms)
    counts, evidence_classes = compare()
    assert not counts["closed-upper-bound"]["stale_reuses"] and not counts["exact-scope"]["stale_reuses"]
    assert counts["exact-scope"]["safe_reuses"] > counts["closed-upper-bound"]["safe_reuses"]
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "lean": version, "axioms": axioms,
        "runner_sha256": digest(Path(__file__).read_bytes()), "model_sha256": digest(source.read_bytes()),
        "scope_profiles": SCOPES, "sample_subsets": SAMPLES, "program_count": len(PROGRAMS),
        "per_policy": counts, "distinct_evidence_classes": evidence_classes, "controls": controls(),
    }, indent=2))


if __name__ == "__main__":
    main()
