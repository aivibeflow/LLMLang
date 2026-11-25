#!/usr/bin/env python3
"""Compare independent C, CPython and Rust callback bodies on native Linux."""
import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import resource
from shutil import which
import signal
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
FLAGS = ("-std=c11", "-O2", "-Wall", "-Wextra", "-Werror")
ENV = {key: value for key, value in os.environ.items()
       if not key.startswith(("LD_", "RUST_", "PYTHON"))}
ENV.update({"LC_ALL": "C", "TZ": "UTC"})


def run(command, path, *, check=True):
    result = subprocess.run(command, cwd=path, env=ENV, capture_output=True, text=True, timeout=15)
    if check:
        assert result.returncode == 0 and not result.stderr, (
            command, result.returncode, result.stdout, result.stderr)
    return result


def build(root, rustc):
    library = root / "libcallbackfixture.so"
    run(["gcc", *FLAGS, "-fPIC", "-shared", "-pthread", "-Wl,-z,defs",
         HERE / "provider.c", HERE / "driver.c", "-o", library], root)
    run(["gcc", *FLAGS, HERE / "consumer.c", f"-L{root}", "-lcallbackfixture",
         "-Wl,-rpath,$ORIGIN", "-o", root / "c-consumer"], root)
    for panic in ("unwind", "abort"):
        run([rustc, "--edition=2021", "-C", "opt-level=2", "-C", f"panic={panic}",
             "-L", f"native={root}", "-l", "dylib=callbackfixture",
             "-C", "link-arg=-Wl,-rpath,$ORIGIN", HERE / "consumer.rs",
             "-o", root / f"rust-{panic}"], root)
    return library


def expected_value(kind, payload, offset):
    if payload == -7:
        return -77
    return {"owner": 1000, "worker": 2000}[kind] + 3 * payload + offset


def oracle(payload, offset):
    owner = expected_value("owner", payload, offset)
    first = expected_value("worker", payload, offset)
    second = expected_value("worker", payload + 1, offset + 7)
    return [owner, first, second, owner, 1, 1, 2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rustc", default=which("rustc"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.rustc is None:
        parser.error("--rustc is required when rustc is absent from PATH")
    _, hard = resource.getrlimit(resource.RLIMIT_CORE)
    resource.setrlimit(resource.RLIMIT_CORE, (0, hard))
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-callback-") as directory:
        root = Path(directory)
        library = build(root, args.rustc)
        symbols = run(["readelf", "--dyn-syms", "--wide", library], root).stdout
        assert all(f"fixture_{name}" in symbols for name in ("start", "finish", "retire", "thread"))
        routes = {"c": [root / "c-consumer"],
                  "python": [sys.executable, "-B", HERE / "consumer.py", library],
                  "rust-unwind": [root / "rust-unwind"]}
        cases = {}
        for name, base in routes.items():
            rows = []
            for payload, profile, offset in product((-8, -7, -6, -1, 0, 1, 31), (0, 1), (3, 17, 61)):
                output = run([*base, str(payload), str(profile), str(offset)], root).stdout
                observed = list(map(int, output.split()))
                assert observed == oracle(payload, offset), (name, payload, offset, observed)
                rows.append({"payload": payload, "join_first": ("first" if profile == 0 else "second"),
                             "primary_context": offset, "peer_context": offset + 7,
                             "results": dict(zip(("inline", "worker_first", "worker_second", "renewed"),
                                                 observed[:4])),
                             "registration_generations": observed[4:]})
            cases[name] = rows

        abort_control = {}
        for payload in (-8, -7, 0):
            result = run([root / "rust-abort", str(payload), "0", "3"], root, check=False)
            if payload < 0:
                assert result.returncode == -signal.SIGABRT and not result.stdout
                abort_control[str(payload)] = "SIGABRT-before-result"
            else:
                assert result.returncode == 0 and list(map(int, result.stdout.split())) == oracle(payload, 3)
                abort_control[str(payload)] = "completed"
        summarized = Counter()
        for rows in cases.values():
            for row in rows:
                summarized.update("typed-error" if item == -77 else "completed-upcall"
                                  for item in row["results"].values())
        versions = {
            "c": run(["gcc", "--version"], root).stdout.splitlines()[0],
            "rust": run([args.rustc, "--version"], root).stdout.strip(),
            "python": sys.version.split()[0],
            "libc": run(["getconf", "GNU_LIBC_VERSION"], root).stdout.strip(),
            "machine": run(["uname", "-m"], root).stdout.strip(),
        }
        record = {"versions": versions, "routes": cases, "summary": dict(summarized),
                  "driver_cases": sum(map(len, cases.values())), "rust_abort_control": abort_control,
                  "provider_sha256": sha256(library.read_bytes()).hexdigest()}
    args.out.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
