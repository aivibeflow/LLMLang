#!/usr/bin/env python3
"""Exhaust finite recovery contracts with ordered traces and universal handoff."""

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
CODES = ("retry", "fatal")


@dataclass(frozen=True)
class Observation:
    outcome: str
    state: int | None
    trace: tuple[str, ...]
    code: str | None = None


def primary_cases(initial):
    return (
        *(Observation("done", state, (f"primary-{initial}:done-{state}",)) for state in (0, 1)),
        *(Observation("error", state, (f"primary-{initial}:{code}-{state}",), code)
          for code, state in product(CODES, (0, 1))),
        *(Observation("cancelled", state, (f"primary-{initial}:cancelled-{state}",)) for state in (0, 1)),
        Observation("diverged", None, (f"primary-{initial}:diverged",)),
    )


def handler(code, state, wide):
    result = Observation("done", state, (f"handler:{code}-{state}:done",))
    if not wide:
        return (result,)
    stop = (Observation("diverged", None, (f"handler:{code}-{state}:diverged",)) if state == 0
            else Observation("error", 0, (f"handler:{code}-{state}:error",), "fatal"))
    return result, stop


def invoked(outcome, selection):
    return outcome.outcome == "error" and outcome.code in selection


def compose(primary, initial, selection, wide, mode="exact"):
    result = set()
    for outcome in primary:
        code = outcome.code
        if invoked(outcome, selection):
            state = initial if mode == "rollback_state" else outcome.state
        elif mode == "cancel_is_retry" and outcome.outcome == "cancelled" and "retry" in selection:
            code = "retry"
            state = outcome.state
        else:
            result.add(outcome)
            continue
        trace = () if mode == "erase_prefix" else outcome.trace
        for observation in handler(code, state, wide):
            result.add(Observation(observation.outcome, observation.state,
                                   trace + observation.trace, observation.code))
    return result


def relation_rows(atoms, enabled_errors):
    rows = []
    for index, observation in enumerate(atoms):
        if 2 <= index <= 5 and (enabled_errors & (1 << (index - 2))):
            code_index, state = divmod(index - 2, 2)
            prefix = f"handler:{CODES[code_index]}-{state}:"
            done = Observation("done", state, (*observation.trace, prefix + "done"))
            alternative = (Observation("error", 0, (*observation.trace, prefix + "error"), "fatal")
                           if state else Observation("diverged", None, (*observation.trace, prefix + "diverged")))
            rows.append({done, alternative})
        else:
            rows.append({observation})
    return rows


def observation_key(observation):
    return json.dumps(asdict(observation), sort_keys=True, separators=(",", ":"))


def summarize():
    counts = Counter()
    mutants = ("rollback_state", "cancel_is_retry", "erase_prefix")
    disagreements = Counter()
    witnesses = {}
    rows = sha256()
    for initial in (0, 1):
        atoms = primary_cases(initial)
        total = 1 << len(atoms)
        sets = [tuple(atoms[i] for i in range(len(atoms)) if mask & (1 << i)) for mask in range(total)]
        for catch_bits in range(4):
            selection = {code for i, code in enumerate(CODES) if catch_bits & (1 << i)}
            exact = [compose(primary, initial, selection, True) for primary in sets]
            narrow = [compose(primary, initial, selection, False) for primary in sets]
            # Errors occupy bits 2 through 5 in retry/state then fatal/state order.
            error_selection = (3 if "retry" in selection else 0) | (12 if "fatal" in selection else 0)
            relation = relation_rows(atoms, error_selection)
            for mask, primary in enumerate(sets):
                direct = set().union(*(row for index, row in enumerate(relation) if mask & (1 << index)))
                if exact[mask] != direct:
                    raise AssertionError((initial, catch_bits, mask, exact[mask], direct))
                callees = {(observation.code, observation.state)
                           for observation in primary if invoked(observation, selection)}
                actual_callees = sum(1 << (2 * CODES.index(code) + state) for code, state in callees)
                expected_callees = ((mask >> 2) & 15) & error_selection
                if actual_callees != expected_callees:
                    raise AssertionError((initial, catch_bits, mask))
                for allowance in range(16):
                    good = {(code, state) for index, (code, state) in enumerate(product(CODES, (0, 1)))
                            if allowance & (1 << index)}
                    universal = callees <= good
                    if universal != ((expected_callees & ~allowance) == 0):
                        raise AssertionError((mask, catch_bits, allowance))
                    exists = not callees or bool(callees & good)
                    counts["admission_profiles"] += 1
                    counts["exists_false_admission"] += exists and not universal
                    if exists and not universal:
                        witnesses.setdefault("existential_handoff", {
                            "initial": initial, "handlers": sorted(selection), "primary_mask": mask,
                            "allowed_inputs": sorted(good), "actual_handler_inputs": sorted(callees),
                        })

                counts["composition_profiles"] += 1
                for mode in mutants:
                    changed = compose(primary, initial, selection, True, mode=mode)
                    if changed != exact[mask]:
                        disagreements[mode] += 1
                        witnesses.setdefault(mode, {
                            "initial": initial, "handlers": sorted(selection), "primary_mask": mask,
                            "exact_only": min(map(observation_key, exact[mask] - changed), default=None),
                            "mutation_only": min(map(observation_key, changed - exact[mask]), default=None),
                        })
                    counts["mutation_comparisons"] += 1
                row = (initial, catch_bits, mask, sorted(map(observation_key, exact[mask])))
                rows.update(json.dumps(row, separators=(",", ":")).encode("ascii") + b"\n")

                smaller = mask
                while True:
                    if not narrow[smaller] <= exact[mask]:
                        raise AssertionError((initial, catch_bits, smaller, mask))
                    counts["refinement_comparisons"] += 1
                    if smaller == 0:
                        break
                    smaller = (smaller - 1) & mask
    if set(disagreements) != set(mutants) or not counts["exists_false_admission"]:
        raise AssertionError("A configured invalid alternative has no distinguishing context")
    return {
        "schema": "llmlang-recovery-contracts/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("Recovery.lean", "axioms.txt", "run.py")},
        "primary_atoms_per_initial_state": len(primary_cases(0)),
        "counts": counts, "disagreements": disagreements, "witnesses": witnesses,
        "composition_rows_sha256": rows.hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
