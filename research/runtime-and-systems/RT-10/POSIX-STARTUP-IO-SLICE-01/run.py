"""Compose process startup and file I/O across two statically verified libcs."""

import argparse
import errno
import json
from pathlib import Path
import platform
import runpy
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE.parent / "POSIX-CROSS-LIBC-01/run.py"))
EXPECTED = {
    "progress": (0, 0, "eof;counts=2210;payload=bcdef", 6),
    "empty": (0, 0, "eof;counts=0;payload=", 0),
    "child-read-error": (0, 12, f"io-error:{errno.EBADF};counts=e;payload=", 0),
    "missing-map": (0, 12, f"io-error:{errno.EBADF};counts=e;payload=", 0),
    "invalid-map": (errno.EBADF, -1, "", 0),
    "missing-program": (errno.ENOENT, -1, "", 0),
}


def study(args, work):
    run = REFERENCE["invoke"]
    digest = REFERENCE["digest"]
    system_archive = Path(run([args.cc, "-print-file-name=libc.a"], work).strip())
    specs, musl_archive, original_specs = REFERENCE["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (system_archive, ()), "musl": (musl_archive, (f"-specs={specs}",))}
    assert digest(system_archive) != digest(musl_archive)
    results = {}
    file = work / "source"
    for profile, (archive, flags) in profiles.items():
        for level in (0, 2):
            binary = REFERENCE["checked_binary"](args, work, profile, archive, flags, HERE, level)
            rows = {}
            for scenario, expected in EXPECTED.items():
                file.write_bytes(b"" if scenario == "empty" else b"abcdef")
                response = run([str(binary), scenario, str(file)], work)
                actual = dict(row.split("=", 1) for row in response.splitlines())
                observed = (int(actual["spawn"]), int(actual["child_exit"]), actual["report"],
                            int(actual["parent_offset"]))
                assert observed == expected, (profile, level, scenario, actual)
                rows[scenario] = actual
            results[f"{profile}-O{level}"] = rows
    assert all(result == results["glibc-O0"] for result in results.values())
    return {
        "kernel": platform.release(),
        "python": platform.python_version(),
        "gcc": run([args.cc, "--version"], work).splitlines()[0],
        "libc_archive_sha256": {name: digest(archive) for name, (archive, _) in profiles.items()},
        "musl_original_specs_sha256": original_specs,
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument("--musl-root", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory() as temporary:
        print(json.dumps(study(args, Path(temporary)), indent=2, sort_keys=True))
