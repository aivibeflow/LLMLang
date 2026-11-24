#!/usr/bin/env python3
"""Compare two canonical Git layouts for one admitted closed source inventory."""

import argparse
from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
for parent in HERE.parents:
    candidate = parent / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
    if candidate.is_dir():
        os.environ.setdefault("LLMLANG_DEPENDENCY_GRAPH_PROTOTYPE", str(candidate))
        break
PROTOTYPE = Path(os.environ["LLMLANG_DEPENDENCY_GRAPH_PROTOTYPE"]).resolve()
sys.path.insert(0, str(PROTOTYPE))
from src.semantic_dependency_index import SemanticObjectError, publish_declaration
from src.semantic_graph import ContentStore, canonical_bytes, digest
from tests import test_rt24_merge_tree_gate as graph


def populate(*, offset=1, effect="archive", slot="caller", event_order=(1, 2), unbound=False):
    store = ContentStore()
    result = graph.declaration("type", "type:result", {"int": 32})
    result_id = publish_declaration(store, result)
    contract = graph.declaration("contract", "contract:score", {"name": "счёт"}, references=[
        {"reference_id": "result", "relation": "uses_type", "target_kind": "type", "target_hash": result_id},
    ])
    contract_id = publish_declaration(store, contract)
    flags = graph.declaration("effect", "effect:journal", {"scope": effect})
    provider = graph.declaration("function", "function:score", {"offset": offset, "events": list(event_order)},
                                 references=[{"reference_id": "provides", "relation": "provides_contract",
                                              "target_kind": "contract", "target_hash": contract_id}])
    provider_id = publish_declaration(store, provider)
    targets = [{"target_id": name, "condition": name, "required_contract_hash": contract_id,
                "target_hash": "unbound" if unbound else provider_id} for name in ("z-on", "a-off")]
    caller = graph.declaration("function", "function:entry", call_sites=[
        {"call_site_id": "second", "targets": targets},
        {"call_site_id": "first", "targets": list(reversed(targets))},
    ])
    return [graph.row("z-type", result), graph.row("contract", contract),
            graph.row("aa-provider", provider), graph.row(slot, caller),
            graph.row("copy/счёт", provider), graph.row("effect", flags)]


def raw_files(rows, *, compact=False, groups=1, moved=False, reversed_orders=False):
    rows = deepcopy(rows)
    if reversed_orders:
        rows.reverse()
        for row in rows:
            decl = row["declaration"]
            decl["references"].reverse()
            decl["call_sites"].reverse()
            for site in decl["call_sites"]:
                site["targets"].reverse()
    paths = [f"program/{'folder/moved' if moved else 'source'}/{index}.json" for index in range(groups)]
    manifest = graph.manifest(*reversed(paths) if reversed_orders else paths)
    records = {path: rows[index::groups] for index, path in enumerate(paths)}
    records[graph.MANIFEST] = manifest
    options = {"separators": (",", ":"), "sort_keys": True} if compact else {"indent": 2, "ensure_ascii": False}
    return {path: (json.dumps(item, **options) + ("\n" if compact else "\n\n")).encode()
            for path, item in records.items()}


def program_tree(repo, work, files):
    with TemporaryDirectory(prefix="private-index-", dir=work) as temp:
        index = Path(temp) / "index"
        graph.git(repo, "read-tree", "--empty", index=index)
        entries = b""
        for path, data in sorted(files.items()):
            blob = graph.git(repo, "hash-object", "-w", "--stdin", stdin=data).strip()
            entries += b"100644 " + blob + b"\t" + path.encode("ascii") + b"\0"
        graph.git(repo, "update-index", "-z", "--index-info", index=index, stdin=entries)
        return graph.git(repo, "write-tree", index=index).decode().strip()


def export(store, snapshot, layout):
    rows = [graph.row(slot, store.get(identity).payload) for slot, identity in sorted(snapshot.mapping.items())]
    if layout == "packed":
        files = {"program/objects.json": rows}
    elif layout == "slot_files":
        files = {f"program/slots/{digest(['rt24.slot-path.v1', row['slot']])}.json": [row] for row in rows}
        if len(files) != len(rows):
            raise ValueError("Case-neutral slot paths are not unique")
    else:
        raise ValueError("Unsupported canonical layout")
    files[graph.MANIFEST] = graph.manifest(*sorted(files))
    return {path: canonical_bytes(body) + b"\n" for path, body in files.items()}


def canonicalize(repo, work, original, layout):
    initial = graph.read_inventory(repo, original)
    store, root = graph.import_closed(initial)
    encoded = export(store, root, layout)
    exact = program_tree(repo, work, encoded)
    exported = graph.read_inventory(repo, exact)
    reloaded_store, reloaded = graph.import_closed(exported)
    if root.mapping != reloaded.mapping or root.root_hash != reloaded.root_hash:
        raise ValueError("Canonical export changed selections or their roots")
    if export(reloaded_store, reloaded, layout) != encoded:
        raise ValueError("Export did not stabilize after a fresh import")
    return root, exact, encoded


