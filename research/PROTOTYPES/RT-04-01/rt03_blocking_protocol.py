"""Finite two-actor protocol experiment for buffered and rendezvous sends.

This is a deliberately small candidate model, not a claim about actor semantics
in general. Actors execute one send and one receive in a fixed order. Buffered
sends enqueue; rendezvous sends advance only when the peer is at receive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Operation = Literal["send", "receive"]
Mode = Literal["buffered", "rendezvous"]


@dataclass(frozen=True)
class Action:
    actor: str
    operation: Operation


@dataclass(frozen=True)
class State:
    a_pc: int = 0
    b_pc: int = 0
    # Number of queued messages, indexed by sender. Each actor sends once.
    a_to_b: int = 0
    b_to_a: int = 0


@dataclass(frozen=True)
class Outcome:
    status: Literal["completed", "blocked"]
    trace: tuple[Action, ...]
    terminal_state: State


class BlockingProtocol:
    """Explore all schedules of two actors with fixed two-operation scripts."""

    def __init__(self, a_script: tuple[Operation, Operation],
                 b_script: tuple[Operation, Operation], *, mode: Mode):
        if mode not in ("buffered", "rendezvous"):
            raise ValueError("unsupported message mode")
        if any(tuple(script) not in (("send", "receive"), ("receive", "send"))
               for script in (a_script, b_script)):
            raise ValueError("each actor must perform one send and one receive")
        self._scripts = {"a": a_script, "b": b_script}
        self._mode = mode

    def _enabled(self, state: State) -> tuple[Action, ...]:
        pcs = {"a": state.a_pc, "b": state.b_pc}
        actions = []
        for actor in ("a", "b"):
            pc = pcs[actor]
            if pc == 2:
                continue
            operation = self._scripts[actor][pc]
            peer = "b" if actor == "a" else "a"
            if operation == "send":
                if self._mode == "buffered" or self._scripts[peer][pcs[peer]] == "receive":
                    actions.append(Action(actor, "send"))
            else:
                queued = state.b_to_a if actor == "a" else state.a_to_b
                if queued:
                    actions.append(Action(actor, "receive"))
        return tuple(actions)

    def _step(self, state: State, action: Action) -> State:
        a_pc, b_pc = state.a_pc, state.b_pc
        a_to_b, b_to_a = state.a_to_b, state.b_to_a
        pc = a_pc if action.actor == "a" else b_pc
        operation = self._scripts[action.actor][pc]
        if operation != action.operation:
            raise ValueError("action does not match the actor's next operation")
        if operation == "send" and self._mode == "rendezvous":
            peer = "b" if action.actor == "a" else "a"
            peer_pc = b_pc if peer == "b" else a_pc
            if self._scripts[peer][peer_pc] != "receive":
                raise ValueError("rendezvous send has no waiting receiver")
            if action.actor == "a":
                a_pc += 1
                b_pc += 1
            else:
                b_pc += 1
                a_pc += 1
            return State(a_pc, b_pc, a_to_b, b_to_a)
        if operation == "send":
            if action.actor == "a":
                a_pc += 1
                a_to_b += 1
            else:
                b_pc += 1
                b_to_a += 1
        else:
            if action.actor == "a":
                a_pc += 1
                b_to_a -= 1
            else:
                b_pc += 1
                a_to_b -= 1
        return State(a_pc, b_pc, a_to_b, b_to_a)

    def explore(self) -> dict[Outcome, tuple[Action, ...]]:
        pending = [(State(), ())]
        outcomes = {}
        while pending:
            state, trace = pending.pop()
            enabled = self._enabled(state)
            if not enabled:
                status = "completed" if state.a_pc == state.b_pc == 2 else "blocked"
                outcome = Outcome(status, trace, state)
                outcomes.setdefault(outcome, trace)
                continue
            for action in enabled:
                successor = self._step(state, action)
                # Keep schedule prefixes distinct because the observable trace is
                # part of the outcome, even when two schedules reach one state.
                pending.append((successor, trace + (action,)))
        return outcomes

    def replay(self, trace: tuple[Action, ...]) -> Outcome:
        state = State()
        for position, action in enumerate(trace):
            if action not in self._enabled(state):
                raise ValueError(f"step {position} is not enabled: {action}")
            state = self._step(state, action)
        if self._enabled(state):
            raise ValueError("incomplete trace")
        status = "completed" if state.a_pc == state.b_pc == 2 else "blocked"
        return Outcome(status, trace, state)
