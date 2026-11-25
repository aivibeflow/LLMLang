"""Check that native build freshness and migration artifact evidence stay distinct."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
FILES = ("Makefile", "provider.c", "limits.h", "build.opts")
STAMP = 946684800
CASES = tuple(range(-8, 9))


def digest(data):
    return sha256(data).hexdigest()


def execute(args, directory, payload=None):
    return subprocess.run(args, cwd=directory, check=True, text=True, input=payload,
                          capture_output=True, timeout=30).stdout


def build_key(directory, profile):
    materials = {name: digest((directory / name).read_bytes()) for name in FILES}
    return digest(json.dumps({"inputs": materials, "profile": profile}, sort_keys=True).encode())


def observe(directory):
    binary = str(directory / "provider.so")
    client = (
        "import ctypes, json, sys\n"
        "lib = ctypes.CDLL(sys.argv[1])\n"
        "lib.reserve.argtypes = (ctypes.c_int,)\n"
        "lib.reserve.restype = ctypes.c_int\n"
        "print(json.dumps([lib.reserve(i) for i in json.load(sys.stdin)]))\n"
    )
    return json.loads(execute([sys.executable, "-I", "-c", client, binary],
                              directory, json.dumps(CASES)))


def admits(directory, receipt, profile):
    return (build_key(directory, profile), digest((directory / "provider.so").read_bytes())) == (
        receipt["build_key"], receipt["artifact"])


def run(args, directory):
    profile = {
        "cc": execute([args.cc, "--version"], directory).splitlines()[0],
        "cc_sha256": digest(Path(args.cc).read_bytes()),
        "target": execute([args.cc, "-dumpmachine"], directory).strip(),
        "make": execute([args.make, "--version"], directory).splitlines()[0],
    }

    def write(name, value, timestamp):
        path = directory / name
        path.write_bytes(value)
        os.utime(path, (timestamp, timestamp))

    def make(force):
        flags = ["-B"] if force else []
        result = execute([args.make, "-rR", *flags, f"CC={args.cc}", "provider.so"], directory)
        return "rebuilt" if "-shared" in result else "current"

    def receipt(factor, offset):
        observations = observe(directory)
        assert observations == [factor * i + offset for i in CASES]
        return {"build_key": build_key(directory, profile),
                "artifact": digest((directory / "provider.so").read_bytes()),
                "observations": observations}

    write("Makefile", (HERE / "Makefile.fixture").read_bytes(), STAMP)
    write("provider.c", (HERE / "provider.c").read_bytes(), STAMP)
    write("limits.h", b"#define FIXTURE_FACTOR 2\n", STAMP)
    write("build.opts", b"-DFIXTURE_OFFSET=1\n", STAMP)
    assert make(False) == "rebuilt"
    baseline = receipt(2, 1)

    write("README.md", b"ordinary documentation change\n", STAMP + 1)
    assert make(False) == "current" and admits(directory, baseline, profile)
    header = directory / "limits.h"
    old_time = header.stat().st_mtime_ns
    header.write_bytes(b"#define FIXTURE_FACTOR 3\n")
    os.utime(header, ns=(old_time, old_time))
    assert make(False) == "current"
    assert observe(directory) == baseline["observations"]
    assert not admits(directory, baseline, profile)
    assert make(True) == "rebuilt"
    corrected = receipt(3, 1)
    assert corrected["artifact"] != baseline["artifact"] and admits(directory, corrected, profile)

    output_path = directory / "provider.so"
    os.utime(output_path, (STAMP + 10, STAMP + 10))
    write("build.opts", b"-DFIXTURE_OFFSET=2\n", STAMP + 11)
    assert make(False) == "rebuilt"
    latest = receipt(3, 2)
    assert latest["build_key"] != corrected["build_key"] and latest["artifact"] != corrected["artifact"]
    assert not admits(directory, corrected, profile)
    assert admits(directory, latest, profile)
    assert not admits(directory, latest, {**profile, "target": "fixture-target"})
    return {"python": platform.python_version(), "profile": profile, "inputs": CASES,
            "baseline": baseline, "after_header_rebuild": corrected, "after_flag_change": latest,
            "controls": {"unrelated_file": "preserves-exact-build-key",
                         "same_time_header_change": "make-current-receipt-refused",
                         "declared_build_option": "rebuilt", "wrong_target": "refused"},
            "sources": {name: digest((HERE / name).read_bytes())
                        for name in ("Makefile.fixture", "provider.c", "check.py")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", required=True)
    parser.add_argument("--make", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt28-build-handoff-") as temp:
        print(json.dumps(run(args, Path(temp)), sort_keys=True, indent=2))
