#!/usr/bin/env python3
"""Replay the archived navigation and offline citation checks."""

from hashlib import sha256
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
from audit_research_index_reachability import measure

BASELINE = "c5413e08742e90e3d8c38572a6af771cca600c9d"
IMAGE = "lycheeverse/lychee@sha256:e2d19e57cf6ab037026f20b8e449a1f30d9d7f81eef4194763aab2eab20bd28d"
REPAIR = "research/research-management/RT-00/RT-00-B-COMPONENT-IMMUTABILITY-AND-RUNTIME-COMMIT-2026-11-25.md"
OLD = "](RESEARCH-DEPENDENCY-MAP.md)"
NEW = "](../RESEARCH-DEPENDENCY-MAP.md)"


def scan(root):
    navigation = measure(root)
    run = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "-v", f"{root}:/input:ro",
         "-w", "/input", IMAGE, "--offline", "--include-fragments", "--root-dir", "/input",
         "--no-progress", "--format", "json", "research/**/*.md", "research/**/*.mdx"],
        capture_output=True, check=False, timeout=90,
    )
    if run.returncode not in (0, 2):
        raise RuntimeError((run.stdout + run.stderr).decode())
    report = json.loads(run.stdout)
    errors = []
    for path, outcomes in sorted(report["error_map"].items()):
        for finding in outcomes:
            errors.append({
                "source": path.removeprefix("/input/"), "url": finding["url"],
                "line": finding.get("span", {}).get("line"),
                "column": finding.get("span", {}).get("column"),
                "status": finding["status"]["text"],
            })
    errors.sort(key=lambda error: (error["source"], error["line"] or 0,
                                   error["column"] or 0, error["url"], error["status"]))
    return {
        "navigation": navigation["summary"],
        "directory_only_documents": [
            path for path in navigation["artifacts_reachable_only_with_directory_links"]
            if Path(path).suffix.lower() in (".md", ".mdx")
        ],
        "unreachable_with_directory_links": navigation["artifacts_unreachable_with_directory_links"],
        "path_only_unresolved": navigation["unresolved_local_path_occurrences"],
        "lychee_exit": run.returncode,
        "lychee_counts": {name: report[name] for name in ("total", "unique", "successful", "errors", "excludes")},
        "lychee_errors": errors,
    }


def results():
    with TemporaryDirectory(prefix="llmlang-nav-delta-") as directory:
        root = Path(directory)
        tree = subprocess.check_output(["git", "archive", BASELINE], cwd=ROOT, timeout=30)
        with tarfile.open(fileobj=io.BytesIO(tree)) as archive:
            archive.extractall(root, filter="data")
        baseline = scan(root)
        edited = root / REPAIR
        text = edited.read_text(encoding="utf-8")
        if text.count(OLD) != 1:
            raise ValueError("Expected one exact link to repair")
        edited.write_text(text.replace(OLD, NEW), encoding="utf-8")
        curated = scan(root)
    before = [entry for entry in baseline["lychee_errors"]
              if not entry["source"].startswith("research/references/")]
    after = [entry for entry in curated["lychee_errors"]
             if not entry["source"].startswith("research/references/")]
    if (len(before) != 1 or before[0]["source"] != REPAIR or after
            or baseline["unreachable_with_directory_links"] or curated["unreachable_with_directory_links"]):
        raise AssertionError("Expected one repaired first-party citation and full directory reachability")
    return {
        "schema": "llmlang-shared-branch-navigation-delta/1", "revision": BASELINE,
        "python": platform.python_version(), "kernel": platform.release(), "arch": platform.machine(),
        "image": IMAGE, "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in (
            Path(__file__), ROOT / ".github/scripts/audit_research_index_coverage.py",
            ROOT / ".github/scripts/audit_research_index_reachability.py",
        )},
        "repair": {"path": REPAIR, "from": OLD, "to": NEW},
        "baseline": baseline, "after_link_repair": curated,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
