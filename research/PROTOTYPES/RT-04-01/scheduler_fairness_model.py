"""Tiny transition-system witnesses for weak/strong scheduler fairness."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    ENABLE_B = "enable_b"
    DISABLE_B = "disable_b"
    RUN_A = "run_a"
    RUN_B = "run_b"


@dataclass(frozen=True)
class State:
    b_enabled: bool
    b_runs: int = 0


def step(state: State, action: Action, *, intermittent: bool) -> State:
    if action is Action.ENABLE_B and intermittent and not state.b_enabled:
        return State(True, state.b_runs)
    if action is Action.DISABLE_B and intermittent and state.b_enabled:
        return State(False, state.b_runs)
    if action is Action.RUN_A:
        return state
    if action is Action.RUN_B and state.b_enabled:
        return State(False if intermittent else True, state.b_runs + 1)
    raise ValueError(f"action is not enabled: {action.value}")


def replay_cycle(
    initial: State, actions: tuple[Action, ...], *, intermittent: bool
) -> tuple[State, ...]:
    """Replay one candidate cycle and require it to return to its initial state."""
    states = [initial]
    for action in actions:
        states.append(step(states[-1], action, intermittent=intermittent))
    if states[-1] != initial:
        raise ValueError("actions do not form a cycle")
    return tuple(states[:-1])


def weak_fair_cycle(states: tuple[State, ...]) -> bool:
    """A starvation cycle is weak-fair for B iff B is not always enabled."""
    return not all(state.b_enabled for state in states)


def strong_fair_cycle(states: tuple[State, ...]) -> bool:
    """A starvation cycle is strong-fair for B iff B is never enabled."""
    return not any(state.b_enabled for state in states)


def round_robin_first_b(cursor: str) -> int:
    """Return B's zero-based turn in a fixed two-task, always-runnable RR queue."""
    if cursor not in {"A", "B"}:
        raise ValueError("cursor must be A or B")
    return 0 if cursor == "B" else 1
