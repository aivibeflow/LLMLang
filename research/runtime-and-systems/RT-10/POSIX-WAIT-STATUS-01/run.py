"""Compare native wait status traces using the existing static libc build audit."""
import argparse
import csv
import io
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import signal
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent


def expect():
    rows = []
    for scenario, kind, detail in (
        ("exit-143", "exit", "143"),
        ("signal-term", "signal", "TERM"),
        ("stop-continue-exit", "exit", "7"),
    ):
        steps = [("empty_waitid", "none", "0"), ("empty_waitpid", "none", "0")]
        if scenario == "stop-continue-exit":
            steps += [("peek_stop_a", "stopped", "STOP"), ("peek_stop_b", "stopped", "STOP"),
                      ("consume_stop", "stopped", "STOP"), ("drained_stop", "none", "0"),
                      ("peek_continue_a", "continued", "CONT"),
                      ("peek_continue_b", "continued", "CONT"),
                      ("consume_continue", "continued", "CONT"), ("drained_continue", "none", "0")]
        steps += [(step, kind, detail) for step in ("peek_exit_a", "peek_exit_b", "reap")]
        steps.append(("after_reap", "no_child", "0"))
        rows.extend(
            {"scenario": scenario, "step": step, "kind": row_kind, "detail": data}
            for step, row_kind, data in steps
        )
    return rows


def run_binary(path):
    with subprocess.Popen([path], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        if process.returncode:
            raise RuntimeError((path, process.returncode, stderr))
        return list(csv.DictReader(io.StringIO(stdout)))


def assess(args, scratch):
    libc = import_runner(HERE.parent / "POSIX-CROSS-LIBC-01", "rt10_static_libc")
    glibc = Path(libc.invoke([args.cc, "-print-file-name=libc.a"], scratch).strip())
    specs, musl, spec_hash = libc.musl_specs(args.musl_root.resolve(), scratch)
    expected = expect()
    builds = {}
    for profile, archive, options in (
        ("glibc", glibc, ()), ("musl", musl, (f"-specs={specs}",)),
    ):
        for opt in (0, 2):
            binary = libc.checked_binary(args, scratch, profile, archive, options, HERE, opt)
            for repeat in range(4):
                found = run_binary(binary)
                if found != expected:
                    raise AssertionError((profile, opt, repeat, found))
            builds[f"{profile}-O{opt}"] = {
                "binary_sha256": libc.digest(binary),
                "runtime_archive_sha256": libc.digest(archive),
                "verified_runs": 4,
            }
    assert libc.digest(glibc) != libc.digest(musl)
    signal_projection = 128 + int(signal.SIGTERM)
    assert signal_projection == 143
    return {
        "compiler": libc.invoke([args.cc, "--version"], scratch).splitlines()[0],
        "kernel": os.uname().release,
        "musl_specs_sha256": spec_hash,
        "builds": builds,
        "observations": len(expected) * sum(build["verified_runs"] for build in builds.values()),
        "numeric_collision_control": {"ordinary_exit": 143, "128_plus_sigterm": signal_projection},
        "trace": expected,
    }


def import_runner(path, name):
    spec = spec_from_file_location(name, path / "run.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--musl-root", required=True, type=Path)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--readelf", default="readelf")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-posix-wait-") as directory:
        print(json.dumps(assess(args, Path(directory)), indent=2))


if __name__ == "__main__":
    main()
