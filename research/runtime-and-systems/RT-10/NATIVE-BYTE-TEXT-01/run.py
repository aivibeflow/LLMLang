"""Compare exact native bytes, C-string prefixes and strict UTF-8 values."""

import argparse
from ctypes import CDLL, c_size_t, c_void_p, create_string_buffer
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


INVALID = c_size_t(-1).value
SENTINEL = b"\xa5"
PAYLOADS = {
    "empty": b"",
    "ascii": b"text",
    "leading_zero": b"\0leading",
    "embedded_zero": b"embedded\0middle",
    "trailing_zero": b"trailing\0",
    "precomposed": "é".encode(),
    "combining": "e\u0301".encode(),
    "supplementary": "😀".encode(),
    "zero_and_supplementary": "x\0😀".encode(),
    "invalid_octet": b"\xff",
    "overlong_zero": b"\xc0\x80",
    "truncated_sequence": b"\xe2\x82",
    "surrogate": b"\xed\xa0\x80",
    "stray_continuation": b"\x80",
    "beyond_scalar_range": b"\xf4\x90\x80\x80",
    "zero_hides_invalid_octet": b"\0\xff",
}


def utf8_oracle(payload):
    try:
        return len(payload.decode("utf-8", errors="strict"))
    except UnicodeDecodeError:
        return None


def check_copy(function, args, expected, capacity):
    output = create_string_buffer(SENTINEL * (capacity + 2), capacity + 2)
    returned = function(*args, output, capacity)
    if len(expected) > capacity:
        assert returned == INVALID and output.raw == SENTINEL * (capacity + 2)
        return 1
    assert returned == len(expected)
    assert output.raw == expected + SENTINEL * (capacity + 2 - len(expected))
    return 0


def observe(c_bridge, rust_bridge):
    binary = c_bridge.copy_bytes
    binary.argtypes = [c_void_p, c_size_t, c_void_p, c_size_t]
    binary.restype = c_size_t
    c_string = c_bridge.copy_c_string
    c_string.argtypes = [c_void_p, c_void_p, c_size_t]
    c_string.restype = c_size_t
    count = rust_bridge.utf8_scalar_count
    count.argtypes = [c_void_p, c_size_t]
    count.restype = c_size_t
    cases = {}
    capacity_controls = 0
    for name, payload in PAYLOADS.items():
        input_span = create_string_buffer(payload, len(payload) + 1)
        assert input_span.raw == payload + b"\0"
        prefix = payload.split(b"\0", 1)[0]
        scalar_count = count(input_span, len(payload))
        clipped_count = count(input_span, len(prefix))
        expected = utf8_oracle(payload)
        expected_clipped = utf8_oracle(prefix)
        assert scalar_count == (INVALID if expected is None else expected)
        assert clipped_count == (INVALID if expected_clipped is None else expected_clipped)

        binary_refusals = 0
        c_string_refusals = 0
        for capacity in range(len(payload) + 2):
            binary_refusals += check_copy(binary, (input_span, len(payload)), payload, capacity)
            c_string_refusals += check_copy(c_string, (input_span,), prefix, capacity)
            capacity_controls += 2
        cases[name] = {
            "original_hex": payload.hex(),
            "c_string_hex": prefix.hex(),
            "byte_length": len(payload),
            "c_string_length": len(prefix),
            "utf8_scalars": expected,
            "c_string_utf8_scalars": expected_clipped,
            "binary_capacity_refusals": binary_refusals,
            "c_string_capacity_refusals": c_string_refusals,
        }
    return cases, capacity_controls


def study(gcc, rustc):
    folder = Path(__file__).resolve().parent
    observations = []
    with TemporaryDirectory() as temporary:
        for level in (0, 2):
            c_library = Path(temporary) / f"c{level}.so"
            rust_library = Path(temporary) / f"rust{level}.so"
            subprocess.run(
                [gcc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared", f"-O{level}",
                 str(folder / "copy.c"), "-o", str(c_library)],
                check=True, timeout=30,
            )
            subprocess.run(
                [rustc, "--edition=2021", "--crate-type", "cdylib", "-Dwarnings", f"-Copt-level={level}",
                 str(folder / "text.rs"), "-o", str(rust_library)],
                check=True, timeout=30,
            )
            observations.append(observe(CDLL(str(c_library)), CDLL(str(rust_library))))
    assert observations[0] == observations[1]
    cases, capacity_controls = observations[0]
    return {
        "python": platform.python_version(),
        "gcc": subprocess.check_output([gcc, "--version"], text=True).splitlines()[0],
        "rustc": subprocess.check_output([rustc, "-Vv"], text=True).splitlines(),
        "optimization_levels": [0, 2],
        "capacity_controls_per_level": capacity_controls,
        "c_string_truncations": sum(row["byte_length"] != row["c_string_length"] for row in cases.values()),
        "rejected_full_utf8": sum(row["utf8_scalars"] is None for row in cases.values()),
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--rustc", default="rustc")
    args = parser.parse_args()
    print(json.dumps(study(args.gcc, args.rustc), indent=2, sort_keys=True))
