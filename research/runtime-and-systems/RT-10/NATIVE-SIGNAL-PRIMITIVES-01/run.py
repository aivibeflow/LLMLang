#!/usr/bin/env python3
"""Compare directed native signal schedules and primitive-specific dispositions."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ORACLE = (
    "read 0 -1 EINTR 0 1",
    "read 1 1 E2BIG 81 0",
    "poll 0 -1 EINTR 0 1",
    "poll 1 -1 EINTR 0 1",
    "nonblocking -1 EAGAIN",
    "eof 0 E2BIG",
    "invalid -1 EBADF",
)


def disposition(observation):
    line = observation.split()
    if line[0] in ("read", "poll"):
        if int(line[2]) > 0:
            return "performed"
        assert line[3] == "EINTR"
        return "interrupted"
    return {"nonblocking": "would-block", "eof": "end-of-stream", "invalid": "failure"}[line[0]]


def experiment(root):
    cc = os.environ.get("CC", "gcc")
    outputs = {}
    for level in ("-O0", "-O2"):
        binary = root / f"probe-{level[1:]}"
        subprocess.run(
            [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pthread", level,
             str(HERE / "probe.c"), "-o", str(binary)],
            cwd=root, capture_output=True, check=True,
        )
        native = subprocess.run([str(binary)], cwd=root, capture_output=True,
                                text=True, check=True, timeout=60)
        assert not native.stderr
        rows = tuple(native.stdout.splitlines())
        assert rows == ORACLE * 5
        outputs[level] = {"native_probes": len(rows), "directed_signals": 20,
                          "trace": sha256(native.stdout.encode()).hexdigest()}
    assert outputs["-O0"] == outputs["-O2"]
    return {
        "format": "native-signal-primitives-01",
        "gcc": subprocess.check_output([cc, "--version"], text=True).splitlines()[0],
        "outputs": outputs, "kernel": os.uname().release,
        "controls": [{"native": row, "contract_disposition": disposition(row)} for row in ORACLE],
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-native-signals-") as directory:
        evidence = experiment(Path(directory))
    content = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
