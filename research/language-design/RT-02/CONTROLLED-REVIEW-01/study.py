"""Generate randomized review slots and score the frozen RT-02 pilot cases."""

import argparse
import hashlib
import json
import math
import random
from statistics import NormalDist, median
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / "RECONSTRUCTION-ROUNDTRIP-01"
sys.path.insert(0, str(PILOT))
import run as pilot

PROTOCOL = json.loads((HERE / "protocol.json").read_text())
REASONS = {
    "omitted-exception": "missing-rule", "added-notification": "added-obligation",
    "weaker-deadline": "timing-window", "stronger-deadline": "timing-window",
    "flipped-prohibition": "polarity", "shifted-clock": "timing-window",
    "expanded-scope": "scope", "shifted-trigger": "trigger",
    "unfaithful-reconstruction": "timing-window", "missing-provenance": "source-reference",
    "dangling-provenance": "source-reference", "conflicting-unapproved-provenance": "source-reference",
    "unsupported-action": "unsupported-action", "unreadable-reconstruction": "unreadable",
    "incomplete-trace": "missing-observation",
}
# The same panel is attached to every expanded candidate. It is not selected by the answer key.
SCENARIOS = (
    ("retail", "failed", 0, None), ("retail", "failed", None, None),
    ("retail", "succeeded", None, None), ("retail", "succeeded", 0, None),
    ("retail", "succeeded", 5, None), ("retail", "succeeded", 6, 5),
    ("retail", "succeeded", 7, None), ("wholesale", "succeeded", None, None),
)


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_pilot():
    root = HERE.parents[3]
    for name in ("corpus.json", "evidence.json", "run.py", "render.py"):
        path = PILOT / name
        expected = subprocess.check_output(
            ["git", "show", f"{PROTOCOL['pilot_revision']}:{path.relative_to(root)}"], cwd=root,
        )
        if path.read_bytes() != expected:
            raise ValueError(f"pilot artifact has changed: {name}")


def build(directory):
    check_pilot()
    directory.mkdir(parents=True, exist_ok=True)
    public = directory / "packets"
    public.mkdir(exist_ok=True)
    corpus = read(PILOT / "corpus.json")
    evidence = read(PILOT / "evidence.json")["results"]
    rng = random.Random(PROTOCOL["assignment_seed"])
    inputs = {name: sha256(path) for name, path in (
        ("protocol", HERE / "protocol.json"), ("study", HERE / "study.py"),
        ("corpus", PILOT / "corpus.json"),
        ("results", PILOT / "evidence.json"), ("pilot_runner", PILOT / "run.py"),
    )}
    manifest = {"source_sha256": inputs, "slots": {}}
    drafts = pilot.cases(corpus["clauses"])
    for name, clauses, expected, _ in drafts:
        row = evidence[name]
        assert row["status"] == expected
        actual_lines = row.get("observed_lines", row["rendered"].get("lines"))
        normalized = {clause["id"]: clause for clause in pilot.semantic_payload(clauses)}
        policy = {
            "intent": corpus["source_fragments"]["intent"],
            "clarifications": [corpus["source_fragments"][ref] for ref in ("operator", "clock", "exception")],
            "observation": row["trace"] if name == "incomplete-trace" else {"complete_through_s": 9},
        }
        for arm in PROTOCOL["arms"]:
            packet = {
                "policy": policy,
                "decisions": PROTOCOL["decisions"],
                "reason_codes": PROTOCOL["reason_codes"],
                "instructions": "Assess the supplied evidence. Select a disposition and reason. "
                                "If evidence is insufficient, select CLARIFY.",
            }
            if arm == "formal":
                packet["typed_candidate"] = list(normalized.values())
            if arm in {"reconstruction", "expanded"}:
                packet["explanation"] = actual_lines
            if arm == "expanded":
                packet["candidate_scenarios"] = [
                    pilot.trace_payload(trace) | {"permitted": pilot.allows(normalized, trace)}
                    for trace in SCENARIOS
                ] if name != "unsupported-action" else []
                packet["attached_references"] = [
                    {"clause": clause["id"], "fragments": [
                        {"label": ref, "excerpt": corpus["source_fragments"].get(ref)}
                        for ref in clause["refs"]]}
                    for clause in clauses
                ]
            for role in PROTOCOL["roles"]:
                for _ in range(PROTOCOL["replicates_per_arm_case_role"]):
                    slot = f"{rng.getrandbits(80):020x}"
                    assert slot not in manifest["slots"]
                    packet_path = public / (slot + ".json")
                    write(packet_path, {"slot": slot} | packet)
                    manifest["slots"][slot] = {
                        "packet_sha256": sha256(packet_path),
                        "arm": arm, "case": name, "role": role, "answer": expected,
                        "reason": REASONS.get(name, "none"),
                    }
    allocation = {role: [slot for slot, item in manifest["slots"].items() if item["role"] == role]
                  for role in PROTOCOL["roles"]}
    for slots in allocation.values():
        rng.shuffle(slots)
    write(directory / "coordinator-key.json", manifest)
    write(directory / "allocation.json", allocation)
    return manifest


def wilson(successes, count):
    z = NormalDist().inv_cdf((1 + PROTOCOL["criteria"]["confidence"]) / 2)
    p = successes / count
    divisor = 1 + z * z / count
    center = (p + z * z / (2 * count)) / divisor
    half = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / divisor
    return max(0.0, center - half), min(1.0, center + half)


