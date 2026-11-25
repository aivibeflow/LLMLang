"""Verify scalar, pointer and tagged sum C ABI carriers via separate compiled libraries."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
CASES = ["0:0:-7", f"0:0:{2**63-1}", "1:0:0", "0:0:-13", "0:0:512",
         "2:0:0", "2:0:0", "0:0:7", "3:0:0", "4:0:0"]


def run(options):
    return subprocess.check_output(options, text=True, timeout=20)


def digest(file):
    return sha256(file.read_bytes()).hexdigest()


def check():
    out = {}
    profiles = ["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-Wl,--build-id=none"]
    with TemporaryDirectory() as directory:
        work = Path(directory)
        binary, lib = work / "consumer", work / "libsum.so"
        for level in ("-O0", "-O2"):
            run([*profiles, level, "-fPIC", "-shared", HERE / "provider.c", "-o", lib])
            run([*profiles, level, HERE / "client.c", f"-L{work}", "-lsum", "-Wl,-rpath,$ORIGIN", "-o", binary])
            actual = run([binary]).splitlines()
            assert actual == [value for item in CASES for value in (item, item)]
            mismatch = subprocess.run([*profiles, level, "-DWRONG_CALL_CONVENTION", "-fsyntax-only",
                                       HERE / "client.c"], capture_output=True, text=True, check=False, timeout=15)
            assert mismatch.returncode and "incompatible pointer type" in mismatch.stderr
            out[level] = {"trace": actual, "wrong_convention_refused": True,
                          "provider_sha256": digest(lib), "consumer_sha256": digest(binary)}
    return {"compiler": run(["cc", "--version"]).splitlines()[0], "profiles": out,
            "inputs": {name: digest(HERE / name) for name in ("provider.c", "client.c", "abi.h", "check.py")}}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
