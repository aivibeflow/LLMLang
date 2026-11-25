"""Replay the package model's content and delivery identity distinctions."""

from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
import zipfile


HERE = Path(__file__).resolve().parent
PROTOTYPES = HERE.parents[1] / "PROTOTYPES"
INDEX = PROTOTYPES / "PACKAGE-INDEX-01"
IDENTITY = PROTOTYPES / "PACKAGE-IDENTITY-01"
sys.path[:0] = [str(INDEX), str(IDENTITY)]

from package_archive import ArchiveError, build_archive, verify_archive
from package_identity import PackageFormatError, logical_index_hash, package_content_root, parse_manifest
from package_index import IndexError, normalize


def content_hash(data):
    return "sha256:" + sha256(data).hexdigest()


PAYLOADS = {name: text.encode() for name, text in {
    "entry": "entry function", "type": "value type", "proof": "checked proof",
    "extra": "extra clause", "external": "external optional object",
}.items()}
HASHES = {name: content_hash(payload) for name, payload in PAYLOADS.items()}


def object_row(name, kind):
    return {"hash": HASHES[name], "kind": kind, "size": len(PAYLOADS[name])}


def edge(key, kind, target, included, **condition):
    return {"source_hash": HASHES["entry"], "edge_id": key, "kind": kind,
            "target_hash": HASHES[target], "included": included, **condition}


def base_index():
    return {
        "objects": [object_row("entry", "function"), object_row("type", "type"),
                    object_row("proof", "proof")],
        "dependencies": [edge("signature", "required", "type", True),
                         edge("proof", "evidence", "proof", True),
                         edge("target", "target", "external", False, condition={"target": "amd64"})],
        "exports": [{"module_id": "module:core", "name": "entry", "object_hash": HASHES["entry"]}],
        "modules": [{"module_id": "module:core", "members": [HASHES["entry"], HASHES["type"]]}],
    }


def package(index, *, roots=None, policy="closure", index_path="index", label="base", features=None):
    roots = [HASHES["entry"], HASHES["type"]] if roots is None else roots
    normalized = normalize(index)
    text = f'''format = "llmlang.package"
schema_version = 1

[package]
name = "{label}"

[content]
roots = {json.dumps(roots)}
dependency_policy = "{policy}"
content_root = "@ROOT@"

[index]
path = "{index_path}"
format_version = 1
logical_hash = "{logical_index_hash(normalized)}"
'''
    if features is not None:
        text += f"\n[content.resolution_inputs]\nfeatures = {json.dumps(features)}\n"
    placeholder = "sha256:" + "0" * 64
    root = package_content_root(parse_manifest(text.replace("@ROOT@", placeholder).encode()), normalized)
    return root, text.replace("@ROOT@", root).encode(), normalized


def archive(scratch, name, index, **changes):
    root, raw, normalized = package(index, **changes)
    blobs = {HASHES[name]: payload for name, payload in PAYLOADS.items()}
    objects = ((row["hash"], io.BytesIO(blobs[row["hash"]])) for row in normalized["objects"])
    path = scratch / f"{name}.llpkg"
    build_archive(raw, normalized, objects, path, max_records_in_memory=2)
    assert verify_archive(path, max_records_in_memory=2)
    return {"root": root, "index": logical_index_hash(normalized),
            "archive": content_hash(path.read_bytes())}


def alter_index(case):
    index = deepcopy(base_index())
    if case == "reordered":
        for rows in index.values():
            rows.reverse()
        index["modules"][0]["members"].reverse()
    elif case == "object_membership":
        index["objects"].append(object_row("extra", "clause"))
    elif case == "edge_kind":
        index["dependencies"][2]["kind"] = "optional"
    elif case == "edge_target":
        index["dependencies"][2]["target_hash"] = HASHES["extra"]
    elif case == "edge_condition":
        index["dependencies"][2]["condition"]["target"] = "arm64"
    elif case == "export_name":
        index["exports"][0]["name"] = "compute"
    elif case == "module_membership":
        index["modules"][0]["members"].remove(HASHES["type"])
    elif case == "external_evidence":
        index["objects"].pop()
        index["dependencies"][1]["included"] = False
    elif case == "malformed_export":
        index["exports"][0]["object_hash"] = HASHES["external"]
    elif case == "malformed_member":
        index["modules"][0]["members"].append(HASHES["external"])
    elif case == "missing_evidence":
        index["objects"].pop()
    return index


