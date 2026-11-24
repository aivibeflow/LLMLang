#!/usr/bin/env python3
"""Refresh exact inventory identities across the pinned thematic moves."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

from audit_research_index_coverage import INLINE_LINK
from audit_research_relocation import AFTER, git, relocation_map, research_tree

MANAGEMENT = "research/research-management"
MANIFEST = f"{MANAGEMENT}/RESEARCH-CORPUS-INVENTORY-2026-11-20.json"

PR446_MOVE = "822cbf5175b55db0ffd8aac680178cfb5578e5d6"
ROOT_MOVE = "074bd058fe53d580dcdc0f8432e6d727f4412484"
SCENARIO = re.compile(r"^RESEARCH-SCENARIO-\d+[A-Z]?(?:-|\.)", re.IGNORECASE)
FIXED_METADATA = {
    "RT-00-G-CURRENT-STATUS-AND-EXIT-REPORT-2026-11-21.md": (["PLAN.md §0.1"], [0]),
    "RT-07-SOURCE-OWNED-QUERY-ENVELOPE.md": (["RT-07", "Scenario 34"], [2]),
    "RT-24-GIT-REPLAY-SOURCE-CLOSURE.md": (["RT-24"], [4]),
}


def active_research_tree(commit):
    tree = research_tree(commit)
    tree.pop(MANIFEST, None)
    return tree


def map_record_paths(paths):
    before = git("rev-parse", f"{AFTER}^").decode("ascii").strip()
    first, _ = relocation_map(research_tree(before), research_tree(AFTER))
    delta = git("diff", "--diff-filter=R", "--name-status", "-M100%", "-z",
                AFTER, PR446_MOVE, "--", "research/").decode("utf-8").split("\0")[:-1]
    second = dict(zip(delta[1::3], delta[2::3], strict=True))
    root_before = active_research_tree(f"{ROOT_MOVE}^")
    root_after = active_research_tree(ROOT_MOVE)
    third = {
        path: f"{MANAGEMENT}/{PurePosixPath(path).name}"
        for path in root_before.keys() - root_after.keys()
        if len(PurePosixPath(path).parts) == 2
    }
    if (set(third) != root_before.keys() - root_after.keys()
            or set(third.values()) != root_after.keys() - root_before.keys()):
        raise ValueError("Root move requires unique same-name paths")
    result = {}
    for path in paths:
        moved = first.get(path, path)
        moved = second.get(moved, moved)
        result[path] = third.get(moved, moved)
    if len(set(result.values())) != len(result):
        raise ValueError("Two archived records map to the same current path")
    return result


def new_role(path):
    file = PurePosixPath(path)
    name = file.name
    parts = file.parts
    if name == "README.md" and (len(parts) == 3 or parts[-2] == "RT-08"):
        items = ["RT-08"] if parts[-2] == "RT-08" else ["PLAN.md §0.1"]
        stages = [2] if parts[-2] == "RT-08" else [0]
        return "index-or-research-management", items, stages, "Navigation and scope index."
    if name == "README.md" and parts[-2] in {"RT-37", "RT-38"}:
        item = parts[-2]
        return "research-area-or-experiment-document", [item], [5 if item == "RT-37" else 6], "Proposed research brief, pilot and prerequisite gates."
    if "CONTRACT-FORMALIZATION-CORPUS" in parts:
        items = ["RT-02", "RT-36"]
        if name.startswith("CF-008-"):
            items.append("RT-10")
        return "example-or-fixture", items, [1, 2], "Contract formalization case with scoped claims and explicit assumptions."
    if "PROOF-OBLIGATION-BENCHMARK" in parts:
        items = ["RT-33"]
        if len(parts) == 4 and file.suffix == ".md":
            return "research-area-or-experiment-document", items, [2], "Design, result, negative controls and reproduction report."
        if file.suffix in {".py", ".lean"}:
            if name.startswith("test_"):
                return "prototype-test-evidence", items, [2], "Executable unit and negative-control tests for the bounded benchmark."
            return "prototype-or-experiment-implementation", items, [2], "Bounded proof experiment or adapter source."
        if file.suffix == ".smt2":
            return "structured-fixture-or-schema", items, [2], "Archived generated SMT-LIB query for the symbolic model."
        if file.suffix in {".json", ".txt"}:
            return "prototype-test-evidence", items, [2], "Archived bounded experiment output, proof, diagnostic or summary."
    if name == "SymbolicCpcCertificate.lean":
        return "prototype-or-experiment-implementation", ["RT-07", "RT-33"], [2], "Lean binding for exact source assertions and Logos CPC verdicts."
    if name == "LLMLang-FORMAL-VERIFICATION.ru.md":
        return "research-background-or-design-analysis", ["RT-07"], [2], "Russian-language companion on formal verification."
    if name.startswith("RT-36-"):
        return "research-area-or-experiment-document", ["RT-36"], [2], "Typed assumptions, trust boundaries and conditional proof research."
    if name == "PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md":
        return "research-area-or-experiment-document", ["RT-05", "RT-20"], [1], "Candidate public names, provider refinement and evidence binding."
    if len(parts) == 4 and parts[1:3] == ("research-management", "RT-00"):
        if name.startswith(("RT-00-QUALITY-RULES-", "RT-00-A-CORPUS-RELOCATION-", "RT-00-A-THEMATIC-INVENTORY-")):
            section = "PLAN.md §0.2" if "QUALITY-RULES-" in name else "PLAN.md §0.1"
            category = "audit-or-review-report" if file.suffix == ".md" else "prototype-test-evidence"
            return category, [section], [0], "RT-00 audit report or its reproducible observation ledger."
    raise ValueError(f"Unclassified new path: {path}")


def mask_relative_inline_destinations(text):
    def mask(match):
        group = 1 if match.group(1) else 2
        target = match.group(group)
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path or target.startswith("/"):
            return match.group()
        start = match.start(group) - match.start()
        end = match.end(group) - match.start()
        return match.group()[:start] + "<relative destination>" + match.group()[end:]

    return INLINE_LINK.sub(mask, text)


def scan_stale(source, destination, blob, previous_blob):
    record = {"path": destination, "prior_path": source, "prior_blob": previous_blob, "current_blob": blob}
    if PurePosixPath(destination).suffix in {".md", ".mdx"}:
        old = git("cat-file", "blob", previous_blob).decode("utf-8")
        new = git("cat-file", "blob", blob).decode("utf-8")
        if mask_relative_inline_destinations(old) == mask_relative_inline_destinations(new):
            record["delta"] = "inline relative destinations only"
            return record
    record["delta"] = "additional content or unrecognized navigation changes"
    return record


def counts(paths, records, target):
    sizes = Counter(PurePosixPath(path).suffix for path in paths)
    categories = Counter(record["category"] for record in records)
    taxonomy = git("show", f"{target}:{MANAGEMENT}/RESEARCH-TAXONOMY.md").decode("utf-8")
    dependency_map = git("show", f"{target}:{MANAGEMENT}/RESEARCH-DEPENDENCY-MAP.md").decode("utf-8")
    return {
        "research_files": len(paths),
        "research_artifacts_excluding_manifest": len(paths),
        "markdown_files": sizes[".md"],
        "mdx_files": sizes[".mdx"],
        "python_files": sizes[".py"],
        "lean_source_files": sizes[".lean"],
        "scenario_named_documents": sum(bool(SCENARIO.match(PurePosixPath(path).name)) for path in paths),
        "prototype_tree_files": sum(
            "PROTOTYPES" in PurePosixPath(path).parts[:-2] for path in paths
        ),
        "preparation_and_reference_files": sum(
            path.startswith(("research/preparation/", "research/references/")) for path in paths
        ),
        "taxonomy_research_areas": len(re.findall(r"^\|\s*RT-\d{2}\s*\|", taxonomy, re.M)),
        "dependency_edges": len(re.findall(r"^\|\s*DEP-\d{3}\s*\|", dependency_map, re.M)),
        "category_counts": dict(sorted(categories.items())),
    }


def refresh(baseline, target):
    archived = json.loads(git("show", f"{baseline}:{MANIFEST}"))
    old_records = {record["path"]: record for record in archived["artifacts"]}
    path_map = map_record_paths(old_records)
    reverse_map = {new: old for old, new in path_map.items()}
    paths = active_research_tree(target)
    dropped = sorted(reverse_map.keys() - paths.keys())
    if dropped:
        raise ValueError(f"Archived record paths need an explicit disposition: {dropped}")
    reviewed_roles = set(archived["current_tree_reconciliation"]["refreshed_existing_paths"])
    records, stale, added = [], [], []
    for path, (blob, size) in sorted(paths.items()):
        if path in reverse_map:
            source = reverse_map[path]
            record = dict(old_records[source])
            previous = record["git_blob_sha"]
            if previous != blob or record["size_bytes"] != size:
                stale.append(scan_stale(source, path, blob, previous))
            if source in reviewed_roles:
                fields = FIXED_METADATA.get(PurePosixPath(path).name)
                if fields:
                    items, stages = fields
                    record["traceability"] = {
                        "items": items, "method": "current title, purpose and direct research links",
                        "confidence": "high",
                    }
                    record["plan_stages"] = stages
                record["role_recheck"] = "Current title or module entry point, purpose and family reviewed. Claim reruns are tracked independently."
        else:
            category, items, stages, basis = new_role(path)
            added.append(path)
            record = {
                "category": category,
                "traceability": {"items": items, "method": "current file and research-family scope", "confidence": "medium"},
                "plan_stages": stages,
                "semantic_review": {"status": "first-pass-content-triage", "basis": basis},
            }
        record.update(path=path, git_blob_sha=blob, size_bytes=size)
        records.append(record)

    blobs = defaultdict(list)
    for path, (blob, _) in paths.items():
        blobs[blob].append(path)
    prior_dupes = {row["blob_sha"]: row for row in archived["duplicate_blob_groups"]}
    raw_unsat_paths = [
        f"research/formal-verification/PROOF-OBLIGATION-BENCHMARK/symbolic-smt-results/{case}-stdout.txt"
        for case in ("absolute", "zero-final")
    ]
    if all(path in paths for path in raw_unsat_paths):
        verdict_blob = paths[raw_unsat_paths[0]][0]
        if sorted(blobs[verdict_blob]) == sorted(raw_unsat_paths):
            prior_dupes[verdict_blob] = {
                "interpretation": "Same raw unsat output from distinct pinned queries. Keep both query-scoped records."
            }
    dupes = [
        {"blob_sha": blob, "paths": sorted(names),
         "interpretation": prior_dupes.get(blob, {}).get("interpretation", "Exact bytes; relationship requires review.")}
        for blob, names in sorted(blobs.items()) if len(names) > 1
    ]
    source_tree = active_research_tree(baseline)
    source_id = git("rev-parse", f"{baseline}:{MANIFEST}").decode("ascii").strip()
    archived["revision"] = baseline
    archived["source"] = "Exact research path, blob and byte inventory for the staged tree based on this main revision, excluding the inventory manifest itself."
    archived["classification_note"] = "New paths have first-pass roles. Carried-forward role mappings and recorded byte changes do not certify scientific or semantic equivalence."
    archived["counts"] = counts(paths, records, target)
    archived["duplicate_blob_groups"] = dupes
    archived["artifacts"] = records
    archived["previous_post_refresh_reconciliation"] = archived.pop("current_tree_reconciliation")
    archived["current_tree_reconciliation"] = {
        "source_revision": baseline,
        "archived_manifest_git_blob": source_id,
        "baseline_artifacts_excluding_manifest": len(source_tree),
        "previous_records": len(old_records),
        "current_records": len(records),
        "mapped_relocations": sum(old != new for old, new in path_map.items()),
        "new_role_records": added,
        "refreshed_existing_paths": [path_map[path] for path in sorted(reviewed_roles)],
        "updated_identities": stale,
        "edit_shape_counts": dict(sorted(Counter(row["delta"] for row in stale).items())),
        "prototype_path_scope": "Files under a family directory in any thematic or shared PROTOTYPES tree.",
        "role_review_boundary": "Only the explicitly recorded prior role queue and new roles were reviewed. Masking link destinations establishes edit shape, not destination or semantic equivalence.",
    }
    return archived


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--target-tree", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = refresh(args.baseline, args.target_tree)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reconciliation = data["current_tree_reconciliation"]
    print(json.dumps({key: reconciliation[key] for key in (
        "baseline_artifacts_excluding_manifest", "previous_records", "current_records",
        "mapped_relocations", "edit_shape_counts",
    )}, indent=2))
