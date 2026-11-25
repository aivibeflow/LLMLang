"""Compare a generated ELF and its resolved runtime with an independent oracle."""

import argparse
import hashlib
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(content):
    return hashlib.sha256(content).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def call(args, cwd, *, input_data=None):
    return subprocess.run(
        args, cwd=cwd, input=input_data, text=True, capture_output=True, check=True
    ).stdout


def oracle(initial, quota, left, right):
    supplied = [(11, left), (29, right)]
    admitted = supplied[:quota]
    denied = supplied[quota : quota + 1]
    observations = [(tag, value, 0) for tag, value in admitted]
    observations.extend((tag, value, 1) for tag, value in denied)
    status = int(bool(denied))
    return (
        status,
        -99 if denied else sum(value for _, value in admitted),
        initial + sum(value for _, value in admitted),
        quota - len(admitted),
        len(observations),
        *itertools.chain.from_iterable(observations),
    )


def compare(actual, expected):
    assert len(actual) == len(expected)
    assert all(len(row) == 5 + 3 * row[4] for row in actual)
    return {
        "full_matches": sum(a == b for a, b in zip(actual, expected)),
        "status_value_state_and_quota_matches": sum(
            a[:4] == b[:4] for a, b in zip(actual, expected)
        ),
        "matching_projections_with_wrong_ordered_effects": sum(
            a[:4] == b[:4] and a != b for a, b in zip(actual, expected)
        ),
        "observations_sha256": digest(encode(actual)),
    }


def run_profile(cc, optimization, data, expected):
    with tempfile.TemporaryDirectory(prefix="rt09-runtime-") as temporary:
        cwd = Path(temporary)
        for filename in ("abi.h", "driver.c", "runtime.c"):
            shutil.copyfile(HERE / filename, cwd / filename)
        flags = [cc, "-std=c17", "-Wall", "-Wextra", "-Werror", optimization, "-fno-lto"]
        call(flags + ["-c", "driver.c", "-o", "driver.o"], cwd)
        for provider, extra_flags in (("intended", []), ("same_abi", ["-DMUTATE_RUNTIME_EVENT"])):
            call(flags + extra_flags + ["-c", "runtime.c", "-o", "runtime.o"], cwd)
            call(["ar", "crsD", f"{provider}.a", "runtime.o"], cwd)
        for lowering, extra_args in (("ordered", []), ("reversed", ["--reverse"])):
            source = call(
                [sys.executable, str(HERE / "emit.py"), str(HERE / "program.json"), *extra_args],
                cwd,
            )
            (cwd / f"{lowering}.c").write_text(source, encoding="utf-8")
            call(flags + ["-c", f"{lowering}.c", "-o", f"{lowering}.o"], cwd)
            assert call(["nm", "-u", f"{lowering}.o"], cwd).split() == ["U", "rt_emit"]

        missing = subprocess.run(
            [cc, "-fuse-ld=bfd", "driver.o", "ordered.o", "-o", "missing"],
            cwd=cwd, text=True, capture_output=True,
        )
        assert missing.returncode != 0 and "rt_emit" in missing.stderr
        assert not (cwd / "missing").exists()

        rows = {}
        for lowering, provider in (
            ("ordered", "intended"), ("reversed", "intended"), ("ordered", "same_abi"),
        ):
            archive = f"{provider}.a"
            linked = call(
                [cc, "-fuse-ld=bfd", "-Wl,-t,-t", "driver.o", f"{lowering}.o", archive, "-o", "artifact"],
                cwd,
            )
            assert f"({archive})runtime.o" in linked.splitlines()
            runtime_member = subprocess.check_output(["ar", "p", archive, "runtime.o"], cwd=cwd)
            symbols = call(["nm", "--defined-only", "artifact"], cwd)
            assert sum(line.split()[-2:] == ["T", "rt_emit"] for line in symbols.splitlines()) == 1
            dynamic = call(["readelf", "-dW", "artifact"], cwd)
            libraries = [
                line.split("[", 1)[1].split("]", 1)[0]
                for line in dynamic.splitlines()
                if "(NEEDED)" in line
            ]
            assert libraries == ["libc.so.6"]
            output = call(["./artifact"], cwd, input_data=data)
            actual = [tuple(map(int, line.split())) for line in output.splitlines()]
            rows[f"{lowering}/{provider}"] = {
                **compare(actual, expected),
                "dynamic_libraries": libraries,
                "archive_sha256": digest((cwd / archive).read_bytes()),
                "runtime_object_sha256": digest(runtime_member),
                "lowered_source_sha256": digest((cwd / f"{lowering}.c").read_bytes()),
                "elf_sha256": digest((cwd / "artifact").read_bytes()),
                "matches_required_archive": (
                    digest((cwd / archive).read_bytes()) == digest((cwd / "intended.a").read_bytes())
                ),
            }

        exact = rows["ordered/intended"]
        reversed_effects = rows["reversed/intended"]
        wrong_runtime = rows["ordered/same_abi"]
        assert exact["full_matches"] == len(expected)
        assert exact["matches_required_archive"] and reversed_effects["matches_required_archive"]
        assert 0 < reversed_effects["matching_projections_with_wrong_ordered_effects"]
        assert reversed_effects["full_matches"] == 0
        assert wrong_runtime["status_value_state_and_quota_matches"] == len(expected)
        assert wrong_runtime["full_matches"] == 0 and not wrong_runtime["matches_required_archive"]
        return {"missing_runtime_link": "rejected", "routes": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = list(itertools.product(range(-2, 3), range(3), range(-2, 3), range(-2, 3)))
    data = "".join(" ".join(map(str, case)) + "\n" for case in cases)
    expected = [oracle(*case) for case in cases]
    ledgers = {
        "target": call([args.cc, "-dumpmachine"], HERE).strip(),
        "compiler": call([args.cc, "--version"], HERE).splitlines()[0],
        "linker": call(["ld", "--version"], HERE).splitlines()[0],
        "input_count": len(cases),
        "inputs_sha256": digest(data.encode("ascii")),
        "oracle_trace_sha256": digest(encode(expected)),
        "fixture_sha256": {
            filename: digest((HERE / filename).read_bytes())
            for filename in ("program.json", "abi.h", "emit.py", "driver.c", "runtime.c", "run.py")
        },
        "profiles": {
            optimization: run_profile(args.cc, optimization, data, expected)
            for optimization in ("-O0", "-O2")
        },
    }
    result = json.dumps(ledgers, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(result, end="")
    else:
        args.output.write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
