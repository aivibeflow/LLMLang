"""Check archived source projections, review packets and review scope together."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PINS = {
    "GIT-REVIEW-PROJECTION-01": "8308b0f6fcc83513dd469aef3635ce8e3bd053e6f45388b25b2a008d5277daf4",
    "REVIEW-PACKET-01": "2edd1a76377025b6455d0b4d9fd7282a8cb6fee922a8176e0005c1f70fc305e4",
    "CHANGESET-REVIEW-SCOPE-01": "e8d42a3cc9bee3efb763e48f945f20d5d35466b8c38f768adefad68c25ccbfc2",
}


def load(name):
    raw = (HERE.parent / name / "evidence.json").read_bytes()
    assert sha256(raw).hexdigest() == PINS[name]
    return json.loads(raw)


def check():
    examples = load("GIT-REVIEW-PROJECTION-01")["examples"]
    metadata_mismatches = sorted(name for name, row in examples.items()
                                 if not row["generated_metadata_matches"])
    assert metadata_mismatches == ["metadata-only", "provider-stale"]
    assert not examples["metadata-only"]["configured_patch"] and examples["metadata-only"]["metadata_patch"]
    assert examples["provider-fresh"]["configured_patch"] == examples["provider-stale"]["configured_patch"]

    packets = load("REVIEW-PACKET-01")
    assert len(packets["bundle_summaries"]) == 8 and all(
        packet["exactly_verified"] for packet in packets["bundle_summaries"].values())
    assert set(packets["refused_controls"]) == {"wrong_patch", "wrong_scope_with_new_digest", "wrong_candidate"}
    packet = packets["bundle_summaries"]["invalid-provider"]
    assert packet["state"] == "unavailable" and packet["has_source_patch"] and not packet["changed_slots"]

    cases = load("CHANGESET-REVIEW-SCOPE-01")["cases"]
    reusable = sorted(name for name, row in cases.items()
                      if "closed" in (row.get("approval_matches") or ()))
    assert reusable == ["different_key_order", "exact", "unrelated_base", "unrelated_candidate"]
    assert "direct" in cases["new_transitive_consumer"]["approval_matches"]
    assert "closed" not in cases["new_transitive_consumer"]["approval_matches"]
    return {"input_sha256": PINS, "rendering_examples": len(examples),
            "metadata_mismatches": metadata_mismatches, "verified_packets": len(packets["bundle_summaries"]),
            "refused_packet_controls": packets["refused_controls"],
            "review_cases": len(cases), "reusable_closed_scope": reusable,
            "checker_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True, indent=2))
