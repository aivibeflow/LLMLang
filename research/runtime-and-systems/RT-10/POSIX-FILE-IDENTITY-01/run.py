"""Check native descriptor, offset, and directory-entry observations."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "first_read": "A", "duplicate_read": "B", "independent_read": "A",
    "pread_at_zero": "A", "first_offset_after_pread": "2", "independent_offset": "1",
    "alias_keeps_first_object": "1", "current_keeps_first_object": "0",
    "fresh_read": "X", "alias_read": "A", "first_links_after_rename": "1",
    "current_absent": "1", "first_links_after_unlink": "0", "fresh_links_after_unlink": "0",
    "duplicate_read_after_unlink": "C", "fresh_read_after_unlink": "Y",
    "replaced_slot_now_points_at_fresh": "1", "duplicate_remains_on_original": "1",
    "remaining_fresh_read_via_replaced_slot": "Z", "fresh_now_at_eof": "1",
    "independent_still_reads_original": "B",
}


def replay(compiler):
    rows = []
    with TemporaryDirectory(prefix="llmlang-posix-descriptor-") as temporary:
        root = Path(temporary)
        filesystem = subprocess.check_output(["stat", "-f", "-c", "%T", root], text=True).strip()
        for level in ("0", "2"):
            binary = root / f"probe-{level}"
            subprocess.run([compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", "-O" + level,
                            HERE / "probe.c", "-o", binary], check=True, timeout=30)
            for repetition in range(4):
                directory = root / f"run-{level}-{repetition}"
                directory.mkdir()
                result = subprocess.check_output([binary], cwd=directory, text=True, timeout=10)
                values = dict(line.split("=", 1) for line in result.splitlines())
                assert len(result.splitlines()) == len(EXPECTED) and values == EXPECTED, values
                rows.append({"optimization": level, "repetition": repetition, "observations": values})
    return {
        "schema": "rt10-posix-file-identity-v1", "python": platform.python_version(),
        "compiler": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
        "compiler_sha256": sha256(Path(compiler).read_bytes()).hexdigest(),
        "compiler_target": subprocess.check_output([compiler, "-dumpmachine"], text=True).strip(),
        "kernel": platform.release(), "platform": platform.machine(), "filesystem": filesystem,
        "libc": platform.libc_ver(), "cases": rows,
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                          for path in (HERE / "probe.c", HERE / "run.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="/usr/bin/cc")
    args = parser.parse_args()
    print(json.dumps(replay(args.cc), indent=2, sort_keys=True))