def differences(base, updated):
    changed = [name for name, text in updated.items() if text != base.get(name)]
    removed = sorted(base.keys() - updated)
    return {"added_or_changed_blobs": len(changed), "deleted_blobs": len(removed),
            "added_or_changed_bytes": sum(len(updated[name]) for name in changed)}


def controls(repo, work):
    invalid = {}
    baseline = raw_files(populate())
    bad_manifest = dict(baseline)
    bad_manifest[graph.MANIFEST] = b'{"version":2,"sources":["program/source/0.json"]}'
    invalid["unknown_manifest_version"] = (bad_manifest, graph.InventoryError)
    wrong = populate()
    wrong[0]["declaration"]["schema_version"] = -1
    invalid["unknown_declaration_version"] = (raw_files(wrong), SemanticObjectError)
    dup = populate()
    invalid["duplicate_slot"] = (raw_files([*dup, dup[0]]), graph.InventoryError)
    invalid["missing_file"] = ({graph.MANIFEST: baseline[graph.MANIFEST]}, graph.InventoryError)
    invalid["unavailable_callee"] = (raw_files(populate(unbound=True)), graph.GraphImportError)
    for name, (files, expected) in invalid.items():
        tree = program_tree(repo, work, files)
        try:
            canonicalize(repo, work, tree, "packed")
        except expected:
            continue
        raise ValueError(f"Unadmitted source was accepted: {name}")
    return {name: expected.__name__ for name, (_, expected) in invalid.items()}


def replay():
    layouts = ("packed", "slot_files")
    with TemporaryDirectory(prefix="llmlang-rt24-canonical-") as temporary:
        work = Path(temporary)
        repo = work / "repo"
        repo.mkdir()
        graph.git(repo, "init", "--bare", "--quiet", "--template=", "--object-format=sha1")

        raw_trees = set()
        canonical_results = {}
        expected_root = None
        for compact, groups, moved, reversed_orders in product((False, True), (1, 2, 6), (False, True), (False, True)):
            raw = raw_files(populate(), compact=compact, groups=groups, moved=moved, reversed_orders=reversed_orders)
            original = program_tree(repo, work, raw)
            raw_trees.add(original)
            for layout in layouts:
                root, exact, files = canonicalize(repo, work, original, layout)
                if expected_root is None:
                    expected_root = root
                if root.root_hash != expected_root.root_hash:
                    raise ValueError("Physical input layout altered semantic identity")
                if root.mapping["aa-provider"] != root.mapping["copy/счёт"] or len(root.mapping) != 6:
                    raise ValueError("Equal value aliases lost their two occurrence selections")
                known_tree, known_files = canonical_results.setdefault(layout, (exact, files))
                if (known_tree, known_files) != (exact, files):
                    raise ValueError("The same semantic fixture produced multiple canonical trees")

        if len(raw_trees) != 24 or canonical_results["packed"][0] == canonical_results["slot_files"][0]:
            raise ValueError("Fixture failed to vary physical representation")
        changes = {}
        for name, parameters in {
            "unrelated_effect_edit": {"effect": "send"},
            "provider_and_exact_retarget": {"offset": 2},
            "rename_occurrence": {"slot": "moved-entry"},
            "change_ordered_payload": {"event_order": (2, 1)},
        }.items():
            original = program_tree(repo, work, raw_files(populate(**parameters)))
            changes[name] = {}
            for layout in layouts:
                root, exact, new_files = canonicalize(repo, work, original, layout)
                previous_tree, previous_files = canonical_results[layout]
                if root.root_hash == expected_root.root_hash or exact == previous_tree:
                    raise ValueError(f"Semantic change failed to update its identities: {name}")
                changes[name][layout] = differences(previous_files, new_files)

        records = {layout: {"canonical_tree": exact, "files": len(files),
                            "bytes": sum(len(blob) for blob in files.values()),
                            "blob_sha256": {path: sha256(blob).hexdigest() for path, blob in sorted(files.items())}}
                   for layout, (exact, files) in canonical_results.items()}
        rejected = controls(repo, work)
    hashes = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            source = Path(filename).resolve()
            if source.suffix == ".py" and source.is_relative_to(PROTOTYPE):
                hashes[str(source.relative_to(PROTOTYPE))] = sha256(source.read_bytes()).hexdigest()
    return {"schema": "llmlang-rt24-canonical-layouts-v1",
            "git": subprocess.check_output(["git", "--version"], text=True).strip(),
            "python": sys.version.split()[0], "input_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "prototype_sha256": dict(sorted(hashes.items())), "raw_trees": sorted(raw_trees),
            "semantic_root": expected_root.root_hash, "layouts": records, "changes": changes, "rejected": rejected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), indent=2) + "\n", encoding="utf-8")
