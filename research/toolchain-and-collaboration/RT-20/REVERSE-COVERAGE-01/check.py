"""Check reverse-call completeness across distinct call-site families."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


KINDS = ("direct", "indirect", "dynamic", "external", "generated")
CONTEXT = ("snapshot:current", "target:leaf-v2", "extractor:v1", "declared-scope:a")
INVENTORIES = {
    "direct": ("entry:site-1",),
    "indirect": ("table:site-2",),
    "dynamic": ("registry:site-3",),
    "external": (),
    "generated": ("generator:site-4",),
}


@dataclass(frozen=True)
class Coverage:
    kind: str
    context: tuple[str, ...]
    closed: bool
    positions: tuple[str, ...]


def verify(inventory, receipts):
    expected = set(inventory)
    claimed = [item.kind for item in receipts]
    if len(claimed) != len(set(claimed)) or set(claimed) != expected:
        return "unknown-roster", ()
    for item in receipts:
        if item.context != CONTEXT:
            return "stale", ()
    for item in receipts:
        if not item.closed:
            return "open-domain", ()
    for item in receipts:
        if sorted(item.positions) != sorted(inventory[item.kind]):
            return "inventory-disagrees", ()
    return "exact", tuple(sorted((item.kind, position) for item in receipts for position in item.positions))


def collect():
    counts = Counter()
    options = ("exact", "missing", "open", "stale", "different-positions")
    for states in product(options, repeat=len(KINDS)):
        receipts = []
        for kind, status in zip(KINDS, states, strict=True):
            if status == "missing":
                continue
            record = Coverage(kind, CONTEXT, True, INVENTORIES[kind])
            if status == "open":
                record = replace(record, closed=False)
            if status == "stale":
                record = replace(record, context=("snapshot:old", *CONTEXT[1:]))
            if status == "different-positions":
                record = replace(record, positions=() if INVENTORIES[kind] else ("unknown:site",))
            receipts.append(record)
        outcome, positions = verify(INVENTORIES, receipts)
        assert (outcome == "exact") == (states == ("exact",) * len(KINDS))
        if positions:
            assert set(positions) == {(kind, pos) for kind, sites in INVENTORIES.items() for pos in sites}
        counts[outcome] += 1
    empty = dict.fromkeys(KINDS, ())
    all_closed = tuple(Coverage(kind, CONTEXT, True, ()) for kind in KINDS)
    assert verify(empty, all_closed) == ("exact", ())
    assert verify(empty, all_closed[:-1]) == ("unknown-roster", ())
    assert verify(empty, (*all_closed, all_closed[0])) == ("unknown-roster", ())
    assert verify(empty, (replace(all_closed[0], closed=False), *all_closed[1:])) == ("open-domain", ())
    return {"python": platform.python_version(), "cases": sum(counts.values()), "outcomes": counts,
            "independent_inventory": INVENTORIES,
            "empty_results": {"all_families_closed": "exact", "missing_family": "unknown-roster",
                              "duplicate_family": "unknown-roster", "open_family": "open-domain"},
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, indent=2))
