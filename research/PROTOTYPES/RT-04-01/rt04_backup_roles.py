"""Compare alias-aware FFI roles and reservation order for two resources."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from itertools import product
from typing import Literal


Policy = Literal["role_order", "identity_order", "all_or_none"]
Mode = Literal["shared", "exclusive"]


@dataclass(frozen=True)
class Lease:
    identity: str
    mode: Mode


@dataclass(frozen=True)
class BackupPair:
    source: str
    destination: str

    @property
    def leases(self) -> tuple[Lease, Lease]:
        return Lease(self.source, "shared"), Lease(self.destination, "exclusive")


def resolve(pair: BackupPair, identities: Mapping[str, str]) -> BackupPair:
    return BackupPair(identities[pair.source], identities[pair.destination])


def _available(requested: tuple[Lease, ...], held: tuple[Lease, ...]) -> bool:
    return all(
        wanted.identity != previous.identity or (wanted.mode == previous.mode == "shared")
        for wanted, previous in product(requested, held)
    )


def permits(active: tuple[BackupPair, ...], candidate: BackupPair) -> bool:
    """Check a pair using the supplied resource identities."""
    return candidate.source != candidate.destination and all(
        _available(candidate.leases, previous.leases) for previous in active
    )


@dataclass(frozen=True)
class InitPlan:
    pair: BackupPair
    succeeds: bool


class Stage(Enum):
    READY = auto()
    FIRST_HELD = auto()
    RESERVED = auto()
    ACTIVE = auto()
    DONE = auto()


State = tuple[Stage, Stage]
_HELD = {Stage.READY: 0, Stage.FIRST_HELD: 1, Stage.RESERVED: 2, Stage.ACTIVE: 2, Stage.DONE: 0}


@dataclass(frozen=True)
class Exploration:
    reachable: frozenset[State]
    deadlocks: frozenset[State]


def explore(policy: Policy, first: InitPlan, second: InitPlan) -> Exploration:
    """Explore two contenders with finite init and eventual finish transitions."""
    if policy not in ("role_order", "identity_order", "all_or_none"):
        raise ValueError("unsupported reservation policy")
    plans = (first, second)
    if any(not permits((), plan.pair) for plan in plans):
        raise ValueError("the two roles must have distinct resource identities")

    orders = tuple(plan.pair.leases for plan in plans)
    if policy == "identity_order":
        orders = tuple(tuple(sorted(order, key=lambda lease: lease.identity)) for order in orders)

    pending: list[State] = [(Stage.READY, Stage.READY)]
    reached = set()
    deadlocks = set()
    while pending:
        state = pending.pop()
        if state in reached:
            continue
        reached.add(state)
        next_states = []
        for index, (stage, order, plan) in enumerate(zip(state, orders, plans)):
            if stage in (Stage.READY, Stage.FIRST_HELD):
                other = 1 - index
                held = orders[other][:_HELD[state[other]]]
                acquired = _HELD[stage]
                count = 2 if policy == "all_or_none" else acquired + 1
                if not _available(order[acquired:count], held):
                    continue
                next_stage = Stage.RESERVED if count == 2 else Stage.FIRST_HELD
            elif stage == Stage.RESERVED:
                # A failed init consumes its reservation and yields no backup.
                next_stage = Stage.ACTIVE if plan.succeeds else Stage.DONE
            elif stage == Stage.ACTIVE:
                next_stage = Stage.DONE
            else:
                continue
            next_states.append(state[:index] + (next_stage,) + state[index + 1:])

        if not next_states and state != (Stage.DONE, Stage.DONE):
            deadlocks.add(state)
        pending.extend(next_states)
    return Exploration(frozenset(reached), frozenset(deadlocks))
