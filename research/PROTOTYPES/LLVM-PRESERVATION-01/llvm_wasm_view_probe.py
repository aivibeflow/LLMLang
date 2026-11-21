"""Lower the existing read-only byte-view LLVM IR to Wasm memory32."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from llvm_integer_probe import LLVM_VERSION, TRIPLE
from llvm_view_probe import DATA, OFFSETS, STATUS, VIEWS, lower, reference


WASM_TRIPLE = "wasm32-unknown-unknown"
HOST = Path(__file__).with_name("wasm_view_host.mjs")
WIDTH_EDGES = (-(2**32), -(2**32) + 1, 2**32, 2**32 + 1)


def cases():
    for op, origin, expected, offset, delta in product(
        ("form", "read"), range(len(VIEWS)), range(len(VIEWS)), OFFSETS + WIDTH_EDGES,
        OFFSETS + WIDTH_EDGES,
    ):
        status, value = reference(op, origin, expected, offset, delta)
        yield [op, origin, expected, str(offset), str(delta), status, value]


def compile_module(folder, ir, level, opt, llc, linker):
    compiled = folder / f"O{level}.ll"
    obj = folder / f"O{level}.o"
    wasm = folder / f"O{level}.wasm"
    subprocess.run([opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o",
                    str(compiled), "-"], input=ir, text=True, check=True, timeout=30)
    subprocess.run([llc, f"-mtriple={WASM_TRIPLE}", f"-O={level}", "-filetype=obj",
                    str(compiled), "-o", str(obj)], check=True, timeout=30)
    subprocess.run([linker, "--no-entry", "--export-memory", "--export=form_view",
                    "--export=read_view", str(obj), "-o", str(wasm)], check=True, timeout=30)
    return wasm


def run(opt, llc, linker, node):
    for tool in (opt, llc, linker):
        version = subprocess.check_output([tool, "--version"], text=True, timeout=30).splitlines()[0]
        if f" {LLVM_VERSION}" not in version:
            raise ValueError(f"expected tool version {LLVM_VERSION}, got {version}")
        print(version, flush=True)
    source = lower().replace(f'target triple = "{TRIPLE}"', f'target triple = "{WASM_TRIPLE}"', 1)
    print("lowering input SHA-256", sha256(source.encode()).hexdigest(), flush=True)
    workload = json.dumps({"cases": list(cases()), "names": STATUS, "views": VIEWS, "bytes": list(DATA)})
    with TemporaryDirectory(prefix="llmlang-llvm-wasm-") as tmp:
        for level in (0, 3):
            module = compile_module(Path(tmp), source, level, opt, llc, linker)
            print(f"O{level} WebAssembly SHA-256 {sha256(module.read_bytes()).hexdigest()}", flush=True)
            subprocess.run([node, str(HOST), str(module)], input=workload,
                           text=True, check=True, timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", default="opt")
    parser.add_argument("--llc", default="llc")
    parser.add_argument("--wasm-ld", default="wasm-ld")
    parser.add_argument("--node", default="node")
    arguments = parser.parse_args()
    run(arguments.opt, arguments.llc, arguments.wasm_ld, arguments.node)
