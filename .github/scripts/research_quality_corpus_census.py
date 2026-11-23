#!/usr/bin/env python3
"""Pinned ROOT research Markdown structural census and deterministic reviewer queue.

This intentionally does NOT certify claim-level quality, technical correctness,
reviewer independence, or any specification/ADR acceptance. Its warning schema
is the existing Stage 0.2 *surface* heuristic, with known legacy false alarms.
Only root research/*.md and research/*.mdx files are in scope.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from check_research_quality import inspect


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True,
    ).stdout


def kind(path: str) -> str:
    name = path.removeprefix("research/")
    if name.startswith("RESEARCH-SCENARIO-"):
        return "scenario"
    if name.startswith("RT-"):
        return "rt"
    return "other-root"


def paths_at_commit(root: Path, sha: str) -> list[str]:
    entries = git(root, "ls-tree", "-r", "-z", "--name-only", sha, "research/")
    paths = (p.decode("utf-8") for p in entries.split(b"\0") if p)
    return sorted(
        p for p in paths
        if len(Path(p).parts) == 2 and
        Path(p).suffix.lower() in {".md", ".mdx"}
    )


def choose_sample(entries: list[dict], *, seed: str, per_stratum: int = 8) -> list[dict]:
    """Deterministic fixed-size stratum samples; no selection by warnings."""
    result = []
    for group in ("scenario", "rt", "other-root"):
        candidates = [r for r in entries if r["kind"] == group]
        ordered = sorted(
            candidates,
            key=lambda r: (hashlib.sha256((seed + ":" + r["path"]).encode("utf-8")).hexdigest(), r["path"]),
        )
        for index, r in enumerate(ordered[:per_stratum], 1):
            result.append({
                "path": r["path"], "blob": r["blob"], "kind": r["kind"],
                "selection_rank": index, "warning_count": len(r["warnings"]),
                "human_review": "NOT REVIEWED",
            })
    return result


def run(root: Path, baseline: str) -> dict:
    root = root.resolve()
    actual = git(root, "rev-parse", baseline).decode("ascii").strip()
    if actual != baseline:
        raise ValueError("baseline must be an exact 40-character Git commit SHA")
    entries = []
    hist = Counter()
    for path in paths_at_commit(root, baseline):
        raw = git(root, "show", f"{baseline}:{path}")
        blob = subprocess.run(
            ["git", "-C", str(root), "hash-object", "--stdin"],
            input=raw, check=True, capture_output=True,
        ).stdout.decode("ascii").strip()
        content = raw.decode("utf-8")
        warnings = inspect(content)
        hist.update(warnings)
        status_area = "\n".join(content.splitlines()[:12])
        executable_hint = bool(re.search(
            r"(?im)^\s*(?:-\s*)?\*\*status:?\*\*\s*(?:[:·—–-]\s*)?[^\n]*(?:executable|experiment|benchmark|native|probe)",
            status_area
        ))
        exact_type_marker = bool(re.search(r"(?im)^\*\*Evidence type:\*\*\s*\S", content))
        entries.append({
            "path": path, "kind": kind(path), "blob": blob,
            "warnings": warnings,
            "status_executable_hint": executable_hint,
            "explicit_evidence_type_field": exact_type_marker,
        })

    counts = Counter(r["kind"] for r in entries)
    sample_seed = "stage-0.2-reviewed-after:" + baseline
    sample = choose_sample(entries, seed=sample_seed, per_stratum=8)
    return {
        "schema": "stage02-pinned-root-research-structure-census-v1",
        "baseline_commit": baseline,
        "scope": "all Markdown/MDX documents DIRECTLY under research/ only; excludes nested markdown, prototype source, all other repository paths",
        "scientific_truth_validated": False,
        "human_review_completed": False,
        "quality_policy_adopted": False,
        "known_limitation": "legacy headings and formatting cause false structural warnings; absent warnings do NOT imply valid evidence; status keywords are non-authoritative hints",
        "selection": {
            "method": "deterministic SHA-256 rank seeded by exact baseline path, first 8 from each of three groups; no warning-dependent selection",
            "seed": sample_seed, "per_group": 8,
            "strata_populations": dict(sorted(counts.items())),
            "sampling_is_statistically_representative": False,
        },
        "summary": {
            "documents": len(entries),
            "by_kind": dict(sorted(counts.items())),
            "warning_instances": sum(len(r["warnings"]) for r in entries),
            "documents_with_warnings": sum(bool(r["warnings"]) for r in entries),
            "documents_without_warnings": sum(not r["warnings"] for r in entries),
            "explicit_evidence_type_field": sum(r["explicit_evidence_type_field"] for r in entries),
            "status_executable_hint": sum(r["status_executable_hint"] for r in entries),
            "warning_histogram": dict(sorted(hist.items())),
            "review_queue_count": len(sample),
        },
        "review_queue": sample,
        "reports": entries,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--baseline", required=True)
    p.add_argument("--json-out", type=Path)
    args = p.parse_args()
    result = run(args.repo, args.baseline)
    summ = result["summary"]
    print("CORPUS_CENSUS_SUMMARY=" + json.dumps(summ, separators=(",", ":"), sort_keys=True))
    print("CORPUS_CENSUS_SAMPLE=" + json.dumps(result["review_queue"], separators=(",", ":"), sort_keys=True))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
