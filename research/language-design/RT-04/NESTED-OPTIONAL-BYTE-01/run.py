"""Check both native carriers against independent finite semantic inventories."""

import argparse
from ctypes import CDLL, c_uint16
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


DOMAIN = 1 << 16
INVALID = DOMAIN - 1
VALUES = ("absent", "present-empty", *range(256))


def inventory(layout):
    table = {}
    for ordinal, value in enumerate(VALUES):
        if layout == "dense":
            code = ordinal
        else:
            if value == "absent":
                parts = (0, 0)
            elif value == "present-empty":
                parts = (1, 0)
            else:
                parts = (2, value)
            code = int.from_bytes(bytes(parts), "big")
        assert code not in table
        table[code] = ordinal
    return table


def check_layout(bridge, layout):
    expected = inventory(layout)
    encode = getattr(bridge, f"encode_{layout}")
    decode = getattr(bridge, f"decode_{layout}")
    for function in (encode, decode):
        function.argtypes = [c_uint16]
        function.restype = c_uint16

    canonical = {ordinal: code for code, ordinal in expected.items()}
    digest = hashlib.sha256()
    accepted = 0
    for number in range(DOMAIN):
        decoded = decode(number)
        encoded = encode(number)
        assert decoded == expected.get(number, INVALID)
        assert encoded == canonical.get(number, INVALID)
        if decoded != INVALID:
            accepted += 1
            assert encode(decoded) == number
        digest.update(decoded.to_bytes(2, "big") + encoded.to_bytes(2, "big"))
    assert accepted == 258
    return {
        "accepted_codes": accepted,
        "rejected_codes": DOMAIN - accepted,
        "rejected_ordinals": DOMAIN - len(canonical),
        "exhaustive_encode_decode_sha256": digest.hexdigest(),
        "semantic_boundaries": [
            [value, encode(VALUES.index(value))] for value in ("absent", "present-empty", 0, 255)
        ],
    }


def study(compilers):
    source = Path(__file__).with_name("bridge.c")
    baseline = None
    builds = {}
    with TemporaryDirectory() as temporary:
        for name, executable in compilers.items():
            version = subprocess.check_output([executable, "--version"], text=True).splitlines()[0]
            builds[name] = {"version": version, "variants": {}}
            for optimization in ("-O0", "-O2"):
                shared = Path(temporary) / f"{name}{optimization}.so"
                subprocess.run(
                    [executable, "-std=c11", "-Wall", "-Wextra", "-Wconversion", "-Werror",
                     "-shared", "-fPIC", optimization, str(source), "-o", str(shared)],
                    check=True,
                    timeout=30,
                )
                library = CDLL(str(shared))
                layouts = {layout: check_layout(library, layout) for layout in ("dense", "tagged")}
                if baseline is None:
                    baseline = layouts
                assert layouts == baseline
                builds[name]["variants"][optimization] = layouts

    dense = inventory("dense")
    tagged = inventory("tagged")
    agreed = sorted(code for code in dense.keys() & tagged.keys() if dense[code] == tagged[code])
    assert agreed == [0]
    return {
        "python": platform.python_version(),
        "native_platform": platform.machine(),
        "logical_value_count": len(VALUES),
        "minimum_fixed_bit_count": (len(VALUES) - 1).bit_length(),
        "common_codes": len(dense.keys() & tagged.keys()),
        "agreed_common_codes": agreed,
        "layouts": builds,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--clang", default="clang")
    options = parser.parse_args()
    print(json.dumps(study({"gcc": options.gcc, "clang": options.clang}), indent=2, sort_keys=True))
