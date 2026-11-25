"""Immutable event records and a bounded causal verifier for the MCP fixture."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json

PROVENANCE = {
    "session": "coordinator", "turn": "coordinator", "attempt": "coordinator",
    "request": "client", "response": "adapter", "tool": "adapter",
    "validation": "checker", "repair": "coordinator", "terminal": "coordinator",
}
OUTCOMES = {
    "session": ("opened",), "turn": ("opened",), "attempt": ("opened",),
    "request": ("issued",), "response": ("refused", "ok"), "tool": ("refused", "ok"),
    "validation": ("failed", "passed"), "repair": ("opened",), "terminal": ("complete",),
}
PARENTS = {
    "turn": ("session",), "attempt": ("turn",), "request": ("attempt", "repair"),
    "response": ("request",), "tool": ("response",), "validation": ("tool",),
    "repair": ("validation",), "terminal": ("validation",),
}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Scope:
    session: str
    baseline: str
    adapter: str


@dataclass(frozen=True)
class Event:
    scope: Scope
    kind: str
    actor: str
    outcome: str
    turn: int = 0
    attempt: int = 0
    wire: int | None = None
    result_root: str | None = None
    parent: str | None = None

    @property
    def key(self):
        return self.scope.session, self.turn, self.attempt, self.kind, self.wire

    @property
    def identity(self):
        return digest({"schema": "mcp-event/1", **asdict(self)})


def event(scope, kind, outcome, *, turn=0, attempt=0, wire=None, result_root=None, parent=None):
    return Event(scope, kind, PROVENANCE[kind], outcome, turn, attempt, wire,
                 result_root, parent.identity if parent is not None else None)


def expected_shape(entry, expected):
    current = expected.get(entry.scope.session)
    if current is None or entry.scope != current[0]:
        return False
    if entry.actor != PROVENANCE.get(entry.kind) or entry.outcome not in OUTCOMES.get(entry.kind, ()):
        return False
    if type(entry.turn) is not int or type(entry.attempt) is not int:
        return False
    expected_turn = 0 if entry.kind == "session" else 1
    if entry.turn != expected_turn:
        return False
    if entry.kind in ("session", "turn"):
        return entry.attempt == 0 and entry.wire is None and entry.result_root is None
    if entry.kind in ("attempt", "repair", "terminal"):
        expected_attempt = 1 if entry.kind == "attempt" else 2
        expected_root = current[1] if entry.kind == "terminal" else None
        return entry.attempt == expected_attempt and entry.wire is None and entry.result_root == expected_root
    if entry.attempt not in (1, 2) or type(entry.wire) is not int:
        return False
    if entry.kind == "request":
        return entry.result_root is None
    return entry.result_root == (entry.scope.baseline if entry.attempt == 1 else current[1])


def parent_matches(entry, parent):
    if entry.scope != parent.scope or parent.kind not in PARENTS[entry.kind]:
        return False
    if entry.kind == "turn":
        return parent.turn == 0
    if entry.kind == "attempt":
        return parent.attempt == 0
    if entry.kind == "repair":
        return parent.attempt == entry.attempt - 1 and parent.outcome == "failed"
    if entry.attempt != parent.attempt:
        return False
    if entry.kind == "request":
        return parent.kind == ("attempt" if entry.attempt == 1 else "repair")
    if entry.kind == "response":
        return entry.wire == parent.wire
    if entry.kind == "tool":
        return (entry.wire, entry.outcome, entry.result_root) == (
            parent.wire, parent.outcome, parent.result_root
        )
    if entry.kind == "validation":
        return (entry.wire == parent.wire and entry.result_root == parent.result_root
                and entry.outcome == ("passed" if parent.outcome == "ok" else "failed"))
    return entry.kind == "terminal" and parent.outcome == "passed" and entry.result_root == parent.result_root


def verify(records, expected):
    by_key, by_identity, requests = {}, {}, {}
    for entry in records:
        if not expected_shape(entry, expected):
            return "refused-scope-or-schema"
        opaque = entry.identity
        if by_key.setdefault(entry.key, opaque) != opaque:
            return "refused-conflicting-event"
        if entry.kind == "request":
            request_key = (entry.scope.session, entry.wire)
            if requests.setdefault(request_key, entry.key) != entry.key:
                return "refused-wire-reuse"
        by_identity[opaque] = entry
    pending = False
    for entry in by_identity.values():
        if entry.kind == "session":
            if entry.parent is not None:
                return "refused-causal-edge"
            continue
        parent = by_identity.get(entry.parent)
        if parent is None:
            pending = True
        elif not parent_matches(entry, parent):
            return "refused-causal-edge"
    terminals = {entry.scope.session for entry in by_identity.values() if entry.kind == "terminal"}
    return "complete" if not pending and terminals == set(expected) else "pending"
