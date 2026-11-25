"""Check finite Knowledge Context inventories under rank-only and exact selection."""

import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return sha256(value).hexdigest()


@dataclass(frozen=True, order=True)
class Entry:
    role: str
    source: str
    snapshot: str
    content: str
    rank: int

    @property
    def cost(self):
        return len(self.content.encode()) + 1

    def reference(self):
        return {"source": self.source, "sha256": digest(self.content.encode())}


CONTRACT = Entry("contract", "spec#1", "snap-7", "quota ≤ 3", 20)
TEST = Entry("test", "test#1", "snap-7", "4 is error", 10)
NOTE = Entry("note", "design#1", "snap-7", "retry safely", 30)
OTHER_NOTE = replace(NOTE, source="design#2", content="manual retry")
STALE_TEST = replace(TEST, snapshot="snap-6", rank=50)
CONFLICT = replace(CONTRACT, source="spec#2", content="quota ≤ 4", rank=40)
CORRUPT = replace(TEST, content="5 is error")
BASIS = (CONTRACT, TEST, NOTE)


@dataclass(frozen=True)
class Scope:
    revision: str = "capability-revision-1"
    read: frozenset[str] = frozenset({"spec#1", "test#1", "design#1", "design#2", "spec#2"})


@dataclass(frozen=True)
class Case:
    name: str
    entries: tuple[Entry, ...]
    budget: int
    expected: str
    ranked_loses_required: bool
    scope: Scope = Scope()


def render(entries):
    return "".join(entry.content + "\n" for entry in entries).encode()


def ranked(entries, scope, budget):
    remaining = budget
    chosen = []
    for entry in sorted(entries, key=lambda row: (-row.rank, row)):
        if entry.source in scope.read and entry.role in {"contract", "test", "note"}:
            if entry.cost <= remaining:
                chosen.append(entry)
                remaining -= entry.cost
    return chosen


def exact(entries, scope, budget, required, optional):
    selected = []
    by_role = {}
    for entry in entries:
        if entry.snapshot == "snap-7" and entry.source in scope.read:
            by_role.setdefault(entry.role, set()).add(entry)

    for role, reference in sorted(required.items()):
        available = by_role.get(role, set())
        if not available:
            return {"status": "unavailable"}
        refs = {item.source for item in available}
        if refs != {reference["source"]}:
            return {"status": "conflicting-required"}
        if any(item.reference() != reference for item in available):
            return {"status": "required-bytes-mismatch"}
        # Ranking is irrelevant for mandatory identity.
        selected.append(min(available))

    remaining = budget - sum(entry.cost for entry in selected)
    if remaining < 0:
        return {"status": "required-over-budget"}

    omissions = {}
    for role in sorted(optional):
        available = by_role.get(role, set())
        # Independent sources or bytes for one optional role require adjudication.
        references = {(entry.source, entry.reference()["sha256"]) for entry in available}
        if len(references) > 1:
            omissions[role] = "ambiguous"
        elif not available:
            omissions[role] = "unavailable"
        else:
            entry = min(available)
            if entry.cost <= remaining:
                selected.append(entry)
                remaining -= entry.cost
            else:
                omissions[role] = "over-budget"

    manifest = {
        "snapshot": "snap-7",
        "purpose": "review-quota-change",
        "assembly_version": 1,
        "scope_revision": scope.revision,
        "budget_utf8_bytes": budget,
        "required": required,
        "bindings": {entry.role: entry.reference() for entry in selected},
        "omissions": omissions,
    }
    return {"status": "ready", "manifest": manifest, "manifest_sha256": digest(canonical(manifest)),
            "rendered_sha256": digest(render(selected)), "rendered_utf8_bytes": budget - remaining}


