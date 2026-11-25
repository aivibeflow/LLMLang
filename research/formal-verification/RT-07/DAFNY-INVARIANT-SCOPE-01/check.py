"""Compare two contract renderings and exact verification receipts for an affine loop."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import platform
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class Loop:
    post: int
    step: int
    invariant: int | None


BASE = "97c373cf8c67156e13a03161787b3d7153f3908c"
DAFNY = re.compile(
    r"method (?:Acc|VerifyAcc)\(n: int, seed: int\) returns \(sum: int\)\n"
    r"  requires 0 <= n\n  ensures sum == seed \+ (\d+) \* n\n"
    r"\{\n  var i := 0;\n  sum := seed;\n  while i < n\n"
    r"    invariant 0 <= i <= n\n(?:    invariant sum == seed \+ (\d+) \* i\n)?"
    r"    decreases n - i\n  \{\n    sum := sum \+ (\d+);\n    i := i \+ 1;\n  \}\n\}\n"
)
CANDIDATE = re.compile(
    r"contract accumulate\(n: Int, seed: Int\) -> Int\n"
    r"  input n >= 0\n  output seed \+ (\d+) \* n\n"
    r"  effects none\n  failure none on admitted inputs\n  terminates by n - index\n"
    r"  loop index in 0\.\.n, step (\d+)\n(?:  invariant sum = seed \+ (\d+) \* index\n)?"
)


def dafny_text(loop, member="Acc"):
    logical = "" if loop.invariant is None else f"    invariant sum == seed + {loop.invariant} * i\n"
    return (
        f"method {member}(n: int, seed: int) returns (sum: int)\n"
        f"  requires 0 <= n\n  ensures sum == seed + {loop.post} * n\n"
        "{\n  var i := 0;\n  sum := seed;\n  while i < n\n"
        f"    invariant 0 <= i <= n\n{logical}    decreases n - i\n"
        f"  {{\n    sum := sum + {loop.step};\n    i := i + 1;\n  }}\n}}\n"
    )


def candidate_text(loop):
    invariant = "" if loop.invariant is None else f"  invariant sum = seed + {loop.invariant} * index\n"
    return (
        "contract accumulate(n: Int, seed: Int) -> Int\n"
        f"  input n >= 0\n  output seed + {loop.post} * n\n"
        "  effects none\n  failure none on admitted inputs\n  terminates by n - index\n"
        f"  loop index in 0..n, step {loop.step}\n{invariant}"
    )


def parse(source, profile):
    pattern = DAFNY if profile == "dafny" else CANDIDATE
    match = pattern.fullmatch(source)
    if not match:
        raise ValueError("outside the corresponded subset")
    post, first, second = match.groups()
    step, invariant = (second, first) if profile == "dafny" else (first, second)
    return Loop(int(post), int(step), int(invariant) if invariant is not None else None)


def replay(loop):
    rows = []
    for n in range(9):
        for seed in (-3, 0, 7):
            sum_state = seed
            for i in range(n):
                sum_state += loop.step
                rows.append((i + 1, sum_state - seed))
            assert sum_state == seed + n * loop.step
    slopes = {delta // index for index, delta in rows if delta % index == 0}
    assert len(slopes) == 1 and all(delta == index * next(iter(slopes)) for index, delta in rows)
    return next(iter(slopes)), len(rows)


def version(path, option):
    return subprocess.check_output([path, option], text=True).splitlines()[0]


def identity(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify(dafny, solver, source, limit, directory):
    entry = directory / "Loop.dfy"
    entry.write_text(source)
    command = [dafny, "verify", "--cores", "1", "--verification-time-limit", "20",
               "--solver-path", solver, "--resource-limit", str(limit), entry]
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    output = result.stdout + result.stderr
    lower = output.lower()
    if result.returncode == 0:
        assert "verified, 0 errors" in lower
        return "verified"
    if "out of resource" in lower or "resource limit" in lower:
        return "unknown-resource"
    if "postcondition" in lower:
        return "postcondition-failure"
    if "invariant" in lower:
        return "invariant-failure"
    raise AssertionError((result.returncode, output))


def run(dafny, solvers):
    regular, state_rows = replay(Loop(1, 1, None))
    changed, _ = replay(Loop(2, 2, None))
    assert (regular, changed) == (1, 2)
    scenarios = {
        "exact": (Loop(1, 1, regular), "Acc", 1000000, "verified"),
        "renamed-entry": (Loop(1, 1, regular), "VerifyAcc", 1000000, "verified"),
        "missing-invariant": (Loop(1, 1, None), "Acc", 1000000, "postcondition-failure"),
        "body-edit": (Loop(1, 2, regular), "Acc", 1000000, "invariant-failure"),
        "spec-edit": (Loop(2, 1, regular), "Acc", 1000000, "postcondition-failure"),
        "recovered": (Loop(2, 2, changed), "Acc", 1000000, "verified"),
        "work-exhaustion": (Loop(1, 1, regular), "Acc", 1, "unknown-resource"),
    }
    dafny_version = version(dafny, "--version")
    tool_root = Path(dafny).resolve().parent
    verifier = {
        component.name: sha256(component.read_bytes()).hexdigest()
        for component in (Path(dafny), tool_root / "DafnyCore.dll", tool_root / "Boogie.ExecutionEngine.dll",
                          tool_root / "Boogie.Provers.SMTLib.dll")
    }
    solver_info = {str(solver): [version(solver, "--version"), sha256(Path(solver).read_bytes()).hexdigest()]
                   for solver in solvers}
    output = {}
    repeat = {}
    for solver in solvers:
        scopes = {}
        exact_cache = {}
        invoked = 0
        with TemporaryDirectory() as path:
            directory = Path(path)
            for name in (*scenarios, "repeat"):
                loop, member, limit, expected = scenarios["exact" if name == "repeat" else name]
                d_source, candidate = dafny_text(loop, member), candidate_text(loop)
                assert parse(d_source, "dafny") == parse(candidate, "candidate") == loop
                typed = identity(["affine-proof-graph/1", "int", "pure", "failure-free", asdict(loop)])
                source = sha256(d_source.encode()).hexdigest()
                key = identity([typed, source, dafny_version, verifier, solver_info[str(solver)], limit,
                                "one-core", "host-limit-30s", "verification-limit-20s"])
                if name == "repeat":
                    repeat[solver_info[str(solver)][0]] = exact_cache[key]
                    continue
                assert key not in exact_cache
                actual = verify(dafny, solver, d_source, limit, directory)
                invoked += 1
                assert actual == expected, (name, solver, expected, actual)
                if actual == "verified":
                    exact_cache[key] = actual
                scopes[name] = {"typed": typed, "dafny_source": source,
                                "candidate_source": sha256(candidate.encode()).hexdigest(), "key": key,
                                "disposition": actual}
        assert scopes["renamed-entry"]["typed"] == scopes["exact"]["typed"]
        assert len({row["key"] for row in scopes.values()}) == len(scopes)
        assert invoked == len(scenarios)
        output[solver_info[str(solver)][0]] = scopes
    statuses = Counter(row["disposition"] for scopes in output.values() for row in scopes.values())
    return {
        "baseline": BASE, "dafny": dafny_version, "verifier_component_sha256": verifier,
        "python": platform.python_version(), "solvers": sorted(solver_info.values()),
        "candidate_runtime": "integer-affine-loop/1", "calibration_states_per_body": state_rows,
        "results": output, "status_totals": dict(statuses), "exact_repeat_hits": repeat,
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dafny", required=True)
    parser.add_argument("--solver", required=True, action="append")
    args = parser.parse_args()
    print(json.dumps(run(args.dafny, args.solver), indent=2, sort_keys=True))
