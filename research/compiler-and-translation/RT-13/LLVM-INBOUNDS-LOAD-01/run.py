"""Contrast LLVM IR definedness for bounded immutable byte reads."""

import argparse
from collections import Counter
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASELINE = "6b7d93f2a86fe5f8b0f3b142c693b4a70ffa145f"
DATA = b"LLMprobe"
SIZE = len(DATA)
WORD = 1 << 64
VARIANTS = (
    "branch_first", "choose_pointer_first", "choose_index_first",
    "choose_result_last", "freeze_pointer",
)
WORDS = tuple(range(256)) + (
    (1 << 63) - 1, 1 << 63, (1 << 63) + 1, WORD - 256, WORD - 9, WORD - 8, WORD - 2, WORD - 1,
)


def input_pointer(word):
    offset = word if word < (1 << 63) else word - WORD
    if 0 <= offset < SIZE:
        return "inside"
    if offset == SIZE:
        return "one-past"
    return "poison"


def classify(variant, word):
    pointer = input_pointer(word)
    if pointer == "inside":
        return "defined"
    if variant in ("branch_first", "choose_pointer_first", "choose_index_first"):
        return "defined"
    if pointer == "one-past":
        return "one-past-load"
    if variant == "freeze_pointer":
        return "frozen-poison-pointer-load"
    return "poison-pointer-load"


def run_command(*command, input_data=None, cwd):
    return subprocess.check_output(command, cwd=cwd, input=input_data, timeout=30)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def experiment(args, work):
    llvm = [run_command(tool, "--version", cwd=work).decode().splitlines()[0]
            for tool in (args.opt, args.llc)]
    assert all(line.endswith("LLVM version 19.1.7") for line in llvm), llvm
    source = (HERE / "fixture.ll").read_bytes()
    bounds = {n: input_pointer(n) for n in WORDS}
    assert Counter(bounds.values()) == {"inside": 8, "one-past": 1, "poison": 255}
    semantics = {variant: Counter(classify(variant, word) for word in WORDS) for variant in VARIANTS}
    assert list(semantics.values()) == [
        {"defined": 264}, {"defined": 264}, {"defined": 264},
        {"defined": 8, "one-past-load": 1, "poison-pointer-load": 255},
        {"defined": 8, "one-past-load": 1, "frozen-poison-pointer-load": 255},
    ]
    profiles = {}
    for level in (0, 3):
        ir = run_command(args.opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o", "-", "-",
                         input_data=source, cwd=work)
        optimized = work / f"optimized-O{level}.ll"
        obj = work / f"object-O{level}.o"
        library = work / f"fixture-O{level}.so"
        optimized.write_bytes(ir)
        run_command(args.llc, "-mtriple=x86_64-pc-linux-gnu", "-relocation-model=pic", f"-O={level}",
                    "-filetype=obj", optimized, "-o", obj, cwd=work)
        run_command(args.cc, "-shared", "-Wl,--no-undefined", obj, "-o", library, cwd=work)
        shared = ctypes.CDLL(str(library))
        observed = {}
        for variant in VARIANTS:
            entry = getattr(shared, variant)
            entry.argtypes = [ctypes.c_uint64]
            entry.restype = ctypes.c_int
            rows = []
            for word in WORDS:
                reason = classify(variant, word)
                if reason != "defined":
                    continue
                result = entry(word)
                assert result == (DATA[word] if word < SIZE else -1), (level, variant, word, result)
                rows.append([word, result])
            observed[variant] = rows
        assert sum(map(len, observed.values())) == 808
        profiles[f"O{level}"] = {
            "optimized_ir_sha256": sha(ir), "object_sha256": sha(obj.read_bytes()),
            "native": observed,
        }
    assert profiles["O0"]["native"] == profiles["O3"]["native"]
    return {
        "baseline": BASELINE, "python": platform.python_version(),
        "tools": {"opt": llvm[0], "llc": llvm[1],
                  "cc": run_command(args.cc, "--version", cwd=work).decode().splitlines()[0]},
        "target_triple": "x86_64-pc-linux-gnu",
        "source_sha256": {"fixture.ll": sha(source), "run.py": sha(Path(__file__).read_bytes())},
        "byte_array": DATA.decode(), "input_words": WORDS, "analysis": semantics,
        "pointer_boundaries": {str(n): bounds[n] for n in (7, 8, 9, WORD - 1)},
        "profiles": profiles,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opt", required=True, type=Path)
    parser.add_argument("--llc", required=True, type=Path)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-inbounds-load-") as temporary:
        print(json.dumps(experiment(args, Path(temporary)), indent=2))
