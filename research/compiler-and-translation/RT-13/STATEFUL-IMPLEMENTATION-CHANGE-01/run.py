"""Verify complete stateful traces across implementation changes and a reset fault."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ACTIONS = (
    ("credit", 1), ("credit", 4), ("debit", 0), ("debit", 2),
    ("debit", 5), ("read", 0), ("direct", 0), ("split", 0),
)
INITIAL = ((3, 0, False), (7, 4, True), (0, 0, False), (9, 9, True))


def reference(balance, actions):
    replies = []
    for action, amount in actions:
        if action == "credit":
            balance += amount
            replies.append(("credited", amount))
        elif action == "debit":
            if amount <= balance:
                balance -= amount
                replies.append(("debited", amount))
            else:
                replies.append(("refused", None))
        elif action == "read":
            replies.append(("balance", balance))
    return replies, balance


def implementation(state, actions, reset_on_migration=False):
    credits, debits, split = state
    replies = []
    for action, amount in actions:
        if action in {"direct", "split"}:
            credits, debits = (0 if reset_on_migration else credits - debits), 0
            split = action == "split"
        elif action == "credit":
            credits += amount
            replies.append(("credited", amount))
        elif action == "debit":
            if amount + debits > credits:
                replies.append(("refused", None))
            else:
                if split:
                    debits += amount
                else:
                    credits -= amount
                replies.append(("debited", amount))
        elif action == "read":
            replies.append(("balance", credits - debits))
        if not 0 <= debits <= credits or (not split and debits):
            raise ValueError("invalid representation")
    return replies, credits - debits


def matrix():
    total = fault_detected = 0
    for count in range(5):
        for initial, actions in product(INITIAL, product(ACTIONS, repeat=count)):
            balance = initial[0] - initial[1]
            expected = reference(balance, actions)
            if implementation(initial, actions) != expected:
                raise ValueError((initial, actions, expected))
            total += 1
            fault_detected += implementation(initial, actions, reset_on_migration=True) != expected

    sequence = (("credit", 4), ("split", 0), ("credit", 1), ("debit", 5))
    preserved = implementation(INITIAL[2], sequence)
    corrupted = implementation(INITIAL[2], sequence, reset_on_migration=True)
    if preserved[0][:2] != corrupted[0][:2] or preserved[0][2] == corrupted[0][2]:
        raise ValueError("the delayed divergence control changed")
    return {
        "compared_traces": total, "reset_fault_mismatches": fault_detected,
        "future_divergence": {"actions": sequence, "preserved": preserved, "reset_fault": corrupted},
    }


def run_lean(lean):
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    check = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Migration.lean")],
                           text=True, capture_output=True, check=True, timeout=30)
    expected = (
        "'migration_preserves_state' depends on axioms: [propext]",
        "'execution_refines' depends on axioms: [propext, Quot.sound]",
        "'complete_trace_refines' depends on axioms: [propext, Quot.sound]",
    )
    if check.stderr or tuple(check.stdout.splitlines()) != expected:
        raise ValueError((check.stdout, check.stderr))
    return {"version": version, "axioms": expected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    value = {
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Migration.lean", "run.py")},
        "lean": run_lean(args.lean), "finite_controls": matrix(),
    }
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
