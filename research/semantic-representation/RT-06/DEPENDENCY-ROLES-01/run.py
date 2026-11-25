#!/usr/bin/env python3
"""Check semantic, proof and navigation edges in the pinned content store."""

from collections import Counter
from hashlib import sha256
from io import BytesIO
from itertools import combinations, product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
ARCHIVE = "e32fd0697dfeca50052593077d507ef38bb0b3a4"
BASE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src"


def instantiate(api, fields):
    helper, literal, note, text, bound, verifier, uses_note = fields
    graph, relations = api.ContentStore(), api.RelationStore()
    dependency = api.Dependency
    policy = graph.put("verification-policy", {"policy": verifier})
    contract = graph.put("return-bound", {"maximum": bound})
    metadata = graph.put("display-note", {"value": note})
    source_bytes = f"fn x => helper(x) + {literal}\n"
    if text:
        source_bytes = "// presentation-only line\n" + source_bytes
    provenance = graph.put("source-revision", {"source": source_bytes})
    provider = graph.put("provider", {"multiplier": 1 + helper})

    required = [dependency("calls", provider, "exact-provider")]
    if uses_note:
        required.append(dependency("reads", metadata, "consumed-runtime-note"))
    value = graph.put("implementation", {"literal": literal, "uses_note": uses_note}, required)
    lookup_only = graph.put("implementation", {"literal": literal, "uses_note": uses_note},
                            [*required, dependency("came-from", provenance, "source", False),
                             dependency("has-note", metadata, "navigation", False)])
    assert lookup_only == value
    relations.add("navigation", value, "source-revision", provenance)
    relations.add("navigation", value, "display-note", metadata)

    check = graph.put("verification-request", {"profile": "two-exact-inputs"}, [
        dependency("checks", value, "subject"), dependency("uses", contract, "obligation"),
        dependency("uses", policy, "checker"),
    ])
    audit = graph.put("source-audit", {"profile": "verbatim-source"}, [
        dependency("inspects", value, "subject"), dependency("uses", provenance, "source-bytes"),
        dependency("uses", metadata, "reported-note"),
    ])
    relations.add("navigation", value, "verification-receipt", check)
    assert check not in {dep.target_hash for dep in graph.get(value).dependencies}
    assert len(relations.for_scope("navigation")) == 3

    core = {value, provider}
    if uses_note:
        core.add(metadata)
    inventories = {
        "execution": (value, core),
        "verification": (check, core | {check, contract, policy}),
        "source_audit": (audit, core | {audit, provenance, metadata}),
    }
    for action, (root, members) in inventories.items():
        wanted = api.digest({"domain": "llmlang.closure.v1", "members": sorted(members)})
        if graph.closure_digest(root) != wanted:
            raise AssertionError((action, fields))
    synthetic_flat_key = api.digest(["execution-without-note", literal, uses_note, provider])
    full_snapshot = api.make_snapshot({"value": value, "check": check, "audit": audit}).root_hash
    values = (literal, 1 + helper + literal)
    runtime_note = note if uses_note else None
    expected = {
        "execution": (values, runtime_note),
        "verification": (values, runtime_note, bound, verifier,
                         all(result <= bound for result in values)),
        "source_audit": (values, runtime_note, source_bytes, note),
    }
    keys = {
        "typed": {name: addresses[0] for name, addresses in inventories.items()},
        "full_snapshot": dict.fromkeys(inventories, full_snapshot),
        "runtime_only": dict.fromkeys(inventories, value),
        "skip_consumed_note": dict.fromkeys(inventories, synthetic_flat_key),
    }
    return {"keys": keys, "observations": expected,
            "closures": {name: len(members) for name, (_, members) in inventories.items()}}


def compare(api):
    profiles = {mask: instantiate(api, fields)
                for mask, fields in enumerate(product(range(2), repeat=7))}
    counts, witnesses = {}, {}
    digest = sha256()
    for left, right in combinations(profiles, 2):
        baseline, next_case = profiles[left], profiles[right]
        for policy, actions in baseline["keys"].items():
            for action, expected_key in actions.items():
                observed_same = baseline["observations"][action] == next_case["observations"][action]
                reused = expected_key == next_case["keys"][policy][action]
                outcome = ("safe" if observed_same else "stale") if reused else (
                    "missed_safe" if observed_same else "different")
                count = counts.setdefault(policy, {}).setdefault(action, Counter())
                count[outcome] += 1
                if outcome == "stale":
                    witnesses.setdefault(f"{policy}/{action}", [left, right])
                digest.update(f"{left},{right},{policy},{action},{outcome}\n".encode())
    assert all(row["stale"] == 0 for row in counts["typed"].values())
    assert counts["skip_consumed_note"]["execution"]["stale"]
    assert counts["runtime_only"]["verification"]["stale"]
    assert counts["runtime_only"]["source_audit"]["stale"]
    return profiles, counts, witnesses, digest.hexdigest()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        archive = subprocess.check_output(["git", "archive", ARCHIVE, BASE])
        with open_tar(fileobj=BytesIO(archive), mode="r:") as stored:
            stored.extractall(directory, filter="data")
        src = Path(directory) / BASE
        sys.path.insert(0, str(src.parent))
        from src import semantic_graph as api
        profiles, counts, witnesses, transcript = compare(api)
        source_digest = sha256((src / "semantic_graph.py").read_bytes()).hexdigest()
    print(json.dumps({
        "schema": "llmlang-dependency-role-closure/1", "python": platform.python_version(),
        "archive_revision": ARCHIVE, "store_sha256": source_digest,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Observation.lean", "axioms.txt")},
        "factor_order": ["helper", "literal", "note", "source_text", "bound", "verifier",
                         "uses_note"],
        "profiles": len(profiles),
        "exact_closure_checks": sum(len(row["closures"]) for row in profiles.values()),
        "pairs": len(profiles) * (len(profiles) - 1) // 2,
        "counts": counts,
        "witnesses": {name: {"profiles": pair, "observations": [profiles[i]["observations"] for i in pair]}
                      for name, pair in witnesses.items()},
        "ordered_rows_sha256": transcript,
    }, indent=2))
