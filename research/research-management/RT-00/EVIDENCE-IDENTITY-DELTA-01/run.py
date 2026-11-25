#!/usr/bin/env python3
"""Bind the new research/all exact-name ledgers to their declared tracked inputs."""

from collections import Counter
from functools import cache
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import platform
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / ".github" / "scripts"))
from audit_research_evidence_ledger_identities import BASELINE, MAP_FIELDS, SHA256_PATTERN, git, research_tree

HEAD = "087d2e5e952255778d76637ce5fd41b9df2d5396"
ROOTED_SOURCE_MAPS = {
    "ALLOCATOR-REPLAY-01", "CLAUSE-PROVENANCE-01", "OPERATION-SUBSTITUTION-EVIDENCE-01",
    "PROOF-RECEIPT-STATUS-01", "RECONSTRUCTION-PACKAGE-01", "RECONSTRUCTION-ROUTING-01",
    "REQUIREMENT-CLASS-COVERAGE-01", "REQUIREMENT-LIFECYCLE-01", "REVISION-IMPACT-01",
    "SCOPED-PROVENANCE-01", "SEMANTIC-DIRECTION-01",
}
DEP = "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
POLICY = "research/PROTOTYPES/RT-04-01"
PACKAGE = "research/packages-and-ecosystem/PROTOTYPES/PACKAGE-IDENTITY-01"
SEMANTIC = "research/semantic-representation"
PREVIOUS = "research/toolchain-and-collaboration/RT-11/CACHE-INDEX-MERGE-01"
PORTABLE = f"{SEMANTIC}/PROTOTYPES/IDENTITY-BYTES-01"
SYNTAX = "research/language-design/RT-31/CROSS-PROFILE-SPG-01"
NATIVE_LEDGER = f"{SEMANTIC}/RT-05/OPERATION-IDENTITY-01/evidence.json"
EXTRA_MAPS = ("file_sha256", "fixture_sha256", "input_sha256", "prototype_sha256",
              "replayed_ledger_sha256", "replayed_axiom_output_sha256")
SCALARS = {
    "CONFORMANCE-CLASS-IDENTITY-01": {"source_ledger_sha256": NATIVE_LEDGER},
    "PROVIDED-CONTRACT-IDENTITY-01": {"native_ledger_sha256": NATIVE_LEDGER},
    "CROSS-SYNTAX-SPG-01": {"upstream_ledger_sha256": f"{SYNTAX}/evidence.json"},
    "DEPENDENCY-EVIDENCE-01": {"model_sha256": "Coverage.lean"},
}
ALIASES = {
    "STRICT-QFLIA-ADMISSION-01": {
        "LLMLangLogosBinding.lean": f"{DEP}/logos_binding/LLMLangLogosBinding.lean",
        **{name: f"{DEP}/src/{name}" for name in ("qf_lia_ir.py", "qf_lia_profile.py")},
    },
    "REQUIREMENT-APPROVAL-01": {name: f"{DEP}/src/{name}" for name in ("business_intent.py", "semantic_graph.py")},
    "DIFFERENCE-CERTIFICATE-01": {"rt03_feasibility_outcomes.py": f"{POLICY}/rt03_feasibility_outcomes.py"},
    "QFLIA-RESOURCE-CONTROLS-01": {"rt03_feasibility_outcomes.py": f"{POLICY}/rt03_feasibility_outcomes.py"},
    "SOURCE-DIFFERENCE-ROUTES-01": {
        "rt03_feasibility_outcomes.py": f"{POLICY}/rt03_feasibility_outcomes.py",
        "checker.py": "research/language-design/RT-03/DIFFERENCE-CERTIFICATE-01/checker.py",
    },
    "CANONICAL-WIRE-01": {name: f"{PORTABLE}/{name}" for name in ("compare.py", "encode.mjs")},
    "DIGEST-MIGRATION-01": {"semantic_graph.py": f"{DEP}/src/semantic_graph.py"},
    "OPERATION-LIFETIME-01": {"semantic_graph": f"{DEP}/src/semantic_graph.py", "runner": "run.py"},
    "RECURSIVE-TOPOLOGY-EDITS-01": {
        "runner": "run.py",
        **{name: f"{DEP}/src/{name}" for name in ("semantic_graph.py", "recursive_identity.py")},
    },
    "CACHE-INDEX-MERGE-01": {
        name: f"{PACKAGE}/{name}" for name in ("cache_index.py", "language_version.py", "package_identity.py")
    },
    "LAYERED-CACHE-01": {
        "cache_index": f"{PACKAGE}/cache_index.py", "fixture": f"{PREVIOUS}/run.py",
        "merge": f"{PREVIOUS}/merge.py", "runner": "run.py",
    },
    "CROSS-SYNTAX-SPG-01": {name: f"{SYNTAX}/{name}" for name in ("profiles.py", "run.py")},
    "THREE-SEMANTICS-01": {
        name: f"{POLICY}/{name}" for name in ("rt03_reference.py", "rt03_smallstep.py")
    },
}


