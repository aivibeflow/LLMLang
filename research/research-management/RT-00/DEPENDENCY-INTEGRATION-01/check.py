"""Audit evidence pointers and local composition in the dependency register."""

from collections import Counter
import hashlib
import json
import posixpath
import re
import subprocess

BASE = "92a121b69d5d3389ee413850f33dc62d6d63bcbb"
ROOT = "research/research-management"
MAP = f"{ROOT}/RESEARCH-DEPENDENCY-MAP.md"
RELEASE = f"{ROOT}/planning-and-synthesis/EXACT-PROVIDER-RELEASE-01/evidence.json"
BOOTSTRAP = "research/toolchain-and-collaboration/RT-21/DEPENDENCY-BOOTSTRAP-01/observations.json"
TYPES = {"Requires", "Constrains", "Influences", "Conflicts with", "Enables"}


def git(*args):
    return subprocess.check_output(["git", *args])


def read(path):
    return git("show", f"{BASE}:{path}")


def register(paths):
    areas = set(re.findall(r"(?m)^\| (RT-\d{2}) \|", read(f"{ROOT}/RESEARCH-TAXONOMY.md").decode()))
    assert len(areas) == 38
    rows = {}
    for line in read(MAP).decode().splitlines():
        if not line.startswith("| DEP-"):
            continue
        cells = line.split("|")
        assert len(cells) in (6, 7), line
        identifier, endpoints, relation, scope, confidence = (cell.strip() for cell in cells[1:6])
        source, target = endpoints.split(" → ")
        assert source != target and {source, target} <= areas and relation in TYPES
        assert identifier not in rows
        links = []
        for link in re.findall(r"\]\(([^)]+)\)", scope):
            if "://" in link or link.startswith("#"):
                continue
            relative, _, anchor = link.partition("#")
            path = posixpath.normpath(posixpath.join(ROOT, relative))
            links.append({"path": path, "anchor": anchor, "blob": paths.get(path)})
        rows[identifier] = {
            "source": source, "target": target, "relation": relation,
            "confidence": confidence, "links": links,
            "terminal_separator": line.endswith("|"),
        }
    assert set(rows) == {f"DEP-{number:03d}" for number in range(1, 265)}
    return rows


def scoped_controls():
    release_bytes, bootstrap_bytes = read(RELEASE), read(BOOTSTRAP)
    release, bootstrap = json.loads(release_bytes), json.loads(bootstrap_bytes)
    assert (release["native_executions_total"], release["rows_per_execution"],
            release["replacement_changed_rows_per_route"]) == (8, 20992, 5720)
    checks = {}
    for route, row in release["outcomes"].items():
        attempts = row["attempts"]
        assert Counter(attempt["verdict"] == "published"
                       for attempt in attempts.values()) == {True: 3, False: 11}
        initial = attempts["initial_release"]["selected_after"]
        replacement = attempts["exact_replacement"]["selected_after"]
        rollback = attempts["exact_rollback_reauthorized"]["selected_after"]
        assert initial != replacement and initial == rollback
        assert len(row["history"]) == 3
        assert attempts["stale_trace"]["selected_after"] == initial
        assert attempts["revoked_publisher"]["selected_after"] == replacement
        checks[route] = {case: attempts[case]["verdict"] for case in sorted(attempts)}
    assert set(checks) == {"c", "rust"} and checks["c"] == checks["rust"]
    assert (bootstrap["case_count"], bootstrap["register_cases"],
            len(bootstrap["refused_controls"]), len(bootstrap["semantic_mutants"])) == (16468, 12, 8, 3)
    return {
        "release_verdicts": checks,
        "native_observations": release["native_executions_total"] * release["rows_per_execution"],
        "bootstrap_cases": bootstrap["case_count"],
        "control_inputs_sha256": {
            RELEASE: hashlib.sha256(release_bytes).hexdigest(),
            BOOTSTRAP: hashlib.sha256(bootstrap_bytes).hexdigest(),
        },
    }


def main():
    paths = {}
    for entry in git("ls-tree", "-r", "-z", BASE).split(b"\0"):
        if entry:
            headers, path = entry.decode().split("\t", 1)
            paths[path] = headers.split()[-1]
    rows = register(paths)
    broken = {identifier: [link["path"] for link in row["links"] if link["blob"] is None]
              for identifier, row in rows.items()
              if any(link["blob"] is None for link in row["links"])}
    print(json.dumps({
        "baseline": BASE, "map_blob": paths[MAP], "rows": rows,
        "edges_with_linked_paths": sum(bool(row["links"]) for row in rows.values()),
        "local_link_occurrences": sum(len(row["links"]) for row in rows.values()),
        "missing_link_paths": broken,
        "missing_terminal_separator": [key for key, row in rows.items()
                                       if not row["terminal_separator"]],
        "scoped_controls": scoped_controls(),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
