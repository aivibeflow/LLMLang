"""Replay the plan path repair and shared-branch navigation check."""

from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".github/scripts"))
from audit_research_index_reachability import measure

BASELINE = "600173d375b4bdf6b1634381bba2dfea1c77469b"
CODE_PATH = re.compile(r"`(research/[^*`#]+\.md)`")
AUTHORED_REPORT = "research/compiler-and-translation/RT-13/RT-13-WIDE-DIVISION-CAPABILITY-2026-11-25.md"
EXPECTED_OUTPUT = "research/FEATURE-COMPATIBILITY-AND-FEASIBILITY-AUDIT.md"


def inspect_plan(root):
    by_name = defaultdict(list)
    for path in (root / "research").rglob("*.md"):
        by_name[path.name].append(path.relative_to(root).as_posix())
    missing, repairs = [], []
    lines = (root / "PLAN.md").read_text(encoding="utf-8").splitlines(keepends=True)
    for number, line in enumerate(lines, 1):
        for found in CODE_PATH.finditer(line):
            src = found[1]
            if (root / src).is_file():
                continue
            if src == EXPECTED_OUTPUT and "**Expected output:**" in line:
                missing.append({"line": number, "path": src, "classification": "future-output"})
                continue
            name = PurePosixPath(src).name
            candidates = sorted(by_name[name])
            if len(candidates) != 1:
                raise ValueError(f"unresolved or ambiguous live pointer: {src}: {candidates}")
            repairs.append({"line": number, "old": src, "new": candidates[0]})
            lines[number - 1] = lines[number - 1].replace(found[0], f"[{name}]({candidates[0]})", 1)
    return "".join(lines), repairs, missing


def summarize(root):
    result = measure(root)
    unresolved = result["unresolved_local_path_occurrences"]
    return {
        "metrics": result["summary"],
        "unresolved_origins": dict(sorted(Counter(
            "copied-reference" if row["source"].startswith("research/references/") else "first-party"
            for row in unresolved
        ).items())),
        "first_party_unresolved": [row for row in unresolved if not row["source"].startswith("research/references/")],
    }


def main():
    archive = subprocess.check_output(["git", "archive", BASELINE], cwd=ROOT, timeout=30)
    with tempfile.TemporaryDirectory(prefix="llmlang-plan-navigation-") as temporary:
        root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
            tree.extractall(root, filter="data")
        before = summarize(root)
        repaired, repairs, future = inspect_plan(root)
        assert repairs
        (root / "PLAN.md").write_text(repaired, encoding="utf-8")
        path = root / AUTHORED_REPORT
        text = path.read_text(encoding="utf-8")
        old = "](../TRANSLATION-AND-TARGET-BACKENDS.md)"
        assert text.count(old) == 1
        path.write_text(text.replace(old, "](TRANSLATION-AND-TARGET-BACKENDS.md)"), encoding="utf-8")
        after = summarize(root)
        _, remaining, remaining_future = inspect_plan(root)
        assert not remaining and future == remaining_future
        assert not after["first_party_unresolved"]
        assert after["metrics"]["artifacts"] == after["metrics"]["artifacts_reachable_with_directory_links"]
    source_files = (
        Path(__file__),
        ROOT / ".github/scripts/audit_research_index_coverage.py",
        ROOT / ".github/scripts/audit_research_index_reachability.py",
    )
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(), "git": subprocess.check_output(
            ["git", "--version"], text=True).strip(),
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files},
        "before": before, "after_overlay": after, "plan_path_repairs": repairs,
        "preserved_missing_designation": future,
    }, indent=2))


if __name__ == "__main__":
    main()
