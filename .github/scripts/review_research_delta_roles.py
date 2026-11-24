#!/usr/bin/env python3
"""Classify the formerly unclassified evidence-inventory deltas at pinned blobs."""

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import re

from audit_research_relocation import git
from refresh_relocated_research_inventory import MANIFEST, mask_relative_inline_destinations

ARCHIVED_INVENTORY = "6ea8f0891190b9c3029a879fd1f7fa61fb84d7b8"
CURRENT = "f98df901a0213bd06315dc8878bd5a9f66938f99"
DIRECTION_PATH = re.compile(
    r"\bresearch/(?:compiler-and-translation|formal-verification|language-design|"
    r"packages-and-ecosystem|research-management|runtime-and-systems|security|"
    r"semantic-representation|toolchain-and-collaboration)/"
)
PUBLIC = re.compile(r"Public.interface (?:integration|extension)|Public interfaces|"
                    r"Публичные интерфейсы|Public-interface cross-area", re.I)
ASSUMPTIONS = re.compile(r"RT-36|explicit assumptions and conditional", re.I)
CASES = re.compile(r"CF-00[6-8]")
EXPLICIT_ROLES = {
    "lakefile.lean": "Lean build roots",
    "run_llvm_preservation_probes.py": "Relocated launcher paths",
    "RT-00-QUALITY-RULES-ADJUDICATION-2026-11-23.md": "Archived citation validation",
    "RESEARCH-DEPENDENCY-MAP.md": "Dependency register",
    "RESEARCH-TAXONOMY.md": "Research taxonomy",
    "LLMLang-FORMAL-VERIFICATION.md": "Translation and source companion",
    "LLMLang-CONCEPT.ru.md": "Translated candidate public interface section",
}


def navigation_projection(text):
    return mask_relative_inline_destinations(DIRECTION_PATH.sub("research/", text))


def classify(entry):
    path = entry["path"]
    old_blob = entry["prior_blob"]
    after_blob = entry["current_blob"]
    old = git("cat-file", "blob", old_blob).decode("utf-8")
    after = git("cat-file", "blob", after_blob).decode("utf-8")
    patch = git("diff", "--no-color", "--unified=0", old_blob, after_blob).decode("utf-8")
    added = [line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:] for line in patch.splitlines() if line.startswith("-") and not line.startswith("---")]
    body = "\n".join(added)
    if navigation_projection(old) == navigation_projection(after):
        roles = ["Recognized navigation or command paths"]
    else:
        roles = []
        if PUBLIC.search(body):
            roles.append("Public-interface candidate integration")
        if ASSUMPTIONS.search(body):
            roles.append("Proposed proof assumptions or trust boundary")
        if CASES.search(body):
            roles.append("Recently added contract-formalization case or link")
        explicit = EXPLICIT_ROLES.get(Path(path).name)
        if path == "research/README.md":
            roles.append("Research navigation and status index")
        if explicit:
            roles.append(explicit)
        if not roles:
            raise ValueError(f"Unreviewed change at {path}")

    current = git("rev-parse", f"{CURRENT}:{path}").decode("ascii").strip()
    return {
        "path": path,
        "prior_path": entry["prior_path"],
        "prior_blob": old_blob,
        "inventory_blob": after_blob,
        "current_main_blob": current,
        "added_line_count": len(added),
        "removed_line_count": len(removed),
        "added_headings": [line for line in added if line.startswith("#")],
        "reviewed_roles": roles,
    }


def review():
    manifest = json.loads(git("show", f"{ARCHIVED_INVENTORY}:{MANIFEST}"))
    deltas = manifest["current_tree_reconciliation"]["updated_identities"]
    selected = [entry for entry in deltas if entry["delta"] == "additional content or unrecognized navigation changes"]
    results = [classify(entry) for entry in selected]
    return {
        "schema": "rt00-research-delta-role-triage-v1",
        "inventory_commit": ARCHIVED_INVENTORY,
        "current_main_checked": CURRENT,
        "environment": {"python": platform.python_version(),
                        "git": git("--version").decode("ascii").strip(),
                        "platform": platform.platform()},
        "deltas": len(results),
        "role_counts": dict(sorted(Counter(
            role for row in results for role in row["reviewed_roles"]
        ).items())),
        "paths_updated_after_inventory": [
            row["path"] for row in results if row["inventory_blob"] != row["current_main_blob"]
        ],
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = review()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("deltas", "role_counts", "paths_updated_after_inventory")}, indent=2))