@cache
def tracked(ref):
    return research_tree(ref)


@cache
def digest(blob):
    return sha256(git("cat-file", "blob", blob)).hexdigest()


def ledgers(tree):
    return {path: value[0] for path, value in tree.items() if PurePosixPath(path).name == "evidence.json"}


def sources(folder, data):
    for field in (*MAP_FIELDS, *EXTRA_MAPS):
        value = data.get(field)
        if field == "runner_sha256" and isinstance(value, str):
            value = {"run.py": value}
        if isinstance(value, dict):
            for label, expected in sorted(value.items()):
                yield field, label, expected
    for field, label in SCALARS.get(folder.name, {}).items():
        yield field, label, data[field]


def resolve(folder, field, label):
    fixture = folder.name
    if fixture == "CLEANUP-IDENTITY-01" and field == "source_sha256":
        return f"research/{label}", "research-root"
    if fixture in ROOTED_SOURCE_MAPS and field == "source_sha256":
        return label, "repository-root"
    if fixture == "SOURCE-OCCURRENCE-01" and field == "input_sha256":
        return f"{DEP}/{label}", "prototype-root"
    if fixture == "IDENTITY-CROSSWALK-01" and field.startswith("replayed_"):
        artifact = "evidence.json" if field == "replayed_ledger_sha256" else "axioms.txt"
        return str(folder.parent / label / artifact), "crosswalk-fixture"
    alias = ALIASES.get(fixture, {}).get(label)
    if alias is not None:
        return alias if alias.startswith("research/") else str(folder / alias), "runner-defined-alias"
    if field in SCALARS.get(fixture, {}) and label.startswith("research/"):
        return label, "runner-defined-scalar"
    return str(folder / label), "adjacent"


def observe(path, body, tree):
    folder = PurePosixPath(path).parent
    for field, label, expected in sources(folder, body):
        row = {"field": field, "label": label}
        if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
            row["outcome"] = "inline-data" if field == "sources" else "outside-flat-sha256"
            yield row
            continue
        resolved, basis = resolve(folder, field, label)
        row.update(path=resolved, resolution=basis, expected_sha256=expected)
        if resolved in tree and resolved != path:
            blob = tree[resolved][0]
            actual = digest(blob)
            row.update(current_blob=blob, current_sha256=actual)
            if actual == expected:
                yield {**row, "outcome": "match"}
                continue
        yield {**row, "outcome": "mismatch" if resolved in tree else "unresolved"}


def inline_identities(folder, body):
    if folder == "PROOF-FRESHNESS-01":
        for profile, result in sorted(body["checked_source_runs"].items()):
            label, _ = profile.split("/", 1)
            actual = sha256(body["sources"][label].encode("utf-8")).hexdigest()
            expected = result["source_sha256"]
            yield {
                "field": "checked_source_runs.source_sha256", "label": profile,
                "expected_sha256": expected, "actual_sha256": actual,
                "outcome": "inline-match" if actual == expected else "inline-mismatch",
            }
    if folder == "SCOPED-PROVENANCE-01":
        for identity, result in sorted(body["interpretations"].items()):
            text = body["sources"][result["source"]]
            encoded = json.dumps({"kind": "rt02-source", "text": text}, ensure_ascii=False,
                                 sort_keys=True, separators=(",", ":")).encode("utf-8")
            actual = sha256(encoded).hexdigest()
            expected = result["revision"]
            start, end = result["start"], result["end"]
            span = 0 <= start < end <= len(text) and text[start:end] == result["quote"]
            yield {
                "field": "interpretations.revision", "label": identity, "span_matches": span,
                "expected_sha256": expected, "actual_sha256": actual,
                "outcome": "inline-match" if actual == expected and span else "inline-mismatch",
            }


def results():
    tree = tracked(HEAD)
    old, new = ledgers(tracked(BASELINE)), ledgers(tree)
    touched = [path for path in sorted(new) if new[path] != old.get(path)]
    rows, counts = [], Counter()
    for path in touched:
        body = json.loads(git("cat-file", "blob", new[path]))
        folder = PurePosixPath(path).parent.name
        items = [*observe(path, body, tree), *inline_identities(folder, body)]
        counts.update(item["outcome"] for item in items)
        rows.append({"path": path, "blob": new[path], "old_blob": old.get(path), "source_identities": items})
    return {
        "schema": "llmlang-rt00-evidence-identity-delta/1",
        "baseline": BASELINE, "tree": HEAD, "python": platform.python_version(),
        "git": git("--version").decode().strip(), "baseline_ledgers": len(old), "current_ledgers": len(new),
        "added": len(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
        "changed": sum(path in old for path in touched), "counts": dict(counts),
        "ledgers": rows,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
