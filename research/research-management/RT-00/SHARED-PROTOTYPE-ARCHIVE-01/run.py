"""Run the two shared Python suites in a fresh, tracked research archive."""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile

import sympy

BASE = "1521400115a540d3e79083df03e9ab55f6c339bd"
HISTORICAL = "08c8490e92b472f99abf3117e82bc7b11643fe0d"
ROOT = Path("research/PROTOTYPES")
FEASIBILITY = ROOT / "RT-04-01/test_rt03_feasibility_outcomes.py"
SUITES = {"RT-04-01": ".", "DEPENDENCY-GRAPH-01": "tests"}
CASE = re.compile(r"^test_\w+ \(([^)]+)\) \.\.\. (ok|skipped .+)$", re.MULTILINE)


def git(*args):
    return subprocess.check_output(["git", *args])


def tool_version(tool):
    return subprocess.check_output([tool, "--version"], text=True).splitlines()[0]


def discover(suite, directory):
    command = [sys.executable, "-B", "-m", "unittest", "discover",
               "-s", directory, "-p", "test_*.py", "-v"]
    return subprocess.run(command, cwd=suite, text=True, capture_output=True,
                          env={**os.environ, "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"})


def run_suite(archive, name, directory):
    suite = archive / ROOT / name
    process = discover(suite, directory)
    if process.returncode != 0:
        raise RuntimeError(process.stdout + process.stderr)
    observed = dict(CASE.findall(process.stderr))
    summary = re.search(r"(?m)^Ran (\d+) tests? in", process.stderr)
    assert summary and int(summary[1]) == len(observed), process.stderr
    files = {}
    for file in sorted((suite / directory).glob("test_*.py")):
        data = file.read_bytes()
        files[str(file.relative_to(archive))] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "method_declarations": len(re.findall(rb"(?m)^    def test_", data)),
        }
    discovered_modules = {name.split(".", 1)[0] for name in observed}
    assert {Path(file).stem for file in files} == discovered_modules
    return {"directory": directory, "files": files, "cases": observed,
            "outcomes": dict(Counter(observed.values()))}


def main():
    with tempfile.TemporaryDirectory(prefix="llmlang-shared-suites-") as work:
        archive = Path(work)
        subprocess.run(["tar", "-x", "-C", work], input=git("archive", BASE), check=True)
        root_discovery = discover(archive / ROOT / "DEPENDENCY-GRAPH-01", ".")
        assert root_discovery.returncode == 5 and "Ran 0 tests" in root_discovery.stderr
        results = {name: run_suite(archive, name, directory) for name, directory in SUITES.items()}
    historical_blob = git("rev-parse", f"{HISTORICAL}:{FEASIBILITY}").decode().strip()
    assert historical_blob == git("rev-parse", f"{BASE}:{FEASIBILITY}").decode().strip()
    feasibility = {name: outcome for name, outcome in results["RT-04-01"]["cases"].items()
                   if name.startswith("test_rt03_feasibility_outcomes.")}
    assert len(feasibility) == 8 and set(feasibility.values()) == {"ok"}
    print(json.dumps({
        "base": BASE, "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "sympy": sympy.__version__,
        "tools": {tool: tool_version(tool) for tool in ("git", "tar", "cc", "rustc", "z3")},
        "system": [platform.system(), platform.release(), platform.machine()],
        "root_discovery_control": {"code": 5, "tests": 0},
        "sc102": {"historical_commit": HISTORICAL, "historical_blob": historical_blob,
                  "current_cases": feasibility},
        "suites": results,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
