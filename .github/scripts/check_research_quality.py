#!/usr/bin/env python3
"""Warning-first structural pilot for newly added LLMLang research reports.

Presence is not evidence quality. This checker never verifies a claim or accepts a decision.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

SECTION_RULES = {
    "question/problem": r"question|problem",
    "hypotheses/alternatives": r"hypothes|alternativ|candidate vector",
    "prior art/sources": r"prior|source|related research|existing evidence",
    "formal model/assumptions": r"formal model|model|assumption|scope|definitions",
    "experiments/method": r"experiment|method|procedure|reproduction",
    "results": r"result|finding|observation",
    "limitations": r"limitation|limit|threat|validity",
    "decision boundary": r"decision|recommendation|conclusion",
    "draft impact/traceability": r"draft impact|traceability|normative boundary|downstream impact",
}
EXPERIMENTAL = re.compile(r"(?im)^\*\*Evidence type:\*\*\s*(?:executable|experiment(?:al)?)\b")


def is_new_report(path: str) -> bool:
    p = Path(path)
    return (len(p.parts) == 2 and p.parts[0] == "research" and
            p.suffix.lower() in {".md", ".mdx"} and
            (p.name.startswith("RT-") or p.name.startswith("RESEARCH-SCENARIO-")))


def added_reports(root: Path, base: str) -> list[str]:
    cp = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=A", "-z",
         f"{base}...HEAD", "--", "research/"],
        check=True, capture_output=True,
    )
    return sorted(p for p in cp.stdout.decode("utf-8").split("\0") if is_new_report(p))


def inspect(text: str) -> list[str]:
    """Heuristic warnings only: no interpretation of evidence or acceptance status."""
    findings = []
    headings = "\n".join(re.findall(r"(?m)^#{2,4}\s+(.+)$", text)).lower()
    for name, pattern in SECTION_RULES.items():
        if not re.search(pattern, headings, re.IGNORECASE):
            findings.append(f"missing section for {name}")
    for label in ("Status", "Baseline"):
        # Historical reports use "**Status:** ...", "**Status** — ...",
        # or "- **Status** · ...". This is formatting variation, not absence.
        marker = rf"(?im)^[ \t]*(?:-[ \t]*)?\*\*{label}:?\*\*[ \t]*(?:[:·—–-][ \t]*)?\S"
        if not re.search(marker, text):
            findings.append(f"missing metadata: {label}")
    if not re.search(r"(?i)observation|assumption|conjecture|hypothesis|model result|experimental result|proof|prior.art claim", text):
        findings.append("no recognizable evidence class; human claim-level review required")
    if not re.search(r"(?i)negative|reject|counterexample|failure|unknown|not applicable", text):
        findings.append("negative/rejected/UNKNOWN cases or justified N/A not located")
    if EXPERIMENTAL.search(text):
        for label in ("Fixture", "Tool versions", "Expected output"):
            if not re.search(rf"(?im)^\*\*{label}:\*\*\s*\S", text):
                findings.append(f"executable evidence missing: {label}")
        if not re.search(r"(?m)^```(?:sh|bash|shell|console)\b", text):
            findings.append("executable evidence missing: fenced reproduction command")
    return findings


def run(root: Path, paths: list[str]) -> dict:
    reports = []
    for rel in sorted(set(paths)):
        file = (root / rel).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():
            reports.append({"path": rel, "warnings": ["file missing or outside repository"]})
            continue
        reports.append({"path": rel, "warnings": inspect(file.read_text(encoding="utf-8"))})
    return {"scope": "structural heuristic only; not claim validation or policy adoption",
            "reports_checked": len(reports),
            "warnings": sum(len(p["warnings"]) for p in reports), "reports": reports}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--changed-base", help="Git base ref; inspect added first-party research reports")
    src.add_argument("--files", nargs="+", help="Explicit repo-relative paths for a local review")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--strict", action="store_true", help="Opt-in local check; not enabled in CI")
    args = parser.parse_args()
    root = args.root.resolve()
    paths = added_reports(root, args.changed_base) if args.changed_base else args.files
    result = run(root, paths)
    result_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(result_json, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(result_json, encoding="utf-8")
    return int(args.strict and bool(result["warnings"]))


if __name__ == "__main__":
    raise SystemExit(main())
