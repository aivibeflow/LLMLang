"""Score a rank-only readiness surrogate against the published fixture oracle."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / "KNOWLEDGE-CONTEXT-01" / "evidence.json"
PIN = "b43c30661b1e7ebc60fe7c70163f47161a7782f866a1f60dd94af7e7d97db51f"
READY = {"complete", "same-bytes-other-scope-revision", "fresh-and-stale-copy",
         "duplicate-required", "required-ranking-changed", "ambiguous-optional",
         "optional-trims-to-budget", "optional-same-text-other-source", "hidden-alternative"}


def check():
    raw = ARCHIVE.read_bytes()
    assert sha256(raw).hexdigest() == PIN
    observations = json.loads(raw)["cases"]
    assert len(observations) == 15
    assert sum(row["permutations"] for row in observations.values()) == 164
    confusion = Counter()
    errors = {}
    for name, row in observations.items():
        expected = name in READY
        assert (row["exact"]["status"] == "ready") == expected
        observed = row["ranked"]["exact_required_present"]
        key = { (True, True): "true_positive", (True, False): "false_negative",
                (False, True): "false_positive", (False, False): "true_negative"}[(expected, observed)]
        confusion[key] += 1
        if expected != observed:
            errors[name] = key
    assert errors == {"conflicting-required": "false_positive", "optional-trims-to-budget": "false_negative"}
    assert confusion == {"true_positive": 8, "false_positive": 1, "false_negative": 1, "true_negative": 5}
    return {"input_sha256": PIN, "ranked_readiness_surrogate": confusion,
            "ranked_precision": [8, 9], "ranked_recall": [8, 9],
            "exact_gate_matches": len(observations), "incorrect_ranked_readiness": errors,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True, indent=2))
