#!/usr/bin/env python3
"""Replay query lower-bound witnesses, FIFO histories, and explicit live-entry costs."""

from collections import Counter, deque
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
THEOREMS = (
    "unread_determines_failure", "lower_reads", "scan_correct", "scan_reads",
    "step_charge", "history_charge", "live_during_move", "copy_peak_exceeds",
)


def probes(values):
    for index, bit in enumerate(values):
        if bit:
            return True, index + 1
    return False, len(values)


def query_cases(max_size):
    totals = Counter()
    for n in range(max_size + 1):
        zero = (False,) * n
        assert probes(zero) == (False, n)
        for values in product((False, True), repeat=n):
            answer, reads = probes(values)
            assert answer == any(values)
            assert reads == (values.index(True) + 1 if answer else n)
            totals["scan_inputs"] += 1
        for choices in product((False, True), repeat=n):
            read = [i for i, used in enumerate(choices) if used]
            totals["candidate_query_sets"] += 1
            for ignored, used in enumerate(choices):
                if not used:
                    spike = tuple(i == ignored for i in range(n))
                    assert [spike[i] for i in read] == [zero[i] for i in read]
                    assert probes(spike)[0] and not probes(zero)[0]
                    totals["indistinguishable_pairs"] += 1
    return dict(totals)


class Queue:
    def __init__(self, incoming=()):
        self.incoming = list(incoming)
        self.outgoing = []

    def live(self):
        return len(self.incoming) + len(self.outgoing)

    def potential(self):
        return 2 * len(self.incoming)

    def ordered(self):
        return list(reversed(self.outgoing)) + self.incoming

    def push(self, value):
        self.incoming.append(value)
        return 1, self.live()

    def pop(self):
        peak = self.live()
        cost = 1
        if not self.outgoing:
            while self.incoming:
                temporary = self.incoming.pop()
                assert self.live() + 1 == peak
                self.outgoing.append(temporary)
                assert self.live() == peak
                cost += 2
        return self.outgoing.pop(), cost, peak


def histories(maximum):
    def extend(prefix, live):
        yield prefix
        if len(prefix) == maximum:
            return
        yield from extend(prefix + (True,), live + 1)
        if live:
            yield from extend(prefix + (False,), live - 1)
    return extend((), 0)


def replay_queues(maximum):
    corpus = Counter()
    for ops in histories(maximum):
        checked = Queue()
        independent = deque()
        cumulative = 0
        peak = 0
        assert checked.potential() == 0
        for index, push in enumerate(ops):
            last_potential = checked.potential()
            previous_size = len(independent)
            if push:
                value = (-1) ** index * (index + 5)
                independent.append(value)
                cost, step_peak = checked.push(value)
            else:
                expected = independent.popleft()
                actual, cost, step_peak = checked.pop()
                assert actual == expected
            assert checked.ordered() == list(independent)
            assert step_peak == max(previous_size, len(independent))
            assert cost + checked.potential() <= 3 + last_potential
            cumulative += cost
            assert cumulative + checked.potential() <= 3 * (index + 1)
            peak = max(peak, step_peak)
            corpus["max_step_cost"] = max(corpus["max_step_cost"], cost)
            corpus["primitive_cost_over_three"] += cost > 3
            corpus["checked_prefix_occurrences"] += 1
        assert peak <= maximum
        corpus["histories"] += 1

    controls = []
    for n in range(1, maximum + 1):
        warm = Queue(range(n))
        initial_potential = warm.potential()
        first, cost, peak = warm.pop()
        assert first == 0 and peak == n
        assert cost == 1 + initial_potential and cost + warm.potential() <= 3 + initial_potential
        # Copy-stack construction retains the entire old list until the mirror is ready.
        old = list(range(n))
        mirror = []
        copy_peak = len(old)
        for value in reversed(old):
            mirror.append(value)
            copy_peak = max(copy_peak, len(old) + len(mirror))
        assert copy_peak == 2 * n
        assert mirror.pop() == first and list(reversed(mirror)) == warm.ordered()
        controls.append({"initial_entries": n, "initial_potential": initial_potential,
                         "single_pop_cost": cost, "move_peak": peak, "copy_peak": copy_peak})
    assert corpus["max_step_cost"] == 2 * (maximum - 1) + 1
    return dict(corpus), controls


def check_lean():
    lean = os.environ.get("LEAN", "lean")
    reply = subprocess.run(
        [lean, "-DwarningAsError=true", "Bounds.lean"], cwd=HERE,
        capture_output=True, text=True, check=True,
    )
    assert not reply.stderr
    axioms = {}
    for line in reply.stdout.splitlines():
        name, printed = re.fullmatch(r"'([^']+)' depends on axioms: \[([^\]]+)\]", line).groups()
        axioms[name] = printed.split(", ")
    assert tuple(axioms) == THEOREMS
    assert all(set(allowed) <= {"propext", "Classical.choice", "Quot.sound"} for allowed in axioms.values())
    return axioms


if __name__ == "__main__":
    axioms = check_lean()
    histories_summary, warm_start = replay_queues(12)
    evidence = {
        "format": "read-lower-and-queue-01",
        "query_cases": query_cases(12), "fifo_histories": histories_summary,
        "warm_start": warm_start, "proof_axioms": axioms,
        "proof_source": sha256((HERE / "Bounds.lean").read_bytes()).hexdigest(),
    }
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
