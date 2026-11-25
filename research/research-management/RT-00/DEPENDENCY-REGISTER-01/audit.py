"""Measure the directed research register at an exact Git revision."""

import json
import platform
import re
import subprocess
from collections import Counter, defaultdict

ROOT = "research/research-management"
BASELINE = "2c0ce76a1eecc1aee9a6557db451b70afd4b869a"
AREAS = re.compile(r"^\| (RT-\d{2}) \|", re.MULTILINE)
EDGES = re.compile(r"^\| (DEP-\d{3}) \| (RT-\d{2}) → (RT-\d{2}) \| ([^|]+) \|", re.MULTILINE)
PATH_ROWS = ("DEP-010", "DEP-053", "DEP-060")


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def reachable(start, adjacent):
    seen = {start}
    stack = [start]
    while stack:
        for successor in adjacent[stack.pop()] - seen:
            seen.add(successor)
            stack.append(successor)
    return seen


def main():
    taxonomy_spec = f"{BASELINE}:{ROOT}/RESEARCH-TAXONOMY.md"
    dependencies_spec = f"{BASELINE}:{ROOT}/RESEARCH-DEPENDENCY-MAP.md"
    taxonomy = git("show", taxonomy_spec)
    dependencies = git("show", dependencies_spec)
    areas = AREAS.findall(taxonomy)
    rows = EDGES.findall(dependencies)
    if any(line.startswith("| DEP-") and not EDGES.match(line) for line in dependencies.splitlines()):
        raise ValueError("a dependency row does not match the register schema")
    ids = [row[0] for row in rows]
    assert len(areas) == len(set(areas)) and len(ids) == len(set(ids))
    types = Counter(row[3] for row in rows)
    documented_types = {"Requires", "Constrains", "Influences", "Conflicts with", "Enables"}
    undocumented = [identifier for identifier, _, _, relation in rows if relation not in documented_types]
    adjacent = {area: set() for area in areas}
    parallel = defaultdict(list)
    for identifier, source, target, relation in rows:
        assert source in adjacent and target in adjacent, identifier
        assert source != target, identifier
        parallel[source, target, relation].append(identifier)
        if relation != "Conflicts with":
            adjacent[source].add(target)
    closure = {area: reachable(area, adjacent) for area in areas}
    components = {
        tuple(sorted(other for other in closure[area] if area in closure[other]))
        for area in areas
    }
    print(json.dumps({
        "baseline": BASELINE,
        "python": platform.python_version(),
        "git": git("--version"),
        "taxonomy_blob": git("rev-parse", taxonomy_spec),
        "dependency_map_blob": git("rev-parse", dependencies_spec),
        "area_ids": sorted(areas),
        "edge_rows": len(rows),
        "missing_edge_numbers": sorted(set(range(1, max(int(key[4:]) for key in ids) + 1))
                                       - {int(key[4:]) for key in ids}),
        "relation_counts": dict(sorted(types.items())),
        "rows_with_undocumented_relation": undocumented,
        "distinct_directed_endpoint_pairs": len({(source, target) for _, source, target, _ in rows}),
        "same_endpoint_and_relation_groups": [
            {"source": source, "target": target, "relation": relation, "ids": sorted(identifiers)}
            for (source, target, relation), identifiers in sorted(parallel.items())
            if len(identifiers) > 1
        ],
        "nontrivial_mutual_reachability_components": sorted(group for group in components if len(group) > 1),
        "path_rows": {identifier: [source, target, relation] for identifier, source, target, relation in rows
                      if identifier in PATH_ROWS},
    }, indent=2))


if __name__ == "__main__":
    main()
