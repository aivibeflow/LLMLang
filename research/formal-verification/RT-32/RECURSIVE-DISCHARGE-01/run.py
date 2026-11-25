"""Compare recursive proof closures with every finite model and a Lean rule."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from collections import Counter
from itertools import product
from pathlib import Path

BASELINE = "a824e8e0d92f7ead7eac313376352ad21b3e8bca"
HERE = Path(__file__).resolve().parent
MODES = {
    "both-decrease": (1, 1),
    "left-same": (0, 1),
    "right-same": (1, 0),
    "both-same": (0, 0),
}
MASKS = range(4)
HORIZONS = range(6)
WRONG = """\
import Discharge
open ProofDischarge
example (left right : Nat → Prop)
    (baseLeft : left 0) (baseRight : right 0)
    (stepLeft : ∀ n, right (n+1) → left (n+1))
    (stepRight : ∀ n, left (n+1) → right (n+1)) :
    ∀ n, left n ∧ right n := closeDecreasing left right baseLeft baseRight stepLeft stepRight
"""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def node(which, level):
    return 1 << (2 * level + which)


def premises(horizon, base, steps, decrease):
    facts = base  # Lowest two bits name the level-zero claims.
    rules = []
    for level, which in product(range(1, horizon + 1), (0, 1)):
        if steps & (1 << which):
            rules.append((node(1 - which, level - decrease[which]), node(which, level)))
    return facts, rules


def forward(facts, rules):
    result = facts
    while True:
        previous = result
        for premise, conclusion in rules:
            if result & premise:
                result |= conclusion
        if result == previous:
            return result


def all_models(facts, rules, complete):
    """Intersect all finite Boolean models satisfying the axioms and implications."""
    intersection = complete
    for model in range(complete + 1):
        if facts & model == facts and all(not model & premise or model & conclusion
                                         for premise, conclusion in rules):
            intersection &= model
    return intersection


def one_step_presence(facts, rules):
    """Control that uses all available conclusion receipts as if already closed."""
    local = facts
    for _, conclusion in rules:
        local |= conclusion
    result = facts
    for premise, conclusion in rules:
        if local & premise:
            result |= conclusion
    return result


def cases():
    modes = {name: Counter() for name in MODES}
    examples = {}
    for horizon, base, steps, (name, measure) in product(HORIZONS, MASKS, MASKS, MODES.items()):
        facts, rules = premises(horizon, base, steps, measure)
        complete = (1 << (2 * (horizon + 1))) - 1
        root = node(0, horizon) | node(1, horizon)
        correct = forward(facts, rules)
        assert correct == all_models(facts, rules, complete)
        optimistic = one_step_presence(facts, rules)
        counts = modes[name]
        counts["cases"] += 1
        counts["both_roots_closed"] += correct & root == root
        counts["false_root_closures"] += ((optimistic & ~correct) & root).bit_count()
        if horizon == max(HORIZONS) and (base, steps) in {(3, 3), (1, 3), (0, 3)}:
            label = f"{name}-{base}-{steps}"
            examples[label] = {"horizon": horizon, "base_mask": base, "step_mask": steps,
                               "grounded_mask": correct, "one_step_mask": optimistic,
                               "closed_root_mask": correct & root}
    return modes, examples


def check_lean(lean):
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    source = (HERE / "Discharge.lean").read_bytes()
    with tempfile.TemporaryDirectory(prefix="llmlang-proof-discharge-") as temporary:
        work = Path(temporary)
        (work / "Discharge.lean").write_bytes(source)
        env = os.environ | {"LC_ALL": "C", "LEAN_PATH": temporary}
        axioms = subprocess.check_output([lean, "-o", "Discharge.olean", "Discharge.lean"],
                                         cwd=work, env=env, text=True, timeout=30).splitlines()
        assert len(axioms) == 5 and all("does not depend on any axioms" in line for line in axioms)
        wrong = work / "Wrong.lean"
        wrong.write_text(WRONG, encoding="utf-8")
        error = subprocess.run([lean, wrong.name], cwd=work, env=env, text=True,
                               capture_output=True, timeout=30)
        assert error.returncode and "Application type mismatch" in error.stdout
    return {"lean": version, "source_sha256": digest(source), "axioms": axioms,
            "wrong_rule_rejected": True, "wrong_rule_source_sha256": digest(WRONG.encode())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    args = parser.parse_args()
    modes, examples = cases()
    result = {
        "baseline": BASELINE, "python": platform.python_version(), "horizons": list(HORIZONS),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "case_count": sum(row["cases"] for row in modes.values()),
        "mode_counts": modes, "selected_examples": examples,
        "proof_check": check_lean(args.lean.resolve(strict=True)),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
