"""Compare six lowering paths for ordered commit and rollback observations."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
TEMPLATES = ("observer.cpp", "observer.go", "observer.rs", "Observer.java", "observer.py")
COMPILERS = ("cxx", "clang", "go", "rustc", "java")
MUTATIONS = ("ERASE_RELEASE_EFFECT", "ERASE_CLEANUP_ERROR", "SKIP_RESTORE")


def run(command, cwd, *, data=None, extra_env=None):
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1764000000"}
    env.update(extra_env or {})
    return subprocess.run(
        command, cwd=cwd, input=data, env=env, text=True, check=True, capture_output=True, timeout=120,
    ).stdout


def digest(value):
    return sha256(value).hexdigest()


def reference(contract, stimulus):
    initial, delta, acquisition, write, rollback, release = stimulus
    e, primary, cleanup = (contract[field] for field in ("events", "primary", "cleanup"))
    if not acquisition:
        return primary["acquire"], 0, -1, initial, 0, e["acquire_denied"]

    proposed = initial + delta
    final = initial
    value = -1
    errors = cleanup["release"] if not release else 0
    if proposed < 0 or proposed > contract["maximum"]:
        cause, action = primary["range"], ("range",)
    elif write:
        cause, action = 0, ("committed",)
        final = value = proposed
    elif rollback:
        cause, action = primary["write"], ("write_partial", "rolled_back")
    else:
        cause, action = primary["write"], ("write_partial", "rollback_failed")
        final = proposed
        errors += cleanup["rollback"]
    ordered = ("acquired", *action, "released" if release else "release_failed")
    return cause, errors, value, final, 1 - release, *(e[name] for name in ordered)


def emit(contract, work):
    if contract["operation"] != "checked_write" or not 0 <= contract["maximum"] <= 255:
        raise ValueError("unsupported operation or byte domain")
    substitutions = {"MAX": contract["maximum"]}
    for key, prefix in (("primary", "P"), ("cleanup", "C"), ("events", "E")):
        values = contract[key]
        if any(type(value) is not int or not 1 <= value <= 255 for value in values.values()):
            raise ValueError(key)
        substitutions.update({f"{prefix}_{name.upper()}": value for name, value in values.items()})
    if set(contract["cleanup"].values()) != {1, 2}:
        raise ValueError("cleanup outcomes require distinct bits")
    for name in TEMPLATES:
        source = (HERE / f"{name}.in").read_text(encoding="utf-8")
        native = re.sub(r"@([A-Z_]+)@", lambda match: str(substitutions[match[1]]), source)
        (work / name).write_text(native, encoding="utf-8")


def build(args, work):
    commands = {}
    for optimization in (0, 2):
        path = work / f"cpp-O{optimization}"
        run([args.cxx, "-std=c++20", f"-O{optimization}", "-Wall", "-Wextra", "-Werror",
             "observer.cpp", "-o", path], work)
        commands[f"cpp-O{optimization}"] = ([path], path)
    for fault in MUTATIONS:
        path = work / fault
        run([args.cxx, "-std=c++20", "-O2", f"-D{fault}", "observer.cpp", "-o", path], work)
        commands[fault] = ([path], path)
    llvm = work / "observer.ll"
    run([args.clang, "-std=c++20", "-O2", "-S", "-emit-llvm",
         "observer.cpp", "-o", llvm], work)
    body = llvm.read_text(encoding="utf-8")
    assert 'target triple = "x86_64' in body and "@main(" in body
    from_llvm = work / "from-llvm"
    run([args.clang, "-O2", llvm, "-o", from_llvm], work)
    commands["clang-llvm"] = ([from_llvm], from_llvm)
    rust = work / "rust"
    run([args.rustc, "--edition=2021", "-Copt-level=2", "-Coverflow-checks=yes",
         "--remap-path-prefix", f"{work}=/fixture", "observer.rs", "-o", rust], work)
    commands["rust-checked"] = ([rust], rust)
    go = work / "go"
    go_env = {
        "GOCACHE": str(args.go_cache.resolve()), "CGO_ENABLED": "0", "GOAMD64": "v1",
        "GOTOOLCHAIN": "local", "GOENV": "off", "GOPROXY": "off", "GOSUMDB": "off",
        "GOMAXPROCS": "2", "GOFLAGS": "", "GOWORK": "off", "GOOS": "linux", "GOARCH": "amd64",
    }
    run([args.go, "build", "-trimpath", "-buildvcs=false", "-ldflags=-buildid=", "-o", go,
         "observer.go"], work, extra_env=go_env)
    commands["go-standalone"] = ([go], go)
    run([args.java, "-m", "jdk.compiler/com.sun.tools.javac.Main",
         "-source", "21", "-target", "21", "Observer.java"], work)
    java_class = work / "Observer.class"
    assert java_class.read_bytes()[:8] == bytes.fromhex("cafebabe00000041")
    commands["java-interpreted"] = ([args.java, "-Xint", "-cp", ".", "Observer"], java_class)
    commands["java-default"] = ([args.java, "-cp", ".", "Observer"], java_class)
    script = work / "observer.py"
    commands["python"] = ([sys.executable, "-B", script], script)
    return commands, digest(llvm.read_bytes())


def report(actual, expected):
    assert len(actual) == len(expected)
    assert all(6 <= len(row) <= 9 for row in actual)
    names = ("primary", "cleanup", "value", "state", "ownership", "ordered_effects")
    differences = dict.fromkeys(names, 0)
    wrong = 0
    misses = Counter()
    for a, b in zip(actual, expected):
        if a == b:
            continue
        wrong += 1
        for field, x, y in zip(names, (*a[:5], a[5:]), (*b[:5], b[5:])):
            differences[field] += x != y
        misses["primary_and_value"] += (a[0], a[2]) == (b[0], b[2])
        misses["primary_value_state_and_ownership"] += (a[0], *a[2:5]) == (b[0], *b[2:5])
        misses["all_scalars"] += a[:5] == b[:5]
    normalized = json.dumps(actual, separators=(",", ":")).encode("utf-8")
    return {
        "observations": len(actual), "wrong": wrong, "differences": differences,
        "wrong_rows_missed_by_projection": dict(misses), "trace_sha256": digest(normalized),
    }


def collect(args, work):
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    emit(contract, work)
    commands, ir_digest = build(args, work)
    cases = list(product(
        (0, 1, 63, 127, 128, 254, 255), (-255, -129, -1, 0, 1, 128, 255), *[(0, 1)] * 4,
    ))
    inputs = "".join(" ".join(map(str, case)) + "\n" for case in cases)
    expected = [reference(contract, case) for case in cases]
    ledgers = {}
    for profile, (command, artifact) in commands.items():
        output = run(command, work, data=inputs)
        actual = [tuple(map(int, row.split())) for row in output.splitlines()]
        ledgers[profile] = {
            **report(actual, expected), "artifact_sha256": digest(artifact.read_bytes()),
        }
    assert all(e["wrong"] == 0 for p, e in ledgers.items() if p not in MUTATIONS)
    assert len({e["trace_sha256"] for p, e in ledgers.items() if p not in MUTATIONS}) == 1
    omitted_effect = ledgers["ERASE_RELEASE_EFFECT"]
    omitted_error = ledgers["ERASE_CLEANUP_ERROR"]
    skipped_restore = ledgers["SKIP_RESTORE"]
    assert omitted_effect["wrong"] == omitted_effect["wrong_rows_missed_by_projection"]["all_scalars"] > 0
    assert omitted_error["wrong"] == omitted_error["differences"]["cleanup"] > 0
    assert omitted_error["differences"]["ordered_effects"] == 0
    assert skipped_restore["wrong"] == skipped_restore["differences"]["state"] > 0
    assert skipped_restore["differences"]["ordered_effects"] == 0
    return {
        "versions": {
            name: run([getattr(args, name), "version" if name == "go" else "--version"], work).splitlines()[0]
            for name in COMPILERS
        },
        "sources": {path.name: digest(path.read_bytes()) for path in sorted(HERE.glob("*.in"))}
        | {name: digest((HERE / name).read_bytes()) for name in ("contract.json", "run.py")},
        "input_count": len(cases), "input_sha256": digest(inputs.encode("ascii")),
        "generated_llvm_sha256": ir_digest,
        "generated_sources": {name: digest((work / name).read_bytes()) for name in TEMPLATES},
        "profiles": ledgers,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, tool in zip(COMPILERS, ("g++", "clang", "go", "rustc", "java")):
        parser.add_argument(f"--{name}", default=tool)
    parser.add_argument("--go-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-cross-backend-") as temporary:
        evidence = collect(args, Path(temporary))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
