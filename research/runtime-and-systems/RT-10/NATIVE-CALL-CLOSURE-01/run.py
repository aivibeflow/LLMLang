"""Compare an immutable wrapper with the declared closure of a loaded C call."""

import argparse
from ctypes import CDLL, c_char_p, c_uint32
import hashlib
import json
import os
from pathlib import Path
import platform
from shutil import copyfile
import subprocess
import sys
from tempfile import TemporaryDirectory


NEEDED = "libllmlang_fixture_arithmetic.so"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_shared(compiler, source, output, *extra):
    subprocess.run(
        [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-shared", "-fPIC",
         str(source), "-o", str(output), *extra],
        check=True, timeout=30,
    )


def probe(wrapper):
    try:
        handle = CDLL(str(wrapper))
    except OSError as error:
        assert NEEDED in str(error), error
        return {"load": "missing-dependency"}
    handle.loaded_helper.argtypes = []
    handle.loaded_helper.restype = c_char_p
    actual = Path(os.fsdecode(handle.loaded_helper()))
    assert actual.resolve() == (wrapper.parent / NEEDED).resolve()
    handle.invoke.argtypes = [c_uint32]
    handle.invoke.restype = c_uint32
    return {
        "load": "resolved",
        "helper_digest": digest(actual),
        "outcomes_for_inputs_0_to_15": [handle.invoke(operand) for operand in range(16)],
    }


def study(compiler):
    folder = Path(__file__).resolve().parent
    cases = {
        "selected": (1, 1),
        "different_behavior": (2, 2),
        "same_behavior_different_bytes": (1, 3),
        "dependency_absent": None,
    }
    env = {name: value for name, value in os.environ.items()
           if name not in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT")}
    rows = {}
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name, spec in cases.items():
            pending = root / name
            pending.mkdir()
            if spec is None:
                continue
            step, revision = spec
            compile_shared(compiler, folder / "helper.c", pending / NEEDED,
                           f"-DSTEP={step}u", f"-DREVISION={revision}u", f"-Wl,-soname,{NEEDED}")

        primary = root / "selected"
        wrapper = primary / "wrapper.so"
        compile_shared(compiler, folder / "wrapper.c", wrapper,
                       f"-L{primary}", f"-l:{NEEDED}", "-Wl,-rpath,$ORIGIN", "-ldl")
        elf = subprocess.check_output(["readelf", "-d", str(wrapper)], text=True)
        assert f"Shared library: [{NEEDED}]" in elf
        assert "Library runpath: [$ORIGIN]" in elf
        wrapper_address = digest(wrapper)
        expected_dependency = digest(primary / NEEDED)
        assert len({digest(root / name / NEEDED) for name, spec in cases.items() if spec}) == 3

        for name, spec in cases.items():
            selected = root / name / "wrapper.so"
            if selected != wrapper:
                copyfile(wrapper, selected)
            dependency = selected.parent / NEEDED
            wrapper_only = digest(selected) == wrapper_address
            exact_closure = wrapper_only and dependency.is_file() and digest(dependency) == expected_dependency
            output = subprocess.check_output(
                [sys.executable, "-B", str(Path(__file__).resolve()), "--probe", str(selected)],
                env=env, text=True, timeout=10,
            )
            native = json.loads(output)
            if spec is None:
                assert native == {"load": "missing-dependency"}
                oracle_matches = False
            else:
                assert native["load"] == "resolved"
                assert native["helper_digest"] == digest(dependency)
                assert native["outcomes_for_inputs_0_to_15"] == [value + spec[0] for value in range(16)]
                oracle_matches = native["outcomes_for_inputs_0_to_15"] == list(range(1, 17))
            assert wrapper_only
            assert exact_closure == (name == "selected")
            rows[name] = {"wrapper_only": wrapper_only, "exact_closure": exact_closure,
                          "source_oracle_matches": oracle_matches, "native": native}

    return {
        "python": platform.python_version(),
        "gcc": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
        "readelf": subprocess.check_output(["readelf", "--version"], text=True).splitlines()[0],
        "platform": platform.machine(),
        "wrapper_sha256": wrapper_address,
        "required_dependency": NEEDED,
        "declared_dependency_sha256": expected_dependency,
        "cases": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--probe", type=Path)
    args = parser.parse_args()
    print(json.dumps(probe(args.probe) if args.probe else study(args.gcc), indent=2, sort_keys=True))
