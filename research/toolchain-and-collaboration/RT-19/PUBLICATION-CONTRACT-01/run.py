#!/usr/bin/env python3
"""Cross-check the proposed publication contract in TLC and a Python enumerator."""
import argparse
from collections import deque
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
TARGETS = ("alpha", "beta")
VALUES = ("old", "new", "other")
RIGHTS = frozenset(("observe", "append", "seal"))
ENV = {**os.environ, "LC_ALL": "C", "TZ": "UTC"}


def powerset(values):
    values = tuple(sorted(values))
    return tuple(frozenset(items) for size in range(len(values) + 1)
                 for items in combinations(values, size))


RIGHT_SETS = powerset(RIGHTS)
TARGET_SETS = powerset(TARGETS)


@dataclass(frozen=True)
class State:
    live: tuple[str, str] = ("old", "old")
    witnessed: frozenset[str] = frozenset()
    seen: frozenset[str] = frozenset()
    online: frozenset[str] = frozenset(TARGETS)
    rights: frozenset[str] = RIGHTS
    journal: str = "absent"
    released: bool = False
    violations: frozenset[str] = frozenset()

    def value_at(self, target, value):
        data = list(self.live)
        data[TARGETS.index(target)] = value
        return tuple(data)

    def as_json(self):
        return {"live": dict(zip(TARGETS, self.live)), "journal": self.journal, "released": self.released,
                **{key: sorted(getattr(self, key))
                   for key in ("witnessed", "seen", "online", "rights", "violations")}}


def interpret(raw):
    return State(tuple(raw["live"][target] for target in TARGETS),
                 **{key: frozenset(raw[key]) for key in ("witnessed", "seen", "online", "rights", "violations")},
                 journal=raw["journal"], released=raw["released"])


def successors(state, mode):
    observe = "observe" in state.rights
    append = "append" in state.rights
    seal = "seal" in state.rights
    if state.journal == "absent" and observe and append:
        yield "prepare", replace(state, journal="pending")
    if state.journal == "pending" and observe and not state.released:
        for target, value in zip(TARGETS, state.live):
            if target not in state.online:
                continue
            if (target not in state.witnessed and (append or mode == "UnfencedAppend")
                    and (value == "old" or mode == "OverwriteDiverged")):
                flags = state.violations
                if not append:
                    flags = flags | {"append-without-authority"}
                if value != "old":
                    flags = flags | {"overwrote-divergence"}
                yield f"append/{target}", replace(state, live=state.value_at(target, "new"),
                                                  witnessed=state.witnessed | {target}, violations=flags)
            if value == "new" and (target in state.witnessed or mode == "RawTipOnly"):
                yield f"probe/{target}", replace(state, seen=state.seen | {target})
        if state.seen == frozenset(TARGETS) and (seal or mode == "UnfencedSeal"):
            flags = state.violations if seal else state.violations | {"seal-without-authority"}
            yield "seal", replace(state, released=True, violations=flags)
    if state.journal == "pending" and observe and (state.released or mode == "SpeculativeSettle"):
        yield "settle", replace(state, journal="settled")
    for target in TARGETS:
        for value in VALUES:
            yield f"outside/{target}/{value}", replace(state, live=state.value_at(target, value))
    for rights in RIGHT_SETS:
        yield "change-rights", replace(state, rights=rights)
    for online in TARGET_SETS:
        yield "change-availability", replace(state, online=online)
    yield "crash", replace(state, seen=frozenset())


INVARIANTS = {
    "AuthorizedAndCompared": lambda state: not state.violations,
    "ObservedWitnesses": lambda state: state.seen <= state.witnessed,
    "ReleaseHasWitnesses": lambda state: not state.released or state.witnessed == frozenset(TARGETS),
    "SettleHasRelease": lambda state: state.journal != "settled" or state.released,
    "NeverSettled": lambda state: state.journal != "settled",
    "ReleasedPairIsCurrent": lambda state: not state.released or state.live == ("new", "new"),
}


