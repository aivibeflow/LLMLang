#!/usr/bin/env python3
"""Audit the exact dedicated evidence and registry links of one published Git batch."""

import argparse
from collections import Counter
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import platform
import posixpath
import re
import subprocess

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "inputs.json"
REGISTRIES = ("PLAN.md", "research/research-management/RESEARCH-DEPENDENCY-MAP.md",
              "research/research-management/RESEARCH-OPTION-MATRIX-01.md",
              "research/research-management/RESEARCH-TAXONOMY.md")
LINK = re.compile(r"\]\((?:<([^>]+)>|([^\s\)]+))\)")
POLICIES = ("path_presence", "exact_dedicated", "exact_and_register_links", "all_pr_blobs")


def git(repo, *arguments):
    return subprocess.check_output(["git", "-C", str(repo), *arguments], timeout=20)


@lru_cache(maxsize=None)
def entries(repo, commit):
    result = {}
    for row in git(repo, "ls-tree", "-r", "-z", commit).split(b"\0")[:-1]:
        mode_oid, path = row.split(b"\t", 1)
        mode, kind, oid = mode_oid.decode().split()
        result[path.decode("utf-8")] = (mode, kind, oid)
    return result


def changed_paths(repo, source):
    return sorted(part.decode("utf-8") for part in
                  git(repo, "diff", "--name-only", "-z", "--no-renames", f"{source}^", source).split(b"\0")[:-1])


def links(path, text):
    for match in LINK.finditer(text):
        raw = match[1] or match[2]
        filename, sep, fragment = raw.partition("#")
        if not filename or "://" in filename or filename.startswith(("mailto:", "/")):
            continue
        target = posixpath.normpath(posixpath.join(str(PurePosixPath(path).parent), filename))
        if target.startswith("research/"):
            yield path, target, fragment if sep else ""


def added_links(repo, commit, path):
    diff = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--unified=0", f"{commit}^", commit, "--", path).decode()
    additions = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    return set(links(path, "\n".join(additions)))


def published_index_links(repo, commit):
    return {item for path in REGISTRIES for item in links(path, git(repo, "show", f"{commit}:{path}").decode())}


def action_map(repo, config, published, index_links):
    expected_dedicated = {}
    expected_links = set()
    rows = []
    for item in config["pulls"]:
        head = item["pull_head"]
        integrated = item["integration_commit"]
        declared = changed_paths(repo, head)
        assert declared == changed_paths(repo, integrated), item
        parent_version = entries(repo, head)
        integrated_version = entries(repo, integrated)
        dedicated = [path for path in declared if path not in REGISTRIES]
        shared = [path for path in declared if path in REGISTRIES]
        assert all(path.startswith("research/") for path in dedicated)
        assert set(expected_dedicated).isdisjoint(dedicated), item
        before = {path: parent_version[path] for path in declared}
        after = {path: integrated_version[path] for path in declared}
        assert all(before[path] == after[path] for path in dedicated), item
        expected_dedicated.update({path: before[path] for path in dedicated})
        source_links = {edge for path in shared for edge in added_links(repo, head, path) if edge[1] in dedicated}
        step_links = {edge for path in shared for edge in added_links(repo, integrated, path) if edge[1] in dedicated}
        expected_links.update(source_links)
        rows.append({**item, "paths": declared,
                     "evidence_paths": [{"path": path, "pr_object": before[path], "integrated_object": after[path],
                                         "published_object": published.get(path)} for path in dedicated],
                     "registry_paths": [{"path": path, "pr_object": before[path], "integrated_object": after[path],
                                         "published_object": published.get(path)} for path in shared],
                     "original_added_links_to_own_evidence": sorted(source_links),
                     "integration_added_links_to_own_evidence": sorted(step_links),
                     "missing_published_edges": sorted(source_links - index_links),
                     "missing_step_edges": sorted(source_links - step_links)})
    return expected_dedicated, expected_links, rows


def gates(published, index_links, dedicated, expected_links, rows):
    missing = set(dedicated) - published.keys()
    changed = {path for path, expected in dedicated.items() if published.get(path) != expected}
    missing_links = {edge for edge in expected_links if edge not in index_links or edge[1] not in published}
    whole_registry_matches = all(published.get(item["path"]) == item["pr_object"]
                                 for row in rows for item in row["registry_paths"])
    return {"path_presence": not missing, "exact_dedicated": not changed,
            "exact_and_register_links": not changed and not missing_links,
            "all_pr_blobs": not changed and whole_registry_matches}


