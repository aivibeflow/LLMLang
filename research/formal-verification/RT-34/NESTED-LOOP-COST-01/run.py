#!/usr/bin/env python3
"""Compare formal nested-loop cost profiles with native instrumented observations."""

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SIZES = (*range(65), 128, 256)
PROFILES = {"unit": (1, 1, 1), "effect_weighted": (2, 5, 3)}
FIELDS = ("body_entry", "guarded_effect", "extra_effect")
LEAN_COMMIT = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"


@dataclass(frozen=True)
class Program:
    bound: str
    extra: bool

    def __post_init__(self):
        if self.bound not in {"outer_index", "size"} or type(self.extra) is not bool:
            raise ValueError("Unsupported inner bound or extra effect")

    @property
    def name(self):
        return f"{self.bound}_{'extra' if self.extra else 'base'}"


def row_counts(program, n):
    """Mathematical oracle derived from completed rows, independently of native loops."""
    triangular = n * (n - 1) // 2
    if program.bound == "outer_index":
        visits = triangular
        guard_hits = 0
    else:
        visits = n * n
        guard_hits = n * (n + 1) // 2
    return visits, guard_hits, visits if program.extra else 0


def native_source(programs):
    declarations = ["#include <inttypes.h>", "#include <stdint.h>", "#include <stdio.h>",
                    "struct counts { uint64_t body_entry, guarded, extra; };"]
    for program in programs:
        bound = "i" if program.bound == "outer_index" else "size"
        extra = "            result->extra += 1;\n" if program.extra else ""
        declarations.append(f"""\
static uint64_t {program.name}(uint64_t size, struct counts *result)
{{
    for (uint64_t i = 0; i < size; ++i) {{
        for (uint64_t j = 0; j < {bound}; ++j) {{
            result->body_entry += 1;
            if (j >= i) {{
                result->guarded += 1;
            }}
{extra}        }}
    }}
    return size;
}}
""")
    queries = []
    for program in programs:
        queries.append(f"""\
    for (size_t index = 0; index < sizeof(sizes) / sizeof(sizes[0]); ++index) {{
        struct counts counts = {{0}};
        uint64_t size = sizes[index];
        uint64_t value = {program.name}(size, &counts);
        printf("{program.name} %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\\n",
               size, value, counts.body_entry, counts.guarded, counts.extra);
    }}
""")
    sizes = ", ".join(map(str, SIZES))
    declarations.append(f"int main(void)\n{{\n    const uint64_t sizes[] = {{{sizes}}};\n"
                        + "".join(queries) + "    return 0;\n}\n")
    return "\n".join(declarations)


def lean_source(programs):
    kinds = {"outer_index": "outerIndex", "size": "size"}
    cases = ", ".join(f'("{program.name}", .{kinds[program.bound]}, {str(program.extra).lower()})'
                      for program in programs)
    samples = ", ".join(map(str, SIZES))
    return f"""\
import Cost
open LoopCost

def cases : List (String × InnerBound × Bool) := [{cases}]
def sizes : List Nat := [{samples}]

def main : IO Unit := do
  for (name, kind, extra) in cases do
    for n in sizes do
      let visits := hits kind n
      let guard := guarded kind n
      let added := if extra then visits else 0
      IO.println s!"{{name}} {{n}} {{n}} {{visits}} {{guard}} {{added}}"
"""


def call(argv, cwd=None, *, env=None):
    done = subprocess.run(argv, cwd=cwd, env=env, check=False, text=True,
                          capture_output=True, timeout=60)
    if done.returncode or done.stderr:
        raise RuntimeError(done.stdout + done.stderr)
    return done.stdout


def parse_rows(output):
    return [(name, *map(int, fields)) for name, *fields in map(str.split, output.splitlines())]


def digest(text):
    return sha256(text.encode()).hexdigest()


def weighted(counts, weights):
    return sum(count * weight for count, weight in zip(counts, weights, strict=True))


