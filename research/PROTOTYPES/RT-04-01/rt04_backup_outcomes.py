"""Compare caller contracts for a foreign call that reserved two roles."""

from dataclasses import dataclass
from typing import Literal

from rt04_backup_roles import BackupPair, permits
from rt04_owned_call_match import Obligation, ResultCase
from rt04_return_disposition import Disposition


Init = Literal["ok", "clean_error", "indeterminate"]
Policy = Literal["release_on_error", "retain_on_error", "quarantine", "bounded_roles"]

_OWNED = frozenset({Obligation("handle", "owned")})
_RETAINED = frozenset({Obligation("handle", "retained")})
_RECONCILE = frozenset({Obligation("handle", "reconcile")})

_INIT_ERRORS = {
    "clean_error": ResultCase("InitErrorNoHandle"),
    "indeterminate": ResultCase("InitUncertain", _RECONCILE),
}
_FINISH_OUTCOMES = {
    None: ResultCase("OkWithValue", _OWNED),
    "ok": ResultCase("Finished"),
    "consumed_error": ResultCase("FinishErrorConsumed"),
    "retained_error": ResultCase("FinishErrorRetained", _RETAINED),
    "indeterminate": ResultCase("FinishUncertain", _RECONCILE),
}


@dataclass(frozen=True)
class Decision:
    admits: bool
    output: ResultCase
    roles: BackupPair | None


def receipt(init: Init, finish: Disposition | None = None) -> ResultCase:
    """Read a declared disposition after an admitted init and optional finish."""
    if init == "ok":
        return _FINISH_OUTCOMES[finish]
    if finish is not None:
        raise ValueError("finish requires a usable backup")
    return _INIT_ERRORS[init]


def consider(policy: Policy, previous: BackupPair, proposed: BackupPair, observed: ResultCase) -> Decision:
    """Check a proposed call and preserve the policy's account of earlier roles."""
    output = observed
    if observed.tag not in ("OkWithValue", "Finished"):
        if policy == "release_on_error":
            output = ResultCase("Err")
        elif policy == "retain_on_error":
            output = ResultCase("Err", _RETAINED)

    holds = bool(output.obligations)
    active = (previous,) if holds else ()
    if policy == "quarantine" and output.obligations == _RECONCILE:
        disjoint = {previous.source, previous.destination}.isdisjoint({proposed.source, proposed.destination})
        admitted = disjoint and permits((), proposed)
    else:
        # A reconciliation payload can still describe a bounded footprint. In
        # that case the call must be compatible if those roles are still live.
        admitted = permits(active, proposed)
    return Decision(admitted, output, previous if holds else None)
