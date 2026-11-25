#!/usr/bin/env python3
"""Check scoped C/Rust result reuse with exact directional closure receipts."""

from copy import deepcopy
import ctypes
from hashlib import sha256
from itertools import permutations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
PROFILES = ("c-wrap", "c-saturate", "rust-wrap", "rust-saturate")
PROJECTIONS = ("return-u8", "return-and-provider-marker")
DOMAINS = (255, 256)
CLOSURE_ROLES = {
    "source", "compiler_parts", "linker_parts", "observer_parts", "linked_object", "native_imports",
}
C_SOURCE = """unsigned char step(unsigned char value, unsigned char *marker) {
    *marker = 1;
    return EXPRESSION;
}
"""
RUST_SOURCE = """#![no_std]
#[no_mangle]
pub extern "C" fn step(value: u8, marker: &mut u8) -> u8 {
    *marker = 2;
    value.METHOD(1)
}
"""


def digest(data):
    return sha256(data).hexdigest()


def key(data):
    return digest(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())


def run(argv, root, packages=ENV):
    return subprocess.run(
        argv, cwd=root, env=packages, capture_output=True, text=True, check=True
    ).stdout


def binary(path):
    return digest(Path(path).read_bytes())


def tool(path):
    return {"artifact": binary(path), "name": Path(path).name}


def context(root):
    # Resolve the real Rust compiler and native support file before using the
    # controlled child environment. The rustup entry point is only a locator.
    rust_env = os.environ | {"LANG": "C", "LC_ALL": "C"}
    rustup_entry = os.environ.get("RUSTC", "rustc")
    sysroot = Path(run([rustup_entry, "--print", "sysroot"], root, rust_env).strip())
    rustc = sysroot / "bin/rustc"
    rust_version = run([str(rustc), "-Vv"], root).splitlines()
    rust_target = next(line.split(": ", 1)[1] for line in rust_version if line.startswith("host: "))
    core, = sorted((sysroot / "lib/rustlib" / rust_target / "lib").glob("libcore-*.rlib"))
    rust_libraries = sorted((sysroot / "lib").glob("*.so*"))
    assert rust_libraries
    gcc = shutil.which("gcc", path=ENV["PATH"])
    cc1 = run([gcc, "-print-prog-name=cc1"], root).strip()
    target = run([gcc, "-dumpmachine"], root).strip()
    tools = {
        "c": [tool(gcc), tool(cc1), tool("/usr/bin/as")],
        "rust": [tool(rustc), tool(core), *map(tool, rust_libraries)],
        "link": [tool(gcc), tool("/usr/bin/ld"), tool("/usr/bin/readelf"), tool("/usr/bin/nm")],
        "observation": [tool(sys.executable)],
    }
    return gcc, str(rustc), target, rust_target, tools, rust_version


def build(root, name, ctx):
    gcc, rustc, target, rust_target, tools, rust_version = ctx
    language, mode = name.split("-", 1)
    saturated = mode == "saturate"
    work = root / name
    work.mkdir()
    if language == "c":
        expression = "value == 255 ? value : value + 1u" if saturated else "value + 1u"
        raw = C_SOURCE.replace("EXPRESSION", expression)
        filename = "step.c"
        argv = [gcc, "-std=c11", "-O2", "-Werror", "-fPIC", "-c", filename, "-o", "step.o"]
        version = run([gcc, "--version"], work).splitlines()[0]
        language_profile = "c11-u8/" + mode
    else:
        method = "saturating_add" if saturated else "wrapping_add"
        raw = RUST_SOURCE.replace("METHOD", method)
        filename = "step.rs"
        argv = [rustc, "--edition=2021", "--crate-type=lib", "--emit=obj", "-C", "opt-level=2",
                "-C", "relocation-model=pic", "-C", "panic=abort", "--target", rust_target,
                filename, "-o", "step.o"]
        version = rust_version[0]
        language_profile = "rust2021-u8/" + mode
    (work / filename).write_text(raw, encoding="utf-8")
    run(argv, work)
    assert run(["nm", "-u", "step.o"], work) == ""
    link_argv = [gcc, "-shared", "-nostdlib", "step.o", "-o", "step.so"]
    run(link_argv, work)
    assert "(NEEDED)" not in run(["readelf", "-d", "step.so"], work)
    product = work / "step.so"
    dynamic = ctypes.CDLL(str(product))
    entry = dynamic.step
    entry.argtypes = [ctypes.c_ubyte, ctypes.POINTER(ctypes.c_ubyte)]
    entry.restype = ctypes.c_ubyte
    values = []
    for value in range(256):
        marker = ctypes.c_ubyte()
        result = entry(value, ctypes.byref(marker))
        assert result == (min(value + 1, 255) if saturated else (value + 1) % 256)
        assert marker.value == (1 if language == "c" else 2)
        values.append([result, marker.value])
    closure = {
        "source": digest(raw.encode()), "compiler_parts": tools[language],
        "linker_parts": tools["link"], "observer_parts": tools["observation"],
        "linked_object": binary(work / "step.o"), "native_imports": [],
    }
    descriptor = {
        "profile": language_profile, "tool_version": version,
        "target": target if language == "c" else rust_target,
        "compile_args": [Path(argv[0]).name, *argv[1:]],
        "link_args": [Path(link_argv[0]).name, *link_argv[1:]],
        "build_environment": ENV,
        "view": key(closure),
    }
    return {
        "closure": closure, "descriptor": descriptor, "key": key(descriptor),
        "subject": binary(product), "values": values,
    }


