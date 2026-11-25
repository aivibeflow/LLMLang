"""Check live mapping lifecycle over one frame and a scoped visibility premise."""

import argparse
from collections import Counter, deque
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
DEPTH = 12
OPERATIONS = ("scrub", "install", "publish", "detach", "acknowledge", "release", "cancel")


def step(frame, action, fault=None):
    phase, lease = frame
    name, token, proof = action
    if name == "allocate":
        return ("reserved", (token[0], lease[1] + 1)) if phase == "free" else frame
    if lease != token or phase == "free":
        return frame
    if name == "scrub" and phase == "reserved":
        return "scrubbed", lease
    if name == "install" and phase == "scrubbed":
        return "installed", lease
    if name == "publish" and phase == "installed" and (proof or fault == "publish-without-visibility"):
        return "published", lease
    if name == "detach" and phase == "published":
        return "revoking", lease
    if name == "acknowledge" and phase == "revoking" and (proof or fault == "acknowledge-without-proof"):
        return "quiescent", lease
    if name == "release" and (phase == "quiescent" or (phase == "revoking" and fault == "release-while-revoking")):
        return "free", (-1, lease[1])
    if name == "cancel" and phase in {"reserved", "scrubbed"}:
        return "free", (-1, lease[1])
    return frame


def expected(frame, action):
    phase, (owner, generation) = frame
    name, (selected, epoch), proof = action
    transitions = {
        "free": {"allocate": ("reserved", (selected, generation + 1))},
        "reserved": {"scrub": ("scrubbed", (owner, generation)), "cancel": ("free", (-1, generation))},
        "scrubbed": {"install": ("installed", (owner, generation)), "cancel": ("free", (-1, generation))},
        "installed": {"publish": ("published", (owner, generation))} if proof else {},
        "published": {"detach": ("revoking", (owner, generation))},
        "revoking": {"acknowledge": ("quiescent", (owner, generation))} if proof else {},
        "quiescent": {"release": ("free", (-1, generation))},
    }
    if phase != "free" and (selected != owner or epoch != generation):
        return frame
    return transitions[phase].get(name, frame)


def explore():
    initial = ("free", (-1, 0))
    queue = deque([(initial, ())])
    seen = {initial}
    outcomes = Counter()
    witnesses = {}
    while queue:
        frame, history = queue.popleft()
        if len(history) == DEPTH:
            continue
        _, (_, epoch) = frame
        for token in product((0, 1), (max(0, epoch - 1), epoch, epoch + 1)):
            alternatives = [(name, token, proof) for name in OPERATIONS for proof in (False, True)]
            alternatives.append(("allocate", token, False))
            for action in alternatives:
                want = expected(frame, action)
                got = step(frame, action)
                if got != want:
                    raise ValueError((frame, history, action, got, want))
                outcomes["transitions"] += 1
                for fault in ("publish-without-visibility", "acknowledge-without-proof", "release-while-revoking"):
                    mutant = step(frame, action, fault)
                    if mutant != want:
                        outcomes[fault] += 1
                        witnesses.setdefault(fault, {"history": history, "action": action, "correct": want,
                                                     "mutant": mutant})
                if got not in seen:
                    seen.add(got)
                    queue.append((got, (*history, action)))
    outcomes["states"] = len(seen)
    if len(witnesses) != 3:
        raise ValueError("a seeded lifecycle change escaped")
    return dict(outcomes), witnesses


def proof_receipt(lean):
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    probe = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Mapping.lean")],
                           check=True, text=True, capture_output=True, timeout=30)
    theorems = ("absent_acknowledgment_keeps_ownership", "outstanding_translation_blocks_reuse",
                "publishing_requires_visibility", "retirement_stops_new_calls_but_retains_old_lease",
                "acknowledged_reuse_advances_generation")
    axioms = [f"'{theorem}' depends on axioms: [propext]" for theorem in theorems]
    if probe.stderr or probe.stdout.splitlines() != axioms:
        raise ValueError((probe.stdout, probe.stderr))
    return {"version": version, "axioms": axioms}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    counts, witnesses = explore()
    value = {
        "lean": proof_receipt(args.lean), "maximum_search_depth": DEPTH, "counts": counts,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Mapping.lean", "run.py")},
        "first_witnesses": witnesses,
    }
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
