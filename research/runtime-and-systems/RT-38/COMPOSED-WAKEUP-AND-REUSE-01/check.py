"""Reconcile frame retirement, new mappings and endpoint wakeup obligations."""

from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = {
    "compose": "COMPOSED-MAPPING-IPC-01/evidence.json",
    "hardware": "SCOPED-SMP-DMA-REUSE-01/evidence.json",
    "live": "RV64-LIVE-FRAME-IPC-01/evidence.json",
    "preemptive": "RV64-PREEMPTIVE-IPC-01/evidence.json",
}


def transition_replay(schedule, device, relaxation=None):
    joined = set()
    gates = {"detach": set(), "local": {"detach"}, "remote": {"detach"},
             "sanitize": {"local", "remote"}, "publish": {"sanitize"},
             "rebind": {"publish"}, "wake": {"rebind"}}
    if device:
        gates.update({"drain": {"detach"}, "visible": {"drain"}})
        gates["sanitize"].add("visible")
    if relaxation == "omit-remote":
        gates["sanitize"].remove("remote")
    elif relaxation == "omit-visibility":
        gates["sanitize"].discard("visible")
    elif relaxation == "wake-before-map":
        gates["wake"] = {"detach"}
    for event in schedule:
        if not gates[event] <= joined:
            return False
        joined.add(event)
    return True


def chronological(schedule, device):
    era = {label: index for index, label in enumerate(schedule)}
    expected = (era["detach"] < min(era["local"], era["remote"])
                and max(era["local"], era["remote"]) < era["sanitize"]
                and era["sanitize"] < era["publish"] < era["rebind"] < era["wake"])
    if device:
        expected &= era["detach"] < era["drain"] < era["visible"] < era["sanitize"]
    return expected


def schedules(device):
    base = ("detach", "local", "remote", "sanitize", "publish", "rebind", "wake")
    events = base + (("drain", "visible") if device else ())
    admissible = 0
    inputs = 0
    controls = dict.fromkeys(("omit-remote", "omit-visibility", "wake-before-map"), 0)
    for schedule in permutations(events):
        inputs += 1
        expected = chronological(schedule, device)
        assert transition_replay(schedule, device) == expected
        if expected:
            admissible += 1
            continue
        for name in controls:
            controls[name] += transition_replay(schedule, device, name)
    return {"inputs": inputs, "admissible": admissible, "false_admissions": controls}


def main():
    raw = {name: (ROOT / path).read_bytes() for name, path in ARCHIVES.items()}
    data = {name: json.loads(payload) for name, payload in raw.items()}
    assert data["compose"]["counts"]["transitions"] == 20976
    assert data["hardware"]["matrix"]["rows"] == 5184
    assert data["hardware"]["ordered_histories"]["schedules"] == 10080
    live = data["live"]["profiles"]
    assert live["sanitized_replacement"]["uart"] == "WIBCARba!"
    assert len({row["user_sha256"] for row in live.values()}) == 1
    assert len({row["uart"] for row in live.values()}) == len(live) == 4
    assert set(data["preemptive"]["observations"]) == {
        "accept_stale_generation", "alias_private_stack", "deliver", "revoke", "run_blocked",
    }
    return {"archive_sha256": {name: sha256(payload).hexdigest() for name, payload in raw.items()},
            "cpu_only": schedules(False), "cpu_and_device": schedules(True)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
