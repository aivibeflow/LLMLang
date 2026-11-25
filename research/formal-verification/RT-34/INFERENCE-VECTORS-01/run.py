#!/usr/bin/env python3
"""Compare resource inference vectors on pre-adjudication pointwise benchmarks."""

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASIS = ("constant", "n", "square", "hidden")
Equation = tuple[int, int, int, int]
LINEAR = (0, 1, 0, 0)
QUADRATIC = (0, 0, 1, 0)
DELAYED = (0, 1, 0, 1)
ZERO = (0, 0, 0, 0)
VISIBLE_SIZES = range(13)
WITNESS_SIZES = range(65)
MODELS = {
    "sum-steps": LINEAR,
    "rectangular-steps": QUADRATIC,
    "equal-size-pipeline": (0, 2, 0, 0),
    "expanded-pipeline": (0, 1, 1, 0),
    "hidden-expensive-branch": DELAYED,
    "foreign-assumption": (0, 2, 0, 0),
    "no-provider-bound": None,
}


@dataclass(frozen=True)
class Case:
    id: str
    subject: str
    bound: Equation
    expected: str
    domain: str = "all-natural"
    scope: str = "exact-steps"
    assumption: str | None = None


CASES = (
    Case("CXB-001-exact", "sum-steps", LINEAR, "proved"),
    Case("CXB-001-too-low", "sum-steps", ZERO, "refuted"),
    Case("CXB-008-rectangle", "rectangular-steps", QUADRATIC, "proved"),
    Case("CXB-008-linear-claim", "rectangular-steps", LINEAR, "refuted"),
    Case("CXB-016-size-preserved", "equal-size-pipeline", (0, 2, 0, 0), "proved"),
    Case("CXB-016-size-expanded", "expanded-pipeline", (0, 2, 0, 0), "refuted"),
    Case("CXB-022-missing", "no-provider-bound", LINEAR, "unknown"),
    Case("CXB-022-conditional", "foreign-assumption", (0, 2, 0, 0), "conditional",
         assumption="provider twice-n summary"),
    Case("CXB-024-extra-work", "rectangular-steps", LINEAR, "refuted"),
    Case("CXB-026-finite-parent", "sum-steps", LINEAR, "unsupported", domain="0-12"),
    Case("CXB-026-empty-parent", "sum-steps", LINEAR, "unsupported", domain="empty"),
    Case("CXB-029-threshold", "hidden-expensive-branch", LINEAR, "refuted"),
    Case("CXB-029-bounded-domain", "hidden-expensive-branch", LINEAR, "unsupported", domain="0-12"),
    Case("CXB-030-wrong-projection", "sum-steps", LINEAR, "unsupported", scope="wall-time"),
)


def value(equation, n):
    coordinates = (1, n, n * n, 128 if n > 32 else 0)
    return sum(coefficient * term for coefficient, term in zip(equation, coordinates, strict=True))


def finite(case):
    if case.domain == "empty" or case.scope != "exact-steps":
        return "abstain", None
    model = MODELS[case.subject]
    if model is None:
        return "abstain", None
    for n in VISIBLE_SIZES:
        if value(model, n) > value(case.bound, n):
            return "visible-witness", n
    return "finite-agreement", None


def eligible(case):
    if case.domain != "all-natural" or case.scope != "exact-steps":
        return "unsupported"
    if MODELS[case.subject] is None:
        return "unknown"
    return None


def symbolic(case):
    unavailable = eligible(case)
    if unavailable:
        return unavailable, None
    model = MODELS[case.subject]
    if all(cost <= bound for cost, bound in zip(model, case.bound, strict=True)):
        return ("conditional" if case.assumption else "proved"), None
    for n in WITNESS_SIZES:
        if value(model, n) > value(case.bound, n):
            return "refuted", n
    return "unknown", None


def expr(equation):
    terms = ("1", "n", "(n * n)", "(if 32 < n then 128 else 0)")
    return " + ".join(f"{a} * {b}" for a, b in zip(equation, terms, strict=True))


