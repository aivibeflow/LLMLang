"""Check bounded single-hart blocking-IPC interleavings and lifecycle faults."""

import argparse
from collections import Counter, deque
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
DEPTH = 8


@dataclass(frozen=True)
class State:
    generation: int = 1
    active: bool = True
    phase: str = "ready"
    pending: tuple[str, int] | None = None


def step(state, action, fault=None):
    name, arg = action
    if name == "schedule" and state.phase == "ready":
        return replace(state, phase="running")
    if name == "preempt" and state.phase == "running":
        return replace(state, phase="ready", pending=None if fault == "preempt-loses-completion" else state.pending)
    if name == "block" and state.phase == "running" and state.pending is None and state.active:
        if state.generation == arg:
            return replace(state, phase="waiting")
    if name == "send" and state.phase == "waiting" and state.active:
        if state.generation == arg or fault == "send-ignores-generation":
            return replace(state, phase="ready", pending=("message", arg))
    if name == "consume" and state.phase == "running" and state.pending is not None:
        return replace(state, pending=None)
    if name == "revoke":
        if state.phase == "waiting" and fault != "revoke-leaves-waiter":
            return replace(state, active=False, phase="ready", pending=("cancelled", 0))
        return replace(state, active=False)
    if name == "regrant" and not state.active and state.phase != "waiting":
        return replace(state, active=True, generation=state.generation + 1)
    return state


def transition_oracle(state, action):
    name, arg = action
    pending = state.pending
    phase = state.phase
    generation = state.generation
    active = state.active
    if name == "revoke":
        return (generation, False, "ready", ("cancelled", 0)) if phase == "waiting" else (
            generation, False, phase, pending)
    if name == "regrant" and active is False:
        return generation + 1, True, phase, pending
    if (name, phase) == ("send", "waiting") and active and arg == generation:
        return generation, active, "ready", ("message", arg)
    if (name, phase, pending) == ("block", "running", None) and active and arg == generation:
        return generation, active, "waiting", None
    phase = {("schedule", "ready"): "running", ("preempt", "running"): "ready"}.get((name, phase), phase)
    if name == "consume" and phase == "running":
        pending = None
    return generation, active, phase, pending


def explore():
    start = State()
    queue = deque([(start, ())])
    seen = {start}
    compared = Counter()
    witnesses = {}
    while queue:
        state, history = queue.popleft()
        if len(history) == DEPTH:
            continue
        actions = [(name, 0) for name in ("schedule", "preempt", "consume", "revoke", "regrant")]
        actions += [(name, arg) for name in ("block", "send")
                    for arg in (state.generation - 1, state.generation, state.generation + 1)]
        for action in actions:
            expected = State(*transition_oracle(state, action))
            observed = step(state, action)
            if observed != expected or (observed.phase == "waiting" and (not observed.active or observed.pending)):
                raise ValueError((history, action, observed, expected))
            compared["reachable_transitions"] += 1
            for fault in ("send-ignores-generation", "revoke-leaves-waiter", "preempt-loses-completion"):
                mutant = step(state, action, fault)
                if mutant != expected:
                    compared[fault] += 1
                    witnesses.setdefault(fault, {
                        "prefix": history, "action": action, "correct": asdict(expected), "fault": asdict(mutant),
                    })
            if observed not in seen:
                seen.add(observed)
                queue.append((observed, (*history, action)))
    if len(witnesses) != 3:
        raise ValueError("a control failed to distinguish a lifecycle fault")
    compared["reachable_states"] = len(seen)
    return dict(compared), witnesses


def replacement_trace():
    actions = (("schedule", 0), ("block", 1), ("revoke", 0), ("regrant", 0),
               ("schedule", 0), ("consume", 0), ("block", 2), ("send", 1),
               ("send", 2), ("schedule", 0), ("preempt", 0))
    state = State()
    trace = []
    for action in actions:
        state = step(state, action)
        trace.append({"action": action, "state": asdict(state)})
    if trace[6]["state"] != trace[7]["state"] or state != State(2, True, "ready", ("message", 2)):
        raise ValueError("endpoint replacement changed the expected completion")
    return trace


def lean_record(lean):
    proof = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Blocking.lean")],
                           text=True, capture_output=True, check=True, timeout=30)
    expected = [
        "'step_preserves_waiter' depends on axioms: [propext, Quot.sound]",
        "'old_generation_does_not_deliver' depends on axioms: [propext]",
        "'waiting_send_wakes_once' depends on axioms: [propext]",
        "'revoke_cancels_waiting' depends on axioms: [propext]",
    ]
    if proof.stderr or proof.stdout.splitlines() != expected:
        raise ValueError((proof.stdout, proof.stderr))
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    return {"version": version, "axioms": expected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    counts, witnesses = explore()
    result = {
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Blocking.lean", "run.py")},
        "lean": lean_record(args.lean), "maximum_depth": DEPTH,
        "counts": counts, "first_witnesses": witnesses, "replacement_trace": replacement_trace(),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
