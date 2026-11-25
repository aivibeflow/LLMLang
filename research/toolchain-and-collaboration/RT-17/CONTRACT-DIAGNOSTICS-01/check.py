"""Check structured contract diagnostics against an exact evaluation context."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


PATH = ("entry", "call:reserve", "provider:reserve")
EVENTS = ("read", "commit")
REVERSE_EDGES = (
    ("provider:reserve", "call:reserve"), ("call:reserve", "entry"),
    ("provider:other", "audit"),
)


def digest(record):
    return sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Context:
    snapshot: str
    contract: str
    profile: str
    call_path: tuple[str, ...]


@dataclass(frozen=True)
class Receipt:
    context: Context
    input_value: int
    result: int | None
    ordered_effects: tuple[str, ...] | None


def diagnose(current, receipt, expected_input, maximum):
    common = {"context": asdict(current), "input": expected_input}
    if receipt is None or (receipt.context, receipt.input_value) != (current, expected_input):
        return {**common, "state": "unavailable", "failures": []}
    if receipt.result is None or receipt.ordered_effects is None:
        return {**common, "state": "unavailable", "failures": []}
    failures = []
    if receipt.result > maximum:
        failures.append({"clause": "output-upper-bound", "expected_max": maximum,
                         "observed": receipt.result})
    if receipt.ordered_effects != EVENTS:
        failures.append({"clause": "event-order", "expected": EVENTS,
                         "observed": receipt.ordered_effects})
    return {**common, "state": "observed-failure" if failures else "observed-match",
            "failures": failures}


def affected(edited, complete_inventory):
    if not complete_inventory:
        return {"state": "unavailable", "affected": []}
    reached = {edited}
    while True:
        next_round = reached | {caller for provider, caller in REVERSE_EDGES if provider in reached}
        if next_round == reached:
            break
        reached = next_round
    return {"state": "known", "affected": sorted(reached)}


def run():
    outcomes = Counter()
    examples = {}
    for before, shift, changed_order, evidence in product(
        range(9), (-1, 0, 1, 2), (False, True),
        ("exact", "missing", "stale-snapshot", "other-clause", "other-profile",
         "other-path", "different-input", "partial-trace"),
    ):
        context = Context(digest([before, shift, changed_order]), "reserve:contract-1", "finite:profile-1", PATH)
        trace = tuple(reversed(EVENTS)) if changed_order else EVENTS
        receipt = Receipt(context, before, before + shift, trace)
        if evidence == "missing":
            receipt = None
        elif evidence == "stale-snapshot":
            receipt = replace(receipt, context=replace(context, snapshot="previous"))
        elif evidence == "other-clause":
            receipt = replace(receipt, context=replace(context, contract="reserve:contract-2"))
        elif evidence == "other-profile":
            receipt = replace(receipt, context=replace(context, profile="finite:profile-2"))
        elif evidence == "other-path":
            receipt = replace(receipt, context=replace(context, call_path=("entry", "call:other", "provider:reserve")))
        elif evidence == "different-input":
            receipt = replace(receipt, input_value=before + 1)
        elif evidence == "partial-trace":
            receipt = replace(receipt, ordered_effects=None)
        row = diagnose(context, receipt, before, before)
        expected = []
        if evidence != "exact":
            assert row["state"] == "unavailable" and not row["failures"]
        else:
            if shift > 0:
                expected.append("output-upper-bound")
            if changed_order:
                expected.append("event-order")
            assert row["state"] == ("observed-failure" if expected else "observed-match")
            assert [item["clause"] for item in row["failures"]] == expected
        key = row["state"] if not expected else "+".join(expected)
        outcomes[key] += 1
        examples.setdefault(key, row)
    assert set(outcomes) == {"unavailable", "observed-match", "output-upper-bound", "event-order",
                             "output-upper-bound+event-order"}
    impact = {
        "selected_provider": affected("provider:reserve", True),
        "unrelated_provider": affected("provider:other", True),
        "incomplete_inventory": affected("provider:reserve", False),
    }
    assert impact == {
        "selected_provider": {"state": "known", "affected": ["call:reserve", "entry", "provider:reserve"]},
        "unrelated_provider": {"state": "known", "affected": ["audit", "provider:other"]},
        "incomplete_inventory": {"state": "unavailable", "affected": []},
    }
    return {"python": platform.python_version(), "cases": sum(outcomes.values()), "counts": outcomes,
            "impact": impact,
            "examples": examples, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
