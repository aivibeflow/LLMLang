"""Compare deferred cancellation at static libc calls and a raw Linux read."""

import argparse
from itertools import product
import json
from pathlib import Path
import platform
import runpy
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE.parent / "POSIX-CROSS-LIBC-01/run.py"))


def study(args, work):
    run = REFERENCE["invoke"]
    digest = REFERENCE["digest"]
    system_archive = Path(run([args.cc, "-print-file-name=libc.a"], work).strip())
    specs, musl_archive, original_specs = REFERENCE["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (system_archive, ()), "musl": (musl_archive, (f"-specs={specs}",))}
    assert digest(system_archive) != digest(musl_archive)
    results = {}
    for profile, (archive, flags) in profiles.items():
        for level in (0, 2):
            binary = REFERENCE["checked_binary"](
                args, work, profile, archive, (*flags, "-pthread"), HERE, level,
            )
            rows = {}
            for path, cancellation in product(("libc", "syscall"), ("none", "pending")):
                recorded = dict(row.split("=") for row in run([str(binary), path, cancellation], work).splitlines())
                stopped_at_read = path == "libc" and cancellation == "pending"
                expected = {
                    "terminal": "cancelled" if cancellation == "pending" else "normal",
                    "cleanup": "1" if cancellation == "pending" else "0",
                    "read_result": "-99" if stopped_at_read else "1",
                    "read_byte": "0" if stopped_at_read else str(ord("x")),
                    "leftover": "1" if stopped_at_read else "0",
                }
                assert recorded == expected, (profile, path, cancellation, recorded)
                rows[f"{path}-{cancellation}"] = recorded
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