def replay(compiler, lean):
    cc_version = call([compiler, "--version"]).splitlines()[0]
    lean_version = call([lean, "--version"]).strip()
    if LEAN_COMMIT not in lean_version:
        raise ValueError("Expected pinned Lean 4.36.0")

    programs = [Program(bound, extra) for bound, extra in product(("outer_index", "size"), (False, True))]
    reference = [(program.name, n, n, *row_counts(program, n)) for program in programs for n in SIZES]
    implemented_c = native_source(programs)
    implemented_lean = lean_source(programs)
    levels = ("0", "3")

    with TemporaryDirectory(prefix="llmlang-nested-loop-cost-") as temporary:
        root = Path(temporary)
        (root / "fixture.c").write_text(implemented_c, encoding="utf-8")
        for level in levels:
            call([compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{level}",
                  "fixture.c", "-o", "fixture"], root)
            assert parse_rows(call(["./fixture"], root)) == reference

        shutil.copy(HERE / "Cost.lean", root / "Cost.lean")
        (root / "RunCost.lean").write_text(implemented_lean, encoding="utf-8")
        env = {**os.environ, "LEAN_PATH": str(root)}
        flags = [lean, "-DwarningAsError=true"]
        axioms_report = call([*flags, "-o", "Cost.olean", "Cost.lean"], root, env=env)
        assert parse_rows(call([*flags, "--run", "RunCost.lean"], root, env=env)) == reference

    axioms = {}
    pattern = re.compile(r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[(.*)\])$")
    for line in axioms_report.splitlines():
        proof = pattern.fullmatch(line)
        if proof is None:
            raise ValueError(f"Unexpected kernel output {line!r}")
        name, dependencies = proof.groups()
        axioms[name] = dependencies.split(", ") if dependencies else []
    assert len(axioms) == 9
    assert all(set(values) <= {"propext", "Quot.sound"} for values in axioms.values())

    observations = []
    profiles = {profile: {"rectangular_loose": 0, "dependent_loose": 0,
                          "unsound_unguarded": 0, "more_work_same_result": 0}
                for profile in PROFILES}
    for program in programs:
        for n in SIZES:
            counts = row_counts(program, n)
            values = {}
            for profile, weights in PROFILES.items():
                visited = counts[0]
                extra_charge = weights[2] if program.extra else 0
                envelope = weights[0] + weights[1] + extra_charge
                rectangular = n * n * envelope
                dependent = visited * envelope
                exact = weighted(counts, weights)
                omit_guard = visited * (weights[0] + extra_charge)
                assert exact <= dependent <= rectangular
                profiles[profile]["rectangular_loose"] += rectangular > exact
                profiles[profile]["dependent_loose"] += dependent > exact
                profiles[profile]["unsound_unguarded"] += omit_guard < exact
                profiles[profile]["more_work_same_result"] += program.extra and visited > 0
                values[profile] = {"rectangular": rectangular, "dependent": dependent,
                                   "exact": exact, "omit_guard": omit_guard}
            observations.append({"program": program.name, "size": n, "result": n, "events": counts,
                                 "costs": values})

    try:
        Program("external_unknown", False)
    except ValueError:
        unknown = "UNKNOWN"
    else:
        raise AssertionError("The candidate accepted a foreign bound without a cost contract")

    return {
        "schema": "llmlang-nested-loop-cost/1", "compiler": cc_version, "lean": lean_version,
        "python": platform.python_version(), "c_levels": levels,
        "generator_sha256": digest(Path(__file__).read_text(encoding="utf-8")),
        "proof_sha256": digest((HERE / "Cost.lean").read_text(encoding="utf-8")),
        "generated_c_sha256": digest(implemented_c),
        "generated_lean_sha256": digest(implemented_lean),
        "abstract_event_fields": FIELDS, "weights": PROFILES,
        "programs": {program.name: asdict(program) for program in programs},
        "native_c_observations": len(reference) * len(levels),
        "lean_observations": len(reference), "theorems": axioms,
        "unknown_external_bound": unknown, "candidate_results": profiles,
        "observations": observations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args()
    record = replay(args.cc, args.lean)
    observations = record.pop("observations")
    print(json.dumps(record, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")


if __name__ == "__main__":
    main()