def goal(case, disposition, witness):
    cost = expr(MODELS[case.subject])
    bound = expr(case.bound)
    if disposition in ("proved", "conditional"):
        return f"theorem audited (n : Nat) : {cost} ≤ {bound} := by omega\n"
    if disposition == "refuted":
        return f"theorem audited : ∃ n : Nat, {bound} < {cost} := by\n  exact ⟨{witness}, by decide⟩\n"
    raise ValueError(disposition)


def checked_goal(work, lean, source):
    destination = work / "Audit.lean"
    source += "#print axioms audited\n"
    destination.write_text(source, encoding="utf-8")
    result = subprocess.run([lean, "-DwarningAsError=true", destination.name], cwd=work, text=True,
                            capture_output=True, check=False)
    assert not result.stderr
    if result.returncode:
        assert "omega could not prove the goal" in result.stdout
        return {"disposition": "unknown", "source": sha256(source.encode()).hexdigest()}
    allowed = (
        "'audited' does not depend on any axioms",
        "'audited' depends on axioms: [propext, Quot.sound]",
    )
    assert result.stdout.strip() in allowed
    return {"disposition": "kernel-checked", "source": sha256(source.encode()).hexdigest(),
            "axiom_audit": result.stdout.strip()}


def experiment(work):
    lean = os.environ.get("LEAN", "lean")
    rows = []
    counts = Counter()
    for case in CASES:
        expected = case.expected
        empirical, empirical_witness = finite(case)
        checked, witness = symbolic(case)
        assert expected == checked
        unknown = eligible(case)
        if unknown is not None:
            manual = {"disposition": unknown}
            audit = {"disposition": unknown}
        else:
            manual = checked_goal(work, lean, goal(case, "proved", None))
            assert (manual["disposition"] == "kernel-checked") == (expected in ("proved", "conditional"))
            if expected == "conditional":
                manual["disposition"] = "kernel-checked-under-foreign-assumption"
            audit = checked_goal(work, lean, goal(case, checked, witness))
            assert audit["disposition"] == "kernel-checked"
        counts[f"label/{checked}"] += 1
        counts[f"manual/{manual['disposition']}"] += 1
        counts[f"finite/{empirical}"] += 1
        counts["false_promotion_if_finite_agreement_means_proved"] += (
            empirical == "finite-agreement" and expected == "refuted"
        )
        rows.append({
            "case": asdict(case), "adjudication": "provisional",
            "manual_budget_vc": manual,
            "finite_scaling": {"disposition": empirical, "witness": empirical_witness},
            "symbolic": {"disposition": checked, "witness": witness},
            "kernel_audit": audit,
        })
    assert counts["false_promotion_if_finite_agreement_means_proved"] == 1
    assert next(row for row in rows if "threshold" in row["case"]["id"])["symbolic"]["witness"] == 33

    # Replay the hand-provided potential certificate from the separate FIFO
    # pilot under the same kernel. This is not an automatic potential search.
    fifo = HERE.parent / "READ-LOWER-AND-QUEUE-01/Bounds.lean"
    potential = subprocess.run([lean, "-DwarningAsError=true", str(fifo)], cwd=work,
                               capture_output=True, text=True, check=True)
    assert "'history_charge' depends on axioms: [propext, Quot.sound]" in potential.stdout
    assert not potential.stderr
    return {
        "format": "inference-vectors-01", "adjudication": "provisional/no-human-adjudication",
        "lean": subprocess.check_output([lean, "--version"], cwd=work, text=True).strip(),
        "visible_sizes": [min(VISIBLE_SIZES), max(VISIBLE_SIZES)],
        "witness_search_sizes": [min(WITNESS_SIZES), max(WITNESS_SIZES)],
        "basis": BASIS, "counts": dict(counts), "rows": rows,
        "potential_vector": {"disposition": "checked-hand-provided-potential",
                             "source": sha256(fifo.read_bytes()).hexdigest()},
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-inference-vectors-") as temporary:
        ledger = experiment(Path(temporary))
    text = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
