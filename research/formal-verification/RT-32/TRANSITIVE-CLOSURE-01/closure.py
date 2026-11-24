"""Exact proof-receipt closure for a fixed, independently supplied claim graph."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, order=True)
class Claim:
    role: str
    subject: str
    theorem: str
    profile: str = "integer/ordered-effects-v1"


@dataclass(frozen=True)
class Receipt:
    claim: Claim
    requires: tuple[Claim, ...]
    producer: str
    toolchain: str
    result: str
    artifact: str


@dataclass(frozen=True)
class Closure:
    evidence: tuple[tuple[Claim, str], ...]
    blockers: tuple[tuple[Claim, str], ...]

    @property
    def evidence_digest(self):
        if self.blockers:
            return None
        return digest([(asdict(claim), receipt) for claim, receipt in self.evidence])


def evaluate(root, inventory, receipts, *, producer, toolchain):
    """Visit exact expected graph edges. Return receipts and unclosed obligations."""
    active = set()
    evidence = {}
    blockers = set()

    def visit(claim):
        if claim in active:
            blockers.add((claim, "cyclic-discharge"))
            return
        if claim in evidence:
            return
        if claim not in inventory:
            blockers.add((claim, "missing-expected-claim"))
            return

        receipt = receipts.get(claim)
        if receipt is None:
            reason = "unresolved-assumption" if claim.role == "assumption" else "pending-receipt"
        elif receipt.claim != claim:
            reason = "wrong-claim"
        elif receipt.producer != producer or receipt.toolchain != toolchain:
            reason = "wrong-provenance"
        elif receipt.requires != tuple(sorted(inventory[claim])):
            reason = "incomplete-or-different-dependencies"
        elif receipt.result != "checked":
            reason = receipt.result
        else:
            reason = None
        if reason is not None:
            blockers.add((claim, reason))
            return

        active.add(claim)
        for required in receipt.requires:
            visit(required)
        active.remove(claim)
        evidence[claim] = digest(asdict(receipt))

    visit(root)
    return Closure(tuple(sorted(evidence.items())), tuple(sorted(blockers)))
