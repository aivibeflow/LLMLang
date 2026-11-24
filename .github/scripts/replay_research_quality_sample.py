#!/usr/bin/env python3
"""Replay a pinned legacy-report sample with a transparent source mode.

--from-baseline reads each file from the manifest's exact Git commit, not
today's working tree. This preserves the 2026-11-23 historical warning sample
after legitimate report revisions. No text matching validates scientific truth.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from check_research_quality import inspect


def git_blob_hash(root: Path, payload: bytes) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "hash-object", "--stdin"],
        input=payload, check=True, capture_output=True,
    ).stdout.decode("ascii").strip()


def read_sample_source(root: Path, path: str, baseline: str | None) -> bytes:
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe repository-relative path")

    if baseline is not None:
        result = subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", f"{baseline}:{path}"],
            capture_output=True,
        )
        if result.returncode:
            raise ValueError("baseline Git object/path unavailable")
        return result.stdout

    target = (root / relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("file missing/outside repository")
    return target.read_bytes()


def run(root: Path, manifest: dict, *, from_baseline: bool = False) -> dict:
    results = []
    root = root.resolve()
    baseline = manifest["baseline_commit"]
    for item in manifest["files"]:
        rel = item["path"]
        try:
            payload = read_sample_source(root, rel, baseline if from_baseline else None)
        except ValueError as error:
            results.append({
                "path": rel, "error": str(error),
                "expected_blob": item["git_blob"], "blob_matched": False,
                "warnings": [], "expected_warning_match": False,
            })
            continue

        blob = git_blob_hash(root, payload)
        try:
            warnings = inspect(payload.decode("utf-8"))
        except UnicodeDecodeError:
            warnings = ["invalid UTF-8 report bytes"]
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
        "scope": "frozen historical structure sample, NOT research claim correctness",
        "source_mode": "git-baseline" if from_baseline else "working-tree",
        "baseline_commit": baseline,
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
    parser.add_argument("--from-baseline", action="store_true",
                        help="Read bytes from the exact manifest baseline commit:path, not current worktree")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--assert-snapshot", action="store_true",
                        help="Fail if the chosen source bytes or warnings differ from the manifest")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    result = run(root, manifest, from_baseline=args.from_baseline)
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
