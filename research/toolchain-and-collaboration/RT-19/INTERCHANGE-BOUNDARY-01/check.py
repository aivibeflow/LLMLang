"""Check the archived import, external-edit and publication boundaries together."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PINS = {
    "GENERATION-PUBLICATION-01": "99040b916f76a17430ddb3b97cd07d1827816eb779572449e229790d3a5bc1f7",
    "WORKTREE-EDIT-01": "3b2f4fda11d49c39755b0da5efe2329e17f1b2c3d4ec93f35ee1eb6585b9b5bb",
    "TOOLCHAIN-ROUNDTRIP-01": "457cf793e805349312c6eefea7e8781c5609780285877bf981e31bfbf6787c58",
}


def load(name):
    raw = (HERE.parent / name / "evidence.json").read_bytes()
    assert sha256(raw).hexdigest() == PINS[name]
    return json.loads(raw)


def verify():
    generation, checkout, roundtrip = [load(name) for name in PINS]
    published = Counter((row["policy"], row["outcome"]) for row in generation["cases"])
    assert len(generation["cases"]) == 133
    assert published["in-place", "inconsistent"] == 64
    assert published["resolve-each", "inconsistent"] == 9
    assert published["pin-directory", "unavailable"] == 10
    leased = [row for row in generation["cases"] if row["policy"] == "leased"]
    assert len(leased) == 21 and not any(row["outcome"] in ("inconsistent", "unavailable") for row in leased)
    worktree = checkout["cases"]
    assert len(worktree) == 72
    weak = sum(row["checkout_edit"] and not row["weak_stat_change"] for row in worktree)
    normalized = sum(row["checkout_edit"] and not row["canonical_tree_edit"] for row in worktree)
    assert (weak, normalized) == (18, 6)
    assert roundtrip["successful_roundtrips"] == 864
    assert "external_edit" in roundtrip["controls"] and "tampered_entity_import" in roundtrip["controls"]
    return {"ledger_sha256": PINS, "publication_schedules": 133,
            "coherent_leased_reads": len(leased), "worktree_cases": len(worktree),
            "stat_missed_checkout": weak, "normalized_checkout_edits": normalized,
            "exact_roundtrips": roundtrip["successful_roundtrips"],
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, indent=2))
