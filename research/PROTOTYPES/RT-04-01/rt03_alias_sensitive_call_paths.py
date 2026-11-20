"""Finite path relation for a reference parameter that may alias one of two fields."""
from __future__ import annotations

from itertools import product


Route = tuple[bool, bool]
FIELDS = frozenset({"flag", "other"})


def routes_for_alias_targets(targets: frozenset[str]) -> frozenset[Route]:
    """Enumerate two branches around a call toggling its referenced Boolean field."""
    if not targets or not targets <= FIELDS:
        raise ValueError("alias targets must be a non-empty subset of the modeled fields")
    routes = set()
    for flag0, other0 in product((False, True), repeat=2):
        for target in targets:
            flag1 = not flag0 if target == "flag" else flag0
            routes.add((flag0, flag1))
    return frozenset(routes)


def routes_for_summary(summary: str) -> frozenset[Route]:
    """Apply call-site points-to evidence; unknown aliases havoc the visible field."""
    if summary == "exact_flag":
        targets = frozenset({"flag"})
    elif summary == "exact_other":
        targets = frozenset({"other"})
    elif summary == "may_alias_either":
        targets = FIELDS
    elif summary == "unknown_aliases":
        # The modeled reachable region is both fields; no complete points-to set exists.
        targets = FIELDS
    else:
        raise ValueError(f"unsupported alias summary: {summary!r}")
    return routes_for_alias_targets(targets)


def incorrectly_assume_no_alias() -> frozenset[Route]:
    """Incorrect path result if the call is treated as writing only `other`."""
    return routes_for_summary("exact_other")


if __name__ == "__main__":
    for summary in ("exact_flag", "exact_other", "may_alias_either", "unknown_aliases"):
        print(summary, sorted(routes_for_summary(summary)))
