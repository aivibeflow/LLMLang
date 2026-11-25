#!/usr/bin/env python3
"""Compare actual exclusive scoped Rust writes with an independent interval oracle."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NEGATIVE = {
    "aliased": (
        """fn main() {
            let mut data = [0u8; 8];
            let first = &mut data[0..4];
            let second = &mut data[2..6];
            std::thread::scope(|s| {
                s.spawn(move || first[0] += 1);
                s.spawn(move || second[0] += 2);
            });
        }""",
        "E0499",
    ),
    "detached-borrow": (
        """fn main() {
            let mut data = [0u8; 8];
            let region = &mut data[0..4];
            std::thread::spawn(move || region[0] += 1);
        }""",
        "E0597",
    ),
    "owner-outlived": (
        """fn invalid<'a>() -> &'a mut [u8] {
            let mut owned = [0u8; 4];
            &mut owned[..]
        }
        fn main() {}""",
        "E0515",
    ),
    "non-send": (
        """fn main() {
            let owner = std::rc::Rc::new(12);
            std::thread::scope(|scope| {
                scope.spawn(move || assert_eq!(*owner, 12));
            });
        }""",
        "E0277",
    ),
}


def oracle(inputs):
    owners = list(range(7))
    paths = []
    for start, size in (inputs[:2], inputs[2:]):
        end = start + size
        if end >= 2**64:
            return ("overflow", owners)
        if end > len(owners):
            return ("out-of-bounds", owners)
        paths.append(set(range(start, end)))
    if paths[0] & paths[1]:
        return ("overlap", owners)
    for region, adjustment in zip(paths, (11, 23), strict=True):
        for address in region:
            owners[address] += adjustment
    return "ok", owners


def experiment(directory):
    rustc = os.environ.get("RUSTC", "rustc")
    lean = os.environ.get("LEAN", "lean")
    version = subprocess.check_output([rustc, "-Vv"], text=True)
    assert "host: x86_64-" in version
    rows = {}
    trials = list(product(range(9), range(7), range(9), range(7)))
    maximum = 2**64 - 1
    trials.extend([(maximum, 0, 0, 0), (maximum, 1, 0, 0), (0, 0, maximum, 2)])
    source = "".join(" ".join(map(str, row)) + "\n" for row in trials)
    for optimization in (0, 2):
        binary = directory / f"regions{optimization}"
        flags = ["--edition=2021", "-Dwarnings", "-C", f"opt-level={optimization}"]
        subprocess.run([rustc, *flags, str(HERE / "regions.rs"), "-o", str(binary)],
                       check=True, capture_output=True)
        observed = subprocess.run([str(binary)], text=True, input=source,
                                  check=True, capture_output=True)
        assert not observed.stderr
        counts = Counter()
        parallel = 0
        for expected, line in zip(trials, observed.stdout.splitlines(), strict=True):
            label, *values = line.split()
            assert (label, list(map(int, values))) == oracle(expected)
            counts[label] += 1
            parallel += label == "ok" and expected[1] > 0 and expected[3] > 0
        assert parallel > 0 and counts["overflow"] == 2

        refusals = {}
        for name, (native, error) in NEGATIVE.items():
            file = directory / (name + ".rs")
            file.write_text(native, encoding="utf-8")
            result = subprocess.run([rustc, *flags, file.name, "-o", "invalid"],
                                    cwd=directory, capture_output=True, text=True, check=False)
            assert result.returncode != 0 and error in result.stderr, (name, result.stderr)
            refusals[name] = error
        rows[optimization] = {
            "observations": len(trials), "dispositions": dict(counts), "parallel_writes": parallel,
            "output": sha256(observed.stdout.encode()).hexdigest(), "compile_refusals": refusals,
        }
    assert rows[0] == rows[2]
    checked = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Regions.lean")],
                             check=True, capture_output=True, text=True)
    axioms = checked.stdout.splitlines()
    assert len(axioms) == 3 and not checked.stderr
    assert all(line.endswith("depends on axioms: [propext, Quot.sound]")
               or line.endswith("does not depend on any axioms") for line in axioms)
    return {"format": "scoped-mutable-regions-01", "rust": version.splitlines()[0],
            "observations": rows, "kernel_audit": axioms}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-scoped-regions-") as work:
        evidence = experiment(Path(work))
    content = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