def check():
    narrow_scope = Scope("limited-capability", frozenset({"spec#1", "design#1"}))
    cases = (
        Case("complete", BASIS, 50, "ready", False),
        Case("same-bytes-other-scope-revision", BASIS, 50, "ready", False, Scope("renewed")),
        Case("stale-required-only", (CONTRACT, STALE_TEST, NOTE), 50, "unavailable", True),
        Case("fresh-and-stale-copy", (*BASIS, STALE_TEST), 50, "ready", False),
        Case("missing-required", (CONTRACT, NOTE), 50, "unavailable", True),
        Case("inaccessible-required", BASIS, 50, "unavailable", True, narrow_scope),
        Case("conflicting-required", (*BASIS, CONFLICT), 50, "conflicting-required", False),
        Case("corrupt-required", (CONTRACT, CORRUPT, NOTE), 50, "required-bytes-mismatch", True),
        Case("duplicate-required", (*BASIS, CONTRACT), 50, "ready", False),
        Case("required-ranking-changed", (replace(CONTRACT, rank=1), TEST, NOTE),
             50, "ready", False),
        Case("ambiguous-optional", (*BASIS, OTHER_NOTE), 50, "ready", False),
        Case("optional-trims-to-budget", BASIS, 23, "ready", True),
        Case("required-over-budget", BASIS, 22, "required-over-budget", True),
        Case("optional-same-text-other-source", (CONTRACT, TEST, replace(NOTE, source="design#2")),
             50, "ready", False),
        Case("hidden-alternative", (*BASIS, CONFLICT), 50, "ready", False,
             Scope("without-conflicting-source", frozenset({"spec#1", "test#1", "design#1"}))),
    )
    required = {"contract": CONTRACT.reference(), "test": TEST.reference()}
    data = {}
    runs = 0
    for case in cases:
        distinct = sorted(set(permutations(case.entries)))
        outcomes = []
        weak_outcomes = []
        for order in distinct:
            outcomes.append(exact(order, case.scope, case.budget, required, {"note"}))
            weak = ranked(order, case.scope, case.budget)
            exact_keys = {(entry.role, entry.snapshot, entry.source, entry.reference()["sha256"])
                          for entry in weak}
            weak_outcomes.append({
                "rendered": render(weak).decode(),
                "count": len(weak),
                "exact_required_present": all(
                    (role, "snap-7", ref["source"], ref["sha256"]) in exact_keys
                    for role, ref in required.items()),
            })
        first, weak_first = outcomes[0], weak_outcomes[0]
        if any(outcome != first for outcome in outcomes):
            raise ValueError(f"Order dependence in exact selection: {case.name}")
        if any(outcome != weak_first for outcome in weak_outcomes):
            raise ValueError(f"Order dependence in ranked selection: {case.name}")
        if first["status"] != case.expected:
            raise ValueError((case.name, case.expected, first))
        if weak_first["exact_required_present"] != (not case.ranked_loses_required):
            raise ValueError((case.name, weak_first))
        if first["status"] == "ready":
            assert all(first["manifest"]["bindings"][role] == value
                       for role, value in required.items())
            assert first["rendered_utf8_bytes"] <= case.budget
        else:
            assert first == {"status": case.expected}
        runs += len(distinct)
        data[case.name] = {"permutations": len(distinct), "ranked": weak_first, "exact": first}

    def outcome(name):
        return data[name]["exact"]

    baseline = outcome("complete")
    for name in ("duplicate-required", "fresh-and-stale-copy", "required-ranking-changed"):
        assert outcome(name) == baseline
    for name in ("same-bytes-other-scope-revision", "optional-same-text-other-source"):
        changed = outcome(name)
        assert changed["rendered_sha256"] == baseline["rendered_sha256"]
        assert changed["manifest_sha256"] != baseline["manifest_sha256"]
    assert outcome("missing-required") == outcome("inaccessible-required")
    assert outcome("hidden-alternative")["rendered_sha256"] == baseline["rendered_sha256"]
    assert outcome("ambiguous-optional")["manifest"]["omissions"] == {"note": "ambiguous"}
    assert outcome("optional-trims-to-budget")["manifest"]["omissions"] == {"note": "over-budget"}
    return {
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "cases": data,
        "totals": {
            "inventory_cases": len(data),
            "orders_per_policy": runs,
            "exact_ready": sum(row["exact"]["status"] == "ready" for row in data.values()),
            "ranked_feeds_missing_exact_required": sum(
                not row["ranked"]["exact_required_present"] for row in data.values()),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(check(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
