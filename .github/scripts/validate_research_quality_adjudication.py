#!/usr/bin/env python3
"""Validate that adjudication covers exactly the frozen unreviewed warnings.

This checks bookkeeping and local citation ranges only. It does not check
whether the human interpretation or scientific result is correct.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED = {"layout-only", "documentation-gap"}


def validate(sample: dict, adjudication: dict, root: Path) -> list[str]:
    errors = []
    originals = {r["path"]: r for r in sample["files"]}
    expected = {
        (r["path"], w)
        for r in sample["files"]
        for w in r["expected_warnings"]
        if w not in {x["warning"] for x in r["confirmed_layout_only"]}
    }
    actual = []
    for file in adjudication["files"]:
        path = file["path"]
        if path not in originals:
            errors.append(f"unexpected path: {path}")
            continue
        rel = Path(path)
        target = (root / rel).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            errors.append(f"missing or invalid source: {path}")
            continue
        line_count = len(target.read_text(encoding="utf-8").splitlines())
        for row in file["judgments"]:
            pair = (path, row["warning"])
            actual.append(pair)
            if row["disposition"] not in ALLOWED:
                errors.append(f"invalid disposition: {pair}")
            if not row.get("assessment", "").strip() or not row.get("follow_up", "").strip():
                errors.append(f"missing rationale or follow-up: {pair}")
            if not row.get("source_lines", "").strip():
                errors.append(f"missing cited lines: {pair}")
            else:
                import re
                nums = [int(n) for n in re.findall(r"\bL(\d+)\b|[–-](\d+)", row["source_lines"]) for n in n if n]
                # The citation is intentionally human-readable; only its explicitly
                # prefixed L markers and range endpoints are checked.
                if not nums or any(n < 1 or n > line_count for n in nums):
                    errors.append(f"invalid cited lines: {pair}")
    if len(set(actual)) != len(actual):
        errors.append("duplicate adjudication entries")
    missing = expected - set(actual)
    unexpected = set(actual) - expected
    if missing:
        errors.append(f"unadjudicated: {sorted(missing)}")
    if unexpected:
        errors.append(f"unexpected adjudications: {sorted(unexpected)}")
    if adjudication.get("baseline_commit") != sample.get("baseline_commit"):
        errors.append("baseline mismatch")

    stated = adjudication.get("summary", {})
    by_type = {k: sum(
        row["disposition"] == k for doc in adjudication["files"] for row in doc["judgments"]
    ) for k in sorted(ALLOWED)}
    for k, v in by_type.items():
        if stated.get(k) != v:
            errors.append(f"incorrect summary count {k}: expected {v}")
    if stated.get("remaining_initial") != len(expected):
        errors.append("incorrect remaining_initial")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--sample", type=Path, default=Path("research/quality-audit/2026-11-23-sample.json"))
    parser.add_argument("--adjudication", type=Path, default=Path("research/quality-audit/2026-11-23-adjudication.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    sample = json.loads((root / args.sample).read_text(encoding="utf-8"))
    adj = json.loads((root / args.adjudication).read_text(encoding="utf-8"))
    errs = validate(sample, adj, root)
    print(json.dumps({
        "scope": "manifest consistency and citation-range presence only",
        "source_reports": len(sample["files"]), "adjudicated": sum(len(x["judgments"]) for x in adj["files"]),
        "layout_only": adj["summary"]["layout-only"],
        "documentation_gaps": adj["summary"]["documentation-gap"], "errors": errs
    }, indent=2))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
