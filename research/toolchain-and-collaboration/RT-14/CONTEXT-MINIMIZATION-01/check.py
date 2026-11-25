"""Check exact permission and field minimization before bounded context rendering."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import platform


@dataclass(frozen=True)
class Entry:
    key: str
    scope: str
    mandatory: bool
    priority: int
    approved_excerpt: str
    private_fixture: str


ENTRIES = (
    Entry("contract", "core", True, 0, "exact contract", "FIXTURE-PRIVATE-ONE"),
    Entry("trace", "observations", False, 9, "short trace", "FIXTURE-PRIVATE-TWO"),
    Entry("example", "examples", False, 4, "bounded example", "FIXTURE-PRIVATE-THREE"),
)
GRANTS = ((), ("core",), ("core", "observations"), ("core", "examples"),
          ("core", "observations", "examples"), ("observations", "examples"))
LIMITS = (0, 10, 25, 50, 80, 120, 300)
NOW = 4


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def envelope(row):
    return {"key": row.key, "excerpt": row.approved_excerpt}


def assemble(entries, grant_epoch, scopes, limit):
    if grant_epoch != NOW:
        return {"status": "unavailable", "body": "", "omitted_for_budget": []}
    projected = sorted(entries, key=lambda row: (not row.mandatory, -row.priority, row.key))
    mandatory = [row for row in projected if row.mandatory]
    if any(row.scope not in scopes for row in mandatory):
        return {"status": "unavailable", "body": "", "omitted_for_budget": []}
    selected = [envelope(row) for row in mandatory]
    body = encode(selected)
    if len(body) > limit:
        return {"status": "over-budget", "body": "", "omitted_for_budget": []}
    skipped = []
    for row in projected:
        if row.mandatory or row.scope not in scopes:
            continue
        candidate = encode([*selected, envelope(row)])
        if len(candidate) > limit:
            skipped.append(row.key)
        else:
            selected.append(envelope(row))
            body = candidate
    return {"status": "ready", "body": body.decode(), "omitted_for_budget": skipped}


def run():
    counts = Counter()
    decisions = 0
    assertions = 0
    for ordered, scopes, epoch, limit in product(permutations(ENTRIES), GRANTS, (3, 4), LIMITS):
        result = assemble(ordered, epoch, scopes, limit)
        assert result == assemble(ENTRIES, epoch, scopes, limit)
        authorized = {row.key for row in ENTRIES if row.scope in scopes}
        public = encode(result)
        assert all(row.private_fixture.encode() not in public for row in ENTRIES)
        if epoch != NOW or "core" not in scopes:
            assert result == {"status": "unavailable", "body": "", "omitted_for_budget": []}
        elif len(encode([envelope(ENTRIES[0])])) > limit:
            assert result["status"] == "over-budget" and result["body"] == ""
        else:
            assert result["status"] == "ready"
            body = json.loads(result["body"])
            assert len(result["body"].encode()) <= limit
            assert {item["key"] for item in body} | set(result["omitted_for_budget"]) == authorized
            assert all(item in [envelope(row) for row in ENTRIES] for item in body)
        counts[result["status"]] += 1
        decisions += 1
        assertions += len(ENTRIES)
    hidden_changed = tuple(Entry(row.key, row.scope, row.mandatory, row.priority,
                                 row.approved_excerpt, row.private_fixture + "-rotated") for row in ENTRIES)
    assert assemble(hidden_changed, 4, GRANTS[4], 300) == assemble(ENTRIES, 4, GRANTS[4], 300)
    return {"python": platform.python_version(), "decisions": decisions, "counts": counts,
            "fixture_private_field_controls": assertions,
            "changed_hidden_fields_preserve_rendering": True,
            "budget_unit": "UTF-8 bytes in fixture canonical JSON",
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
