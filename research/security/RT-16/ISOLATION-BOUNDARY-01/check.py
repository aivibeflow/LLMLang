"""Reconcile native launch isolation and mediated effect settlement records."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PINS = {
    "security/RT-16/WORKER-ISOLATION-01": "90b0c2e6bfdaf86b03e3df7a3802f00f073d07a9928c362014bd6306b137fdb8",
    "language-design/RT-04/EXTERNAL-REVOCATION-01": "a6961d10631f395ad2856c53309d053826981a6318f7ef1a8b611eb864b8a45e",
}


def read(name):
    raw = (HERE.parents[2] / name / "evidence.json").read_bytes()
    assert sha256(raw).hexdigest() == PINS[name]
    return json.loads(raw)


def check():
    worker, effect = [read(name) for name in PINS]
    assert (worker["native_launches"], worker["native_fields_checked"], worker["configurations"]) == (48, 336, 8)
    for label, observation in worker["presence_observations"].items():
        flags = {key: value == "True" for key, value in
                 (pair.split("=") for pair in label.split(","))}
        assert observation["public_env"] and observation["public_fd"]
        assert observation["fixture_private_env"] == flags["env"]
        assert observation["fixture_private_fd"] == flags["fd"]
        if flags["seccomp"]:
            assert not any(observation[field] for field in
                           ("public_path_read", "fixture_private_path_read", "public_path_write"))
    counts = effect["counts"]
    assert effect["process_pairs"] == len(effect["runs"]) == 45
    expected = {"cached": 4, "fresh": 3, "leaf_lock": 2, "ancestry_lock": 1, "db_writer": 0}
    assert {key: row["stale_effects"] for key, row in counts.items()} == expected
    assert sum(row["effect_without_receipt"] for row in counts.values()) == 5
    assert counts["db_writer"]["unrelated_revocation_postponed"] == 1
    return {"source_ledgers": PINS, "launches": worker["native_launches"],
            "launch_fields": worker["native_fields_checked"], "effect_schedules": effect["process_pairs"],
            "stale_effects": expected, "effects_without_receipt": 5,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True, indent=2))
