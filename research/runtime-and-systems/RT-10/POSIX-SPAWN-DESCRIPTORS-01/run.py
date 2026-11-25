"""Compare descriptor observations before and after POSIX process startup."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
CLOSED = ("closed",)
FIRST = ("open", 65)
CLOEXEC_SECOND = ("cloexec", 66)
EXPECTED = {
    "fork-only": (FIRST, CLOEXEC_SECOND, CLOSED, CLOSED, 2),
    "fork-exec": (FIRST, CLOSED, CLOSED, CLOSED, 1),
    "raw-self-dup2-then-exec": (FIRST, CLOSED, CLOSED, CLOSED, 1),
    "spawn-default": (FIRST, CLOSED, CLOSED, CLOSED, 1),
    "spawn-map-then-close": (CLOSED, CLOSED, FIRST, CLOSED, 1),
    "spawn-close-then-map": ("EBADF",),
    "spawn-self-map": (CLOSED, FIRST, CLOSED, CLOSED, 1),
    "spawn-missing-source": ("EBADF",),
}


def run(command, directory):
    return subprocess.run(command, cwd=directory, check=True, capture_output=True, text=True, timeout=30,
                          env={**os.environ, "LC_ALL": "C"}).stdout


def parse(lines):
    rows = {}
    for line in lines.splitlines():
        mode, subject, *details = line.split()
        observation = rows.setdefault(mode, [])
        if subject == "fd":
            number, *record = details
            assert int(number) == 80 + len(observation)
            observation.append(tuple((record[0], *map(int, record[1:]))))
        elif subject == "parent":
            assert len(observation) == 4
            observation.append(int(details[0]))
        elif subject == "spawn":
            assert not observation
            observation.append(details[0])
        else:
            raise ValueError(line)
    return {mode: tuple(values) for mode, values in rows.items()}


def assess(cc, directory):
    source = directory / "input"
    source.write_bytes(b"ABCDEFGH")
    builds = {}
    for level in (0, 2):
        binary = directory / f"descriptor-probe-O{level}"
        run([cc, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{level}",
             str(HERE / "probe.c"), "-o", str(binary)], directory)
        for repeat in range(4):
            result = parse(run([str(binary), str(source)], directory))
            if result != EXPECTED:
                raise AssertionError((level, repeat, result))
        builds[f"O{level}"] = {"repetitions": 4, "outcomes_per_repetition": len(EXPECTED),
                               "artifact_sha256": sha256(binary.read_bytes()).hexdigest()}
    return {
        "compiler": run([cc, "--version"], directory).splitlines()[0],
        "target": run([cc, "-dumpmachine"], directory).strip(),
        "libc": os.confstr("CS_GNU_LIBC_VERSION"),
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("probe.c", "run.py")},
        "case_observations": EXPECTED,
        "builds": builds,
        "verified_outcomes": len(EXPECTED) * len(builds) * 4,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-posix-spawn-") as temp:
        print(json.dumps(assess(args.cc, Path(temp)), indent=2))


if __name__ == "__main__":
    main()
