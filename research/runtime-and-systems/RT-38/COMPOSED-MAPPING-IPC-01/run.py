"""Check composition of the existing frame and endpoint models."""

import argparse
from collections import Counter, deque
from dataclasses import dataclass, replace
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
FRAME = HERE.parent / "LIVE-FRAME-QUIESCENCE-01"
ENDPOINT = HERE.parent / "BLOCKING-ENDPOINT-01"
DEPTH = 10


def load(name, file):
    specification = spec_from_file_location(name, file)
    module = module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


frame_model = load("frame_fixture", FRAME / "run.py")
endpoint_model = load("endpoint_fixture", ENDPOINT / "run.py")


@dataclass(frozen=True)
class State:
    frame: tuple[str, tuple[int, int]]
    endpoint: endpoint_model.State


def live_for_task(frame):
    phase, (owner, _) = frame
    return phase == "published" and owner == 0


def transition(state, action, fault=None):
    domain, token, operation = action
    if domain == "frame":
        frame = frame_model.step(state.frame, operation)
        endpoint = state.endpoint
        if not live_for_task(frame) and fault != "omit-suspension":
            endpoint = endpoint_model.step(endpoint_model.step(endpoint, ("preempt", 0)), ("revoke", 0))
        return State(frame, endpoint)
    current_owner = token[0] == 0
    exact_binding = current_owner and state.frame == ("published", token)
    owner_only = current_owner and live_for_task(state.frame) and fault == "ignore-frame-generation"
    bypass = operation[0] == "schedule" and not live_for_task(state.frame) and fault == "schedule-unmapped"
    if exact_binding or owner_only or bypass:
        return replace(state, endpoint=endpoint_model.step(state.endpoint, operation))
    return state


def reference(state, action):
    domain, lease, operation = action
    frame = state.frame
    endpoint = state.endpoint
    if domain == "frame":
        frame = frame_model.expected(frame, operation)
        if frame[0] != "published" or frame[1][0] != 0:
            cancelled = ("cancelled", 0) if endpoint.phase == "waiting" else endpoint.pending
            endpoint = replace(endpoint, active=False, phase="ready", pending=cancelled)
    elif frame[0] == "published" and frame[1] == lease and lease[0] == 0:
        endpoint = endpoint_model.State(*endpoint_model.transition_oracle(endpoint, operation))
    return State(frame, endpoint)


def actions(state):
    epoch = state.frame[1][1]
    endpoint_epoch = state.endpoint.generation
    for token in product((0, 1), (max(0, epoch - 1), epoch, epoch + 1)):
        for operation in ("allocate", "scrub", "install", "publish", "detach", "acknowledge", "release", "cancel"):
            yield "frame", None, (operation, token, True)
        for operation in ("publish", "acknowledge"):
            yield "frame", None, (operation, token, False)
        for operation in ("schedule", "preempt", "consume", "revoke", "regrant"):
            yield "endpoint", token, (operation, 0)
        for operation, generation in product(("block", "send"), (max(0, endpoint_epoch - 1), endpoint_epoch)):
            yield "endpoint", token, (operation, generation)


def serialized(state):
    return {"frame": state.frame, "endpoint": {
        "active": state.endpoint.active, "generation": state.endpoint.generation,
        "phase": state.endpoint.phase, "pending": state.endpoint.pending,
    }}


def check_states():
    start = State(("published", (0, 1)), endpoint_model.State())
    queue = deque([(start, 0)])
    seen = {start}
    counts = Counter()
    witnesses = {}
    while queue:
        state, depth = queue.popleft()
        if depth == DEPTH:
            continue
        for action in actions(state):
            observed = transition(state, action)
            expected = reference(state, action)
            active = observed.endpoint.phase in {"running", "waiting"}
            if expected != observed or active and not live_for_task(observed.frame):
                raise ValueError((state, action, observed, expected))
            counts["transitions"] += 1
            for fault in ("omit-suspension", "ignore-frame-generation", "schedule-unmapped"):
                wrong = transition(state, action, fault)
                if wrong != expected:
                    counts[fault] += 1
                    witnesses.setdefault(fault, {"state": serialized(state), "action": action,
                                                 "correct": serialized(observed), "mutant": serialized(wrong)})
            if observed not in seen:
                seen.add(observed)
                queue.append((observed, depth + 1))
    counts["states"] = len(seen)
    if len(witnesses) != 3:
        raise ValueError("a composition control was missed")
    return dict(counts), witnesses


def check_proof(lean):
    input_files = {"Mapping": FRAME / "Mapping.lean", "Endpoint": ENDPOINT / "Blocking.lean"}
    compiled = "".join(f"namespace {name}\n{file.read_text()}end {name}\n" for name, file in input_files.items())
    compiled += (HERE / "Compose.lean").read_text()
    with TemporaryDirectory(prefix="rt38-composition-") as scratch:
        source = Path(scratch) / "Combined.lean"
        source.write_text(compiled)
        result = subprocess.run([lean, "-DwarningAsError=true", source], check=True, text=True,
                                capture_output=True, timeout=30)
    expected = ("suspended_has_no_active_waiter_or_runner", "frame_change_preserves_joint_invariant",
                "endpoint_change_preserves_joint_invariant", "stale_frame_lease_refuses_dispatch",
                "detaching_cancels_waiting_receiver")
    axioms = [line for line in result.stdout.splitlines() if line.startswith("'Combined.")]
    if result.stderr or [line.split("'")[1].removeprefix("Combined.") for line in axioms] != list(expected):
        raise ValueError((result.stdout, result.stderr))
    return {"axioms": axioms, "generated_proof_sha256": sha256(compiled.encode()).hexdigest(),
            "version": subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    counts, witnesses = check_states()
    sources = (Path(__file__), HERE / "Compose.lean", FRAME / "Mapping.lean", FRAME / "run.py",
               ENDPOINT / "Blocking.lean", ENDPOINT / "run.py")
    receipt = {
        "sources_sha256": {str(path.relative_to(HERE.parent)): sha256(path.read_bytes()).hexdigest() for path in sources},
        "lean": check_proof(args.lean), "depth": DEPTH, "counts": counts, "witnesses": witnesses,
    }
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
