"""Verify exact inputs and coverage of the four-candidate comparison audit."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COVERAGE = {"bounded_shared", "component_only", "protocol_only"}


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def validate(data, names, candidates):
    if data["profiles"] != candidates or data["rating"] != "unknown":
        raise ValueError("Unknown or incomplete profile and rating assessment")
    if [row["name"] for row in data["criteria"]] != names:
        raise ValueError("Comparison criteria mismatch")
    for row in data["criteria"]:
        references = row["source_refs"]
        if row["coverage"] not in COVERAGE or set(row["per_profile"]) != set(candidates):
            raise ValueError("Incomplete criterion coverage")
        if "score" in row or "scores" in row:
            raise ValueError("Numeric scoring requires comparable integrated results")
        if not references or any(source not in data["sources"] for source in references):
            raise ValueError("Evidence reference missing")
        if not row["shared_requirements"] or not all(row["per_profile"].values()):
            raise ValueError("Missing shared or profile requirement")


def negative_controls(data, names, profiles):
    controls = {}
    for scenario in ("numeric_rating", "removed_criterion", "removed_candidate",
                     "unresolved_source", "numeric_cell", "missing_exit_requirement"):
        mutated = deepcopy(data)
        if scenario == "numeric_rating":
            mutated["rating"] = 0
        elif scenario == "removed_criterion":
            mutated["criteria"].pop()
        elif scenario == "removed_candidate":
            del mutated["criteria"][0]["per_profile"]["C4"]
        elif scenario == "unresolved_source":
            mutated["criteria"][0]["source_refs"] = ["unknown"]
        elif scenario == "numeric_cell":
            mutated["criteria"][0]["score"] = 3
        else:
            mutated["criteria"][0]["shared_requirements"] = ""
        try:
            validate(mutated, names, profiles)
        except ValueError:
            controls[scenario] = "refused"
        else:
            raise ValueError(f"Invalid audit accepted: {scenario}")
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads((HERE / "inputs.json").read_text())
    baseline = data["revision"]
    matrix_ref = f"{baseline}:{data['matrix']}"
    matrix = git("show", matrix_ref).decode()
    candidate_section = matrix.split("## 4. Integrated candidate vectors\n")[1].split("\n## 5.")[0]
    candidates = re.findall(r"^\| \*\*(C\d+) ", candidate_section, flags=re.M)
    criteria_section = matrix.split("## 6. Shared evaluation criteria\n")[1].split("\n## 7.")[0]
    names = re.findall(r"^\| ([^|]+?) \|", criteria_section, flags=re.M)[1:]
    validate(data, names, candidates)

    source_pins = {}
    for name, path in data["sources"].items():
        ref = f"{baseline}:{path}"
        blob = git("rev-parse", ref).decode().strip()
        content = git("cat-file", "blob", blob)
        source_pins[name] = {"path": path, "blob": blob,
                             "sha256": sha256(content).hexdigest()}
    coverage = Counter(row["coverage"] for row in data["criteria"])
    evidence = {
        "audit_revision": baseline,
        "matrix_blob": git("rev-parse", matrix_ref).decode().strip(),
        "git": git("--version").decode().strip(), "python": sys.version.split()[0],
        "candidates": candidates, "criteria": names, "criterion_coverage": coverage,
        "profile_requirement_count": sum(len(row["per_profile"]) for row in data["criteria"]),
        "scored_profiles": 0, "integrated_rating": data["rating"],
        "negative_controls": negative_controls(data, names, candidates),
        "pinned_evidence": source_pins,
    }
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
