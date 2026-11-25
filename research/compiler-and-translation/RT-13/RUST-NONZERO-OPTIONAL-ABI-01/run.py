"""Check C calls to a documented Rust niche and explicit tagged arithmetic values."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
VALUES = [*range(256), 0x10000, 0x7fffffff, 0x80000000, 0xffffffff]


def run(arguments):
    return subprocess.check_output(arguments, cwd=HERE, text=True, timeout=30)


def oracle():
    rows = ["layout:8:4"]
    for value in VALUES:
        rows.append(f"niche:{value}:{value}:{int(value != 0)}")
        for tag in (0, 1, 2, 255):
            if tag == 0 and value == 0:
                result = 0
            elif tag == 1:
                result = (1 << 32) | value
            else:
                result = 2 << 32
            rows.append(f"tagged:{tag}:{value}:{result}")
    return rows


def study(options):
    profiles = {}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        target = work / "libbridge.so"
        client = work / "client"
        rust = [options.rustc, "--edition=2021", "--crate-type=cdylib", "-Dwarnings",
                "--error-format=json", "bridge.rs", "-o", target]
        for level in (0, 2):
            run([*rust, f"-Copt-level={level}"])
            run([options.gcc, "-std=c17", "-Wall", "-Wextra", "-Werror",
                 "client.c", f"-L{work}", "-lbridge", "-Wl,-rpath,$ORIGIN", "-o", client])
            output = run([client])
            assert output.splitlines() == oracle(), level
            profiles[str(level)] = {
                "native_transcript_sha256": hashlib.sha256(output.encode()).hexdigest(),
                "niche_inputs_checked": len(VALUES),
                "tagged_calls": 4 * len(VALUES),
            }
        assert profiles["0"] == profiles["2"]
        diagnostics = {}
        for negative in ("unrestricted", "nested"):
            built = subprocess.run([*rust, "--cfg", negative], cwd=HERE, capture_output=True,
                                   text=True, check=False, timeout=30)
            assert built.returncode != 0
            rows = [json.loads(line) for line in built.stderr.splitlines()]
            errors = [row for row in rows if row.get("code") and row.get("level") == "error"]
            assert len(errors) == 1
            assert errors[0]["code"]["code"] == "improper_ctypes_definitions"
            diagnostics[negative] = errors[0]["code"]["code"]
    return {
        "profiles": profiles,
        "compiler_refusals": diagnostics,
        "python": platform.python_version(),
        "rustc": run([options.rustc, "-Vv"]).splitlines(),
        "gcc": run([options.gcc, "--version"]).splitlines()[0],
        "controls": {
            "niche_zero": "absent",
            "tagged_absent": {"tag": 0, "bits": 0, "result": 0},
            "tagged_present_zero": {"tag": 1, "bits": 0, "result": 1 << 32},
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--gcc", default="gcc")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
