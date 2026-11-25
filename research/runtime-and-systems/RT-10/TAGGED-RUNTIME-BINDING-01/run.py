#!/usr/bin/env python3
"""Check exact operation binding with real native tagged-result runtime providers."""

import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
OPERATION = {"interface": "sample/u8", "result": ["value/u16", "denied/11", "busy/17"]}
FIXTURES = (
    ("baseline", 1, 5, "1.0"),
    ("alternate-wire-same-release", 2, 5, "1.0"),
    ("changed-value-same-release", 1, 6, "1.0"),
    ("same-semantics-new-release", 1, 5, "1.1"),
)


class Refusal(ValueError):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def identity(value):
    return sha256(encode(value)).hexdigest()


def artifact(path):
    return sha256(path.read_bytes()).hexdigest()


def decode(word, profile):
    if profile == 1:
        tag, payload = word >> 24, word & 65535
        reserved = word & 0x00FF0000
    else:
        assert profile == 2
        tag, payload = word & 255, word >> 16
        reserved = word & 0x0000FF00
    if reserved or tag not in (0, 1, 2):
        raise Refusal("malformed tagged result")
    if tag and payload != (11 if tag == 1 else 17):
        raise Refusal("invalid typed error payload")
    return ("value", "denied", "busy")[tag], payload


def expected(n, offset):
    return (("value", n + offset), ("denied", 11), ("busy", 17))[n % 3]


def build(root, compiler, name, profile, offset, release, level):
    path = root / f"{name}-{level[1:]}.so"
    subprocess.run(
        [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared", level,
         f"-DPROFILE={profile}", f"-DOFFSET={offset}", f'-DRELEASE="{release}"',
         str(HERE / "runtime.c"), "-o", str(path)],
        cwd=root, check=True, capture_output=True,
    )
    manifest = {
        "operation": identity(OPERATION), "abi": "x86_64-linux/u32-to-u32",
        "version": release, "encoding": profile, "runtime_artifact": artifact(path),
        "call_slot": "rt_sample",
    }
    value = {"path": path, "binding": manifest, "offset": offset}
    target = attach(path, manifest, manifest)
    words = [target(n) for n in range(256)]
    observations = [decode(word, profile) for word in words]
    assert observations == [expected(n, offset) for n in range(256)]
    legacy_differences = 0
    invalid_legacy_words = 0
    for word, observation in zip(words, observations, strict=True):
        try:
            received = decode(word, 1)
        except Refusal:
            invalid_legacy_words += 1
        else:
            legacy_differences += received != observation
    return value | {
        "observations": observations, "legacy_differences": legacy_differences,
        "legacy_invalid_words": invalid_legacy_words,
    }


def attach(path, proposed, requested):
    if proposed != requested:
        raise Refusal("exact operation/runtime binding mismatch")
    if proposed["runtime_artifact"] != artifact(path):
        raise Refusal("runtime bytes mismatch")
    runtime = ctypes.CDLL(str(path))
    release = runtime.rt_release
    release.argtypes = []
    release.restype = ctypes.c_char_p
    if release().decode() != proposed["version"]:
        raise Refusal("loaded release does not match")
    callable_operation = getattr(runtime, proposed["call_slot"])
    callable_operation.argtypes = [ctypes.c_uint32]
    callable_operation.restype = ctypes.c_uint32
    return callable_operation


def experiment(root):
    compiler = os.environ.get("CC", "gcc")
    builds = {}
    for level, (name, profile, offset, release) in product(("-O0", "-O2"), FIXTURES):
        builds[level, name] = build(root, compiler, name, profile, offset, release, level)

    controls = []
    attempts = 0
    for level in ("-O0", "-O2"):
        known = {name: builds[level, name] for name, *_ in FIXTURES}
        for requested, supplied in product(known, repeat=2):
            origin = known[supplied]
            wanted = known[requested]["binding"]
            try:
                callback = attach(origin["path"], origin["binding"], wanted)
            except Refusal as error:
                assert supplied != requested and str(error) == "exact operation/runtime binding mismatch"
            else:
                assert supplied == requested
                assert decode(callback(39), wanted["encoding"]) == expected(39, origin["offset"])
            attempts += 1
        baseline = known["baseline"]
        for field, substitution in (
            ("operation", identity(OPERATION | {"interface": "other-operation/u8"})),
            ("abi", "another-abi"),
            ("encoding", 2),
            ("version", "another-release"),
            ("call_slot", "other_symbol"),
        ):
            try:
                attach(baseline["path"], baseline["binding"] | {field: substitution}, baseline["binding"])
            except Refusal as error:
                assert str(error) == "exact operation/runtime binding mismatch"
            else:
                raise AssertionError(field)
            controls.append([level, field, "binding-refused"])
        other = known["alternate-wire-same-release"]
        assert baseline["binding"]["version"] == other["binding"]["version"]
        assert baseline["observations"] == other["observations"]
        assert other["legacy_invalid_words"] > 0
        assert baseline["observations"] == known["same-semantics-new-release"]["observations"]
        assert sum(a != b for a, b in zip(baseline["observations"],
                                         known["changed-value-same-release"]["observations"], strict=True)) == 86
        try:
            attach(other["path"], baseline["binding"], baseline["binding"])
        except Refusal as error:
            assert str(error) == "runtime bytes mismatch"
        else:
            raise AssertionError("a valid binding was paired with wrong bytes")
        false_release = baseline["binding"] | {"version": "ghost release"}
        try:
            attach(baseline["path"], false_release, false_release)
        except Refusal as error:
            assert str(error) == "loaded release does not match"
            controls.append([level, "loaded-release", str(error)])
        else:
            raise AssertionError("loaded release was not compared")

    rows = {
        f"{level}/{name}": {"exact_binding": value["binding"],
                            "observations": identity(value["observations"]),
                            "legacy_differences": value["legacy_differences"],
                            "legacy_invalid_words": value["legacy_invalid_words"]}
        for (level, name), value in builds.items()
    }
    return {
        "format": "tagged-runtime-binding-01",
        "gcc": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
        "native_calls": 256 * len(rows), "pair_admission_cases": attempts,
        "rows": rows, "changed_field_controls": controls,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-runtime-values-") as directory:
        evidence = experiment(Path(directory))
    out = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(out, encoding="utf-8")
    else:
        print(out, end="")
