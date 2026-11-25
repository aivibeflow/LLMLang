"""Check native callback admission, foreign reentry and exact joining across two providers."""

import argparse
import ctypes as c
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
PEEK = c.CFUNCTYPE(c.c_int32, c.c_uint32)
CALLBACK = c.CFUNCTYPE(c.c_int32, c.c_void_p, c.c_uint32, c.c_int32)


class Context(c.Structure):
    _fields_ = [("peek", PEEK), ("fail", c.c_int32)]


class CallbackFailure(Exception):
    pass


@CALLBACK
def python_callback(raw, token, value):
    context = c.cast(raw, c.POINTER(Context)).contents
    try:
        scope = context.peek(token)
        if scope < 0:
            return scope
        if context.fail:
            raise CallbackFailure("injected callback failure")
        return scope + value
    except CallbackFailure:
        return 70


def invoke(args, cwd):
    return subprocess.run(
        args, cwd=cwd, env={**os.environ, "LC_ALL": "C", "TZ": "UTC"},
        capture_output=True, text=True, check=True, timeout=60,
    ).stdout.strip()


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def function(library, name, restype, *arguments):
    entry = getattr(library, name)
    entry.restype = restype
    entry.argtypes = list(arguments)
    return entry


class Provider:
    def __init__(self, path):
        library = c.CDLL(str(path))
        self.peek = PEEK(("peek_worker", library))
        self.open = function(library, "open_session", c.c_uint32)
        self.close = function(library, "close_session", c.c_int32, c.c_uint32)
        self.start = function(library, "start_callback", c.c_int32, c.c_uint32, CALLBACK,
                              c.c_void_p, c.c_int32)
        self.finish = function(library, "finish_callback", c.c_int32, c.c_uint32, c.c_int32,
                               c.POINTER(c.c_int32))
        self.count = function(library, "completed_count", c.c_uint32)


def collect(args, work):
    for name in ("provider.h", "provider.c", "bridge.cc", "bridge.rs"):
        shutil.copyfile(HERE / name, work / name)
    modules = {name: work / name for name in ("first.so", "second.so", "cpp.so", "rust.so")}
    invoke([args.cc, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC", "-pthread",
            "-shared", "-Wl,--no-undefined", "provider.c", "-o", modules["first.so"]], work)
    shutil.copyfile(modules["first.so"], modules["second.so"])
    invoke([args.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC",
            "-shared", "-Wl,--no-undefined", "bridge.cc", "-o", modules["cpp.so"]], work)
    invoke([args.rustc, "--edition=2021", "--crate-name=ffi_lifetime_bridge", "--crate-type=cdylib",
            "-Copt-level=2", "-Cpanic=unwind", "--remap-path-prefix", f"{work}=/fixture",
            "bridge.rs", "-o", modules["rust.so"]], work)
    apartments = [Provider(modules[name]) for name in ("first.so", "second.so")]
    cpp = c.CDLL(str(modules["cpp.so"]))
    rust = c.CDLL(str(modules["rust.so"]))
    function(rust, "initialize_bridge", None)()
    bridges = {"cpp": CALLBACK(("bridge", cpp)), "rust": CALLBACK(("bridge", rust)),
               "python": python_callback}

    traces = []
    previous_tokens = [0, 0]
    for bridge, (scenario, payload) in product(
        bridges, product(("normal", "failure", "canceled", "wrong_instance"), (-3, 0, 7, 127)),
    ):
        tokens = [provider.open() for provider in apartments]
        assert tokens[0] == tokens[1]  # Numerically equal tokens in distinct library scopes.
        for index, provider in enumerate(apartments):
            token = tokens[index]
            if previous_tokens[index] != 0:
                assert token != previous_tokens[index]
                assert provider.start(previous_tokens[index], python_callback, None, payload) == -3
            target = apartments[1 - index] if scenario == "wrong_instance" else provider
            context = Context(target.peek, scenario == "failure")
            callback = bridges[bridge]
            before = provider.count()
            assert provider.peek(token) == -6
            assert provider.start(token, callback, c.byref(context), payload) == 0
            assert provider.start(token, callback, c.byref(context), payload) == -4
            assert provider.close(token) == -4
            canceled = scenario == "canceled"
            result = c.c_int32(-101)
            disposition = provider.finish(token, canceled, c.byref(result))
            expected_value = {
                "normal": 1000 + token + payload, "failure": 70,
                "canceled": -101, "wrong_instance": -6,
            }[scenario]
            assert (disposition, result.value, provider.count() - before) == (
                int(canceled), expected_value, int(not canceled),
            )
            assert provider.finish(token, 0, c.byref(result)) == -3
            traces.append([bridge, scenario, payload, index, token, disposition, result.value,
                           provider.count() - before])
        for provider, token in zip(apartments, tokens):
            assert provider.close(token) == 0
            assert provider.start(token, python_callback, None, payload) == -3
            assert provider.peek(token) == -3
        previous_tokens = tokens
    assert len(traces) == 96
    assert [provider.count() for provider in apartments] == [36, 36]
    assert digest(modules["first.so"]) == digest(modules["second.so"])
    return {
        "tools": {
            name: invoke([getattr(args, name), "--version"], work).splitlines()[0]
            for name in ("cc", "cxx", "rustc")
        },
        "artifact_sha256": {name: digest(path) for name, path in modules.items()},
        "source_sha256": {
            name: digest(HERE / name)
            for name in ("provider.h", "provider.c", "bridge.cc", "bridge.rs", "run.py")
        },
        "native_traces": traces,
        "completed_callbacks": [provider.count() for provider in apartments],
        "stale_requests_with_new_session_open": (len(traces) // 2 - 1) * 2,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, tool in (("cc", "gcc"), ("cxx", "g++"), ("rustc", "rustc")):
        parser.add_argument(f"--{name}", default=tool)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-callback-") as temporary:
        evidence = collect(args, Path(temporary))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
