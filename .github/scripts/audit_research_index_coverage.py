#!/usr/bin/env python3
"""Audit incoming Markdown references to tracked research documents.

This is a structural discoverability audit, not a semantic index-acceptance gate.
It uses only the Python standard library and intentionally reports candidates
rather than failing when a research document has no incoming Markdown link.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit


FENCED_BLOCK = re.compile(r"(?ms)^[ \t]{0,3}(`{3,}|~{3,}).*?^[ \t]{0,3}\1[ \t]*$")
HTML_COMMENT = re.compile(r"(?s)<!--.*?-->")
INLINE_CODE = re.compile(r"(?s)(?<!`)(`+).*?\1(?!`)")
INLINE_LINK = re.compile(r"!?(?:\[[^\]]*\])\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)")
HTML_TARGET = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
REFERENCE_DEF = re.compile(r"(?m)^[ \t]{0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))")
SCENARIO_NAME = re.compile(r"^RESEARCH-SCENARIO-\d+[A-Z]?(?:-|\.)", re.IGNORECASE)


def strip_non_prose(text: str) -> str:
    text = HTML_COMMENT.sub("", text)
    text = FENCED_BLOCK.sub("", text)
    return INLINE_CODE.sub("", text)


def extract_targets(text: str) -> list[str]:
    prose = strip_non_prose(text)
    targets: list[str] = []
    for match in INLINE_LINK.finditer(prose):
        targets.append(match.group(1) or match.group(2))
    targets.extend(match.group(1) or match.group(2) for match in HTML_TARGET.finditer(prose))
    # Reference definitions are included as declared navigation targets. This
    # may include an unused definition; the output is a conservative candidate map.
    targets.extend(match.group(1) or match.group(2) for match in REFERENCE_DEF.finditer(prose))
    return targets


def resolve_local_target(root: Path, source: Path, raw_target: str) -> str | None:
    parsed = urlsplit(raw_target.strip())
    if parsed.scheme or parsed.netloc or raw_target.startswith(("/", "#")):
        return None
    decoded = unquote(parsed.path)
    if not decoded:
        return None
    target = (source.parent / decoded).resolve()
    root_resolved = root.resolve()
    try:
        relative = target.relative_to(root_resolved)
    except ValueError:
        return None
    if target.is_dir():
        readme = target / "README.md"
        if readme.is_file():
            return readme.relative_to(root_resolved).as_posix()
        return relative.as_posix()
    return relative.as_posix()


def is_index_document(path: str) -> bool:
    p = Path(path)
    name = p.name.upper()
    return (
        name == "README.MD"
        or "INDEX" in name
        or path == "PLAN.md"
        or path == "research/research-management/RESEARCH-TAXONOMY.md"
        or path == "research/research-management/RESEARCH-CORPUS-SEMANTIC-TRACEABILITY-2026-11-20.md"
    )


def audit(root: Path) -> dict:
    root = root.resolve()
    docs = sorted(
        p for base in (root / "research",)
        for p in base.rglob("*")
        if p.is_file() and p.suffix.lower() in {".md", ".mdx"}
    )
    plan = root / "PLAN.md"
    if plan.is_file():
        docs.append(plan)

    doc_paths = {p.relative_to(root).as_posix() for p in docs}
    inbound: dict[str, set[str]] = defaultdict(set)
    inbound_from_index: dict[str, set[str]] = defaultdict(set)
    local_link_occurrences = 0
    unresolved_local_targets: list[dict[str, str]] = []
    non_markdown_targets: list[dict[str, str]] = []

    for source in docs:
        source_rel = source.relative_to(root).as_posix()
        for raw in extract_targets(source.read_text(encoding="utf-8", errors="replace")):
            target = resolve_local_target(root, source, raw)
            if target is None:
                continue
            local_link_occurrences += 1
            if target in doc_paths and target != source_rel:
                inbound[target].add(source_rel)
                if is_index_document(source_rel):
                    inbound_from_index[target].add(source_rel)
            elif (root / target).exists():
                non_markdown_targets.append({"source": source_rel, "target": target})
            else:
                unresolved_local_targets.append({"source": source_rel, "target": raw})

    research_docs = sorted(p for p in doc_paths if p.startswith("research/"))
    scenario_docs = sorted(p for p in research_docs if SCENARIO_NAME.match(Path(p).name))
    index_docs = sorted(p for p in doc_paths if is_index_document(p))
    zero_inbound = [p for p in research_docs if not inbound.get(p)]
    no_index_inbound = [p for p in research_docs if not inbound_from_index.get(p)]
    scenario_no_index = [p for p in scenario_docs if not inbound_from_index.get(p)]
    scenario_zero_inbound = [p for p in scenario_docs if not inbound.get(p)]

    return {
        "method": {
            "parser": "Python stdlib conservative Markdown/HTML link-target extraction",
            "ignored": ["external URLs", "mailto/data URLs", "fragment-only links", "root-absolute site paths", "code blocks", "HTML comments"],
            "reference_definitions": "counted as declared targets whether or not a usage was detected",
            "index_document_rule": "README.md, *INDEX*.md, PLAN.md, RESEARCH-TAXONOMY.md, and the semantic traceability report",
            "interpretation": "zero-inbound and no-index-inbound are review candidates, not automatic defects"
        },
        "summary": {
            "documents_scanned": len(doc_paths),
            "research_markdown_mdx_documents": len(research_docs),
            "index_documents": len(index_docs),
            "local_link_occurrences": local_link_occurrences,
            "unique_research_targets_with_inbound_links": sum(1 for p in research_docs if inbound.get(p)),
            "research_documents_with_zero_inbound_links": len(zero_inbound),
            "research_documents_without_inbound_link_from_designated_index": len(no_index_inbound),
            "scenario_documents": len(scenario_docs),
            "scenario_documents_with_zero_inbound_links": len(scenario_zero_inbound),
            "scenario_documents_without_inbound_link_from_designated_index": len(scenario_no_index),
            "unresolved_local_targets": len(unresolved_local_targets),
            "non_markdown_targets": len(non_markdown_targets)
        },
        "index_documents": index_docs,
        "scenario_documents_without_index_inbound": scenario_no_index,
        "scenario_documents_with_zero_inbound": scenario_zero_inbound,
        "research_documents_with_zero_inbound": zero_inbound,
        "research_documents_without_index_inbound": no_index_inbound,
        "unresolved_local_targets": unresolved_local_targets,
        "non_markdown_targets": non_markdown_targets
    }


def markdown_report(result: dict, revision: str) -> str:
    s = result["summary"]
    lines = [
        "# Research index coverage audit",
        "",
        f"**Revision:** `{revision}`",
        "",
        "## Summary",
        "",
        "| Measure | Count |",
        "|---|---:|",
    ]
    for key, value in s.items():
        lines.append(f"| {key.replace('_', ' ')} | {value} |")
    lines.extend([
        "",
        "## Scenario documents without a designated-index inbound link",
        "",
    ])
    lines.extend(f"- `{p}`" for p in result["scenario_documents_without_index_inbound"])
    lines.extend([
        "",
        "## Scenario documents with zero inbound Markdown/MDX links",
        "",
    ])
    lines.extend(f"- `{p}`" for p in result["scenario_documents_with_zero_inbound"])
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This is a conservative structural scan. A file with no incoming link is a discoverability candidate, not automatically an orphan or an invalid artifact. A link from a designated index is a navigation edge only; it does not establish semantic relevance, test coverage, evidence support, or PLAN exit-criterion acceptance. Manual review is required before changing indexes or deleting/reclassifying any file.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--revision", default="unknown")
    args = parser.parse_args()
    result = audit(args.root)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    report = markdown_report(result, args.revision)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(report, encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
