"""Enumerate bounded inputs for local, relational and indexed zip contracts."""

from itertools import product
import json
import platform


BOUND = 4


def locally_bounded_zip(left, right):
    assert len(left) <= BOUND and len(right) <= BOUND
    return tuple(zip(left, right))


def checked_zip(left, right):
    if len(left) != len(right):
        return None
    return tuple(zip(left, right, strict=True))


def from_declared_length(left, right, declared):
    if len(left) != declared or len(right) != declared:
        return None
    return tuple(zip(left, right, strict=True))


def study():
    lists = [items for n in range(BOUND + 1) for items in product((0, 1), repeat=n)]
    totals = {
        "list_pairs": 0,
        "local_bound_admissions": 0,
        "local_admissions_that_truncate": 0,
        "relational_admissions": 0,
        "declared_length_cases": 0,
        "declared_length_admissions": 0,
        "equal_length_pairs_with_a_rejected_declaration": 0,
    }
    for left, right in product(lists, repeat=2):
        totals["list_pairs"] += 1
        local = locally_bounded_zip(left, right)
        checked = checked_zip(left, right)
        totals["local_bound_admissions"] += 1
        common = min(len(left), len(right))
        expected_pairs = tuple((left[index], right[index]) for index in range(common))
        assert local == expected_pairs
        equal_lengths = len(left) == len(right)
        assert checked == (expected_pairs if equal_lengths else None)
        totals["local_admissions_that_truncate"] += not equal_lengths
        totals["relational_admissions"] += checked is not None

        decisions = []
        for declared in range(BOUND + 1):
            totals["declared_length_cases"] += 1
            result = from_declared_length(left, right, declared)
            decisions.append(result is not None)
            assert result == (expected_pairs if declared == len(left) == len(right) else None)
        totals["declared_length_admissions"] += sum(decisions)
        totals["equal_length_pairs_with_a_rejected_declaration"] += equal_lengths and not all(decisions)

    assert tuple(totals.values()) == (961, 961, 620, 341, 4805, 341, 341)
    return {"python": platform.python_version(), "input_length_bound": BOUND, "totals": totals}


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