def enumerate_model(mode, names):
    checks = [INVARIANTS[name] for name in names if name != "TypeOK"]
    initial = State()
    frontier = deque([initial])
    depths = {initial: 0}
    counts = 1
    while frontier:
        state = frontier.popleft()
        if not all(check(state) for check in checks):
            return {"violation_depth": depths[state]}
        for _, candidate in successors(state, mode):
            counts += 1
            if candidate not in depths:
                depths[candidate] = depths[state] + 1
                frontier.append(candidate)
    return {"generated_states": counts, "distinct_states": len(depths),
            "search_depth": 1 + max(depths.values())}


def run_tlc(jar, directory, mode, invariants):
    directory.mkdir()
    (directory / "Publication.tla").write_bytes((HERE / "Publication.tla").read_bytes())
    configuration = (f'CONSTANT Mode = "{mode}"\nINIT Init\nNEXT Next\n'
                     f'INVARIANTS {" ".join(invariants)}\nCHECK_DEADLOCK FALSE\n')
    (directory / "Publication.cfg").write_text(configuration)
    tool = ["java", "-Xmx512m", "-XX:+UseParallelGC", "-cp", jar, "tlc2.TLC", "-workers", "1",
            "-fp", "0", "-seed", "811", "-checkpoint", "0", "-dumpTrace", "json", "trace.json",
            "-config", "Publication.cfg", "Publication.tla"]
    completed = subprocess.run(tool, cwd=directory, env=ENV, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=40)
    output = completed.stdout
    assert "Version 2026.11.19.180144 (rev: bc1b506)" in output
    independent = enumerate_model(mode, invariants)
    if completed.returncode == 0:
        assert "Model checking completed. No error has been found." in output
        [counts] = re.findall(r"(\d+) states generated, (\d+) distinct states found, 0 states left on queue", output)
        [depth] = re.findall(r"depth of the complete state graph search is (\d+)", output)
        tc = dict(zip(("generated_states", "distinct_states", "search_depth"),
                      [*map(int, counts), int(depth)]))
        assert tc == independent, (tc, independent)
        return {"invariants": list(invariants), "tlc_exit": completed.returncode, **tc}
    assert len(invariants) == 1 and f"Invariant {invariants[0]} is violated." in output, output
    document = json.loads((directory / "trace.json").read_text())
    raw_states = document["counterexample"]["state"]
    states = [interpret(state) for index, state in raw_states]
    assert [index for index, state in raw_states] == list(range(1, len(states) + 1))
    assert states[0] == State()
    labels = []
    for left, right in zip(states, states[1:]):
        possible = {label for label, after in successors(left, mode) if right == after}
        assert possible
        labels.append(sorted(possible))
    tested = INVARIANTS[invariants[0]]
    assert all(tested(state) for state in states[:-1]) and not tested(states[-1])
    assert independent["violation_depth"] == len(states) - 1
    return {"violated": invariants[0], "tlc_exit": completed.returncode, **independent,
            "validated_steps": labels, "states": [state.as_json() for state in states]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tlc", type=lambda value: Path(value).resolve(), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = sha256(args.tlc.read_bytes()).hexdigest()
    assert artifact == "fdffef247f563ef6edbfd44958d2a82db79e7564e07cb673262d896353fa6713"
    variants = [
        ("candidate", "Correct", ("TypeOK", "AuthorizedAndCompared", "ObservedWitnesses",
                                  "ReleaseHasWitnesses", "SettleHasRelease")),
        ("tip-only", "RawTipOnly", ("ReleaseHasWitnesses",)),
        ("append-right-race", "UnfencedAppend", ("AuthorizedAndCompared",)),
        ("seal-right-race", "UnfencedSeal", ("AuthorizedAndCompared",)),
        ("blind-overwrite", "OverwriteDiverged", ("AuthorizedAndCompared",)),
        ("speculative-settle", "SpeculativeSettle", ("SettleHasRelease",)),
        ("settlement-reachable", "Correct", ("NeverSettled",)),
        ("snapshot-is-current", "Correct", ("ReleasedPairIsCurrent",)),
    ]
    with tempfile.TemporaryDirectory(prefix="rt19-publication-contract-") as scratch:
        root = Path(scratch)
        outcomes = {label: run_tlc(args.tlc, root / label, mode, inv)
                    for label, mode, inv in variants}
    record = {"jar_sha256": artifact, "model_sha256": sha256((HERE / "Publication.tla").read_bytes()).hexdigest(),
              "outcomes": outcomes}
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
