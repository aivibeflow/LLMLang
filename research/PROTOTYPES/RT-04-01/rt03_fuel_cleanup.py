"""Tiny model of fuel exhaustion after an effect inside a resource scope.

This is an observation-model probe, not LLMLang source semantics. It compares
structured exhaustion with reserved cleanup fuel, structured exhaustion where
cleanup must use the depleted budget, and an abortive trap with no guest cleanup.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Policy = Literal["reserved_cleanup", "no_reserve", "abortive_trap"]
Terminal = Literal["FuelExhausted", "CleanupFuelExhausted", "Trap"]


@dataclass(frozen=True)
class Observation:
    policy: Policy
    terminal: Terminal
    fuel_used: int
    effect_trace: tuple[str, ...]
    resource_state: str
    cleanup_trace: tuple[str, ...]


def run_effect_in_scope(fuel: int, policy: Policy) -> Observation:
    """Emit an effect, acquire a resource, then exhaust before the body step."""
    if type(fuel) is not int or fuel < 0:
        raise ValueError("fuel must be a non-negative integer")
    if policy not in {"reserved_cleanup", "no_reserve", "abortive_trap"}:
        raise ValueError(f"unsupported policy: {policy}")

    used = 0
    effects: list[str] = []
    cleanup: list[str] = []
    # Two ordinary transitions: an externally visible write, then acquire.
    if fuel > used:
        used += 1
        effects.append("write:recorded")
    else:
        return Observation(policy, "FuelExhausted", used, tuple(effects),
                          "not_acquired", tuple(cleanup))

    if fuel > used:
        used += 1
        resource_state = "active"
    else:
        return Observation(policy, "FuelExhausted", used, tuple(effects),
                          "not_acquired", tuple(cleanup))

    # The next ordinary transition is blocked at the exhausted boundary.
    if policy == "abortive_trap":
        return Observation(policy, "Trap", used, tuple(effects), resource_state,
                          tuple(cleanup))
    if policy == "no_reserve":
        return Observation(policy, "CleanupFuelExhausted", used, tuple(effects),
                          resource_state, tuple(cleanup))

    # Reserved cleanup is a separate, bounded finalization allowance.
    cleanup.append("release:resource")
    return Observation(policy, "FuelExhausted", used, tuple(effects), "released",
                      tuple(cleanup))


if __name__ == "__main__":
    for selected in ("reserved_cleanup", "no_reserve", "abortive_trap"):
        print(run_effect_in_scope(2, selected))
