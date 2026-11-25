#!/usr/bin/env python3
"""Reproduce scoped static, linked ELF and glibc runtime-loading FFI results."""
import argparse
from hashlib import sha256
from itertools import permutations
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
PROVIDERS = {"A": 11, "B": 29, "C": 11}
INPUTS = (-123456, -1, 0, 1, 9, 1024, 123450)
MODES = ("base", "base-keep", "separate")
ENV = {key: value for key, value in os.environ.items() if not key.startswith("LD_")}
ENV.update({"LC_ALL": "C", "TZ": "UTC"})
CFLAGS = ("-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror")


def call(command, root):
    result = subprocess.run(command, cwd=root, env=ENV, capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result.stdout.strip()


def fingerprint(path):
    return sha256(path.read_bytes()).hexdigest()


def build(root):
    for name, value in PROVIDERS.items():
        directory = root / name
        directory.mkdir()
        source = directory / "identity.c"
        source.write_text('__attribute__((used, visibility("hidden"))) '
                          f'const char fixture_identity[] = "provider {name}";\n')
        leaf = directory / "libfixture_leaf.so"
        call(["gcc", *CFLAGS, "-fPIC", "-shared", f"-DVALUE={value}", "-Wl,-z,defs",
              "-Wl,-soname,libfixture_leaf.so", HERE / "leaf.c", source, "-o", leaf], root)
        call(["gcc", *CFLAGS, "-fPIC", "-shared", "-Wl,-z,defs",
              "-Wl,-soname,liboperation.so", "-Wl,-rpath,$ORIGIN",
              f"-Wl,--version-script={HERE / 'operation.map'}",
              HERE / "operation.c", f"-L{directory}", "-lfixture_leaf",
              "-o", directory / "liboperation.so"], root)
        call(["gcc", *CFLAGS, "-DSTATIC_FIXTURE", "-c", HERE / "operation.c",
              "-o", directory / "operation.o"], root)
        call(["gcc", *CFLAGS, f"-DVALUE={value}", "-c", HERE / "leaf.c",
              "-o", directory / "leaf.o"], root)
        archive = directory / "liboperation.a"
        call(["ar", "rcsD", archive, directory / "operation.o", directory / "leaf.o"], root)
        call(["gcc", *CFLAGS, HERE / "static.c", archive, "-o", directory / "static"], root)
        call(["gcc", *CFLAGS, HERE / "linked.c", f"-L{directory}", "-loperation",
              "-Wl,-rpath,$ORIGIN", f"-Wl,-rpath-link,{directory}", "-ldl",
              "-o", directory / "linked"], root)
    call(["gcc", *CFLAGS, HERE / "dynamic.c", "-ldl", "-o", root / "dynamic"], root)


def dynamic_inventory(path, root):
    report = call(["readelf", "-dW", path], root)
    inventory = {}
    for role in ("NEEDED", "SONAME", "RUNPATH", "RPATH"):
        values = re.findall(rf"\({role}\).*?\[([^\]]+)\]", report)
        if values:
            inventory[role.lower()] = values
    return inventory


def audit(root):
    results = {}
    for name in PROVIDERS:
        directory = root / name
        plugin = directory / "liboperation.so"
        leaf = directory / "libfixture_leaf.so"
        symbols = call(["readelf", "--dyn-syms", "--wide", plugin], root)
        exports = set(re.findall(
            r"\b(?:apply@+FIXTURE_[12]\.0|fixture_provider_address@@FIXTURE_2\.0)\b", symbols))
        leaf_symbols = call(["readelf", "--dyn-syms", "--wide", leaf], root)
        leaf_exports = re.findall(r"FUNC\s+GLOBAL\s+DEFAULT\s+\d+\s+(\w+)", leaf_symbols)
        assert leaf_exports == ["fixture_leaf"] and "fixture_identity" not in leaf_symbols
        assert exports == {"apply@FIXTURE_1.0", "apply@@FIXTURE_2.0",
                           "fixture_provider_address@@FIXTURE_2.0"}
        assert "apply_v1" not in symbols and "apply_v2" not in symbols
        archive_members = call(["ar", "t", directory / "liboperation.a"], root).splitlines()
        assert archive_members == ["operation.o", "leaf.o"]
        assert " T fixture_leaf" in call(["nm", directory / "static"], root)
        static = dynamic_inventory(directory / "static", root)
        linked = dynamic_inventory(directory / "linked", root)
        plugin_dynamic = dynamic_inventory(plugin, root)
        leaf_dynamic = dynamic_inventory(leaf, root)
        assert static == {"needed": ["libc.so.6"]}, static
        assert linked == {"needed": ["liboperation.so", "libc.so.6"], "runpath": ["$ORIGIN"]}, linked
        assert plugin_dynamic == {"needed": ["libfixture_leaf.so"], "soname": ["liboperation.so"],
                                  "runpath": ["$ORIGIN"]}, plugin_dynamic
        assert leaf_dynamic == {"soname": ["libfixture_leaf.so"]}, leaf_dynamic
        results[name] = {
            "plugin_sha256": fingerprint(plugin), "leaf_sha256": fingerprint(leaf),
            "plugin_exports": sorted(exports), "leaf_exports": leaf_exports, "archive_members": archive_members,
            "archive_sha256": fingerprint(directory / "liboperation.a"),
            "static": static, "linked": linked, "plugin": plugin_dynamic, "leaf": leaf_dynamic,
        }
    assert len({entry["plugin_sha256"] for entry in results.values()}) == 1
    assert len({entry["leaf_sha256"] for entry in results.values()}) == 3
    return results


def expected_snapshot(mode, phase):
    if mode == "separate":
        return {"both": (1, 1, 1, 1), "close-first": (0, 1, 0, 1),
                "close-both": (0, 0, 0, 0)}[phase]
    keep = int(mode == "base-keep")
    return {"both": (1, 1, 1, 0), "close-first": (keep, 1, 1, 0),
            "close-both": (keep, 0, keep, 0)}[phase]


def observe_dynamic(root, inventory, mode, first, second, value):
    plugins = [root / name / "liboperation.so" for name in (first, second)]
    leaves = [root / name / "libfixture_leaf.so" for name in (first, second)]
    lines = call([root / "dynamic", mode, *plugins, *leaves, str(value)], root).splitlines()
    calls, maps = {}, {}
    for line in lines:
        tag, phase, *details = line.split("\t")
        if tag == "maps":
            assert phase not in maps
            snapshot = tuple(map(int, details))
            assert snapshot == expected_snapshot(mode, phase), (mode, phase, snapshot)
            maps[phase] = snapshot
            continue
        assert tag == "call" and phase not in calls
        ns, current, legacy, versioned = map(int, details[:4])
        resolved = Path(details[4])
        declared = first if phase == "first" else second
        expected = declared if mode == "separate" else first
        assert resolved == root / expected / "libfixture_leaf.so", (mode, phase, resolved)
        leaf_sha = fingerprint(resolved)
        assert leaf_sha == inventory[expected]["leaf_sha256"]
        assert current == versioned == value + PROVIDERS[expected] + 200
        assert legacy == value + PROVIDERS[expected] + 100
        exact_binding = leaf_sha == inventory[declared]["leaf_sha256"]
        semantic_match = current == value + PROVIDERS[declared] + 200
        assert exact_binding == (expected == declared)
        assert semantic_match == (PROVIDERS[expected] == PROVIDERS[declared])
        calls[phase] = {"namespace": ns, "default": current, "legacy": legacy,
                        "explicit_current": versioned, "leaf": expected,
                        "leaf_sha256": leaf_sha, "unknown_version_refused": True,
                        "declared_provider": declared, "exact_binding": exact_binding,
                        "matches_declared_semantics": semantic_match}
    assert list(calls) == ["first", "second", "survivor"]
    assert list(maps) == ["both", "close-first", "close-both"]
    if mode == "separate":
        assert calls["first"]["namespace"] != calls["second"]["namespace"]
        assert calls["first"]["namespace"] > 0 and calls["second"]["namespace"] > 0
    else:
        assert all(item["namespace"] == 0 for item in calls.values())
    assert calls["survivor"] == calls["second"]
    return {"mode": mode, "order": [first, second], "input": value, "calls": calls, "mappings": maps}


def observe_linked(root):
    rows = []
    for name, offset in PROVIDERS.items():
        directory = root / name
        for value in INPUTS:
            current, path = call([directory / "linked", str(value)], root).split("\t")
            assert Path(path) == directory / "libfixture_leaf.so"
            assert int(current) == value + offset + 200
            legacy, explicit = map(int, call([directory / "static", str(value)], root).split("\t"))
            assert (legacy, explicit) == (value + offset + 100, value + offset + 200)
            rows.append({"provider": name, "input": value, "linked": int(current),
                         "archive_legacy": legacy, "archive_current": explicit})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-loader-") as scratch:
        root = Path(scratch)
        build(root)
        inventory = audit(root)
        controls = observe_linked(root)
        observations = [observe_dynamic(root, inventory, mode, first, second, value)
                        for mode in MODES for first, second in permutations(PROVIDERS, 2)
                        for value in INPUTS]
        later = [row["calls"]["second"] for row in observations]
        summary = {"dynamic_processes": len(observations), "calls": len(later) * 3,
                   "mapping_snapshots": len(later) * 3, "linked_and_archive_pairs": len(controls),
                   "exact_later_binding": sum(row["exact_binding"] for row in later),
                   "semantic_later_mismatch": sum(not row["matches_declared_semantics"] for row in later),
                   "semantic_match_wrong_identity": sum(row["matches_declared_semantics"] and
                                                        not row["exact_binding"] for row in later)}
        versions = {
            "gcc": call(["gcc", "--version"], root).splitlines()[0],
            "binutils": call(["ld", "--version"], root).splitlines()[0],
            "glibc": call(["getconf", "GNU_LIBC_VERSION"], root),
            "machine": call(["uname", "-m"], root),
        }
        record = {"versions": versions, "elf": inventory, "summary": summary,
                  "runtime": observations, "linked_archive": controls}
    args.out.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
