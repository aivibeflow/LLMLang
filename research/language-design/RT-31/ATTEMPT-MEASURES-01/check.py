"""Check separate performance and semantic outcomes on synthetic attempt ledgers."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import platform
from statistics import median


HERE = Path(__file__).resolve().parent
ATTRIBUTION = HERE.parent / "MCP-ATTRIBUTION-01" / "evidence.json"
ATTRIBUTION_PIN = "062bf3475432e9e569afa9c6cc67ccc88319ed480371494e1d2f9c6febb7ea09"


@dataclass(frozen=True)
class Observation:
    session: str
    attempt: int
    snapshot: str
    status: str
    failed_checks: tuple[str, ...]
    tokens: int | None
    cost_nanos: int | None
    latency_ms: int | None
    review_ms: int | None


ROWS = (
    Observation("a", 1, "current", "pass", (), 20, 30, 8, 5),
    Observation("b", 1, "current", "fail", ("parse",), 25, 35, 12, None),
    Observation("b", 2, "current", "pass", (), 29, 39, 18, 7),
    Observation("c", 1, "current", "fail", ("semantic", "contract"), 30, 50, 17, None),
    Observation("c", 2, "current", "fail", ("contract",), 34, 56, 23, 8),
    Observation("d", 1, "current", "fail", ("type-effect-ownership",), None, None, 11, None),
    Observation("d", 2, "current", "pending", (), None, None, None, None),
    Observation("e", 1, "current", "fail", ("unsupported-claim", "mcp-tool-call"), 42, 57, 22, 9),
    Observation("e", 2, "current", "pass", (), 47, 62, 26, 12),
    Observation("f", 1, "current", "fail", ("task-completion",), 55, 76, None, 14),
    Observation("g", 1, "current", "pending", (), None, None, None, None),
    Observation("g", 1, "retired", "pass", (), 2, 3, 4, 5),
)


def collect(rows):
    current = {}
    for row in rows:
        if row.snapshot != "current":
            continue
        key = (row.session, row.attempt)
        if key in current and current[key] != row:
            raise ValueError("conflicting attempt evidence")
        current[key] = row
    first = [row for (_, attempt), row in current.items() if attempt == 1]
    repairs = [row for (_, attempt), row in current.items() if attempt > 1]
    assert all(any(item.session == row.session for item in first) for row in repairs)
    status = {name: Counter(row.status for row in group)
              for name, group in (("first_pass", first), ("repair_attempts", repairs))}
    errors = {name: Counter(check for row in group for check in row.failed_checks)
              for name, group in (("first_pass", first), ("repair_attempts", repairs))}
    metrics = {}
    for field in ("tokens", "cost_nanos", "latency_ms", "review_ms"):
        payloads = [getattr(row, field) for row in current.values()]
        known = [value for value in payloads if value is not None]
        metrics[field] = {"observed": len(known), "missing": len(payloads) - len(known),
                          "median": median(known) if known else None}
    first_pass = status["first_pass"]
    return {"status": status, "errors": errors, "metrics": metrics,
            "first_pass_sensitivity_to_pending": {
                "denominator": len(first), "minimum_possible_passes": first_pass["pass"],
                "maximum_possible_passes": first_pass["pass"] + first_pass["pending"],
            }}


def run():
    observed = collect(ROWS)
    for offset in range(len(ROWS)):
        shuffled = ROWS[offset:] + ROWS[:offset]
        assert collect(shuffled) == collect(reversed(shuffled)) == observed
    assert collect((*ROWS, ROWS[0])) == observed
    assert observed["status"] == {"first_pass": {"pass": 1, "fail": 5, "pending": 1},
                                  "repair_attempts": {"pass": 2, "fail": 1, "pending": 1}}
    assert len(observed["errors"]["first_pass"]) == 7
    raw = ATTRIBUTION.read_bytes()
    assert sha256(raw).hexdigest() == ATTRIBUTION_PIN
    totals = json.loads(raw)["totals"]
    assert (totals["schedules"], totals["exact_match"], totals["expected_multiple_causes"],
            totals["expected_unknown"]) == (66048, 66048, 43176, 12288)
    return {"python": platform.python_version(), "mode": "synthetic-attempt-report",
            "observation_orders": 2 * len(ROWS), "archived_attribution_sha256": ATTRIBUTION_PIN,
            "archived_attribution_totals": totals, **observed,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
