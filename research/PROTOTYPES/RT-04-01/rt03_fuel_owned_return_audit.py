"""Independent obligation projection for the fuel/owned-return probe.

The audit consumes observations from ``rt03_fuel_owned_return`` but does not
reuse its transition logic. It reconstructs expected owners from the declared
return-timing and cleanup-budget dimensions, then checks trace/owner coverage
for the finite scenario matrix. This is a cross-check of a bounded model, not
a test suite or a proof of source semantics.
"""
from __future__ import annotations

from itertools import product

from rt03_fuel_owned_return import run_fuel_exhaustion_at_return


def audit_observation(observation) -> tuple[str, ...]:
    issues: list[str] = []
    owner_pairs = observation.owners
    owners = dict(owner_pairs)
    if len(owners) != len(owner_pairs):
        issues.append("duplicate resource owner entry")
    if set(owners) - {"temporary", "handle"}:
        issues.append("unknown resource in owner map")

    expected_names = []
    blocked_names = []
    expected_owners: dict[str, str] = {}
    if observation.cleanup_budget == "depleted":
        blocked_names.append("temporary")
        expected_owners["temporary"] = "callee_cleanup_debt"
        if observation.return_timing == "reserve_then_commit":
            blocked_names.append("handle")
            expected_owners["handle"] = "pending_return_cleanup_debt"
        elif owners.get("handle") != "caller":
            issues.append("transfer-first handle is not caller-owned")
    else:
        expected_names.append("temporary")
        temp_result = dict(observation.cleanup_trace).get("temporary")
        if temp_result == "error":
            expected_owners["temporary"] = "callee_cleanup_debt"
        elif temp_result != "ok":
            issues.append("temporary cleanup result missing or invalid")

        if observation.return_timing == "reserve_then_commit":
            expected_names.append("handle")
            handle_result = dict(observation.cleanup_trace).get("handle")
            if handle_result == "error":
                expected_owners["handle"] = "pending_return_cleanup_debt"
            elif handle_result != "ok":
                issues.append("pending handle cleanup result missing or invalid")
        elif owners.get("handle") != "caller":
            issues.append("transfer-first handle is not caller-owned")

    if tuple(expected_names) != tuple(name for name, _ in observation.cleanup_trace):
        issues.append("cleanup attempt order does not match policy")
    if tuple(blocked_names) != observation.cleanup_blocked:
        issues.append("blocked cleanup obligations do not match policy")
    if owners != expected_owners and not (
        observation.return_timing == "transfer_then_cleanup"
        and owners == {**expected_owners, "handle": "caller"}
    ):
        issues.append(f"owner map mismatch: expected {expected_owners}, got {owners}")
    if observation.returned_value != (
        "handle" if observation.return_timing == "transfer_then_cleanup" else None
    ):
        issues.append("returned value does not match return timing")
    if not observation.fuel_exhausted:
        issues.append("fuel exhaustion outcome missing")
    if observation.effect_trace != ("write:recorded",):
        issues.append("completed effect trace was lost or changed")
    return tuple(issues)


def enumerate_observations() -> tuple[int, tuple[tuple[object, tuple[str, ...]], ...]]:
    cases = []
    for timing, budget in product(
        ("reserve_then_commit", "transfer_then_cleanup"),
        ("reserved", "depleted"),
    ):
        if budget == "depleted":
            combinations = ((False, False),)
        elif timing == "reserve_then_commit":
            combinations = product((False, True), repeat=2)
        else:
            combinations = ((False, False), (True, False))
        for temporary_fails, handle_fails in combinations:
            observation = run_fuel_exhaustion_at_return(
                timing,
                budget,
                temporary_release_fails=temporary_fails,
                pending_handle_release_fails=handle_fails,
            )
            cases.append((observation, audit_observation(observation)))
    return len(cases), tuple(cases)


if __name__ == "__main__":
    count, observations = enumerate_observations()
    failures = [(observation, issues) for observation, issues in observations if issues]
    print(f"Audited {count} bounded observations; {count - len(failures)} satisfy the obligation projection.")
    for observation, issues in failures:
        print(observation)
        for issue in issues:
            print(f"  - {issue}")
    if failures:
        raise SystemExit(1)
