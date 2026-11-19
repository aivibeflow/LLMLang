"""Compare exact content addresses for bounded recursive declaration graphs."""
from __future__ import annotations

from dataclasses import dataclass
from graphlib import TopologicalSorter
from itertools import permutations
from typing import Literal, Mapping

from .semantic_graph import ContentStore, Dependency, canonical_bytes


MAX_STRUCTURAL_MEMBERS = 6


@dataclass(frozen=True)
class Call:
    target: str


@dataclass(frozen=True)
class External:
    value_hash: str


@dataclass(frozen=True)
class Definition:
    body: tuple[str | int | bool | Call | External, ...]
    slot_key: str | None = None


class RecursiveIdentityError(ValueError):
    pass


def _components(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Find strongly connected components with two iterative depth-first passes."""
    reverse = {node: set() for node in graph}
    for source, targets in graph.items():
        for target in targets:
            reverse[target].add(source)

    visited: set[str] = set()
    finished: list[str] = []
    for root in graph:
        stack = [(root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                finished.append(node)
            elif node not in visited:
                visited.add(node)
                stack.append((node, True))
                stack.extend((target, False) for target in graph[node] if target not in visited)

    pending = set(graph)
    components = []
    for root in reversed(finished):
        if root not in pending:
            continue
        members = []
        todo = [root]
        pending.remove(root)
        while todo:
            node = todo.pop()
            members.append(node)
            for predecessor in reverse[node] & pending:
                pending.remove(predecessor)
                todo.append(predecessor)
        components.append(tuple(members))
    return components


def publish_definitions(
    store: ContentStore,
    definitions: Mapping[str, Definition],
    mode: Literal["dag-only", "keyed", "structural"],
) -> dict[str, str]:
    """Publish a finite graph using existing ContentStore hash and dependency rules."""
    if mode not in ("dag-only", "keyed", "structural"):
        raise RecursiveIdentityError("unknown recursive address policy")
    graph: dict[str, set[str]] = {}
    for name, definition in definitions.items():
        targets: set[str] = set()
        for token in definition.body:
            if isinstance(token, Call):
                if token.target not in definitions:
                    raise RecursiveIdentityError(f"unknown call target: {token.target}")
                targets.add(token.target)
            elif isinstance(token, External):
                if token.value_hash not in store:
                    raise RecursiveIdentityError(f"unknown external dependency: {token.value_hash}")
            elif type(token) not in (str, int, bool):
                raise RecursiveIdentityError("unsupported definition token")
        graph[name] = targets

    components = _components(graph)
    owners = {member: index for index, group in enumerate(components) for member in group}
    dependencies = {}
    recursive_groups = set()
    for index, group in enumerate(components):
        dependencies[index] = {
            owners[target] for member in group for target in graph[member] if owners[target] != index
        }
        if len(group) == 1 and group[0] not in graph[group[0]]:
            continue
        recursive_groups.add(index)
        if mode == "dag-only":
            raise RecursiveIdentityError("recursive component is unsupported by dag-only policy")
        if mode == "structural" and len(group) > MAX_STRUCTURAL_MEMBERS:
            raise RecursiveIdentityError("recursive component exceeds structural search bound")
        if mode == "keyed":
            keys = [definitions[member].slot_key for member in group]
            if any(not isinstance(key, str) or not key for key in keys) or len(set(keys)) != len(keys):
                raise RecursiveIdentityError("each recursive member requires a unique slot key")

    addresses: dict[str, str] = {}
    for index in TopologicalSorter(dependencies).static_order():
        group = components[index]
        members = set(group)
        exact_dependencies: set[str] = set()
        for member in group:
            for token in definitions[member].body:
                if isinstance(token, External):
                    exact_dependencies.add(token.value_hash)
                elif isinstance(token, Call) and token.target not in members:
                    exact_dependencies.add(addresses[token.target])
        external_edges = [Dependency("uses", address) for address in sorted(exact_dependencies)]

        def encode(member: str, indexes: Mapping[str, int]) -> list[dict[str, str | int | bool]]:
            tokens = []
            for token in definitions[member].body:
                if isinstance(token, Call):
                    if token.target in indexes:
                        tokens.append({"local_call": indexes[token.target]})
                    else:
                        tokens.append({"exact_call": addresses[token.target]})
                elif isinstance(token, External):
                    tokens.append({"external": token.value_hash})
                else:
                    tokens.append({"literal": token})
            return tokens

        if index not in recursive_groups:
            member = group[0]
            addresses[member] = store.put("rt05-definition-v1", encode(member, {}), external_edges)
            continue

        if mode == "keyed":
            order = sorted(group, key=lambda member: definitions[member].slot_key)
            indexes = {member: position for position, member in enumerate(order)}
            rows = [{"slot": definitions[member].slot_key, "body": encode(member, indexes)}
                    for member in order]
        else:
            # Reference canonicalizer for small components. Equal minima are
            # graph symmetries, so a member uses its lowest canonical position.
            best = None
            for order in permutations(group):
                positions = {member: position for position, member in enumerate(order)}
                candidate = [{"body": encode(member, positions)} for member in order]
                encoding = canonical_bytes(candidate)
                if best is None or encoding < best:
                    best, rows, indexes = encoding, candidate, positions
                elif encoding == best:
                    for member in order:
                        indexes[member] = min(indexes[member], positions[member])

        root = store.put(f"rt05-recursive-{mode}-v1", rows, external_edges)
        for member in group:
            addresses[member] = store.put(
                "rt05-recursive-member-v1", {"position": indexes[member]},
                [Dependency("member_of", root)],
            )
    return addresses
