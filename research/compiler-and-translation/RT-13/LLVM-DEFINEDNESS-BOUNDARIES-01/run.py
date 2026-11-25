"""Compare checked byte arithmetic and audit speculation definedness boundaries."""

import argparse
from ctypes import CDLL, c_uint32
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


CASES = {
    "guarded_shift": ("shift", True),
    "masked_shift": ("shift", True),
    "guarded_div": ("division", True),
    "sanitized_div": ("division", True),
    "eager_div": ("division", False),
    "eager_frozen_div": ("division", False),
}


def expect(operation, left, right):
    if operation == "shift":
        return (left << right) & 255 if right < 8 else 256
    return left // right if right else 256


def check_function(library, name, operation, total):
    entry = getattr(library, name)
    entry.argtypes = [c_uint32, c_uint32]
    entry.restype = c_uint32
    digest = hashlib.sha256()
    calls = 0
    excluded = 0
    for left, right in product(range(256), repeat=2):
        if not total and right == 0:
            # The unconditional division executes before any output select or freeze.
            excluded += 1
            continue
        observed = entry(left, right)
        assert observed == expect(operation, left, right), (name, left, right, observed)
        digest.update(observed.to_bytes(2, "big"))
        calls += 1
    assert calls + excluded == 65536
    assert excluded == (0 if total else 256)
    return {
        "native_observations": calls,
        "inputs_with_immediate_ub_in_ir": excluded,
        "output_sha256": digest.hexdigest(),
    }


def study(options):
    source = Path(__file__).with_name("policies.ll")
    subprocess.run([options.opt, "-passes=verify", "-disable-output", str(source)], check=True, timeout=30)
    profiles = {}
    with TemporaryDirectory() as temporary:
        for level in (0, 3):
            library = Path(temporary) / f"policy-O{level}.so"
            subprocess.run(
                [options.clang, "-Werror", "-Wno-override-module", f"-O{level}", "-shared",
                 "-fPIC", str(source), "-o", str(library)],
                check=True, timeout=30,
            )
            native = CDLL(str(library))
            profiles[str(level)] = {
                name: check_function(native, name, operation, total)
                for name, (operation, total) in CASES.items()
            }
    assert profiles["0"] == profiles["3"]
    return {
        "python": platform.python_version(),
        "clang": subprocess.check_output([options.clang, "--version"], text=True).splitlines()[0],
        "verifier": subprocess.check_output([options.opt, "--version"], text=True).splitlines()[0],
        "profiles": profiles,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--opt", default="opt-19")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
