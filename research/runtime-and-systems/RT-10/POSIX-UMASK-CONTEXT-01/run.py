"""Check how file creation and spawn observe one process's ambient umask."""

import argparse
import json
from pathlib import Path
import platform
import runpy
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REFERENCE = runpy.run_path(str(HERE.parent / "POSIX-CROSS-LIBC-01/run.py"))
EXPECTED = {
    "baseline": ("644", "644", "644"),
    "ambient-overlap": ("600", "600", "600"),
    "ambient-restored": ("600", "644", "644"),
    "per-call": ("600", "644", "644"),
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
            rows = {}
            for name, expected in EXPECTED.items():
                case = work / f"{libc}-{level}-{name}"
                case.mkdir()
                lines = [row.split("=") for row in invoke([str(binary), name], case).splitlines()]
                observed = dict(lines)
                assert tuple(observed[key] for key in ("worker", "peer", "spawned")) == expected
                assert {path.name: f"{path.stat().st_mode & 0o777:03o}" for path in case.iterdir()} == observed
                rows[name] = observed
            results[f"{libc}-O{level}"] = rows
    return {
        "kernel": platform.release(),
        "python": platform.python_version(),
        "gcc": invoke([args.cc, "--version"], work).splitlines()[0],
        "filesystem": invoke(["stat", "-f", "-c", "%T", str(work)], work).strip(),
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
