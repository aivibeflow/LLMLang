#!/usr/bin/env python3
"""Compare a finite Python relation oracle with kernel-checked Lean decisions."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
METHODS = ("signature", "direct-public-body", "separate-body-and-refinement")


def signature(obs):
    return obs["status"], obs["value"], tuple(obs["trace"]), obs["ownership"]


def realized(contract):
    return bool(contract) and all(contract.values())


def behavior(contract, body):
    if not realized(contract):
        return "reject"
    mismatched = any(
        body.get(value) is not None and body[value] not in allowed
        for value, allowed in contract.items()
    )
    if mismatched:
        return "reject"
    return "unknown" if any(body.get(value) is None for value in contract) else "admit"


def python_decisions(case, data):
    if not case["signature"]:
        return ["reject"] * len(METHODS)
    signatures = {label: signature(value) for label, value in data["observations"].items()}
    public, provided = [
        {value: {signatures[label] for label in allowed} for value, allowed in data["contracts"][case[key]].items()}
        for key in ("public", "provided")
    ]
    body = {
        value: signatures[label] if label is not None else None
        for value, label in data["bodies"][case["body"]].items()
    }
    refines = realized(public) and realized(provided) and all(
        value in provided and provided[value] <= allowed for value, allowed in public.items()
    )
    return ["admit", behavior(public, body), behavior(provided, body) if refines else "reject"]


def lean_list(values):
    return "[" + ", ".join(map(str, values)) + "]"


def encode_lean(data, *, mutate_expected=False):
    observations = {
        label: index for index, label in enumerate(data["observations"])
    }
    if len({signature(value) for value in data["observations"].values()}) != len(observations):
        raise ValueError("Distinct observation labels need distinct typed observations")

    def contract(name):
        return lean_list(
            f"({int(value)}, {lean_list(observations[label] for label in allowed)})"
            for value, allowed in data["contracts"][name].items()
        )

    def body(name):
        return lean_list(
            f"({int(value)}, " + ("none)" if label is None else f"some {observations[label]})")
            for value, label in data["bodies"][name].items()
        )

    cases = []
    expected = []
    for case in data["cases"]:
        matches = str(case["signature"]).lower()
        cases.append(f"⟨{matches}, {contract(case['public'])}, {contract(case['provided'])}, {body(case['body'])}⟩")
        expected.append(list(case["expected"]))
    if mutate_expected:
        expected[0][2] = "reject"
    expected_terms = lean_list(lean_list("." + value for value in row) for row in expected)
    checker = (HERE / "Refinement.lean").read_text(encoding="utf-8")
    return (
        checker + "\nopen ProviderPilot\n"
        + "def fixtures : List Case := " + lean_list(cases) + "\n"
        + "theorem checkedCases : fixtures.map decisions = " + expected_terms + " := by decide\n"
        + "#print axioms checkedCases\n"
    )


def run(lean):
    case_file = HERE / "fixtures.json"
    data = json.loads(case_file.read_text(encoding="utf-8"))
    decisions = []
    for case in data["cases"]:
        actual = python_decisions(case, data)
        if actual != case["expected"]:
            raise ValueError(f"{case['name']} disagrees with the adjudicated outcomes")
        decisions.append({"case": case["name"], **dict(zip(METHODS, actual, strict=True))})

    generated = encode_lean(data)
    with TemporaryDirectory(prefix="llmlang-provider-refinement-") as tmp:
        candidate = Path(tmp) / "Check.lean"
        candidate.write_text(generated, encoding="utf-8")
        command = [lean, "-DwarningAsError=true", str(candidate)]
        positive = subprocess.run(command, check=True, text=True, capture_output=True, timeout=30)
        if positive.stderr or positive.stdout.strip() != "'checkedCases' does not depend on any axioms":
            raise ValueError(f"Unexpected Lean audit: {positive.stdout + positive.stderr}")
        candidate.write_text(encode_lean(data, mutate_expected=True), encoding="utf-8")
        negative = subprocess.run(command, text=True, capture_output=True, timeout=30)
        if negative.returncode == 0 or "proved that the proposition" not in negative.stdout + negative.stderr:
            raise ValueError(f"Wrong verdict control did not fail at the proof: {negative.stdout + negative.stderr}")

    return {
        "schema": "llmlang-finite-provider-refinement-v1",
        "python": sys.version,
        "lean": subprocess.check_output([lean, "--version"], text=True).strip(),
        "input_sha256": {file.name: sha256(file.read_bytes()).hexdigest()
                         for file in (case_file, HERE / "Refinement.lean", Path(__file__))},
        "generated_lean_sha256": sha256(generated.encode()).hexdigest(),
        "lean_axioms": positive.stdout.strip(),
        "mutated_lean_expected_outcome_rejected": True,
        "decisions": decisions,
        "outcome_counts": {method: dict(Counter(row[method] for row in decisions))
                           for method in METHODS},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.lean)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["outcome_counts"], indent=2))
