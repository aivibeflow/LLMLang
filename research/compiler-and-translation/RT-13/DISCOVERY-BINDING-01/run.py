"""Compare immutable discovery and target binding through bounded catalog changes."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Descriptor:
    operation: str
    contract: str
    artifact: str


@dataclass(frozen=True)
class Discovery:
    root: str
    request: tuple[str, str]
    descriptors: tuple[Descriptor, ...]


@dataclass(frozen=True)
class Receipt:
    artifact: str
    target: str
    checked: bool = True
    materialized: bool = True


def discover(root, request, catalog):
    return Discovery(root, request, tuple(row for row in catalog if (row.operation, row.contract) == request))


def bind(root, request, catalog, discovered, candidate, target, receipt):
    return (discovered == discover(root, request, catalog) and candidate in discovered.descriptors
            and receipt.artifact == candidate.artifact and receipt.target == target
            and receipt.checked and receipt.materialized)


def matrix():
    original = Descriptor("read", "v1", "provider-1")
    replacement = replace(original, artifact="provider-2")
    fallback = replace(original, artifact="reserve")
    other_contract = replace(original, contract="v2", artifact="provider-v2")
    other_operation = replace(original, operation="write", artifact="writer")
    forged = replace(original, artifact="uncatalogued")
    catalogs = {
        "snapshot-A": (original, fallback, other_contract, other_operation),
        "snapshot-B": (replacement, fallback, other_contract, other_operation),
    }
    requests = tuple(product(("read", "write"), ("v1", "v2")))
    visible_compatibility = {
        ("read", "v1"): {"snapshot-A": {original, fallback}, "snapshot-B": {replacement, fallback}},
        ("read", "v2"): {root: {other_contract} for root in catalogs},
        ("write", "v1"): {root: {other_operation} for root in catalogs},
        ("write", "v2"): {root: set() for root in catalogs},
    }
    receipt_types = ("matching", "wrong-artifact", "wrong-target", "unchecked", "unmaterialized")
    rows = Counter()
    controls = {}
    for root, request, candidate, target in product(catalogs, requests,
            (original, replacement, fallback, other_contract, other_operation, forged), ("x86-64", "aarch64")):
        current = discover(root, request, catalogs[root])
        other = "snapshot-B" if root == "snapshot-A" else "snapshot-A"
        alternate_request = next(query for query in requests if query != request)
        candidates = {
            "fresh": current,
            "old-root": discover(other, request, catalogs[other]),
            "changed-request": discover(root, alternate_request, catalogs[root]),
            "fabricated-candidate": replace(current, descriptors=current.descriptors + (forged,)),
            "omitted-descriptors": replace(current, descriptors=()),
        }
        can_discover = visible_compatibility[request][root]
        if set(current.descriptors) != can_discover:
            raise ValueError((root, request, current))
        for (cursor_label, cursor), receipt_label in product(candidates.items(), receipt_types):
            receipt = Receipt(candidate.artifact, target)
            if receipt_label == "wrong-artifact":
                receipt = replace(receipt, artifact="unrelated")
            elif receipt_label == "wrong-target":
                receipt = replace(receipt, target="wasm64")
            elif receipt_label == "unchecked":
                receipt = replace(receipt, checked=False)
            elif receipt_label == "unmaterialized":
                receipt = replace(receipt, materialized=False)
            use_current = cursor_label == "fresh" or (cursor_label == "omitted-descriptors" and not can_discover)
            expected = use_current and candidate in can_discover and receipt_label == "matching"
            valid = bind(root, request, catalogs[root], cursor, candidate, target, receipt)
            if valid != expected:
                raise ValueError((root, request, candidate, target, cursor, receipt, valid, expected))
            rows["comparisons"] += 1
            rows["accepted" if valid else "refused"] += 1
            if candidate in cursor.descriptors and not valid:
                rows["invalid-if-discovery-alone-authorizes"] += 1
            ignores_freshness = (candidate in cursor.descriptors and receipt_label == "matching")
            if ignores_freshness and not valid:
                rows["invalid-if-cursor-freshness-unchecked"] += 1
            if root == "snapshot-B" and request == ("read", "v1") and target == "x86-64":
                if (cursor_label, candidate, receipt_label) in (
                    ("old-root", original, "matching"), ("old-root", fallback, "matching"),
                    ("fresh", replacement, "unmaterialized"), ("fresh", fallback, "matching"),
                    ("fresh", replacement, "matching"), ("fabricated-candidate", forged, "matching"),
                ):
                    controls[f"{cursor_label}/{candidate.artifact}/{receipt_label}"] = {
                        "discovered_in_cursor": candidate in cursor.descriptors, "selected": valid,
                    }
    return dict(rows), controls


def lean_check(lean):
    version = subprocess.check_output([lean, "--version"], text=True, timeout=30).strip()
    result = subprocess.run([lean, "-DwarningAsError=true", str(HERE / "Discovery.lean")],
                            check=True, text=True, capture_output=True, timeout=30)
    names = ("discovery_membership", "bind_requires_current_catalog", "bind_succeeds_for_admissible")
    expected = [f"'{name}' depends on axioms: [propext]" for name in names]
    observed = result.stdout.splitlines()
    if result.stderr or observed != expected:
        raise ValueError((result.stdout, result.stderr))
    return {"version": version, "axioms": observed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    checked, examples = matrix()
    evidence = {
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Discovery.lean", "run.py")},
        "lean": lean_check(args.lean), "comparisons": checked, "examples": examples,
    }
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
