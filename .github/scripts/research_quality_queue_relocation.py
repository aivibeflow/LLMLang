#!/usr/bin/env python3
"""Compare immutable review evidence with navigation after PR #444."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import platform

from check_research_quality import inspect
from research_quality_corpus_census import git, run

MAIN = "fe229c3215c42d8bded531d77bbef47761ac5770"
REGISTER = "research/quality-audit/2026-11-23-root-census-observations.json"


def documents(repo, commit):
    paths = {}
    for entry in git(repo, "ls-tree", "-r", "-z", commit, "research/").split(b"\0"):
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        _, kind, blob = header.decode("ascii").split()
        path = PurePosixPath(raw_path.decode("utf-8"))
        if kind == "blob" and path.suffix.lower() in {".md", ".mdx"}:
            paths[str(path)] = blob
    return paths


def grouped(paths, key):
    groups = defaultdict(list)
    for path in paths:
        groups[key(path)].append(path)
    return groups


def compare(repo):
    register = json.loads(git(repo, "show", f"{MAIN}:{REGISTER}"))
    baseline = register["baseline_commit"]
    replay = run(repo, baseline)
    if any(replay[key] != register[key] for key in ("summary", "review_queue")):
        raise ValueError("The archived census or review queue failed to reproduce")

    parent = git(repo, "rev-parse", f"{MAIN}^").decode("ascii").strip()
    trees = {commit: documents(repo, commit) for commit in (baseline, parent, MAIN)}
    current = trees[MAIN]
    by_name = grouped(current, lambda path: PurePosixPath(path).name)
    by_blob = grouped(current, current.__getitem__)
    rows = []
    for item in replay["review_queue"]:
        path, blob = item["path"], item["blob"]
        name = PurePosixPath(path).name
        name_matches = by_name[name]
        # A unique basename locates a navigation candidate even when its content
        # changed. It supplies no evidence that the historic review still applies.
        target = path if path in current else name_matches[0] if len(name_matches) == 1 else None
        target_blob = current.get(target)
        historical_warnings = inspect(git(repo, "show", f"{baseline}:{path}").decode("utf-8"))
        current_warnings = (
            inspect(git(repo, "show", f"{MAIN}:{target}").decode("utf-8")) if target else None
        )
        rows.append({
            "archive": item,
            "pre_move_path_blob": trees[parent].get(path),
            "current_old_path_blob": current.get(path),
            "current_basename_matches": name_matches,
            "current_exact_blob_matches": by_blob[blob],
            "current_navigation_path": target,
            "current_navigation_blob": target_blob,
            "archive_warnings": historical_warnings,
            "current_navigation_warnings": current_warnings,
        })

    return {
        "schema": "stage02-review-queue-relocation-v1",
        "baseline": baseline,
        "pre_move": parent,
        "main": MAIN,
        "environment": {
            "python": platform.python_version(),
            "git": git(repo, "--version").decode("ascii").strip(),
            "linux": platform.release(),
            "arch": platform.machine(),
        },
        "checker_git_blob": git(
            repo, "hash-object", ".github/scripts/check_research_quality.py"
        ).decode("ascii").strip(),
        "document_scope": {
            commit: {
                "recursive": len(paths),
                "root": sum(len(PurePosixPath(p).parts) == 2 for p in paths),
            }
            for commit, paths in trees.items()
        },
        "queue": rows,
        "summary": {
            "archival_replay_matches": len(rows),
            "current_exact_path_matches": sum(row["current_old_path_blob"] is not None for row in rows),
            "current_exact_path_and_blob_matches": sum(
                row["current_old_path_blob"] == row["archive"]["blob"] for row in rows
            ),
            "current_unique_exact_blob_matches": sum(
                len(row["current_exact_blob_matches"]) == 1 for row in rows
            ),
            "current_navigation_candidates": sum(row["current_navigation_path"] is not None for row in rows),
            "current_navigation_warning_lists_changed": sum(
                row["current_navigation_warnings"] != row["archive_warnings"]
                for row in rows if row["current_navigation_path"] is not None
            ),
            "current_navigation_blobs_changed_vs_pre_move": sum(
                row["current_navigation_blob"] != row["pre_move_path_blob"]
                for row in rows if row["current_navigation_path"] is not None
            ),
            "archive_warning_counts": dict(sorted(Counter(
                warning for row in rows for warning in row["archive_warnings"]
            ).items())),
            "human_reviews_completed": 0,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(Path(".").resolve())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
