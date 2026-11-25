#!/usr/bin/env python3
"""Check dependent bounds and native smart-constructor admission on exact inputs."""

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
PAIRS = ((0, 0), (1, 2), (4, 4), (4, 16), (16, 4), (255, 256),
         (256, 255), (65535, 65535), (16, 65535))
VALUES = (*range(321), 32768, 65533, 65534, 65535)
DELTAS = (0, 1, 3, 15, 254, 65535)
CLIENT = """use bounded::{checked, Failure};
use std::io::{self, BufRead};

fn main() {
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let inputs: Vec<u16> = line.split_whitespace().map(|token| token.parse().unwrap()).collect();
        let _choice = inputs[0];
        let value = inputs[1];
        let delta = inputs[2];
        let result = match _choice {
ARMS
            _ => panic!("unrecognized fixture type")
        };
        match result {
            Ok(data) => println!("value {data}"),
            Err(Failure::Source) => println!("source"),
            Err(Failure::Overflow) => println!("overflow"),
            Err(Failure::Destination) => println!("destination"),
        }
    }
}
"""

NEGATIVE = {
    "forge": ("fn main() { let _x = bounded::Below::<1>(17); }", "E0603"),
    "wrong-index": ("fn main() { let _x: bounded::Below<4> = bounded::Below::<5>::new(0).unwrap(); }", "E0308"),
    "computed-index": (
        "fn rise<const L: u16>(x: bounded::Below<L>) -> bounded::Below<{L + 1}> {"
        "x.advance::<{L + 1}>(1).unwrap() } fn main() {}",
        "generic parameters may not be used in const operations",
    ),
}


def digest(raw):
    return sha256(raw).hexdigest()


def expected(before, after, value, delta):
    if value >= before:
        return "source"
    exact = value + delta
    if exact > 65535:
        return "overflow"
    if exact >= after:
        return "destination"
    return f"value {exact}"


def check_native(work, rustc, optimization):
    code = (HERE / "bounded.rs").read_bytes()
    (work / "bounded.rs").write_bytes(code)
    flags = ["--edition=2021", "--remap-path-prefix", f"{work}=/fixture",
             "-C", f"opt-level={optimization}"]
    subprocess.run([rustc, *flags, "--crate-type=rlib", "bounded.rs", "-o", "libbounded.rlib"],
                   cwd=work, check=True, capture_output=True)
    arms = [f"            {index} => checked::<{before}, {after}>(value, delta),"
            for index, (before, after) in enumerate(PAIRS)]
    (work / "client.rs").write_text(CLIENT.replace("ARMS", "\n".join(arms)), encoding="utf-8")
    link = ["--extern", "bounded=libbounded.rlib"]
    subprocess.run([rustc, *flags, "client.rs", *link, "-o", "client"],
                   cwd=work, check=True, capture_output=True)
    trials = list(product(range(len(PAIRS)), VALUES, DELTAS))
    source = "".join(f"{selection} {value} {delta}\n" for selection, value, delta in trials)
    result = subprocess.run(["./client"], cwd=work, check=True, capture_output=True,
                            text=True, input=source)
    assert not result.stderr
    observed = result.stdout.splitlines()
    counts = Counter()
    wrap_false_accepts = 0
    for (selection, value, delta), disposition in zip(trials, observed, strict=True):
        before, after = PAIRS[selection]
        assert disposition == expected(before, after, value, delta)
        counts[disposition.split()[0]] += 1
        if disposition == "overflow" and (value + delta) % 65536 < after:
            wrap_false_accepts += 1
    assert wrap_false_accepts > 0
    refusal = {}
    for name, (source, expected_error) in NEGATIVE.items():
        file = work / (name + ".rs")
        file.write_text(source, encoding="utf-8")
        check = subprocess.run([rustc, *flags, *link, file.name, "-o", "negative"],
                               cwd=work, check=False, text=True, capture_output=True)
        assert check.returncode != 0 and expected_error in check.stderr, (name, check.stderr)
        refusal[name] = expected_error
    return {"tests": len(observed), "dispositions": dict(counts), "byte_digest": digest(result.stdout.encode()),
            "wrap_false_accepts": wrap_false_accepts, "refusals": refusal}


def experiment(root):
    rustc = os.environ.get("RUSTC", "rustc")
    lean = os.environ.get("LEAN", "lean")
    rows = {}
    for optimization in (0, 2):
        work = root / f"O{optimization}"
        work.mkdir()
        rows[optimization] = check_native(work, rustc, optimization)
    assert rows[0] == rows[2]
    proof = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Bounds.lean")],
                           cwd=root, check=True, capture_output=True, text=True)
    assert not proof.stderr
    axioms = proof.stdout.splitlines()
    assert len(axioms) == 4 and all(line.endswith("does not depend on any axioms") for line in axioms)
    return {"format": "dependent-boundary-values-01", "pairs": PAIRS, "native": rows,
            "lean_proofs": axioms, "rust": subprocess.check_output([rustc, "--version"], text=True).strip()}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-dependent-boundary-") as directory:
        result = experiment(Path(directory))
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