def score(manifest, responses):
    if manifest["source_sha256"]["protocol"] != sha256(HERE / "protocol.json"):
        raise ValueError("the coordinator key binds a different protocol")
    slots = manifest["slots"]
    seen = set()
    buckets = {arm: Counter() for arm in PROTOCOL["arms"]}
    role_buckets = {
        arm: {role: Counter() for role in PROTOCOL["roles"]} for arm in PROTOCOL["arms"]
    }
    timings = {arm: [] for arm in PROTOCOL["arms"]}
    for response in responses:
        slot = response["slot"]
        decision, reason = response["decision"], response["reason"]
        if slot not in slots or slot in seen:
            raise ValueError(f"unrecognized or duplicate slot: {slot}")
        if decision not in PROTOCOL["decisions"] or reason not in PROTOCOL["reason_codes"]:
            raise ValueError(f"invalid response for slot: {slot}")
        seen.add(slot)
        key = slots[slot]
        if response["packet_sha256"] != key["packet_sha256"]:
            raise ValueError(f"response is bound to another packet: {slot}")
        arm, answer = key["arm"], key["answer"]
        seconds = response.get("review_seconds")
        if seconds is not None:
            if type(seconds) not in {int, float} or not math.isfinite(seconds) or seconds < 0:
                raise ValueError(f"invalid review time: {slot}")
            timings[arm].append(seconds)
        for cell in (buckets[arm], role_buckets[arm][key["role"]]):
            cell[answer] += 1
            cell["detected"] += answer == "DIFFERENT" and decision in {"REVISE", "REJECT"} and reason == key["reason"]
            cell["unsafe_accept"] += answer != "ELIGIBLE" and decision == "ACCEPT"
            cell["eligible_accept"] += answer == "ELIGIBLE" and decision == "ACCEPT"
            cell["unknown_clarify"] += answer == "UNKNOWN" and decision == "CLARIFY"
    results = {arm: dict(cell) for arm, cell in buckets.items()}
    for arm, cell in results.items():
        cell["review_times_reported"] = len(timings[arm])
        if timings[arm]:
            cell["review_seconds_median"] = median(timings[arm])
    if seen != slots.keys():
        return {"complete": False, "responses": len(seen), "arms": results, "role_counts": role_buckets}
    for cell in results.values():
        cell["detection_rate"] = cell["detected"] / cell["DIFFERENT"]
        cell["detection_interval"] = wilson(cell["detected"], cell["DIFFERENT"])
        cell["unsafe_acceptance_interval"] = wilson(cell["unsafe_accept"], cell["DIFFERENT"] + cell["UNKNOWN"])
    plus, text = results["expanded"], results["reconstruction"]
    gain = plus["detection_rate"] - text["detection_rate"]
    plus_low, plus_high = plus["detection_interval"]
    text_low, text_high = text["detection_interval"]
    gain_interval = (
        gain - math.hypot(plus["detection_rate"] - plus_low, text_high - text["detection_rate"]),
        gain + math.hypot(plus_high - plus["detection_rate"], text["detection_rate"] - text_low),
    )
    thresholds = PROTOCOL["criteria"]
    return {
        "complete": True, "responses": len(seen), "arms": results, "role_counts": role_buckets,
        "expanded_detection_gain": gain, "gain_interval": gain_interval,
        "criteria": {
            "gain": gain >= thresholds["expanded_detection_gain"] and gain_interval[0] > 0,
            "unsafe_acceptance": plus["unsafe_acceptance_interval"][1]
            <= thresholds["max_expanded_unsafe_acceptance_wilson_upper"],
            "eligible_acceptance": plus["eligible_accept"] / plus["ELIGIBLE"]
            >= thresholds["min_expanded_eligible_acceptance"],
        },
    }


def dry_run(manifest):
    slots = manifest["slots"]
    complete = [
        {"slot": slot, "packet_sha256": item["packet_sha256"],
         "decision": {"ELIGIBLE": "ACCEPT", "DIFFERENT": "REVISE", "UNKNOWN": "CLARIFY"}[item["answer"]],
         "reason": item["reason"]}
        for slot, item in slots.items()
    ]
    ideal = score(manifest, complete)
    assert all(cell["unsafe_accept"] == 0 and cell["detected"] == 36 for cell in ideal["arms"].values())
    assert not ideal["criteria"]["gain"]  # Perfect performance in both arms has no improvement.
    assert not score(manifest, complete[:-1])["complete"]
    gap = score(manifest, [
        item | {"decision": "CLARIFY", "reason": "none"}
        if slots[item["slot"]]["arm"] == "reconstruction" else item
        for item in complete
    ])
    assert all(gap["criteria"].values())
    try:
        score(manifest, [complete[0] | {"packet_sha256": "wrong"}])
    except ValueError as error:
        assert "another packet" in str(error)
    else:
        raise AssertionError("accepted a response without the exact packet digest")
    always_accept = score(manifest, [item | {"decision": "ACCEPT", "reason": "none"} for item in complete])
    assert all(cell["unsafe_accept"] == 60 for cell in always_accept["arms"].values())
    return {
        "kind": "synthetic instrument check", "human_observations": 0, "source_sha256": manifest["source_sha256"],
        "slots_by_role": dict(Counter(row["role"] for row in slots.values())),
        "perfect_and_always_accept_scored_per_arm": {
            arm: {"perfect": ideal["arms"][arm], "always_accept": always_accept["arms"][arm]}
            for arm in PROTOCOL["arms"]
        },
        "partial_response_set_detected": True, "wrong_packet_rejected": True,
        "synthetic_detection_gap_meets_pilot_thresholds": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    packet = modes.add_parser("build")
    packet.add_argument("directory", type=Path)
    check = modes.add_parser("score")
    check.add_argument("key", type=Path)
    check.add_argument("responses", type=Path)
    args = parser.parse_args()
    if args.mode == "build":
        manifest = build(args.directory)
        write(args.directory / "dry-run.json", dry_run(manifest))
    else:
        print(json.dumps(score(read(args.key), read(args.responses)), indent=2))


if __name__ == "__main__":
    main()
