"""Compare finite incarnation policies for reuse of one typed resource slot."""

import json
import platform


def check_width(width):
    period = 1 << width
    mask = period - 1
    totals = {
        "cases": 0,
        "valid": 0,
        "phase_only_invalid_admissions": 0,
        "wrapped_invalid_admissions": 0,
        "exact_invalid_admissions": 0,
    }
    for issue in range(period):
        for advance in range(3 * period + 1):
            now = issue + advance
            for active in (False, True):
                valid = active and advance == 0
                phase_only = active
                wrapped = active and (issue & mask) == (now & mask)
                exact = active and issue == now
                assert wrapped == (active and advance % period == 0)
                assert exact == valid
                assert not valid or phase_only and wrapped and exact

                totals["cases"] += 1
                totals["valid"] += valid
                totals["phase_only_invalid_admissions"] += phase_only and not valid
                totals["wrapped_invalid_admissions"] += wrapped and not valid
                totals["exact_invalid_admissions"] += exact and not valid

    assert totals == {
        "cases": 2 * period * (3 * period + 1),
        "valid": period,
        "phase_only_invalid_admissions": 3 * period * period,
        "wrapped_invalid_admissions": 3 * period,
        "exact_invalid_admissions": 0,
    }
    return {"width_bits": width, "period": period, **totals}


if __name__ == "__main__":
    rows = [check_width(width) for width in range(1, 7)]
    print(json.dumps({
        "python": platform.python_version(),
        "rows": rows,
        "totals": {key: sum(row[key] for row in rows) for key in rows[0]
                   if key not in ("width_bits", "period")},
    }, indent=2, sort_keys=True))
