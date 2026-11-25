"""Separate one proposal-time search from native snapshot-bound execution."""
import argparse
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
import json
import subprocess
from tempfile import TemporaryDirectory

from scipy import __version__ as scipy_version
from scipy.spatial import cKDTree

from runtime import Binding, canonical_digest, invoke

HERE = Path(__file__).resolve().parent
CONTRACT = canonical_digest({"input": "integer", "domain": [-4, 4], "output": "integer-offset"})
OTHER = canonical_digest({"input": "text", "output": "text"})


def compile_provider(workspace, store, offset):
    executable = workspace / "provider"
    subprocess.run(["gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", "-static",
                    f"-DOFFSET={offset}", HERE / "provider.c", "-o", executable],
                   check=True, capture_output=True, timeout=30)
    elf = subprocess.check_output(["readelf", "-l", "-d", executable], text=True, timeout=10)
    assert "INTERP" not in elf and "(NEEDED)" not in elf
    artifact = executable.read_bytes()
    identifier = sha256(artifact).hexdigest()
    (store / identifier).write_bytes(artifact)
    return identifier


def prepare_catalog(artifact, offset):
    current = canonical_digest({"definition": "fixture-offset", "offset": offset})
    decoy = canonical_digest({"definition": "fixture-text", "name": "offset"})
    return {current: {"contract": CONTRACT, "artifact": artifact},
            decoy: {"contract": OTHER, "artifact": canonical_digest({"fixture": "metadata-only"})}}


def write_index(path, catalog, reverse=False):
    coordinates = [[0.01, 0], [0.9, 0]] if reverse else [[0.9, 0], [0.01, 0]]
    path.write_text(json.dumps({"root": canonical_digest(catalog),
                                "functions": list(catalog), "vectors": coordinates}))


def bind(path, catalog, root):
    index = json.loads(path.read_text())
    names, vectors = index["functions"], index["vectors"]
    if (index["root"] != root or set(names) != set(catalog)
            or len(names) != len(catalog) or len(vectors) != len(names)):
        raise ValueError("stale-index")
    distances, position = cKDTree(vectors).query([0, 0], k=len(catalog))
    ranked = [names[entry] for entry in position]
    assert all(a <= b for a, b in zip(distances, distances[1:]))
    exact = [identifier for identifier in ranked if catalog[identifier]["contract"] == CONTRACT]
    if len(exact) != 1:
        raise ValueError("unresolved-selection")
    selected = exact[0]
    return Binding(root, selected, CONTRACT, catalog[selected]["artifact"]), ranked


def refuse(code, function):
    try:
        function()
    except ValueError as err:
        assert str(err) == code, (code, err)
        return code
    raise AssertionError(f"expected {code}")


def run(work):
    store = work / "store"
    store.mkdir()
    index = work / "index.json"
    old_artifact = compile_provider(work, store, 11)
    new_artifact = compile_provider(work, store, 17)
    assert new_artifact != old_artifact
    old, new = prepare_catalog(old_artifact, 11), prepare_catalog(new_artifact, 17)
    old_root, new_root = canonical_digest(old), canonical_digest(new)

    write_index(index, old)
    original, order = bind(index, old, old_root)
    assert order[0] != original.function
    inputs = range(-4, 5)
    first = [invoke(store, old, original, old_root, CONTRACT, value) for value in inputs]
    assert first == [value + 11 for value in inputs]

    write_index(index, old, reverse=True)
    reordered, alternate_order = bind(index, old, old_root)
    assert original == reordered and alternate_order == order[::-1]
    incomplete = json.loads(index.read_text())
    incomplete["functions"] = [original.function] * len(old)
    index.write_text(json.dumps(incomplete))
    duplicate_index = refuse("stale-index", lambda: bind(index, old, old_root))
    index.unlink()
    retained = [invoke(store, old, original, old_root, CONTRACT, value) for value in inputs]
    assert first == retained

    write_index(index, old)
    stale_index = refuse("stale-index", lambda: bind(index, new, new_root))
    write_index(index, new)
    current, current_order = bind(index, new, new_root)
    assert current.function != original.function and current_order[0] != current.function
    index.unlink()
    switched = [invoke(store, new, current, new_root, CONTRACT, value) for value in inputs]
    assert switched == [value + 17 for value in inputs]
    prior = [invoke(store, old, original, old_root, CONTRACT, value) for value in inputs]
    assert prior == first

    controls = {
        "stale_discovery_index": stale_index,
        "duplicate_rows_with_current_root": duplicate_index,
        "old_binding_at_current_root": refuse("binding-scope", lambda: invoke(
            store, new, original, new_root, CONTRACT, 0)),
        "wrong_required_contract": refuse("binding-scope", lambda: invoke(
            store, old, original, old_root, OTHER, 0)),
        "wrong_selected_function": refuse("function-selection", lambda: invoke(
            store, old, replace(original, function=current.function), old_root, CONTRACT, 0)),
        "wrong_artifact_identity": refuse("artifact-selection", lambda: invoke(
            store, old, replace(original, artifact=new_artifact), old_root, CONTRACT, 0)),
        "wrong_snapshot_contents": refuse("snapshot-digest", lambda: invoke(
            store, new, original, old_root, CONTRACT, 0)),
    }
    old_path = store / old_artifact
    old_path.write_bytes((store / new_artifact).read_bytes())
    controls["replaced_artifact_bytes"] = refuse("artifact-digest", lambda: invoke(
        store, old, original, old_root, CONTRACT, 0))
    old_path.unlink()
    controls["missing_old_artifact"] = refuse("artifact-unavailable", lambda: invoke(
        store, old, original, old_root, CONTRACT, 0))
    return {
        "scipy": scipy_version, "calls": 36, "inputs": list(inputs),
        "original": asdict(original), "current": asdict(current),
        "discovery_order_reversed": True,
        "original_with_index": first, "original_after_index_removed": retained,
        "current_after_index_removed": switched, "authorized_retained_root": prior,
        "refusals": controls,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-bound-native-call-") as path:
        result = run(Path(path))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