def counterexamples(published, index_links, dedicated, expected_links, rows):
    ledger = next(path for path in sorted(dedicated) if path.endswith("/evidence.json"))
    alternate = next(path for path in sorted(dedicated) if path.endswith("/evidence.json") and path != ledger)
    edge = min(expected_links)
    substitute = next(path for path in sorted(dedicated) if (edge[0], path, edge[2]) not in index_links)
    new_edge = edge[0], substitute, edge[2]
    assert len((index_links - {edge}) | {new_edge}) == len(index_links)
    expected = (True, True, True, False)
    cases = {
        "published_tree": (published, index_links, expected),
        "deleted_dedicated_ledger": ({path: item for path, item in published.items() if path != ledger},
                                     index_links, (False, False, False, False)),
        "substituted_ledger_bytes": ({**published, ledger: published[alternate]}, index_links, (True, False, False, False)),
        "omitted_registry_link": (published, index_links - {edge}, (True, True, False, False)),
        "retargeted_registry_link": (published, (index_links - {edge}) | {new_edge}, (True, True, False, False)),
    }
    results = {}
    for name, (tree, references, target) in cases.items():
        results[name] = gates(tree, references, dedicated, expected_links, rows)
        assert tuple(results[name][policy] for policy in POLICIES) == target, (name, results[name])
    return {"removed_or_substituted_ledger": ledger, "substitute_blob_path": alternate,
            "original_edge": edge, "retargeted_edge": new_edge, "outcomes": results}


def run(repo):
    input_bytes = INPUTS.read_bytes()
    config = json.loads(input_bytes)
    pre = config["pre_batch_main"]
    main = config["published_main"]
    integration = config["integration_head"]
    assert git(repo, "rev-parse", f"{main}^").decode().strip() == pre
    integration_log = git(repo, "rev-list", "--first-parent", "--no-merges", "--reverse",
                          f"{config['integration_base']}..{integration}").decode().splitlines()
    assert integration_log == [item["integration_commit"] for item in config["pulls"]]
    main_tree = git(repo, "rev-parse", f"{main}^{{tree}}").decode().strip()
    assert main_tree == git(repo, "rev-parse", f"{integration}^{{tree}}").decode().strip()
    published = entries(repo, main)
    pre_entries = entries(repo, pre)
    index_links = published_index_links(repo, main)
    dedicated, expected_links, rows = action_map(repo, config, published, index_links)
    assert all(not row["missing_published_edges"] and not row["missing_step_edges"] for row in rows), [
        (row["number"], row["missing_published_edges"], row["missing_step_edges"]) for row in rows
        if row["missing_published_edges"] or row["missing_step_edges"]]
    assert all(published.get(path) == wanted for path, wanted in dedicated.items())
    assert set(changed_paths(repo, main)) == dedicated.keys() | set(REGISTRIES)
    kinds = Counter(PurePosixPath(path).suffix for path in dedicated)
    controls = counterexamples(published, index_links, dedicated, expected_links, rows)
    return {"schema": "llmlang-rt00-batch-evidence/1", "python": platform.python_version(),
            "git": git(repo, "--version").decode().strip(), "input_sha256": sha256(input_bytes).hexdigest(),
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "published_tree": main_tree,
            "pull_requests": len(rows), "path_touches": sum(len(row["paths"]) for row in rows),
            "distinct_paths": len(dedicated) + len(REGISTRIES), "dedicated_paths": len(dedicated),
            "dedicated_added": sum(path not in pre_entries for path in dedicated), "dedicated_suffixes": dict(sorted(kinds.items())),
            "shared_registries": len(REGISTRIES), "expected_exact_registry_links": len(expected_links),
            "pulls_with_exact_link_targets": sum(row["original_added_links_to_own_evidence"] != [] for row in rows),
            "whole_registry_blob_changes_across_squashes": sum(item["integrated_object"] != item["pr_object"]
                         for row in rows for item in row["registry_paths"]), "controls": controls, "pulls": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=HERE.parents[3])
    args = parser.parse_args()
    outcome = run(args.repo.resolve())
    rows = outcome.pop("pulls")
    print(json.dumps(outcome, indent=2).removesuffix("\n}") + ',\n  "pulls": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in rows))
    print("  ]\n}")
