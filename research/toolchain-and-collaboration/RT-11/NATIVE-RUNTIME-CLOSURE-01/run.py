#!/usr/bin/env python3
"""Replay a bounded native test action and the policy governing its cache."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


BASE_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
MID = "libllmlang_fixture_mid.so"
LEAF = "libllmlang_fixture_leaf.so"
SOURCES = {
    "leaf.c": "int leaf(void) { return VALUE; }\n",
    "mid.c": "extern int leaf(void); int mid(void) { return leaf(); }\n",
    "driver.c": '#include <stdio.h>\nextern int mid(void);\n'
                'int main(void) { printf("%d\\n", mid()); return 0; }\n',
}


def command(args, root, env=BASE_ENV, *, check=True):
    return subprocess.run(
        args, cwd=root, env=env, capture_output=True, text=True, check=check
    )


def digest(data):
    return hashlib.sha256(data).hexdigest()


def key(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def hash_file(path):
    return digest(path.read_bytes())


def tool_info(path, root):
    return {
        "name": Path(path).name,
        "artifact": hash_file(Path(path)),
        "version": command([path, "--version"], root).stdout.splitlines()[0],
    }


def build(root, gcc, readelf):
    for name in ("base", "first", "second", "third", "variants"):
        (root / name).mkdir()
    for name, content in SOURCES.items():
        (root / name).write_text(content, encoding="utf-8")

    def compile_source(*args):
        command([gcc, "-Werror", *args], root)

    for value in (17, 29):
        compile_source(
            "-shared", "-fPIC", f"-DVALUE={value}", "leaf.c",
            f"-Wl,-soname,{LEAF}", "-o", f"variants/{value}.so",
        )
    shutil.copyfile(root / "variants/17.so", root / "second" / LEAF)
    shutil.copyfile(root / "variants/29.so", root / "third" / LEAF)
    compile_source(
        "-shared", "-fPIC", "mid.c", f"-Wl,-soname,{MID}",
        f"-Wl,-l:{LEAF}", "-Lsecond", "-o", f"base/{MID}",
    )
    compile_source(
        "driver.c", f"-Wl,-l:{MID}", "-Lbase", "-Wl,-rpath-link,second",
        "-o", "driver",
    )

    def needed(path):
        output = command([readelf, "-d", path], root).stdout
        assert "RUNPATH" not in output and "RPATH" not in output
        return re.findall(r"\(NEEDED\).*\[(.*?)\]", output)

    edges = {"driver": needed("driver"), MID: needed(f"base/{MID}")}
    assert MID in edges["driver"] and LEAF not in edges["driver"]
    assert LEAF in edges[MID]
    headers = command([readelf, "-l", "driver"], root).stdout
    loader = re.search(r"Requesting program interpreter: ([^\]]+)", headers)[1]
    return loader, edges


def selected_runtime(root, loader, env):
    result = command([loader, "--list", "./driver"], root, env, check=False)
    if result.returncode != 0:
        return None

    def location(raw):
        path = (root / raw).resolve()
        return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)

    selected = [
        {"soname": name, "path": location(path), "artifact": hash_file(root / path)}
        for name, path in re.findall(r"^\s+(\S+) => (\S+) \(", result.stdout, re.M)
    ]
    assert {MID, LEAF, "libc.so.6"} <= {entry["soname"] for entry in selected}
    return selected


def search_prefix(root, paths, known):
    if not known:
        return None
    prefix = []
    for path in paths:
        candidate = root / path / LEAF
        artifact = hash_file(candidate) if candidate.exists() else None
        prefix.append({"path": f"{path}/{LEAF}", "artifact": artifact})
        if artifact is not None:
            break
    return prefix


def observation(root, loader, env):
    run = command([loader, "./driver"], root, env, check=False)
    return {
        "exit": run.returncode,
        "stdout": run.stdout,
        "missing_fixture_leaf": LEAF in run.stderr,
    }


def replay(root):
    gcc = shutil.which("gcc", path=BASE_ENV["PATH"])
    readelf = shutil.which("readelf", path=BASE_ENV["PATH"])
    loader, edges = build(root, gcc, readelf)
    driver = hash_file(root / "driver")
    leaf17 = hash_file(root / "variants/17.so")
    leaf29 = hash_file(root / "variants/29.so")
    runtime = tool_info(loader, root)
    target = command([gcc, "-dumpmachine"], root).stdout.strip()
    inputs = {
        "subject": driver,
        "tool": runtime,
        "configuration": {"argv": [loader, "./driver"], "expected_stdout": "17\n"},
        "target": target,
        "working_directory": "fixture-root",
    }
    a = ("base", "first", "second", "third")
    b = ("base", "first", "third", "second")
    c = ("base", "first")
    cases = (
        # case, ordered directories, state of first candidate, discovery, allowlist
        ("warm-original", a, None, True, (leaf17, leaf29)),
        ("same-request", a, None, True, (leaf17, leaf29)),
        ("reverse-selection", b, None, True, (leaf17, leaf29)),
        ("restore-order", a, None, True, (leaf17, leaf29)),
        ("shadow-with-29", a, 29, True, (leaf17, leaf29)),
        ("unknown-at-known-key", a, 29, False, (leaf17, leaf29)),
        ("shadow-with-17", a, 17, True, (leaf17, leaf29)),
        ("remove-shadow", a, None, True, (leaf17, leaf29)),
        ("resolve-29-again", b, None, True, (leaf17, leaf29)),
        ("policy-narrows", b, None, True, (leaf17,)),
        ("denial-repeated", b, None, True, (leaf17,)),
        ("unknown-despite-policy", b, None, False, (leaf17,)),
        ("missing-leaf", c, None, True, (leaf17, leaf29)),
        ("missing-leaf-repeated", c, None, True, (leaf17, leaf29)),
    )
    cache = {}
    rows = []
    for name, paths, shadow, complete, allowlist in cases:
        first = root / "first" / LEAF
        first.unlink(missing_ok=True)
        if shadow is not None:
            shutil.copyfile(root / f"variants/{shadow}.so", first)
        env = {**BASE_ENV, "LD_LIBRARY_PATH": ":".join(paths)}
        clean = observation(root, loader, env)
        oracle_runtime = selected_runtime(root, loader, env)
        prefix = search_prefix(root, paths, complete)
        closure = oracle_runtime if complete else None
        before = set(cache)
        receipt_key = None
        if closure is None:
            verdict = "uncached" if not complete else "load-error"
        else:
            selected = next(row for row in closure if row["soname"] == LEAF)
            assert prefix[-1] == {"path": selected["path"], "artifact": selected["artifact"]}
            if selected["artifact"] not in allowlist:
                verdict = "policy-denied"
            else:
                action = {
                    **inputs, "environment": env,
                    "runtime_closure": closure, "leaf_search_prefix": prefix,
                    "policy_allowlist": sorted(allowlist),
                }
                receipt_key = key(action)
                verdict = "hit" if receipt_key in cache else "publish"
                if receipt_key in cache:
                    assert cache[receipt_key] == clean
                else:
                    cache[receipt_key] = clean
        if verdict != "publish":
            assert set(cache) == before
        rows.append({
            "case": name, "environment": env,
            "allowlist": sorted(allowlist),
            "discovered_leaf_prefix": prefix,
            "oracle_runtime": oracle_runtime,
            "action_key": receipt_key, "decision": verdict, "clean": clean,
            "test_passed": clean == {"exit": 0, "stdout": "17\n", "missing_fixture_leaf": False},
        })

    by_name = {row["case"]: row for row in rows}
    assert [row["decision"] for row in rows] == [
        "publish", "hit", "publish", "hit", "publish", "uncached", "publish",
        "hit", "hit", "policy-denied", "policy-denied", "uncached", "load-error", "load-error",
    ]
    assert len(cache) == 4 and hash_file(root / "driver") == driver
    for before_name, after_name in [
        ("warm-original", "reverse-selection"),
        ("warm-original", "shadow-with-29"),
    ]:
        before = by_name[before_name]
        after = by_name[after_name]
        assert before["clean"]["stdout"] == "17\n" and after["clean"]["stdout"] == "29\n"
        assert before["action_key"] != after["action_key"]
    assert by_name["warm-original"]["environment"] == by_name["shadow-with-29"]["environment"]
    assert sorted(by_name["warm-original"]["environment"]["LD_LIBRARY_PATH"].split(":")) == sorted(
        by_name["reverse-selection"]["environment"]["LD_LIBRARY_PATH"].split(":")
    )
    assert by_name["unknown-at-known-key"]["clean"] == by_name["shadow-with-29"]["clean"]
    assert by_name["missing-leaf"]["clean"]["missing_fixture_leaf"]
    assert by_name["policy-narrows"]["clean"] == by_name["reverse-selection"]["clean"]
    return {
        "format": "native-runtime-closure-01",
        "platform": {"system": os.uname().sysname, "machine": os.uname().machine},
        "fixture_compiler": tool_info(gcc, root),
        "fixture_inspector": tool_info(readelf, root),
        "fixed_action_inputs": inputs,
        "needed": edges,
        "rows": rows,
        "published_receipts": len(cache),
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="llmlang-runtime-") as directory:
        result = replay(Path(directory))
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
