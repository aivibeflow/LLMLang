#!/usr/bin/env python3
"""Audit documented replay entry points in a pinned RT-13 evidence cohort."""

import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

REVISION = "037723fc4a4d23c4b0e30e31aefea11e7a13382f"
SCOPE = Path("research/compiler-and-translation/RT-13")
SHELL_BLOCK = re.compile(r"^```(?:sh|bash)\n(.*?)^```", re.MULTILINE | re.DOTALL)
OPTION = re.compile(r"(?<![\w-])--[\w-]+")
TOOL_FIELDS = {
    "python", "tools", "versions", "toolchain", "toolchains", "go_archive_sha256",
    "gcc", "cc", "c_compiler", "compiler", "runtime", "java_compiler", "java_runtime",
    "go", "rustc", "lean", "lean_model", "llvm", "alive2_revision", "vellvm_revision",
    "objdump", "readelf",
}
HOST_FIELDS = {"cpu", "environment", "host", "kernel", "os", "platform", "system", "target"}


def blob(path):
    return subprocess.check_output(["git", "rev-parse", f"{REVISION}:{path}"], text=True).strip()


def commands(archive, ledger):
    directory = ledger.parent.as_posix()
    for report in sorted((archive / SCOPE).glob("*.md")):
        content = report.read_text(encoding="utf-8")
        for block in SHELL_BLOCK.finditer(content):
            assignment = re.search(rf"^(\w+)={re.escape(directory)}$", block[1], re.MULTILINE)
            if assignment is None:
                continue
            variable = assignment[1]
            if f'cmp "${variable}/evidence.json"' not in block[1]:
                continue
            subprocess.run(["bash", "-n"], check=True, input=block[1], text=True)
            pattern = (
                rf'^(?P<command>[^\n]*\bpython3(?: -B)? "\${variable}/run\.py"'
                rf'(?:[^\n]*\\\n)*[^\n]*)\n[ \t]*cmp "\${variable}/evidence\.json"'
            )
            for match in re.finditer(pattern, block[1], re.MULTILINE):
                command = match["command"].replace("\\\n", " ")
                yield {
                    "report": report.relative_to(archive).as_posix(),
                    "line": content.count("\n", 0, block.start(1))
                    + block[1].count("\n", 0, match.start()) + 1,
                    "command": command,
                    "long_options": sorted(set(OPTION.findall(command))),
                }


def inspect(archive, ledger):
    data = json.loads((archive / ledger).read_text(encoding="utf-8"))
    runner = ledger.with_name("run.py")
    routes = list(commands(archive, ledger))
    if not routes:
        raise ValueError(f"Missing archived-ledger comparison for {ledger}")
    if any(route["long_options"] for route in routes):
        help_text = subprocess.check_output(
            [sys.executable, "-B", archive / runner, "--help"], cwd=archive, text=True,
        )
        supported = set(OPTION.findall(help_text))
        for route in routes:
            unknown = set(route["long_options"]) - supported
            if unknown:
                raise ValueError(f"Unknown options for {runner}: {sorted(unknown)}")
    for route in routes:
        route["report_blob"] = blob(route["report"])
    return {
        "ledger": str(ledger),
        "ledger_blob": blob(ledger),
        "runner_blob": blob(runner),
        "reported_tool_fields": sorted(data.keys() & TOOL_FIELDS),
        "reported_host_or_target_fields": sorted(data.keys() & HOST_FIELDS),
        "documented_commands": routes,
    }


def main():
    with TemporaryDirectory(prefix="llmlang-rt13-replay-metadata-") as directory:
        archive = Path(directory)
        tree = subprocess.check_output(["git", "archive", REVISION])
        with tarfile.open(fileobj=io.BytesIO(tree)) as source:
            source.extractall(archive, filter="data")
        ledgers = sorted(path.relative_to(archive) for path in (archive / SCOPE).glob("*/evidence.json"))
        return {
            "schema": "llmlang-rt13-replay-metadata/1",
            "revision": REVISION,
            "ledgers": [inspect(archive, ledger) for ledger in ledgers],
        }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
