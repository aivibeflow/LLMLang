"""Compare exact bytes and open-description state after native positioned writes."""

import argparse
import csv
import hashlib
import json
import platform
import runpy
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "4b9060f0fae2d71ea0b708019ff442ffed82458b"
REFERENCE_PATH = HERE.parent / "POSIX-CROSS-LIBC-01/run.py"
REFERENCE = runpy.run_path(str(REFERENCE_PATH))
EXPECTED = {
    # file content, primary offset, primary append, independent append
    "pwrite-plain": ("AZCD", 2, 0, 0),
    "pwrite-append": ("ABCDZ", 2, 1, 1),
    "vector-plain": ("AZCD", 2, 0, 0),
    "vector-append": ("ABCDZ", 2, 1, 1),
    "vector-noappend-plain": ("AZCD", 2, 0, 0),
    "vector-noappend-append": ("ABCDZ", 2, 1, 1),
    "vector-force-append": ("ABCDZ", 2, 0, 0),
    "vector-append-cursor": ("ABCDZ", 5, 0, 0),
    "clear-through-alias": ("AZCD", 2, 0, 1),
    "set-through-alias": ("ABCDZ", 2, 1, 0),
}


def study(args, work):
    invoke = REFERENCE["invoke"]
    digest = REFERENCE["digest"]
    glibc = Path(invoke([args.cc, "-print-file-name=libc.a"], work).strip())
    specs, musl, original_specs = REFERENCE["musl_specs"](args.musl_root.resolve(), work)
    profiles = {"glibc": (glibc, ()), "musl": (musl, (f"-specs={specs}",))}
    assert digest(glibc) != digest(musl)
    results = {}
    for libc, (archive, flags) in profiles.items():
        for opt in (0, 2):
            binary = REFERENCE["checked_binary"](args, work, libc, archive, flags, HERE, opt)
            for backing, arguments in (("filesystem", ()), ("memfd", ("memfd",))):
                rows = {}
                for case, rc, error, actual, fd, alias, now, fd_append, alias_append, own_append, magic in (
                    csv.reader(invoke([str(binary), *arguments], work).splitlines())
                ):
                    assert magic == {"filesystem": "794c7630", "memfd": "1021994"}[backing]
                    content, shared, append, own = EXPECTED[case]
                    if backing == "memfd" and case == "vector-noappend-append":
                        content = "AZCD"
                    status = tuple(map(int, (rc, error, fd, alias, now, fd_append, alias_append, own_append)))
                    assert actual == content and status == (1, 0, shared, shared, 3, append, append, own), (
                        libc, opt, backing, case, status, actual,
                    )
                    rows[case] = {"filesystem_magic_hex": magic, "bytes_written": int(rc), "error": int(error), "content": actual,
                                  "offsets": list(map(int, (fd, alias, now))),
                                  "append_flags": list(map(int, (fd_append, alias_append, own_append)))}
                assert rows.keys() == EXPECTED.keys()
                results[f"{libc}-O{opt}-{backing}"] = rows
    relative = str(REFERENCE_PATH.relative_to(ROOT))
    archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
    assert archived == REFERENCE_PATH.read_bytes()
    return {
        "baseline": BASELINE, "kernel": platform.release(), "arch": platform.machine(),
        "python": platform.python_version(),
        "gcc": invoke([args.cc, "--version"], work).splitlines()[0],
        "readelf": invoke([args.readelf, "--version"], work).splitlines()[0],
        "filesystem": invoke(["stat", "-f", "-c", "%T", str(work)], work).strip(),
        "libc_archive_sha256": {name: digest(archive) for name, (archive, _) in profiles.items()},
        "musl_original_specs_sha256": original_specs,
        "source_sha256": {name: digest(HERE / name) for name in ("probe.c", "run.py")}
        | {relative: hashlib.sha256(archived).hexdigest()},
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument("--musl-root", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-append-writes-") as temporary:
        print(json.dumps(study(args, Path(temporary)), indent=2))
