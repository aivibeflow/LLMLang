#!/usr/bin/env python3
"""Measure transitive navigation to pinned research files."""
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import platform
from urllib.parse import unquote, urlsplit

from audit_research_index_coverage import audit, extract_targets, resolve_local_target

ROOTS = ("research/README.md", "PLAN.md")


def reachable(edges):
    visited = set(ROOTS)
    pending = deque(ROOTS)
    while pending:
        for target in edges[pending.popleft()] - visited:
            visited.add(target)
            pending.append(target)
    return visited


def measure(root):
    root = root.resolve()
    research = root / "research"
    files = {
        p.relative_to(root).as_posix()
        for p in research.rglob("*") if p.is_file()
    }
    docs = {p for p in files if Path(p).suffix.lower() in {".md", ".mdx"}}
    contents = defaultdict(set)
    for path in files:
        for parent in Path(path).parents:
            if parent.as_posix().startswith("research"):
                contents[parent.as_posix()].add(path)

    explicit = defaultdict(set)
    with_directory = defaultdict(set)
    for path in sorted(docs | set(ROOTS)):
        source = root / path
        for url in extract_targets(source.read_text(encoding="utf-8")):
            target = resolve_local_target(root, source, url)
            if target is None:
                continue
            if target in files:
                explicit[path].add(target)
                with_directory[path].add(target)
            linked = (source.parent / unquote(urlsplit(url).path)).resolve()
            if linked.is_dir() and linked.is_relative_to(research):
                with_directory[path].update(contents[linked.relative_to(root).as_posix()])

    direct_index = audit(root)
    explicit_paths = reachable(explicit) & files
    visible_paths = reachable(with_directory) & files
    return {
        "roots": ROOTS,
        "summary": {
            "artifacts": len(files),
            "markdown_mdx_documents": len(docs),
            "artifacts_reachable_by_document_links": len(explicit_paths),
            "documents_reachable_by_document_links": len(docs & explicit_paths),
            "artifacts_reachable_with_directory_links": len(visible_paths),
            "documents_reachable_with_directory_links": len(docs & visible_paths),
            "documents_without_a_direct_index_link": len(direct_index["research_documents_without_index_inbound"]),
            "documents_without_an_incoming_document_link": len(direct_index["research_documents_with_zero_inbound"]),
        },
        "artifacts_reachable_only_with_directory_links": sorted(visible_paths - explicit_paths),
        "artifacts_unreachable_with_directory_links": sorted(files - visible_paths),
        "unresolved_local_path_occurrences": direct_index["unresolved_local_targets"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", required=True, type=Path)
    parser.add_argument("--baseline-revision", required=True)
    parser.add_argument("--target-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = {
        "schema": "rt00-index-reachability-v1",
        "baseline_revision": args.baseline_revision,
        "environment": {"python": platform.python_version(), "arch": platform.machine()},
        "baseline": measure(args.baseline_dir),
        "curated_links": measure(args.target_dir),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k]["summary"] for k in ("baseline", "curated_links")}, indent=2))
