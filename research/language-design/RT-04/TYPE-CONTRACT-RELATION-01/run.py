#!/usr/bin/env python3
"""Check representation, provider compatibility and distinct guarantee classes."""

import ctypes
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
TYPES = (
    ("Identity", "ticks_identity", lambda x: x),
    ("Offset", "ticks_offset", lambda x: x + 7),
    ("Alternating", "ticks_alternating", lambda x: x + (12 if x % 2 == 0 else 0)),
    ("Far", "ticks_far", lambda x: x + 100),
    ("WrongUnit", "millis_wrong_unit", lambda x: 2 * x),
)
DRIVER = """use provider::*;
fn consumer(source: &dyn Provider<Output=Ticks>, n: u8) -> u16 { source.reading(n).raw() }
fn main() {
    println!("{} {} {} {}", std::mem::size_of::<Ticks>(), std::mem::align_of::<Ticks>(),
             std::mem::size_of::<Millis>(), std::mem::align_of::<Millis>());
    let sources: [&dyn Provider<Output=Ticks>; 4] = [&Identity, &Offset, &Alternating, &Far];
    for source in sources {
        for input in 0..=255u8 {
            println!("{}", consumer(source, input));
        }
    }
}
"""
INVALID = """use provider::*;
fn consumer(source: &dyn Provider<Output=Ticks>) -> u16 { source.reading(0).raw() }
fn main() { println!("{}", consumer(&WrongUnit)); }
"""


def run_build(root, rustc, optimization):
    flags = ["--edition=2021", "-Dwarnings", "--remap-path-prefix", f"{root}=/fixture",
             "-C", f"opt-level={optimization}"]
    (root / "provider.rs").write_bytes((HERE / "provider.rs").read_bytes())
    subprocess.run([rustc, *flags, "--crate-type=rlib,cdylib", "provider.rs", "--out-dir", "."],
                   cwd=root, check=True, capture_output=True)
    (root / "accepted.rs").write_text(DRIVER, encoding="utf-8")
    (root / "refused.rs").write_text(INVALID, encoding="utf-8")
    link = ["--extern", "provider=libprovider.rlib"]
    subprocess.run([rustc, *flags, "accepted.rs", *link, "-o", "app"],
                   cwd=root, check=True, capture_output=True)
    denied = subprocess.run([rustc, *flags, "refused.rs", *link, "-o", "invalid"],
                            cwd=root, check=False, capture_output=True, text=True)
    assert denied.returncode != 0 and "E0271" in denied.stderr
    observed = subprocess.check_output(["./app"], cwd=root, text=True).splitlines()
    layout, *checked = observed
    assert layout == "2 2 2 2" and len(checked) == 4 * 256

    lib = ctypes.CDLL(str(root / "libprovider.so"))
    rows = {}
    for index, (name, abi, oracle) in enumerate(TYPES):
        getter = getattr(lib, abi)
        getter.argtypes = [ctypes.c_uint8]
        getter.restype = ctypes.c_uint16
        values = [getter(n) for n in range(256)]
        assert values == [oracle(n) for n in range(256)]
        if index < 4:
            assert list(map(int, checked[index * 256:(index + 1) * 256])) == values
        bad_points = sum(not n <= value <= n + 32 for n, value in enumerate(values))
        bad_pairs = sum(values[first] > values[second] for first in range(256) for second in range(first, 256))
        assert (bad_points == 0) == (index < 3)
        assert (bad_pairs > 0) == (name == "Alternating")
        rows[name] = {
            "type_admitted": name != "WrongUnit", "raw_abi_observations": len(values),
            "raw_output": sha256(json.dumps(values).encode()).hexdigest(),
            "pointwise_refusals": bad_points, "monotone_pair_refusals": bad_pairs,
        }
    return {"native": rows, "layout": [2, 2, 2, 2], "typed_observations": len(checked),
            "wrong_unit_compiler_code": "E0271"}


def experiment(root):
    rustc = os.environ.get("RUSTC", "rustc")
    lean = os.environ.get("LEAN", "lean")
    rows = {}
    for opt in (0, 2):
        work = root / f"O{opt}"
        work.mkdir()
        rows[opt] = run_build(work, rustc, opt)
    assert rows[0] == rows[2]
    proof = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Models.lean")],
                           check=True, text=True, capture_output=True)
    axioms = proof.stdout.splitlines()
    assert len(axioms) == 7 and not proof.stderr
    assert all(line.endswith(("does not depend on any axioms", "depends on axioms: [propext]",
                              "depends on axioms: [propext, Quot.sound]",
                              "depends on axioms: [propext, Classical.choice, Quot.sound]"))
               for line in axioms)
    return {"format": "type-contract-relation-01", "reported": rows, "lean_axioms": axioms,
            "rustc": subprocess.check_output([rustc, "--version"], text=True).strip()}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-type-contract-relation-") as temporary:
        evidence = experiment(Path(temporary))
    content = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
