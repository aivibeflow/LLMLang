"""Enumerate candidate bundles and refute every classification discrepancy in SMT."""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def classify(candidate, event):
    rejected = []
    outstanding = []
    diagnostic = event.get("diagnostic", False)
    if candidate["binding"] == "contract_only":
        rejected.append("provider_identity_missing")
    if candidate["cache"] == "caller_key_hit":
        rejected.append("action_closure_missing")
    if not diagnostic:
        if candidate["observation"] != "ordered_effects_and_ownership":
            rejected.append("observation_too_weak")
        if candidate["evidence"] != "exact_native_scope":
            rejected.append("evidence_scope_mismatch")
        if candidate["publication"] != "authorized_exact":
            rejected.append("publisher_authority_missing")
    if not diagnostic or event.get("cancel"):
        if candidate["authority"] != "fresh_effect_gate":
            rejected.append("effect_authority_unfenced")
        if candidate["terminal"] != "settled":
            rejected.append("terminal_before_release")
    if event.get("rebound") and candidate["binding"] == "explicit_pin":
        outstanding.append("explicit_repin_required")
    if event.get("larger_scope"):
        outstanding.append("outside_pinned_native_corpus")
    if event.get("revoked") and not diagnostic:
        outstanding.append("publisher_revoked")
    status = "blocked" if rejected else "withheld" if outstanding else "admitted"
    return status, rejected, outstanding


def smt_row(candidate, event):
    facts = {
        "pin": candidate["binding"] == "explicit_pin",
        "snapshot": candidate["binding"] == "snapshot_resolved",
        "ordered": candidate["observation"] == "ordered_effects_and_ownership",
        "rebuild": candidate["cache"] == "clean_rebuild",
        "exact_hit": candidate["cache"] == "exact_validated_hit",
        "exact_evidence": candidate["evidence"] == "exact_native_scope",
        "fresh": candidate["authority"] == "fresh_effect_gate",
        "settled": candidate["terminal"] == "settled",
        "authorized": candidate["publication"] == "authorized_exact",
    }
    facts.update({
        flag: event.get(flag, False)
        for flag in ("diagnostic", "rebound", "cancel", "larger_scope", "revoked")
    })
    terms = [name if enabled else f"(not {name})" for name, enabled in facts.items()]
    return "(and " + " ".join(terms) + ")"


def run_solver(command, script, expected):
    process = subprocess.run(
        command, input=script, text=True, capture_output=True, check=True, timeout=60
    )
    actual = process.stdout.splitlines()
    if actual != expected:
        for index, (result, wanted) in enumerate(zip(actual, expected)):
            if result != wanted:
                raise ValueError(f"{command[0]}, query {index + 1}: {result} != {wanted}")
        raise ValueError(f"{command[0]}: expected {len(expected)} verdicts, got {len(actual)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--z3", default="z3")
    parser.add_argument("--cvc5", default="cvc5")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads((HERE / "space.json").read_text())
    axes = config["axes"]
    events = config["scenarios"]
    base = config["base"]
    pinned_reports = {}
    for name, path in config["sources"].items():
        blob = git("rev-parse", f"{base}:{path}")
        if git("hash-object", path) != blob:
            raise ValueError(f"Evidence changed from the pinned blob: {path}")
        pinned_reports[name] = {"path": path, "blob": blob}

    bundles = [dict(zip(axes, choices)) for choices in product(*axes.values())]
    rows = []
    queries = [("(not (or blocked withheld admitted))", "unsat")]
    for left, right in (("blocked", "withheld"), ("blocked", "admitted"), ("withheld", "admitted")):
        queries.append((f"(and {left} {right})", "unsat"))
    summaries = {}
    for scenario, event in events.items():
        counts = Counter()
        for index, candidate in enumerate(bundles):
            status, rejected, outstanding = classify(candidate, event)
            counts[status] += 1
            rows.append([scenario, index, status, rejected, outstanding])
            facts = smt_row(candidate, event)
            queries.append((f"(and {facts} (not {status}))", "unsat"))
            # A contradictory encoding would otherwise pass every UNSAT test.
            queries.append((f"(and {facts} {status})", "sat"))
        summaries[scenario] = dict(counts)

    baseline = {
        "route": "c", "binding": "snapshot_resolved",
        "observation": "ordered_effects_and_ownership", "cache": "exact_validated_hit",
        "evidence": "exact_native_scope", "authority": "fresh_effect_gate",
        "terminal": "settled", "publication": "authorized_exact",
    }
    controls = []
    weakens = {
        "binding": "contract_only", "observation": "scalar_result",
        "cache": "caller_key_hit", "evidence": "portable_scalar_receipt",
        "authority": "initial_admission", "terminal": "body_stopped",
        "publication": "content_only",
    }
    for axis, weaker in weakens.items():
        mutated = dict(baseline, **{axis: weaker})
        status, reasons, _ = classify(mutated, {})
        if status != "blocked" or len(reasons) != 1:
            raise ValueError((axis, status, reasons))
        controls.append({"axis": axis, "variant": weaker, "reason": reasons[0]})
        # Positive counterexample to erroneously admitting this weakened bundle.
        queries.append((f"(and {smt_row(mutated, {})} blocked)", "sat"))

    if classify(baseline, {}) != ("admitted", [], []):
        raise ValueError("Baseline does not pass within the modeled scope")
    script = (HERE / "rules.smt2").read_text()
    for expression, _ in queries:
        script += f"\n(push 1)\n(assert {expression})\n(check-sat)\n(pop 1)\n"
    solvers = {"z3": ([args.z3, "-in"], "-version"), "cvc5": (
        [args.cvc5, "--incremental", "--lang=smt2"], "--version"
    )}
    versions = {}
    for solver, (command, version_arg) in solvers.items():
        run_solver(command, script, [expected for _, expected in queries])
        versions[solver] = subprocess.check_output(
            [command[0], version_arg], text=True
        ).splitlines()[0]

    evidence = {
        "input_revision": base, "pinned_reports": pinned_reports,
        "axes": list(axes), "bundles": [list(bundle.values()) for bundle in bundles],
        "columns": ["scenario", "bundle_zero_based", "status", "hard_conflicts", "open_conditions"],
        "rows": rows, "summary": summaries, "single_axis_controls": controls,
        "adoption_gates": config["adoption_gates"], "solver_versions": versions,
        "python_version": sys.version.split()[0], "git_version": git("--version"),
        "solver_queries_each": dict(Counter(expected for _, expected in queries)),
    }
    args.out.write_text(json.dumps(evidence, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
