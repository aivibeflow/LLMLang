"""Finite store-buffering litmus enumerator for two candidate memory profiles.

This is an abstract comparison, not an implementation of C++, Rust, or Go.
"""
from itertools import permutations


def sequentially_consistent_outcomes():
    """Enumerate values under one global order preserving each thread's order."""
    # Initial writes precede all events. W_x, R_y are thread 1; W_y, R_x thread 2.
    events = ("Wx", "Ry", "Wy", "Rx")
    outcomes = set()
    for order in permutations(events):
        position = {event: i for i, event in enumerate(order)}
        if position["Wx"] > position["Ry"] or position["Wy"] > position["Rx"]:
            continue
        x = y = 0
        reads = {}
        for event in order:
            if event == "Wx":
                x = 1
            elif event == "Wy":
                y = 1
            elif event == "Rx":
                reads["rx"] = x
            else:
                reads["ry"] = y
        outcomes.add((reads["rx"], reads["ry"]))
    return outcomes


def per_location_atomic_outcomes():
    """Abstract independently ordered locations; each read sees init or store."""
    # Each load can observe the initial value or the other thread's store; this
    # profile intentionally has no cross-location global order constraint.
    return {(rx, ry) for rx in (0, 1) for ry in (0, 1)}


def message_passing_outcomes(synchronized):
    """Enumerate a publication litmus under stated happens-before premises.

    Writer stores payload before flag. Reader loads flag before payload. When
    ``synchronized`` is true, observing flag=1 creates a synchronizes-with edge
    and therefore forbids a subsequent payload read of the initial value.
    Without that edge, all independent read values are admitted in this toy
    model. Data races and weak memory rules are intentionally out of scope.
    """
    outcomes = set()
    for flag in (0, 1):
        for payload in (0, 1):
            if synchronized and flag == 1 and payload == 0:
                continue
            outcomes.add((flag, payload))
    return outcomes


def atomic_counter_outcomes(initial, increments_per_task, task_count):
    """Enumerate all serializations of atomic fetch_adds on one counter."""
    if initial < 0 or increments_per_task < 0 or task_count < 0:
        raise ValueError("counter fixture expects non-negative integers")
    # Each operation is one indivisible RMW in the per-object modification order.
    total = initial
    for _ in range(increments_per_task * task_count):
        total += 1
    return {total}


def naive_load_then_store_outcomes(initial, increments_per_task, task_count):
    """Enumerate schedules of non-atomic load/add/store increments.

    A scheduler step runs one task's load, compute, or store. This finite
    interleaving model exposes lost updates; it makes no memory-model claim.
    """
    if initial < 0 or increments_per_task < 0 or task_count < 0:
        raise ValueError("counter fixture expects non-negative integers")
    states = {(initial, (0,) * task_count, (None,) * task_count)}
    outcomes = set()
    while states:
        next_states = set()
        for shared, pcs, locals_ in states:
            if all(pc == increments_per_task * 3 for pc in pcs):
                outcomes.add(shared)
                continue
            for i, pc in enumerate(pcs):
                if pc == increments_per_task * 3:
                    continue
                step = pc % 3
                new_pcs = list(pcs)
                new_locals = list(locals_)
                new_shared = shared
                if step == 0:
                    new_locals[i] = shared
                elif step == 1:
                    new_locals[i] += 1
                else:
                    new_shared = new_locals[i]
                new_pcs[i] += 1
                next_states.add((new_shared, tuple(new_pcs), tuple(new_locals)))
        states = next_states
    return outcomes


def same_location_atomic_reads(initial, stores, load_count):
    """Enumerate per-location monotone atomic-read outcomes for a reader.

    A reader performs ``load_count`` loads sequenced in program order. Writes
    have one modification order beginning with the initial value. The reader
    may start at any point and may advance or remain at its observed write;
    this witnesses read-read coherence only, not cross-location ordering.
    """
    if load_count < 0:
        raise ValueError("load_count must be non-negative")
    values = (initial, *stores)
    if load_count == 0:
        return {()}
    states = {(index,) for index in range(len(values))}
    for _ in range(1, load_count):
        states = {
            (*prefix, next_index)
            for prefix in states
            for next_index in range(prefix[-1], len(values))
        }
    return {tuple(values[index] for index in indices) for indices in states}


def independent_atomic_reads(initial, stores, load_count):
    """Permissive comparison without a per-location coherence constraint."""
    values = (initial, *stores)
    outcomes = {()}
    for _ in range(load_count):
        outcomes = {(*prefix, value) for prefix in outcomes for value in values}
    return outcomes


def release_relay_payload_outcomes(acquire_reads_release_sequence):
    """Model one explicit C++20 release-sequence/read-from premise.

    The payload itself is atomic and relaxed. If the acquire load of `flag`
    reads an RMW member of the release sequence headed by the release store,
    the release synchronizes with the acquire, so the payload read cannot see
    its older initial write. If it reads a later relaxed plain store that
    breaks the sequence, this fixture adds no synchronization edge.

    This maps a supplied source relation to outcomes; it does not infer the
    modification order or release sequence from executable atomic events.
    """
    return {1} if acquire_reads_release_sequence else {0, 1}
