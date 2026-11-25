"""Check exact frame-disposal acknowledgment scope and ordered protocol histories."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
CHANNELS = ("local-hart", "remote-hart", "dma-drain", "device-visibility")
CPU = frozenset(CHANNELS[:2])
ALL = frozenset(CHANNELS)


@dataclass(frozen=True)
class Scope:
    frame: int
    generation: int
    epoch: int


@dataclass(frozen=True)
class Receipt:
    channel: str
    subject: Scope
    after_detach: bool


def ready(subject, detached, uses_device, receipts):
    if not detached:
        return False
    exact = {
        receipt.channel for receipt in receipts
        if receipt.subject == subject and receipt.after_detach
    }
    return (ALL if uses_device else CPU) <= exact


def candidate(history, subject, uses_device):
    detached = False
    reused = False
    receipts = []
    outcomes = []
    for event in history:
        if event == "detach":
            detached = True
            outcomes.append("detached")
        elif event == "reuse":
            admitted = not reused and ready(subject, detached, uses_device, receipts)
            reused |= admitted
            outcomes.append("reassigned" if admitted else "retained")
        else:
            channel, variant = event
            scopes = {"exact": subject, "wrong-epoch": replace(subject, epoch=subject.epoch + 1)}
            receipts.append(Receipt(channel, scopes[variant], detached))
            outcomes.append("receipt")
    return outcomes


def oracle(history, uses_device):
    cut = history.index("detach")
    publication = None
    outcomes = []
    for index, event in enumerate(history):
        if event == "reuse":
            limit = len(CHANNELS) if uses_device else 2
            witnesses = [(channel, "exact") for channel in CHANNELS[:limit]]
            if publication is None and index > cut and all(
                witness in history[cut + 1:index] for witness in witnesses
            ):
                publication = index
                outcomes.append("reassigned")
            else:
                outcomes.append("retained")
        elif event == "detach":
            outcomes.append("detached")
        else:
            outcomes.append("receipt")
    return outcomes


def matrix(subject):
    variants = ("missing", "exact", "wrong-frame", "wrong-generation", "wrong-epoch", "early")
    constructors = {
        "exact": subject,
        "wrong-frame": replace(subject, frame=subject.frame + 1),
        "wrong-generation": replace(subject, generation=subject.generation + 1),
        "wrong-epoch": replace(subject, epoch=subject.epoch + 1),
        "early": subject,
    }
    counts = Counter()
    skipped_channel = Counter()
    replay_mistakes = 0
    for device_required, detached, vector in product((False, True), (False, True),
                                                       product(variants, repeat=len(CHANNELS))):
        ledger = [
            Receipt(channel, constructors[variant], variant != "early")
            for channel, variant in zip(CHANNELS, vector)
            if variant != "missing"
        ]
        actual = ready(subject, detached, device_required, ledger)
        needed = len(CHANNELS) if device_required else 2
        expected = detached and all(variant == "exact" for variant in vector[:needed])
        assert actual == expected
        counts["rows"] += 1
        counts["allowed"] += actual
        counts["device_rows_allowed"] += actual and device_required
        for index, channel in enumerate(CHANNELS):
            ignores = detached and all(
                variant == "exact" or i == index for i, variant in enumerate(vector[:needed])
            )
            skipped_channel[channel] += ignores and not actual
        same_resource = {
            item.channel for item in ledger if item.subject.frame == subject.frame
        }
        wide = detached and (ALL if device_required else CPU) <= same_resource
        replay_mistakes += wide and not actual
        assert not ready(subject, detached, device_required, [*ledger, *ledger]) or actual
    return {**counts, "ignoring_one_channel_false_accepts": dict(skipped_channel),
            "frame_only_false_accepts": replay_mistakes}


def histories(subject):
    counts = Counter()
    for dma, remote_variant in product((False, True), ("exact", "wrong-epoch")):
        events = (
            "detach", "reuse", "reuse",
            ("local-hart", "exact"), ("remote-hart", remote_variant),
            ("dma-drain", "exact"), ("device-visibility", "exact"),
        )
        for schedule in sorted(set(permutations(events)), key=str):
            actual = candidate(schedule, subject, dma)
            expected = oracle(schedule, dma)
            assert actual == expected, schedule
            counts["schedules"] += 1
            counts["reuse_requests"] += 2
            counts["reassigned"] += actual.count("reassigned")
            counts["blocked"] += actual.count("retained")
    return dict(counts)


def collect(lean):
    source = HERE / "Reuse.lean"
    proof = subprocess.run(
        [lean, source], capture_output=True, text=True, check=True, timeout=20,
    ).stdout.splitlines()
    assert len(proof) == 7 and all("does not depend on any axioms" in row for row in proof)
    initial = Scope(frame=4, generation=17, epoch=31)
    checks = matrix(initial)
    schedules = histories(initial)
    return {
        "conditional_hardware_channels": {
            "local-hart": "local translation and in-flight access quiescence",
            "remote-hart": "remote translation and in-flight access quiescence",
            "dma-drain": "revoke device access and drain previously admitted transactions",
            "device-visibility": "finish required cache, IOMMU and ownership synchronization",
        },
        "matrix": checks, "ordered_histories": schedules, "lean_audit": proof,
        "source_sha256": {
            path.name: sha256(path.read_bytes()).hexdigest() for path in (source, Path(__file__))
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(args.lean), indent=2, sort_keys=True) + "\n", encoding="utf-8")
