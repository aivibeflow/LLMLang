"""Check edition header visibility and static libc runtime behavior separately."""

import argparse
import json
from pathlib import Path
import platform
import runpy
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE.parent / "POSIX-CROSS-LIBC-01/run.py"))
FLAGS = {
    "issue7_request": "-D_POSIX_C_SOURCE=200809L",
    "issue8_request": "-D_POSIX_C_SOURCE=202405L",
    "gnu_extension": "-D_GNU_SOURCE",
}
PROBES = {
    "base": ("PROBE_BASE", None),
    "pipe2": ("PROBE_PIPE2", "implicit declaration of function 'pipe2'"),
    "dup3": ("PROBE_DUP3", "implicit declaration of function 'dup3'"),
    "clofork": ("PROBE_CLOFORK", "close-on-fork flags unavailable"),
}


def study(args, work):
    run = REFERENCE["invoke"]
    digest = REFERENCE["digest"]
    system_archive = Path(run([args.cc, "-print-file-name=libc.a"], work).strip())
    specs, musl_archive, original_specs = REFERENCE["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (system_archive, ()), "musl": (musl_archive, (f"-specs={specs}",))}
    assert digest(system_archive) != digest(musl_archive)
    cases = {}
    for libc, (archive, options) in profiles.items():
        for profile, flag in FLAGS.items():
            rows = {}
            for feature, (define, diagnostic) in PROBES.items():
                compile_options = (*options, flag, f"-D{define}")
                command = [args.cc, *compile_options, "-std=c17", "-Wall", "-Wextra", "-Werror",
                           "-fsyntax-only", str(HERE / "probe.c")]
                compiled = subprocess.run(command, cwd=work, check=False, capture_output=True, text=True,
                                          timeout=30)
                visible = feature == "base" or (
                    feature in ("pipe2", "dup3") and (libc == "musl" or profile == "gnu_extension")
                )
                assert (compiled.returncode == 0) == visible, (libc, profile, feature, compiled.stderr)
                if not visible:
                    assert diagnostic in compiled.stderr, compiled.stderr
                    rows[feature] = {"header": "unavailable", "runtime": None}
                    continue
                binary = REFERENCE["checked_binary"](
                    args, work, f"{libc}-{profile}-{feature}", archive, compile_options, HERE, 2,
                )
                output = run([str(binary)], work).strip().splitlines()
                expected = {
                    "base": ["header=200809", "runtime=200809"],
                    "pipe2": ["both-close-on-exec-and-nonblocking"],
                    "dup3": ["close-on-exec-and-equal-fd-refused"],
                }
                assert output == expected[feature], (feature, output)
                rows[feature] = {"header": "visible", "runtime": output}
            cases[f"{libc}-{profile}"] = rows
    return {
        "python": platform.python_version(),
        "kernel": platform.release(),
        "gcc": run([args.cc, "--version"], work).splitlines()[0],
        "libc_archives_sha256": {name: digest(archive) for name, (archive, _) in profiles.items()},
        "musl_original_specs_sha256": original_specs,
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument("--musl-root", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory() as temporary:
        print(json.dumps(study(args, Path(temporary)), indent=2, sort_keys=True))