def collect(scratch):
    base = base_index()
    baseline = archive(scratch, "baseline", base)
    same_content = {
        "reordered": archive(scratch, "reordered", alter_index("reordered"),
                             roots=[HASHES["type"], HASHES["entry"]]),
        "package_label": archive(scratch, "package-label", base, label="new-label"),
        "index_path": archive(scratch, "index-path", base, index_path="alternate/index"),
    }
    assert all(row["root"] == baseline["root"] and row["index"] == baseline["index"]
               and row["archive"] != baseline["archive"] for row in same_content.values())
    changes = ("object_membership", "edge_kind", "edge_target", "edge_condition",
               "export_name", "module_membership", "external_evidence")
    different_index = {name: archive(scratch, name, alter_index(name)) for name in changes}
    assert all(row["root"] != baseline["root"] and row["index"] != baseline["index"]
               and row["archive"] != baseline["archive"] for row in different_index.values())

    different_manifest = {
        "selected_roots": archive(scratch, "selected-roots", base, roots=[HASHES["entry"]]),
        "policy": archive(scratch, "policy", base, policy="closure_with_optional"),
        "resolution_inputs": archive(scratch, "resolution", base, features=["vector"]),
    }
    assert all(row["root"] != baseline["root"] and row["index"] == baseline["index"]
               for row in different_manifest.values())

    rejected = {}
    trials = {
        "malformed_export": (alter_index("malformed_export"), {}),
        "malformed_member": (alter_index("malformed_member"), {}),
        "missing_evidence": (alter_index("missing_evidence"), {}),
        "absent_root": (base, {"roots": [HASHES["external"]]}),
        "duplicate_root": (base, {"roots": [HASHES["entry"], HASHES["entry"]]}),
    }
    for name, (index, options) in trials.items():
        try:
            package(index, **options)
        except (IndexError, PackageFormatError) as error:
            rejected[name] = str(error)
        else:
            raise ValueError(f"admitted invalid case {name}")

    def sidecar(revision):
        statement = {"package_content_root": baseline["root"], "producer": "synthetic",
                     "archive": baseline["archive"], "source_revision": revision}
        return content_hash(json.dumps(statement, sort_keys=True).encode())

    provenance = [sidecar(revision) for revision in ("source-a", "source-b")]
    assert len(set(provenance)) == 2
    destination = scratch / "inline-provenance.llpkg"
    destination.write_bytes((scratch / "baseline.llpkg").read_bytes())
    with zipfile.ZipFile(destination, "a") as container:
        container.writestr("provenance.json", json.dumps({"digest": provenance[0]}))
    try:
        verify_archive(destination, max_records_in_memory=2)
    except ArchiveError as error:
        rejected["inline_provenance"] = str(error)
    else:
        raise ValueError("prototype unexpectedly accepts an unmodeled archive member")

    paths = [HERE / "check.py", INDEX / "package_archive.py",
             INDEX / "package_index.py", IDENTITY / "package_identity.py"]
    return {"python": platform.python_version(), "baseline": baseline, "payload_ids": HASHES,
            "content_preserving_delivery_changes": same_content, "changed_logical_index": different_index,
            "changed_logical_manifest": different_manifest, "refused": rejected,
            "separate_provenance_statement_digests": provenance,
            "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in paths}}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="rt12-package-content-") as temporary:
        print(json.dumps(collect(Path(temporary)), indent=2, sort_keys=True))
