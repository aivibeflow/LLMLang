"""Predict what recovery can observe after an interrupted completion."""

from dataclasses import dataclass
from typing import Literal

from rt04_cancel_receipts import Evidence, Reservation, apply


Publication = Literal["atomic", "separate"]
Cut = Literal["before_effect", "after_effect", "after_record", "after_commit", "complete"]


@dataclass(frozen=True)
class RecoveryView:
    effect_live: bool
    terminal_record: bool
    delivered: bool


def predict(publication: Publication, cut: Cut) -> RecoveryView:
    committed = cut in ("after_commit", "complete")
    effect_committed = committed or (publication == "separate" and cut in ("after_effect", "after_record"))
    return RecoveryView(not effect_committed, committed, cut == "complete")


def recover(state: Reservation, terminal: Evidence | None) -> Reservation:
    """An empty lookup leaves the reservation pending reconciliation."""
    return state if terminal is None else apply("terminal_by_invocation", state, terminal)
