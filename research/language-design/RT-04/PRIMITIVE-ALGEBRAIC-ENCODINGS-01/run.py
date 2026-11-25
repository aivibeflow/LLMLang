#!/usr/bin/env python3
"""Compare exact typed value sets, raw encodings, and distributive witnesses."""

import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent


def digest(raw):
    return sha256(raw).hexdigest()


def check_lean(lean):
    run = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Shapes.lean")],
                         check=True, capture_output=True, text=True)
    assert not run.stderr
    lines = run.stdout.splitlines()
    assert len(lines) == 5
    for name, line in zip(
        ("factor_after_distribute", "distribute_after_factor", "empty_has_no_branch", "flag_roundtrip", "invalid_flag"),
        lines, strict=True,
    ):
        assert line in (
            f"'{name}' does not depend on any axioms", f"'{name}' depends on axioms: [propext, Quot.sound]",
        )
    return lines


def setup(work, compiler, optimization):
    library = work / "codec.so"
    result = subprocess.run(
        [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", optimization,
         "-shared", "-fPIC", str(HERE / "codec.c"), "-o", str(library)],
        cwd=work, check=True, capture_output=True,
    )
    assert not result.stderr
    native = ctypes.CDLL(str(library))
    for name in ("decode_flag", "decode_byte", "decode_product_first", "decode_sum_first"):
        decoder = getattr(native, name)
        decoder.argtypes = [ctypes.c_uint16]
        decoder.restype = ctypes.c_int
    for name in ("encode_product_first", "encode_sum_first"):
        encoder = getattr(native, name)
        encoder.argtypes = [ctypes.c_uint, ctypes.c_int]
        encoder.restype = ctypes.c_uint16
    return native, digest(library.read_bytes())


def roundtrip(native):
    product_bits = {}
    sum_bits = {}
    for ordinal, (flag, value) in enumerate(product(range(2), range(-1, 256))):
        field_form = sum((flag * 2**9, 2**8 + value) if value >= 0 else (flag * 2**9,))
        branch_form = flag | ((2**9 | (value << 1)) if value >= 0 else 0)
        assert native.encode_product_first(flag, value) == field_form
        assert native.encode_sum_first(flag, value) == branch_form
        assert field_form not in product_bits and branch_form not in sum_bits
        product_bits[field_form] = sum_bits[branch_form] = ordinal
    intersection = set(product_bits) & set(sum_bits)
    mismatches = sorted(word for word in intersection if product_bits[word] != sum_bits[word])

    for word in range(65536):
        assert native.decode_flag(word) == (word if word in (0, 1) else -1)
        assert native.decode_byte(word) == (word if word < 256 else -1)
        assert native.decode_product_first(word) == product_bits.get(word, -1)
        assert native.decode_sum_first(word) == sum_bits.get(word, -1)
    assert len(set(product_bits.values())) == len(set(sum_bits.values())) == 514
    assert mismatches
    return {
        "words": 65536, "strict_flag_values": 2, "strict_byte_values": 256,
        "algebraic_values_per_encoding": 514,
        "wire_intersection": len(intersection), "different_meanings_in_intersection": len(mismatches),
        "first_incompatible_word": mismatches[0],
        "first_incompatible_ranks": [product_bits[mismatches[0]], sum_bits[mismatches[0]]],
    }


def experiment(directory):
    lean = os.environ.get("LEAN", "lean")
    settings = {
        "gcc": os.environ.get("GCC", "gcc"), "clang": os.environ.get("CLANG", "clang"),
    }
    rows = {}
    for (name, compiler), optimization in product(settings.items(), ("-O0", "-O2")):
        work = directory / f"{name}-{optimization[1:]}"
        work.mkdir()
        native, artifact = setup(work, compiler, optimization)
        values = roundtrip(native)
        rows[f"{name}/{optimization}"] = {
            "compiler": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
            "artifact": artifact, "observations": values,
        }
    assert len({json.dumps(row["observations"], sort_keys=True) for row in rows.values()}) == 1
    return {"format": "primitive-algebraic-encodings-01", "rows": rows,
            "lean_proofs": check_lean(lean),
            "source": {name: digest((HERE / name).read_bytes()) for name in ("Shapes.lean", "codec.c") }}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-type-validity-") as temp:
        ledger = experiment(Path(temp))
    content = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
