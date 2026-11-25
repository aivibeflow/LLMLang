#!/usr/bin/env python3
"""Replay a pinned C callback lifecycle through Go cgo and Java FFM consumers."""
import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "FFI-CALLBACK-LIFETIME-01"
ENV = {key: value for key, value in os.environ.items()
       if not key.startswith(("LD_", "GO", "CGO", "FIXTURE_", "JDK_", "JAVA_", "_JAVA_"))}
ENV.update({"LC_ALL": "C", "TZ": "UTC"})


def run(command, working, env=ENV, *, check=True, timeout=90):
    result = subprocess.run(command, cwd=working, env=env, capture_output=True,
                            text=True, timeout=timeout)
    if check:
        assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
    return result


def build(args, root):
    library = root / "libcallbackfixture.so"
    run(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
         "-pthread", "-Wl,-z,defs", PRIOR / "provider.c", PRIOR / "driver.c", "-o", library], root)
    for file in (HERE / "main.go", HERE / "bridge.c", HERE / "bridge.h", PRIOR / "fixture.h"):
        shutil.copyfile(file, root / file.name)
    cache = args.go_cache or root / "cache"
    cache.mkdir(exist_ok=True)
    cgo_environment = {**ENV, "CGO_ENABLED": "1", "GO111MODULE": "off", "GOTOOLCHAIN": "local",
                       "GOCACHE": str(cache), "CGO_LDFLAGS": f"-L{root} -lcallbackfixture"}
    for profile, experiment in (("go-cgo", ""), ("go-cgocheck2", "cgocheck2")):
        run([args.go, "build", "-trimpath", "-o", root / profile, "."], root,
            {**cgo_environment, "GOEXPERIMENT": experiment}, timeout=90)
    run([args.java, "com.sun.tools.javac.Main", "--source", "21", "--enable-preview",
         "-d", root, HERE / "ManagedCallbacks.java"], root)
    return library


def oracle(payload, offset):
    def outcome(worker, value, context):
        return -77 if value == -7 else (2000 if worker else 1000) + 3 * value + context

    return {
        "inline": outcome(False, payload, offset),
        "worker_first": outcome(True, payload, offset),
        "worker_second": outcome(True, payload + 1, offset + 7),
        "renewed": outcome(False, payload, offset),
    }


def observations(command, cases, root, env):
    inputs = [str(value) for triple in cases for value in triple]
    task = run([*command, *inputs], root, env)
    assert not task.stderr, task.stderr
    rows = task.stdout.strip().splitlines()
    assert len(rows) == len(cases)
    results = []
    for (payload, order, offset), row in zip(cases, rows):
        values = list(map(int, row.split("\t")))
        assert len(values) == 7
        received = dict(zip(("inline", "worker_first", "worker_second", "renewed"), values[:4]))
        assert received == oracle(payload, offset) and values[4:] == [1, 1, 2]
        results.append({"payload": payload, "join_first": ("first" if order == 0 else "second"),
                        "primary_context": offset, "peer_context": offset + 7,
                        "registration_generations": values[4:], "results": received})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", type=lambda s: Path(s).resolve(), required=True)
    parser.add_argument("--go-cache", type=lambda s: Path(s).resolve())
    parser.add_argument("--java", default=shutil.which("java"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    baseline = (PRIOR / "observations.json").read_bytes()
    prior = json.loads(baseline)
    with tempfile.TemporaryDirectory(prefix="rt13-managed-callbacks-") as directory:
        root = Path(directory)
        library = build(args, root)
        provider_hash = sha256(library.read_bytes()).hexdigest()
        assert provider_hash == prior["provider_sha256"]
        inputs = list(product((-8, -7, -6, -1, 0, 1, 31), (0, 1), (3, 17, 61)))
        g_env = {**ENV, "LD_LIBRARY_PATH": str(root)}
        jvm = [args.java, "--enable-preview", "--enable-native-access=ALL-UNNAMED",
               "-cp", root, "ManagedCallbacks", library]
        profiles = {
            "go-cgo": ([root / "go-cgo"], g_env),
            "go-cgocheck2": ([root / "go-cgocheck2"], g_env),
            "java-interpreted": ([jvm[0], "-Xint", *jvm[1:], "false"], ENV),
            "java-batch": ([jvm[0], "-Xcomp", "-Xbatch", *jvm[1:], "false"], ENV),
        }
        rows = {name: observations(program, inputs, root, environment)
                for name, (program, environment) in profiles.items()}
        assert all(results == prior["routes"]["c"] for results in rows.values())

        controls = {}
        for payload, site in ((-7, "inline"), (-8, "foreign-worker")):
            arguments = [str(payload), "0", "3"]
            go = run([root / "go-cgo", *arguments], root,
                     {**g_env, "FIXTURE_UNCONTAINED": "1"}, check=False)
            java = run([*jvm, "true", *arguments], root, check=False)
            assert go.returncode == 2 and "panic: fixture callback failed" in go.stderr, go.stderr
            assert java.returncode == 1 and "Unrecoverable uncaught exception" in java.stderr, (
                java.stdout, java.stderr)
            assert not go.stdout and not java.stdout
            controls[f"uncaught-{site}"] = {"go": go.returncode, "java": java.returncode}
        unflushed = run([root / "go-cgo", "0", "0", "3"], root,
                        {**g_env, "FIXTURE_UNFLUSHED": "1"})
        assert not unflushed.stdout and not unflushed.stderr
        controls["go-no-native-stdout-flush"] = {"exit": 0, "stdout_bytes": 0}
        totals = Counter()
        for results in rows.values():
            for row in results:
                totals.update("typed_error" if value == -77 else "returned"
                              for value in row["results"].values())
        j_version = run([args.java, "-version"], root).stderr.splitlines()[0]
        g_version = run([args.go, "version"], root).stdout.strip()
        assert "21.0.13" in j_version and "go1.27.4 linux/amd64" in g_version
        result = {"versions": {"java": j_version, "go": g_version},
                  "profiles": rows, "controls": controls, "upcall_totals": dict(totals),
                  "case_count": sum(map(len, rows.values())), "provider_sha256": provider_hash,
                  "prior_ledger_sha256": sha256(baseline).hexdigest()}
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
