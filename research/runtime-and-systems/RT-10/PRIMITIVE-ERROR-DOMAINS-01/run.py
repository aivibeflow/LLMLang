"""Verify per-operation native error channels under two exact static libcs."""

import argparse
from collections import Counter
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
LIBC = HERE.parent / "POSIX-CROSS-LIBC-01"
sys.path.insert(0, str(LIBC))
from run import checked_binary, invoke, musl_specs


EXPECTED = {
    "open-missing": ("errno", errno.ENOENT),
    "read-invalid": ("errno", errno.EBADF),
    "pthread-busy": ("function-error", errno.EBUSY),
    "pthread-acquired": ("ok", 0),
    "clock-invalid": ("function-error", errno.EINVAL),
    "clock-zero": ("ok", 0),
    "spawn-missing": ("function-error", errno.ENOENT),
    "address-not-numeric": ("name-resolution", socket.EAI_NONAME),
    "long-cleared-boundary": ("ok", 2**63 - 1),
    "long-dirty-boundary": ("uncleared-errno", 0),
    "long-over-range": ("errno", errno.ERANGE),
    "long-partial": ("partial-input", 42),
    "readdir-dirty-end": ("uncleared-errno", 0),
    "readdir-cleared-end": ("eof", 0),
}


def correct_adapter(name, result, error, extra):
    if name.startswith(("open", "read-")):
        return ("errno", error) if result == -1 else ("ok", result)
    if name.startswith(("pthread", "clock", "spawn")):
        return ("function-error", result) if result else ("ok", 0)
    if name.startswith("address"):
        return ("name-resolution", result) if result else ("ok", 0)
    if "dirty" in name:
        return "uncleared-errno", 0
    if name.startswith("long"):
        if error:
            return "errno", error
        return ("ok" if extra else "partial-input"), result
    return ("errno", error) if error else ("eof", 0)


def check_profile(args, work, profile, archive, options):
    all_optimizations = {}
    counts = Counter()
    for level in (0, 2):
        executable = checked_binary(args, work, profile, archive, options, HERE, level)
        baseline = None
        for index in range(3):
            directory = work / f"{profile}-O{level}-{index}"
            directory.mkdir()
            (directory / "empty").mkdir()
            lines = invoke([str(executable)], directory).splitlines()
            parsed = []
            keys = set()
            for line in lines:
                case, *fields = line.split()
                seeded, result, error, extra = map(int, fields)
                if (case, seeded) in keys or seeded not in {errno.E2BIG, errno.ENOEXEC}:
                    raise AssertionError((case, seeded))
                keys.add((case, seeded))
                current = correct_adapter(case, result, error, extra)
                if current != EXPECTED[case]:
                    raise AssertionError((profile, level, line, current, EXPECTED[case]))
                if case in {"spawn-missing", "address-not-numeric"} and extra != 1:
                    raise AssertionError((profile, line, "unexpected process or address"))
                if case == "long-over-range" and (result != 2**63 - 1 or extra != 1):
                    raise AssertionError((profile, line, "overflow did not reach the range sentinel"))
                negative_only = ("errno", error) if result < 0 else ("ok", result)
                errno_only = ("errno", error) if error else ("ok", result)
                counts["checked"] += 1
                counts["negative_errno_rule_disagreements"] += negative_only != current
                counts["errno_only_rule_disagreements"] += errno_only != current
                parsed.append({"case": case, "seed_errno": seeded, "result": result, "errno": error,
                               "auxiliary": extra, "typed_observation": current})
            if len(keys) != 2 * len(EXPECTED):
                raise AssertionError((profile, "incomplete observations"))
            if baseline is None:
                baseline = parsed
            elif baseline != parsed:
                raise AssertionError((profile, "raw observation changed between repetitions"))
        all_optimizations[f"O{level}"] = {
            "probe_sha256": sha256(executable.read_bytes()).hexdigest(), "raw_observations": baseline,
        }
    return {"counts": dict(counts), "builds": all_optimizations,
            "archive_sha256": sha256(archive.read_bytes()).hexdigest()}


def verify(args, work):
    glibc = Path(invoke([args.cc, "-print-file-name=libc.a"], work).strip())
    specs, musl, expected_specs = musl_specs(args.musl_root.resolve(), work)
    profiles = {
        "glibc": check_profile(args, work, "glibc", glibc, ()),
        "musl": check_profile(args, work, "musl", musl, (f"-specs={specs}",)),
    }
    native_differences = []
    for left, right in zip(profiles["glibc"]["builds"]["O0"]["raw_observations"],
                           profiles["musl"]["builds"]["O0"]["raw_observations"], strict=True):
        if (left["case"], left["seed_errno"], left["typed_observation"]) != (
            right["case"], right["seed_errno"], right["typed_observation"]
        ):
            raise AssertionError((left, right))
        if left["errno"] != right["errno"]:
            native_differences.append({"case": left["case"], "seed": left["seed_errno"],
                                       "glibc_errno": left["errno"], "musl_errno": right["errno"]})
    return {
        "compiler": invoke([args.cc, "--version"], work).splitlines()[0],
        "glibc": os.confstr("CS_GNU_LIBC_VERSION"),
        "musl_specs_sha256": expected_specs,
        "checked_observations": sum(profile["counts"]["checked"] for profile in profiles.values()),
        "native_errno_differences": native_differences,
        "profiles": profiles,
        "source_sha256": {path.relative_to(HERE.parent).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in (HERE / "probe.c", HERE / "run.py", LIBC / "run.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument("--musl-root", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-primitive-errors-") as temp:
        print(json.dumps(verify(args, Path(temp)), indent=2))
