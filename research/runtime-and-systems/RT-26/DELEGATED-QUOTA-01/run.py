"""Enumerate safe reclaim and later settlement for a delegated cumulative quota."""

import json
import platform


def study():
    totals = {
        "initial_states": 0,
        "request_cases": 0,
        "full_return_unsafe_admissions": 0,
        "safe_reclaim_unsafe_admissions": 0,
        "exact_settlement_cases": 0,
        "settlement_unsafe_admissions": 0,
    }
    for budget in range(1, 13):
        for delegated in range(budget + 1):
            for spent in range(delegated + 1):
                for held in range(delegated - spent + 1):
                    free = delegated - spent - held
                    parent = budget - delegated
                    reclaimed = parent + free
                    assert reclaimed + held + spent == budget
                    totals["initial_states"] += 1
                    for demand in range(budget + 1):
                        totals["request_cases"] += 1
                        universally_safe = all(demand + spent + used <= budget for used in range(held + 1))
                        assert (demand <= reclaimed) == universally_safe
                        totals["safe_reclaim_unsafe_admissions"] += demand <= reclaimed and not universally_safe
                        totals["full_return_unsafe_admissions"] += demand <= parent + delegated and not universally_safe

                        for confirmed in range(held + 1):
                            after_settlement = reclaimed + held - confirmed
                            assert after_settlement + spent + confirmed == budget
                            affordable = demand <= after_settlement
                            actual = demand + spent + confirmed <= budget
                            assert affordable == actual
                            totals["exact_settlement_cases"] += 1
                            totals["settlement_unsafe_admissions"] += affordable and not actual
    assert totals["full_return_unsafe_admissions"] > 0
    return {
        "python": platform.python_version(),
        "budget_upper_bound": 12,
        "totals": totals,
        "example": {
            "budget": 5,
            "parent_before_reclaim": 1,
            "child_spent": 2,
            "child_unsettled": 1,
            "child_available": 1,
            "parent_after_reclaim": 2,
            "parent_after_exact_settlement_reports_zero_use": 3,
            "parent_after_exact_settlement_reports_one_use": 2,
            "parent_after_restoring_entire_grant": 5,
        },
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
