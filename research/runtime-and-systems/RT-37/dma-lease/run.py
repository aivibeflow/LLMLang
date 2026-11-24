#!/usr/bin/env python3
"""Compare DMA lease identity, cancellation and finite-generation policies."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
LEAN = ["lean", "+leanprover/lean4:v4.36.0", "-DwarningAsError=true"]
ENDPOINT = (7, 11)
CAPACITY = 8
MAX_GENERATION = 3
POLICIES = ("endpoint-only", "exact-wrap", "exact-retire", "exact-unbounded")


@dataclass(frozen=True)
class Lease:
    channel: int
    buffer: int
    generation: int


@dataclass(frozen=True)
class State:
    stage: str
    generation: int = 0
    lease: Lease | None = None


@dataclass(frozen=True)
class Event:
    action: str
    lease: Lease | None = None
    synchronized: bool = False
    offset: int = 0
    size: int = 0


def step(policy, state, event):
    action = event.action
    if action == "cpuUse":
        return state if state.stage in {"cpu", "retired"} else None
    if action == "submit":
        if state.stage != "cpu" or (policy != "exact-unbounded" and state.generation > MAX_GENERATION):
            return None
        return State("running", lease=Lease(*ENDPOINT, state.generation))
    live, reported = state.lease, event.lease
    if live is None or reported is None:
        return None
    if policy == "endpoint-only":
        matched = (live.channel, live.buffer) == (reported.channel, reported.buffer)
    else:
        matched = live == reported
    if not matched:
        return None
    if action == "deviceWrite" and state.stage in {"running", "cancelling"}:
        return state if event.size > 0 and event.offset <= CAPACITY - event.size else None
    if (state.stage, action) == ("running", "cancel"):
        return State("cancelling", lease=live)
    if (state.stage, action) == ("running", "complete"):
        return State("completed", lease=live)
    if (state.stage, action) == ("cancelling", "quiesced"):
        return State("cancelled", lease=live)
    if state.stage in {"completed", "cancelled"} and action == "acquire" and event.synchronized:
        following = live.generation + 1
        if policy == "exact-wrap":
            return State("cpu", generation=following % (MAX_GENERATION + 1))
        if policy != "exact-unbounded" and following > MAX_GENERATION:
            return State("retired")
        return State("cpu", generation=following)
    return None


def encoded(state):
    if state is None:
        return "deny"
    if state.stage == "cpu":
        return f"cpu:{state.generation}"
    if state.lease is None:
        return state.stage
    lease = state.lease
    return f"{state.stage}:{lease.channel}:{lease.buffer}:{lease.generation}"


def interpret_schedule(policy, events):
    state = State("cpu")
    trace = []
    for event in events:
        result = step(policy, state, event)
        if result is not None:
            state = result
        trace.append({"action": event.action, "reported": None if event.lease is None else event.lease.generation,
                      "admitted": result is not None, "after": encoded(state)})
    return trace


def controls():
    zero, one = (Lease(*ENDPOINT, generation) for generation in (0, 1))
    scheduled = {
        "cancel_before_acquire": (
            Event("submit"), Event("cancel", zero), Event("acquire", zero, True), Event("complete", zero),
            Event("cpuUse"), Event("deviceWrite", zero, offset=6, size=2),
            Event("deviceWrite", zero, offset=6, size=3), Event("quiesced", zero), Event("cpuUse"),
            Event("acquire", zero), Event("acquire", zero, True), Event("cpuUse"),
        ),
        "completion_after_reuse": (
            Event("submit"), Event("cancel", zero), Event("quiesced", zero), Event("acquire", zero, True),
            Event("submit"), Event("complete", zero), Event("acquire", one, True), Event("cpuUse"),
        ),
        "completion_after_wrap": (
            *(event for epoch in range(MAX_GENERATION + 1) for event in
              (Event("submit"), Event("complete", Lease(*ENDPOINT, epoch)),
               Event("acquire", Lease(*ENDPOINT, epoch), True))),
            Event("submit"), Event("complete", zero), Event("acquire", zero, True),
        ),
    }
    observed = {case: {policy: interpret_schedule(policy, events) for policy in POLICIES}
                for case, events in scheduled.items()}
    for policy, values in observed["cancel_before_acquire"].items():
        expected = [True, True, False, False, False, True, False, True, False, False, True, True]
        if [item["admitted"] for item in values] != expected:
            raise ValueError(f"Cancellation protocol changed for {policy}")
    for policy, values in observed["completion_after_reuse"].items():
        if [item["admitted"] for item in values[-3:]] != [policy == "endpoint-only"] * 3:
            raise ValueError(f"Stale completion discriminator changed for {policy}")
    wrap_expected = {
        "endpoint-only": [False, False, False], "exact-retire": [False, False, False],
        "exact-wrap": [True, True, True], "exact-unbounded": [True, False, False],
    }
    for policy, values in observed["completion_after_wrap"].items():
        if [item["admitted"] for item in values[-3:]] != wrap_expected[policy]:
            raise ValueError(f"Generation-wrap discriminator changed for {policy}")
    return observed


def lean_lease(lease):
    return f"⟨⟨{lease.channel}, {lease.buffer}⟩, {lease.generation}⟩"


def lean_phase(state):
    if state.stage == "cpu":
        return f".cpu {state.generation}"
    if state.stage == "retired":
        return ".retired"
    if state.stage in {"completed", "cancelled"}:
        return f".ready {lean_lease(state.lease)} .{state.stage}"
    return f".{state.stage} {lean_lease(state.lease)}"


def lean_event(event):
    if event.lease is None:
        return f".{event.action}"
    target = lean_lease(event.lease)
    if event.action == "acquire":
        return f".acquire {target} {str(event.synchronized).lower()}"
    if event.action == "deviceWrite":
        return f".deviceWrite {target} {event.offset} {event.size}"
    return f".{event.action} {target}"


def lean_replay(work):
    generations = (0, 1, 3, 4)
    leases = [Lease(*endpoint, generation) for endpoint, generation in
              product((ENDPOINT, (8, 11), (7, 12)), generations)]
    stages = [State("cpu", generation=generation) for generation in generations] + [State("retired")]
    stages += [State(stage, lease=Lease(*ENDPOINT, generation))
               for stage, generation in product(("running", "cancelling", "completed", "cancelled"), generations)]
    events = [Event("submit"), Event("cpuUse")]
    events += [Event(operation, lease) for lease, operation in product(leases, ("cancel", "complete", "quiesced"))]
    events += [Event("acquire", lease, fence) for lease, fence in product(leases, (False, True))]
    ranges = ((0, 0), (0, CAPACITY), (1, CAPACITY), (CAPACITY - 1, 1), (CAPACITY, 1), (2**64 - 1, 2))
    events += [Event("deviceWrite", lease, offset=offset, size=size) for lease, (offset, size) in product(leases, ranges)]
    phases_text = ",\n  ".join(map(lean_phase, stages))
    events_text = ",\n  ".join(map(lean_event, events))
    driver = f'''import DmaLease
open DmaLease

def phases : List Phase := [
  {phases_text}]

def events : List Event := [
  {events_text}]

def codeLease (lease : Lease) : String := s!"{{lease.endpoint.channel}}:{{lease.endpoint.buffer}}:{{lease.generation}}"

def codeResult : Option Phase → String
  | none => "deny"
  | some (.cpu generation) => s!"cpu:{{generation}}"
  | some (.running lease) => "running:" ++ codeLease lease
  | some (.cancelling lease) => "cancelling:" ++ codeLease lease
  | some (.ready lease .completed) => "completed:" ++ codeLease lease
  | some (.ready lease .cancelled) => "cancelled:" ++ codeLease lease
  | some .retired => "retired"

#eval IO.println (String.intercalate "\\n" ([some {MAX_GENERATION}, none].flatMap fun limit =>
  phases.flatMap fun phase => events.map fun event => codeResult (step ⟨⟨7, 11⟩, {CAPACITY}, limit⟩ phase event)))
'''
    support = HERE / "DmaLease.lean"
    (work / support.name).write_bytes(support.read_bytes())
    (work / "Replay.lean").write_text(driver, encoding="utf-8")
    environment = {**os.environ, "LEAN_PATH": str(work)}

    def lean(*arguments):
        process = subprocess.run([*LEAN, *arguments], cwd=work, env=environment, text=True,
                                 capture_output=True, timeout=60)
        if process.returncode:
            raise ValueError(f"Lean failed for {arguments}:\n{process.stdout}{process.stderr}")
        return process.stdout

    axioms = lean("-o", "DmaLease.olean", support.name).strip()
    observations = lean("Replay.lean")
    expected = [encoded(step(policy, state, event))
                for policy, state, event in product(("exact-retire", "exact-unbounded"), stages, events)]
    if observations.splitlines() != expected:
        raise ValueError("Lean and Python phase observations differed")
    return {"lean": lean("--version").strip(), "phases": len(stages), "events": len(events),
            "observations": len(expected), "observation_sha256": sha256(observations.encode()).hexdigest(),
            "axioms": axioms.splitlines()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-dma-lease-") as tmp:
        result = {"schema": "llmlang-rt37-dma-lease-v1", "bounded_max_generation": MAX_GENERATION,
                  "capacity": CAPACITY,
                  "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                                    for name in ("DmaLease.lean", "run.py")},
                  "kernel_replay": lean_replay(Path(tmp)), "controls": controls()}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
