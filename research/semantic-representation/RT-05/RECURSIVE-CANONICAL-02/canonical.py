"""Canonical traversal for closed SCCs with labeled, ordered body tokens."""

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.recursive_identity import Call, Definition, External
from src.semantic_graph import canonical_bytes


@dataclass(frozen=True)
class CanonicalGroup:
    rows: bytes
    positions: dict[str, int]
    candidates: int
    tokens_visited: int


def rooted_rows(definitions: dict[str, Definition], root: str):
    """Number a rooted component by first encounter in ordered call positions."""
    positions = {root: 0}
    pending = deque([root])
    rows = []
    while pending:
        body = []
        for token in definitions[pending.popleft()].body:
            if isinstance(token, Call):
                if token.target not in definitions:
                    raise ValueError("Unresolved call target in closed component")
                if token.target not in positions:
                    positions[token.target] = len(positions)
                    pending.append(token.target)
                body.append({"local_call": positions[token.target]})
            elif isinstance(token, External):
                body.append({"external": token.value_hash})
            elif type(token) in (str, int, bool):
                body.append({"literal": token})
            else:
                raise ValueError("Unsupported body token")
        rows.append({"body": body})
    if len(positions) != len(definitions):
        raise ValueError("Definitions must form one strongly connected component")
    return canonical_bytes(rows), positions


def canonicalize(definitions: dict[str, Definition]) -> CanonicalGroup:
    if not definitions:
        raise ValueError("Empty component")
    best = None
    best_positions = {}
    for root in definitions:
        candidate, positions = rooted_rows(definitions, root)
        if best is None or candidate < best:
            best, best_positions = candidate, positions
        elif candidate == best:
            best_positions = {member: min(position, best_positions[member])
                              for member, position in positions.items()}
    count = len(definitions)
    return CanonicalGroup(best, best_positions, count,
                          count * sum(len(item.body) for item in definitions.values()))
