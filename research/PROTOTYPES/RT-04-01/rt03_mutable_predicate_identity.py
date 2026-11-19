"""Finite oracle for predicate identity across an explicit Boolean write."""
from __future__ import annotations

from itertools import product


Route = tuple[bool, bool]


def concrete_routes() -> frozenset[Route]:
    """Execute two reads separated by ``x := not x`` for both initial values."""
    routes = set()
    for x0 in (False, True):
        first_branch = x0
        x1 = not x0
        second_branch = x1
        routes.add((first_branch, second_branch))
    return frozenset(routes)


def name_conflated_routes() -> frozenset[Route]:
    """Incorrectly model both source reads as one immutable symbolic value."""
    return frozenset((x, x) for x in (False, True))


def independently_versioned_routes() -> frozenset[Route]:
    """Version x at each read but omit the assignment's transition relation."""
    return frozenset(product((False, True), repeat=2))


def transition_constrained_routes() -> frozenset[Route]:
    """Use x@0 and x@1, constrained by the explicit toggle assignment."""
    return frozenset(
        (x0, x1)
        for x0, x1 in product((False, True), repeat=2)
        if x1 is not x0
    )


if __name__ == "__main__":
    print("concrete:", sorted(concrete_routes()))
    print("name-conflated:", sorted(name_conflated_routes()))
    print("independent-versions:", sorted(independently_versioned_routes()))
    print("transition-constrained:", sorted(transition_constrained_routes()))
