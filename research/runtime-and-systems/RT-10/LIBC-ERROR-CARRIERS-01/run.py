"""Measure return-carried errors, immediate errno capture and thread isolation."""

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
    "trylock-success": [0, errno.EINTR],
    "trylock-busy": [errno.EBUSY, errno.EINTR],
    "successful-read": [1, errno.ENOSPC, ord("x")],
    "failed-read": [-1, errno.EBADF, errno.ENOENT],
    "reader-thread": [errno.EBADF],
    "open-thread": [errno.ENOENT],
}


def study(args, work):
    invoke = REFERENCE["invoke"]
    digest = REFERENCE["digest"]
    glibc_archive = Path(invoke([args.cc, "-print-file-name=libc.a"], work).strip())
    specs, musl_archive, original_specs = REFERENCE["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (glibc_archive, ()), "musl": (musl_archive, (f"-specs={specs}",))}
    assert digest(glibc_archive) != digest(musl_archive)
    results = {}
    for libc, (archive, flags) in profiles.items():
        for level in (0, 2):
            binary = REFERENCE["checked_binary"](
                args, work, libc, archive, (*flags, "-pthread"), HERE, level,
            )
            lines = [row.split("=") for row in invoke([str(binary)], work).splitlines()]
            observed = {key: [int(item) for item in value.split(":")] for key, value in lines}
            assert observed == EXPECTED, (libc, level, observed)
            results[f"{libc}-O{level}"] = observed
    return {
        "kernel": platform.release(),
        "python": platform.python_version(),
        "gcc": invoke([args.cc, "--version"], work).splitlines()[0],
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
