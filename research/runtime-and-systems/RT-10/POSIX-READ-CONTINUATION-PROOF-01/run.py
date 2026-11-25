"""Check which existing native observations supply the model's premises."""

import hashlib
import json
from pathlib import Path
import platform


PIN = "5cdc5d1de0553a3198795ec3237b5f7c26c79d142885a7a9ec6fa8efd14d90c9"


def study():
    native_file = Path(__file__).resolve().parents[1] / "POSIX-READV-PROGRESS-01/evidence.json"
    content = native_file.read_bytes()
    assert hashlib.sha256(content).hexdigest() == PIN
    native = json.loads(content)
    counts = {"bounded_read_premises": 0, "would_block_without_progress": 0}
    for row in native["cases"]:
        target = "".join(row["buffers"])
        initial = row["payload"]
        rest = row["remaining"]
        if row["raw_count"] is None:
            assert row["typed"] == "would-block" and initial == rest
            assert target == "_" * sum(row["shape"])
            counts["would_block_without_progress"] += 1
            continue

        reported = row["raw_count"]
        observed_prefix = target[:reported]
        assert reported <= len(initial) and reported <= sum(row["shape"])
        assert observed_prefix == initial[:reported]
        assert observed_prefix + rest == initial
        counts["bounded_read_premises"] += 1

    resume = native["resume"]
    exact = resume["tracked_cursor"]
    reset = resume["whole_vector_retry"]
    assert exact["first_count"] == reset["first_count"] == 3
    assert exact["second_count"] == reset["second_count"] == 4
    assert exact["pipe_empty"] and reset["pipe_empty"]
    assert "".join(exact["after_resume"]) == "abcdefg"
    assert "".join(reset["after_resume"]) != "abcdefg"
    assert counts == {"bounded_read_premises": 104, "would_block_without_progress": 4}
    return {
        "python": platform.python_version(),
        "input_receipt_sha256": PIN,
        "premises_checked": counts,
        "continuations": {
            "exact_destination_preserves_recorded_prefix": True,
            "full_vector_retry_preserves_recorded_prefix": False,
            "both_report_same_counts_and_empty_pipe": True,
        },
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