def projected(action, projection, count):
    values = action["values"][:count]
    if projection == "return-u8":
        return [row[0] for row in values]
    assert projection == "return-and-provider-marker"
    return values


def bridge(source, target, projection, count):
    original = projected(source, projection, count)
    destination = projected(target, projection, count)
    if original != destination:
        return None
    return {
        "scheme": "exact-finite-compatibility/1", "origin": source["key"],
        "destination": target["key"], "direction": "origin-to-destination",
        "source_subject": source["subject"], "destination_subject": target["subject"],
        "source_closure": source["descriptor"]["view"], "destination_closure": target["descriptor"]["view"],
        "domain": [0, count - 1], "projection": projection,
        "checker": "independent-native-calls-and-oracle/1", "results": key(original),
    }


def admit(receipt, source, destination, projection, count, *, checked="scoped-observations"):
    for action in (source, destination):
        if (set(action["closure"]) != CLOSURE_ROLES
                or action["descriptor"]["view"] != key(action["closure"])
                or action["key"] != key(action["descriptor"])):
            return "closure-refused"
    if checked == "exact-artifact":
        return "exact-miss" if source["key"] != destination["key"] else "action-hit"
    expected = bridge(source, destination, projection, count)
    return "scoped-hit" if receipt is not None and receipt == expected else "bridge-refused"


def experiment(root):
    ctx = context(root)
    actions = {name: build(root, name, ctx) for name in PROFILES}
    assert len({action["key"] for action in actions.values()}) == len(PROFILES)
    rows = []
    for source_name, target_name in permutations(PROFILES, 2):
        source, target = actions[source_name], actions[target_name]
        for projection in PROJECTIONS:
            for count in DOMAINS:
                receipt = bridge(source, target, projection, count)
                decision = admit(receipt, source, target, projection, count)
                same_mode = source_name.endswith("wrap") == target_name.endswith("wrap")
                same_language = source_name.split("-", 1)[0] == target_name.split("-", 1)[0]
                expected = (same_mode or count == 255) and (projection == "return-u8" or same_language)
                assert decision == ("scoped-hit" if expected else "bridge-refused")
                rows.append({
                    "origin": source_name, "destination": target_name, "projection": projection,
                    "inputs": count, "disposition": decision,
                })
    source, destination = actions["c-wrap"], actions["rust-wrap"]
    receipt = bridge(source, destination, "return-u8", 256)
    controls = {}
    for field in receipt:
        changed = deepcopy(receipt)
        changed.pop(field)
        controls[field] = admit(changed, source, destination, "return-u8", 256)
    assert set(controls.values()) == {"bridge-refused"}
    obscure = deepcopy(destination)
    obscure["closure"].pop("linked_object")
    assert admit(receipt, source, obscure, "return-u8", 256) == "closure-refused"
    obscure["descriptor"]["view"] = key(obscure["closure"])
    obscure["key"] = key(obscure["descriptor"])
    assert admit(receipt, source, obscure, "return-u8", 256) == "closure-refused"
    assert admit(receipt, destination, source, "return-u8", 256) == "bridge-refused"
    assert admit(receipt, source, destination, "return-u8", 256, checked="exact-artifact") == "exact-miss"
    return {
        "format": "cross-language-receipts-01", "actions": {
            name: {**action, "values": key(action["values"])} for name, action in actions.items()
        },
        "native_observations": sum(len(action["values"]) for action in actions.values()),
        "rows": rows, "sample_receipt": receipt, "removed_field_controls": controls,
        "wrong_direction": "bridge-refused", "incomplete_closure": "closure-refused",
        "rekeyed_incomplete_closure": "closure-refused",
        "object_request": "exact-miss",
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-cross-language-") as directory:
        ledger = experiment(Path(directory))
    text = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
