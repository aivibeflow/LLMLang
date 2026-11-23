#!/usr/bin/env python3
"""Replay a bounded, pinned research-report formatting sample (not a quality gate).

The tool verifies immutable Git blob identities, then records current heuristic
warnings and their differences from the frozen sample. It never validates
technical claims or interprets an accepted decision.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from check_research_quality import inspect


def run(root: Path, manifest: dict) -> dict:
    results = []
    for item in manifest["files"]:
        rel = item["path"]
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            results.append({
                "path": rel, "error": "file missing/outside repository",
                "expected_blob": item["git_blob"], "blob_matched": False,
                "warnings": [], "expected_warning_match": False,
            })
            continue

        blob = subprocess.run(
            ["git", "-C", str(root), "hash-object", "--", rel],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        warnings = inspect(path.read_text(encoding="utf-8"))
        results.append({
            "path": rel,
            "blob": blob,
            "expected_blob": item["git_blob"],
            "blob_matched": blob == item["git_blob"],
            "warnings": warnings,
            "expected_warning_match": warnings == item["expected_warnings"],
            "confirmed_layout_only": item["confirmed_layout_only"],
        })

    return {
        "scope": "surface-only warning replay, not evidence or specification validation",
        "baseline_commit": manifest["baseline_commit"],
        "reports_checked": len(results),
        "total_warnings": sum(len(x["warnings"]) for x in results),
        "blob_mismatches": sum(not x["blob_matched"] for x in results),
        "warning_snapshot_mismatches": sum(not x["expected_warning_match"] for x in results),
        "reports": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=Path("research/quality-audit/2026-11-23-sample.json"))
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--assert-snapshot", action="store_true",
                        help="Opt-in verification of frozen blob and warning snapshot; not enabled by CI")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    result = run(root, manifest)
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(output, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output, encoding="utf-8")
    return int(args.assert_snapshot and (
        result["blob_mismatches"] > 0 or result["warning_snapshot_mismatches"] > 0
    ))


if __name__ == "__main__":
    raise SystemExit(main())
