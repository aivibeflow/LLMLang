#!/usr/bin/env python3
"""Compare Cranelift JIT and LLVM native observations for the checked-add fixture."""

import argparse
import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
from random import Random
import re
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
FIXTURE = Path(os.environ.get("LLMLANG_INTEGER_FIXTURE",
                              HERE.parents[1] / "PROTOTYPES/LLVM-PRESERVATION-01"))
sys.path.insert(0, str(FIXTURE))
from checked_add_replay import WITNESSES
from integer_fixture import SOURCE, compile_source, evaluate
from llvm_integer_probe import CPU, TRIPLE, _EMIT, _entry, lower


SENTINEL = 0xabad1234
LIMIT = (1 << 32) - 1
CHANGED_FIELDS = {
    "drop_overflow": {"status", "out_slot", "effects"},
    "reverse_effects": {"effects"},
    "store_on_error": {"out_slot"},
}


def execute(arguments, stdin=None):
    result = subprocess.run(list(map(str, arguments)), input=stdin, capture_output=True, text=True, timeout=45)
    if result.returncode or result.stderr:
        raise ValueError(f"Command failed: {arguments!r}\n{result.returncode}: {result.stderr}")
    return result.stdout


def cases():
    edges = (0, 1, 2, 3, 0x7ffffffe, 0x7fffffff, 0x80000000, 0x80000001, 0xfffffffe, LIMIT)
    enables = (0, 1, 2, 0x80000000, LIMIT)
    rows = list(product(edges, edges, enables))
    random = Random(20261124)
    rows += [(random.getrandbits(32), random.getrandbits(32), random.choice(enables)) for _ in range(4096)]
    return rows


def reference(program, case):
    a, b, enabled = case
    result = evaluate(program, a, b, bool(enabled))
    return {"status": int(result.status == "overflow"), "out_slot": SENTINEL if result.value is None else result.value,
            "effects": list(result.events)}


def native_profiles(args, work, program, vectors, expected):
    profiles = {}
    ir = lower((program,))
    for level in (0, 3):
        path = work / f"llvm-O{level}.ll"
        obj, library = path.with_suffix(".o"), path.with_suffix(".so")
        execute([args.opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o", path, "-"], ir)
        execute([args.llc, f"-mtriple={TRIPLE}", f"-mcpu={CPU}", f"-O={level}", "-relocation-model=pic",
                 "-filetype=obj", path, "-o", obj])
        execute([args.cc, "-shared", "-Wl,--no-undefined", "-o", library, obj])
        if execute([args.nm, "--undefined-only", obj]):
            raise ValueError("Unexpected baseline object dependency")
        symbols = execute([args.nm, "--print-size", "--defined-only", obj])
        size = re.search(r"^[0-9a-f]+ ([0-9a-f]+) T probe_0$", symbols, re.MULTILINE)
        if size is None:
            raise ValueError("Exact LLVM symbol extent is missing")
        entry = _entry(ctypes.CDLL(str(library)), 0)
        actual = []
        for case in vectors:
            effects = []
            result = ctypes.c_uint32(SENTINEL)
            status = entry(*case, _EMIT(effects.append), ctypes.byref(result))
            actual.append({"status": status, "out_slot": result.value, "effects": effects})
        if actual != expected:
            raise ValueError(f"LLVM O{level} disagreed with the independent source evaluator")
        profiles[f"llvm_O{level}"] = {"llvm_ir_sha256": sha256(path.read_bytes()).hexdigest(),
                                    "object_sha256": sha256(obj.read_bytes()).hexdigest(),
                                    "function_bytes": int(size[1], 16)}
    return profiles


def jit(args, work, level, policy, vectors):
    clif, code = (work / f"{level}-{policy}.{suffix}" for suffix in ("clif", "bin"))
    inputs = "".join(f"{a} {b} {enabled}\n" for a, b, enabled in vectors)
    output = execute([args.probe, level, policy, clif, code], inputs)
    observations = []
    for line in output.splitlines():
        status, out_slot, *effects = map(int, line.split())
        observations.append({"status": status, "out_slot": out_slot, "effects": effects})
    return observations, {"clif_sha256": sha256(clif.read_bytes()).hexdigest(),
                          "machine_sha256": sha256(code.read_bytes()).hexdigest(),
                          "function_bytes": code.stat().st_size}


def replay(args):
    program = compile_source(SOURCE.replace("operation", "checked_sadd"))
    vectors = cases()
    expected = [reference(program, case) for case in vectors]
    with TemporaryDirectory(prefix="llmlang-rt13-cranelift-") as directory:
        work = Path(directory)
        profiles = native_profiles(args, work, program, vectors, expected)
        controls = {}
        for level in ("none", "speed"):
            seen, exact = jit(args, work, level, "preserving", vectors)
            if seen != expected:
                raise ValueError(f"Cranelift {level} disagreed with the independent source evaluator")
            profiles[f"cranelift_{level}"] = exact
            controls[level] = {}
            for policy, signed in WITNESSES.items():
                witness = tuple(value & LIMIT for value in signed)
                right = reference(program, witness)
                result, artifacts = jit(args, work, level, policy, [witness])
                (wrong,) = result
                if {key for key in right if wrong[key] != right[key]} != CHANGED_FIELDS[policy]:
                    raise ValueError(f"Unexpected negative observation for {policy}: {wrong}, expected {right}")
                controls[level][policy] = {"witness": witness, "source": right, "observed": wrong, **artifacts}
    sources = {"fixture-source": SOURCE.replace("operation", "checked_sadd").encode(),
               "integer-fixture.py": (FIXTURE / "integer_fixture.py").read_bytes(),
               "llvm-integer-probe.py": (FIXTURE / "llvm_integer_probe.py").read_bytes(),
               "checked-add-replay.py": (FIXTURE / "checked_add_replay.py").read_bytes()}
    sources.update((name, (HERE / name).read_bytes()) for name in ("run.py", "Cargo.toml", "Cargo.lock", "src/main.rs"))
    return {"schema": "llmlang-rt13-cranelift-checked-add-v1", "target": TRIPLE, "cranelift": "0.116.1",
            "cranelift_revision": "58282df898d79a787a726d829b166272dde155b9",
            "tools": {name: execute([getattr(args, name), "--version"]).splitlines()[0]
                      for name in ("opt", "llc", "cc", "rustc")},
            "source_sha256": {name: sha256(data).hexdigest() for name, data in sources.items()},
            "vectors": len(vectors), "observations_sha256": sha256(json.dumps(expected).encode()).hexdigest(),
            "profiles": profiles, "controls": controls}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    for tool, command in {"opt": "opt-19", "llc": "llc-19", "cc": "gcc", "nm": "llvm-nm-19",
                          "rustc": "rustc"}.items():
        parser.add_argument(f"--{tool}", default=command)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args), indent=2) + "\n", encoding="utf-8")
