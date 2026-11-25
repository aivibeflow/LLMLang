"""Trace how LLVM optimization consumes progress promises on an exact fixture."""

import argparse
from ctypes import CDLL, c_uint32
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory


NAMES = ("unannotated", "function_progress", "loop_progress", "volatiles_make_progress")


def inspect(text, name):
    match = re.search(rf"^define [^\n]* @{name}\([^\n]*\) [^\n]*\{{\n(.*?)^\}}",
                      text, flags=re.MULTILINE | re.DOTALL)
    assert match is not None, name
    frame = match.group(1)
    has_wait_loop = bool(re.search(r"^wait:[^\n]*\n(?:[^\n]*\n)*?  br label %wait\b",
                                   frame, flags=re.MULTILINE))
    assumption = "@llvm.assume(i1 %done)" in frame
    if assumption:
        assert "%done = icmp eq i32 %stop, 1" in frame
    return {
        "has_wait_backedge": has_wait_loop,
        "assumes_terminating_input": assumption,
        "has_volatile_read": "load volatile i32" in frame,
    }


def study(options):
    source = Path(__file__).with_name("progress.ll")
    profiles = {}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        for level in (0, 3):
            optimized = work / f"progress-O{level}.ll"
            subprocess.run([options.opt, f"-passes=verify,default<O{level}>,verify", "-S",
                            str(source), "-o", str(optimized)], check=True, timeout=30)
            text = optimized.read_text()
            rows = {name: inspect(text, name) for name in NAMES}
            for name, row in rows.items():
                optimized_promise = level == 3 and name in ("function_progress", "loop_progress")
                assert row["has_wait_backedge"] != optimized_promise, rows
                assert row["assumes_terminating_input"] == optimized_promise, rows
                assert row["has_volatile_read"] == (name == "volatiles_make_progress"), rows

            native_library = work / f"progress-O{level}.so"
            subprocess.run([options.clang, "-O0", "-Werror", "-Wno-override-module", "-fPIC", "-shared",
                            str(optimized), "-o", str(native_library)], check=True, timeout=30)
            library = CDLL(str(native_library))
            for name, row in rows.items():
                call = getattr(library, name)
                call.argtypes = [c_uint32]
                call.restype = c_uint32
                # The terminating input is defined in every inspected route.
                row["native_result_for_stop_one"] = call(1)
                assert row["native_result_for_stop_one"] == 7
            profiles[str(level)] = rows
    return {
        "python": platform.python_version(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "clang": subprocess.check_output([options.clang, "--version"], text=True).splitlines()[0],
        "optimizer": subprocess.check_output([options.opt, "--version"], text=True).splitlines()[0],
        "profiles": profiles,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--opt", default="opt-19")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
