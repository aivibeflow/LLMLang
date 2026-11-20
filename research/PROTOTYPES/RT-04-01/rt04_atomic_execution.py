"""Enumerate executions of a bounded atomic load and store fragment."""

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import permutations, product


MAX_OPERATIONS = 6
Edge = tuple[str, str]


@dataclass(frozen=True)
class Store:
    name: str
    location: str
    value: int
    release: bool = False


@dataclass(frozen=True)
class Load:
    name: str
    location: str
    acquire: bool = False


@dataclass(frozen=True)
class Execution:
    modification_orders: tuple[tuple[str, ...], ...]
    read_from: tuple[tuple[str, str], ...]  # (load, source write)
    synchronizes_with: frozenset[Edge]
    happens_before: frozenset[Edge]
    observations: tuple[tuple[str, int], ...]
    admits_global_order: bool


def _strict_closure(nodes: tuple[str, ...], edges: set[Edge]) -> frozenset[Edge] | None:
    """Return the transitive closure, or None when the edges form a cycle."""
    successors: dict[str, set[str]] = {node: set() for node in nodes}
    for earlier, later in edges:
        successors[earlier].add(later)

    result = set()
    for start in nodes:
        pending = list(successors[start])
        reached = set()
        while pending:
            node = pending.pop()
            if node == start:
                return None
            if node not in reached:
                reached.add(node)
                pending.extend(successors[node])
        result.update((start, node) for node in reached)
    return frozenset(result)


def _coherent(
    happens_before: frozenset[Edge],
    locations: dict[str, str],
    ranks: dict[str, int],
    read_from: dict[str, str],
) -> bool:
    for first, second in happens_before:
        if locations[first] != locations[second]:
            continue
        first_rank = ranks[read_from.get(first, first)]
        second_rank = ranks[read_from.get(second, second)]
        # The second event sets a strict bound when it writes and an inclusive
        # bound when it reads. This covers both possible kinds of first event.
        if first_rank > second_rank or (first_rank == second_rank and second in ranks):
            return False
    return True


def enumerate_executions(
    initial: dict[str, int], threads: tuple[tuple[Load | Store, ...], ...]
) -> Iterator[Execution]:
    """Derive witnesses for relaxed loads/stores and direct release/acquire.

    Each input thread fixes the sequence of its operations. Observation pairs
    follow load order in the input. Modification orders list the initial write
    first and are emitted in location name order. The global order flag checks
    whether the same witness could come from one sequential interleaving.
    """
    operations = tuple(op for thread in threads for op in thread)
    if len(operations) > MAX_OPERATIONS:
        raise ValueError(f"fixture supports at most {MAX_OPERATIONS} operations")
    if any(not isinstance(op, (Load, Store)) for op in operations):
        raise ValueError("expected atomic loads and stores")
    if any(not isinstance(loc, str) or not loc for loc in initial):
        raise ValueError("location names must be nonempty strings")
    if any(type(value) is not int for value in initial.values()):
        raise ValueError("initial values must be integers")

    initial_writes = tuple(Store(f"init:{loc}", loc, initial[loc]) for loc in sorted(initial))
    events = (*initial_writes, *operations)
    if any(not isinstance(event.name, str) or not event.name for event in events):
        raise ValueError("event names must be nonempty strings")
    locations = {event.name: event.location for event in events}
    if len(locations) != len(events):
        raise ValueError("event names must be unique, including initial writes")
    if any(not isinstance(loc, str) or loc not in initial for loc in locations.values()):
        raise ValueError("each location needs an initial value")

    loads = tuple(op for op in operations if isinstance(op, Load))
    stores = {event.name: event for event in events if isinstance(event, Store)}
    if any(type(store.value) is not int or type(store.release) is not bool for store in stores.values()):
        raise ValueError("expected integer store values and Boolean release flags")
    if any(type(load.acquire) is not bool for load in loads):
        raise ValueError("expected Boolean acquire flags")

    writes_by_location = {loc: [] for loc in sorted(initial)}
    for store in stores.values():
        writes_by_location[store.location].append(store.name)
    order_options = [
        tuple((writes[0], *order) for order in permutations(writes[1:]))
        for writes in writes_by_location.values()
    ]
    source_options = [writes_by_location[load.location] for load in loads]
    before = {(a.name, b.name) for thread in threads for a, b in zip(thread, thread[1:])}
    before.update((write.name, op.name) for write in initial_writes for op in operations)
    names = tuple(locations)

    for sources in product(*source_options):
        read_from = {load.name: source for load, source in zip(loads, sources)}
        sync = frozenset(
            (source, load.name)
            for load, source in zip(loads, sources)
            if load.acquire and stores[source].release
        )
        happens_before = _strict_closure(names, before | sync)
        if happens_before is None:
            continue

        for orders in product(*order_options):
            ranks = {write: rank for order in orders for rank, write in enumerate(order)}
            if not _coherent(happens_before, locations, ranks, read_from):
                continue

            # The load must follow its source and precede the next write on its
            # location for that source to be the latest write in a global order.
            next_write = {a: b for order in orders for a, b in zip(order, order[1:])}
            global_edges = before | set(next_write.items())
            global_edges.update((source, load) for load, source in read_from.items())
            global_edges.update(
                (load, next_write[source]) for load, source in read_from.items() if source in next_write
            )
            yield Execution(
                orders,
                tuple(read_from.items()),
                sync,
                happens_before,
                tuple((load, stores[source].value) for load, source in read_from.items()),
                _strict_closure(names, global_edges) is not None,
            )
