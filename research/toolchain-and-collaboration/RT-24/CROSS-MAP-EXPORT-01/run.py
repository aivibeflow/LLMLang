#!/usr/bin/env python3
"""Compare three-map merge and exact export eligibility on real Git commits."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, digest
from tests import test_rt24_merge_tree_gate as git_fixture

ARTIFACTS = "program/artifacts.json"
NAMES = "program/names.json"
BINDINGS = "program/bindings.json"
EXPORTS = "program/exports.json"
LEFT = "proofs/left.json"
RIGHT = "proofs/right.json"
BASE = "proofs/base.json"
PATHS = (ARTIFACTS, NAMES, BINDINGS, EXPORTS, BASE, LEFT, RIGHT)
POINTS = {"restricted": (-1, 0, 1), "wide": (-2, -1, 0, 1, 2)}
MODES = ("files", "reftable")
CASES = {
    "symbol_alias": ("portable", "rename", "left_only", "admitted"),
    "abi_receipt_missing": ("portable", "abi", "left_only", "unknown_receipt"),
    "abi_crossed_receipt": ("portable", "abi", "crossed", "admitted"),
    "abi_incompatible": ("narrow_abi", "abi", "left_only", "abi_mismatch"),
    "scope_receipt_missing": ("portable", "wide", "left_only", "unknown_receipt"),
    "scope_incompatible": ("narrow_behavior", "wide", "left_only", "behavior_mismatch"),
    "wrong_receipt_bytes": ("portable", "abi", "wrong_bytes", "invalid_receipt"),
    "dormant_binding_removed": ("remove_dormant", "activate_dormant", "left_only", "missing_binding"),
    "catalog_alias": ("portable", "catalog_alias", "left_only", "admitted"),
}


def git(repo, *args):
    return git_fixture.git(repo, *args).decode("utf-8").strip()


def encode_artifacts():
    store = ContentStore()
    contract = {"type": "I64 -> I64", "points": {str(n): n + 1 for n in POINTS["wide"]}}
    contract_id = store.put("rt24-export-contract-v1", contract)
    operations = {name: {"operation": name, "contract": contract_id} for name in ("entry", "dormant")}
    operation_ids = {name: store.put("rt24-export-operation-v1", row) for name, row in operations.items()}
    profiles = {
        "default": ("a", "b"),
        "portable": ("a", "b"),
        "narrow_abi": ("a",),
        "narrow_behavior": ("a", "b"),
    }
    implementations = {
        name: {
            "identity": name, "type": "I64 -> I64", "abi": abis,
            "points": {str(n): n + 1 + int(name == "narrow_behavior" and n == -2) for n in POINTS["wide"]},
        }
        for name, abis in profiles.items()
    }
    provider_ids = {name: store.put("rt24-export-provider-v1", row) for name, row in implementations.items()}
    payloads = {
        "contracts": {contract_id: contract},
        "operations": {operation_ids[name]: row for name, row in operations.items()},
        "providers": {provider_ids[name]: row for name, row in implementations.items()},
    }
    return payloads, contract_id, operation_ids, provider_ids


def admit_artifacts(artifacts):
    store = ContentStore()
    for category, kind in (("contracts", "rt24-export-contract-v1"),
                           ("operations", "rt24-export-operation-v1"),
                           ("providers", "rt24-export-provider-v1")):
        for artifact, row in artifacts[category].items():
            assert store.put(kind, row) == artifact
    return store


def export(name, symbol="entry", abi="a", scope="restricted"):
    return {"namespace": "fixture", "symbol": symbol, "public_name": name, "abi": abi, "scope": scope}


def exact_key(operation, contract, provider, exported):
    return (operation, contract, provider, exported["abi"], exported["scope"])


def proof_body(store, key):
    operation, contract, provider, abi, scope = key
    contract_value = store.get(contract).payload
    body = store.get(provider).payload
    assert store.get(operation).payload["contract"] == contract
    actual = [body["points"][str(n)] for n in POINTS[scope]]
    expected = [contract_value["points"][str(n)] for n in POINTS[scope]]
    if abi not in body["abi"] or body["type"] != contract_value["type"] or actual != expected:
        raise ValueError("Fixture proof does not establish compatibility")
    return digest({"key": key, "domain": POINTS[scope], "actual": actual})


def certificate(store, key):
    return {"claim": list(key), "test_vector_digest": proof_body(store, key)}


def read_json(repo, revision, path):
    return json.loads(git_fixture.git(repo, "show", f"{revision}:{path}"))


def read_selection(repo, revision):
    objects, names, bindings, exports, baseline, left, right = (
        read_json(repo, revision, path) for path in PATHS
    )
    return admit_artifacts(objects), names, bindings, exports, baseline + left + right


def assess(repo, revision):
    store, names, bindings, exports, receipts = read_selection(repo, revision)
    outputs = []
    for export_row in exports:
        operation = names.get(export_row["public_name"])
        if operation not in bindings:
            outputs.append({"status": "missing_binding", "exact_key": None})
            continue
        provider = bindings[operation]
        contract = store.get(operation).payload["contract"]
        current = exact_key(operation, contract, provider, export_row)
        same_contract = [row for row in receipts if row["claim"][1] == contract]
        exact = [row for row in same_contract if tuple(row["claim"]) == current]
        implementation = store.get(provider).payload
        contract_value = store.get(contract).payload
        if implementation["type"] != contract_value["type"]:
            status = "type_mismatch"
        elif export_row["abi"] not in implementation["abi"]:
            status = "abi_mismatch"
        else:
            try:
                checked = proof_body(store, current)
            except ValueError:
                status = "behavior_mismatch"
            else:
                if not exact:
                    status = "unknown_receipt"
                elif any(row["test_vector_digest"] == checked for row in exact):
                    status = "admitted"
                else:
                    status = "invalid_receipt"
        outputs.append({"status": status, "exact_key": current,
                        "same_contract_receipts": len(same_contract), "exact_receipts": len(exact),
                        "symbol": export_row["symbol"]})
    symbols = {(row["namespace"], row["symbol"]) for row in exports}
    assert len(symbols) == len(exports)
    status = next((row["status"] for row in outputs if row["status"] != "admitted"), "admitted")
    return {
        "status": status, "exports": outputs,
        "closed_references": all(row["exact_key"] is not None for row in outputs),
        "contract_only_gate": all(row.get("same_contract_receipts", 0) for row in outputs),
        "exact_gate": status == "admitted",
        "location": git(repo, "rev-parse", f"{revision}^{{tree}}"),
    }


def history(repo, backend, name):
    left_kind, right_kind, edge_receipt, expected = CASES[name]
    git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1",
        f"--ref-format={backend}")
    assert git(repo, "rev-parse", "--show-ref-format") == backend
    artifacts, contract, operation, provider = encode_artifacts()
    store = admit_artifacts(artifacts)
    bindings = {op: provider["default"] for op in operation.values()}
    entry_row = export("public/entry")
    dormant_row = export("public/dormant", symbol="dormant")
    base_cert = certificate(store, exact_key(operation["entry"], contract, provider["default"], entry_row))
    base = git_fixture.commit(repo, {
        ARTIFACTS: artifacts, NAMES: {f"public/{role}": op for role, op in operation.items()},
        BINDINGS: bindings, EXPORTS: [entry_row], BASE: [base_cert], LEFT: [], RIGHT: [],
    })
    assert assess(repo, base)["exact_gate"]
    git(repo, "switch", "--quiet", "-c", "left", base)
    left_bindings = dict(bindings)
    if left_kind == "remove_dormant":
        del left_bindings[operation["dormant"]]
        left_certificates = []
    else:
        left_bindings[operation["entry"]] = provider[left_kind]
        left_certificates = [certificate(store, exact_key(operation["entry"], contract, provider[left_kind], entry_row))]
    left = git_fixture.commit(repo, {BINDINGS: left_bindings, LEFT: left_certificates})

    git(repo, "switch", "--quiet", "-c", "right", base)
    right_certificates = []
    right_row = dict(entry_row)
    if right_kind == "rename":
        right_row["symbol"] = "renamed_entry"
    elif right_kind == "abi":
        right_row["abi"] = "b"
    elif right_kind == "wide":
        right_row["scope"] = "wide"
    elif right_kind == "catalog_alias":
        right_row["public_name"] = "public/renamed"
    right_extras = {}
    if right_kind == "activate_dormant":
        right_extras[EXPORTS] = [right_row, dormant_row]
        right_certificates.append(certificate(store, exact_key(operation["dormant"], contract, provider["default"],
                                                               dormant_row)))
    else:
        right_extras[EXPORTS] = [right_row]
    if right_kind == "catalog_alias":
        right_extras[NAMES] = {"public/renamed": operation["entry"], "public/dormant": operation["dormant"]}
    right_certificates.append(certificate(store, exact_key(operation["entry"], contract, provider["default"], right_row)))
    if edge_receipt in {"crossed", "wrong_bytes"}:
        crossed = certificate(store, exact_key(operation["entry"], contract, provider["portable"], right_row))
        if edge_receipt == "wrong_bytes":
            crossed["test_vector_digest"] = base_cert["test_vector_digest"]
        right_certificates.append(crossed)
    right = git_fixture.commit(repo, {**right_extras, RIGHT: right_certificates})
    assert assess(repo, left)["exact_gate"] and assess(repo, right)["exact_gate"]
    return base, left, right, expected


def experiment(repo, backend, name):
    base, left, right, expected = history(repo, backend, name)
    paths = [git(repo, "diff", "--name-only", base, parent).splitlines() for parent in (left, right)]
    assert not (set(paths[0]) & set(paths[1]))
    git(repo, "switch", "--quiet", "--detach", left)
    git(repo, "merge", "--quiet", "--no-ff", "--no-edit", right)
    assert git(repo, "status", "--porcelain") == ""
    candidate = git(repo, "rev-parse", "HEAD")
    assert git(repo, "show", "-s", "--format=%P", candidate).split() == [left, right]
    checked = assess(repo, candidate)
    assert checked["status"] == expected
    ref = "refs/heads/accepted"
    git(repo, "update-ref", ref, base, "0" * 40)
    if checked["exact_gate"]:
        git(repo, "update-ref", ref, candidate, base)
    selected = git(repo, "rev-parse", ref)
    assert selected == (candidate if expected == "admitted" else base)
    return {
        "backend": backend, "case": name, "base": base,
        "parents": [left, right], "parent_edit_paths": paths, "candidate": candidate, "published": selected,
        "source_parents_admitted": [assess(repo, parent) for parent in (left, right)],
        "textual_merge_clean": True, "checked": checked,
    }


def run(directory):
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    assert version == "git version 2.52.0", version
    cases = []
    for backend, name in product(MODES, CASES):
        repo = directory / f"{backend}-{name}"
        repo.mkdir()
        cases.append(experiment(repo, backend, name))
    for name in CASES:
        by_backend = [{key: value for key, value in row.items() if key != "backend"}
                      for row in cases if row["case"] == name]
        assert by_backend[0] == by_backend[1]
    return {
        "schema": "llmlang-rt24-cross-map-export/1", "git": version, "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "candidates": len(cases), "textual_clean_merges": sum(row["textual_merge_clean"] for row in cases),
        "closed_references": sum(row["checked"]["closed_references"] for row in cases),
        "contract_only_accepted": sum(row["checked"]["contract_only_gate"] for row in cases),
        "published_exact": sum(row["checked"]["exact_gate"] for row in cases),
        "status_counts": dict(sorted(Counter(row["checked"]["status"] for row in cases).items())),
        "cases": cases,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-cross-map-") as scratch:
        result = run(Path(scratch))
    cases = result.pop("cases")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "cases": [')
    print(",\n".join("    " + json.dumps(row) for row in cases))
    print("  ]\n}")
