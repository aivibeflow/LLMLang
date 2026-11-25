"""Trace scoped state-handler observations into four downstream decisions."""

from dataclasses import asdict
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOTYPE = ROOT / "research/PROTOTYPES/RT-04-01"
sys.path.insert(0, str(PROTOTYPE))
from rt03_typed_calls import Function, project_program, run_program

BASELINE = "4f64b33a5e1712435972a82348a79ea347cceb9b"
VALUES = (-2, -1, 0, 1, 2)
PROFILES = tuple(product((False, True), repeat=2))


def functions(observe_writes, guard):
    state = {"state_get": None}
    adjustment = Function((("delta", "Int"),), "Unit", {
        "state_put": {"add": [state, {"var": "delta"}]},
    }, requires_state=True)
    sequence = {"sequence": [
        {"call": ["adjust", [{"var": "first"}]]},
        {"call": ["adjust", [{"var": "second"}]]},
        state,
    ]}
    entry = Function((("start", "Int"), ("first", "Int"), ("second", "Int")), "Int", {
        "handle_state": [{"var": "start"}, observe_writes, guard, sequence],
    })
    return {"entry": entry, "adjust": adjustment}


def compare(start, first, second, observe_writes, guard):
    program = functions(observe_writes, guard)
    actual = asdict(run_program(program, "entry", (start, first, second), "D", checker="B"))
    state = start
    writes, result, failure = [], None, None
    for delta in (first, second):
        requested = state + delta
        accepted = not guard or requested >= 0
        if observe_writes:
            writes.append({"before": state, "requested": requested, "accepted": accepted})
        if not accepted:
            failure = {"requested": requested}
            break
        state = requested
    else:
        result = state
    assert actual["result"] == result and actual["writes"] == tuple(writes)
    assert actual["failure"] == failure
    assert actual["invocations"] == ("entry",) + ("adjust",) * (
        1 if failure is not None and guard and start + first < 0 else 2
    )
    return actual


def semantic(row):
    return row["result"], row["failure"], row["writes"]


def exercise():
    projection = project_program(functions(False, False), "D")
    for mode in PROFILES:
        assert project_program(functions(*mode), "D") == projection
    rows = []
    counts = {
        "oracle_checks": 0, "cross_profile_reuses": 0, "different_observations_on_cross_profile_reuse": 0,
        "order_comparisons": 0, "same_scalar_but_different_observations": 0,
        "fully_logged_total_order_comparisons": 0, "fully_logged_total_wrong_order": 0,
        "guard_profile_comparisons": 0, "guarded_failures": 0, "guard_stops_second_call": 0,
    }
    for start, a, b in product(VALUES, repeat=3):
        compared = {}
        for watch, guard in PROFILES:
            options = {"observe_writes": watch, "reject_negative_write": guard}
            a_then_b = compare(start, a, b, watch, guard)
            b_then_a = compare(start, b, a, watch, guard)
            compared[watch, guard] = options | {"a_then_b": a_then_b, "b_then_a": b_then_a}
            counts["oracle_checks"] += 2
            counts["order_comparisons"] += 1
            different = semantic(a_then_b) != semantic(b_then_a)
            counts["same_scalar_but_different_observations"] += (
                a_then_b["result"] == b_then_a["result"] and different
            )
            if watch and not guard:
                counts["fully_logged_total_order_comparisons"] += 1
                assert a_then_b["result"] == b_then_a["result"]
                counts["fully_logged_total_wrong_order"] += different
        for order in ("a_then_b", "b_then_a"):
            for old, new in combinations(PROFILES, 2):
                counts["cross_profile_reuses"] += 1
                counts["different_observations_on_cross_profile_reuse"] += (
                    semantic(compared[old][order]) != semantic(compared[new][order])
                )
            for logged in (False, True):
                total = compared[logged, False][order]
                guarded = compared[logged, True][order]
                counts["guard_profile_comparisons"] += 1
                if guarded["failure"] is None:
                    assert semantic(total) == semantic(guarded)
                else:
                    assert semantic(total) != semantic(guarded) and total["failure"] is None
                    counts["guarded_failures"] += 1
                    counts["guard_stops_second_call"] += len(guarded["invocations"]) == 2
                    if logged:
                        assert len(guarded["writes"]) == len(guarded["invocations"]) - 1
                        assert guarded["writes"][-1]["accepted"] is False
        rows.append({"start": start, "left_delta": a, "right_delta": b, "profiles": list(compared.values())})
    assert counts["oracle_checks"] == 1000 and counts["cross_profile_reuses"] == 1500
    return projection, rows, counts


def main():
    pins = {}
    for name in ("rt03_typed_calls.py", "rt04_model.py"):
        path = PROTOTYPE / name
        relative = str(path.relative_to(ROOT))
        archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
        assert archived == path.read_bytes()
        pins[relative] = hashlib.sha256(archived).hexdigest()
    projection, rows, counts = exercise()
    metadata = {"baseline": BASELINE, "python": platform.python_version(),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "sources": pins, "static_projection": projection, "value_domain": VALUES, "counts": counts}
    print(json.dumps(metadata, indent=2).removesuffix("\n}") + ',\n  "cases": [')
    print(",\n".join("    " + json.dumps(row) for row in rows))
    print("  ]\n}")


if __name__ == "__main__":
    main()
