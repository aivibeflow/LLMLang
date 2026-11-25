#!/usr/bin/env python3
"""Reconstruct and execute typed CLI projects from exact, isolated Git clones."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import importlib.util
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
TYPED = HERE.parents[2] / "language-design" / "RT-01" / "TYPED-CLI-01"
sys.path.insert(0, str(TYPED))
spec = importlib.util.spec_from_file_location("typed_cli_fixture", TYPED / "run.py")
typed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(typed)
from tests import test_rt24_merge_tree_gate as git_fixture

LAYOUTS = ("packed", "per_entry")
MANIFEST = "project.json"
PACKED = "graph/entries.json"
RUNTIME = "fixtures/runtime.rs"
FAULTS = ("missing_entry", "changed_recipe", "stale_runtime", "stale_toolchain", "unlisted_file")


class InvalidArchive(ValueError):
    """The archive cannot authorize this build."""


def git(repo, *args):
    return git_fixture.git(repo, *args).decode("utf-8").strip()


def digest(blob):
    return sha256(blob).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def unique(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise InvalidArchive("duplicate_key")
    return fields


def parse(blob):
    return json.loads(blob, object_pairs_hook=unique)


def inputs():
    return {
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True).splitlines(),
        "generator": digest((TYPED / "run.py").read_bytes()),
        "admission": digest((TYPED / "model.py").read_bytes()),
        "acceptance": digest((typed.BASELINE / "run.py").read_bytes()),
    }


def archive(recipe, runtime, layout, toolchain):
    store, snapshot = typed.model.admit(recipe)
    if layout == "packed":
        files = {PACKED: canonical(recipe)}
    else:
        files = {f"graph/{value}.json": canonical(typed.model.body_for(store, snapshot, name))
                 for name, value in snapshot.mapping.items()}
    manifest = {
        "schema": "rt24-executable-cli-archive/1", "layout": layout,
        "snapshot": snapshot.root_hash, "entries": snapshot.mapping,
        "runtime_sha256": digest(runtime.encode()), "toolchain": toolchain,
    }
    return {**files, MANIFEST: canonical(manifest), RUNTIME: runtime}


def tree_blobs(repo, revision):
    entries = git_fixture.git(repo, "ls-tree", "-rz", revision)
    paths = {}
    for entry in entries.split(b"\0")[:-1]:
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        if (mode, kind) != ("100644", "blob"):
            raise InvalidArchive("unsupported_git_mode")
        paths[path.decode()] = oid
    return paths


def clone(origin, destination, branch, revision):
    git(destination.parent, "clone", "--quiet", "--no-local", "--no-tags", "--single-branch",
        "--branch", branch, str(origin), str(destination))
    assert git(destination, "rev-parse", "HEAD") == revision
    objects = destination / ".git" / "objects"
    assert not (objects / "info" / "alternates").exists()
    assert not list((objects / "pack").glob("*.promisor"))
    assert git(destination, "status", "--porcelain") == ""


def restore(repo, revision, toolchain):
    paths = tree_blobs(repo, revision)
    if MANIFEST not in paths:
        raise InvalidArchive("missing_manifest")
    raw = {path: git_fixture.git(repo, "cat-file", "blob", oid) for path, oid in paths.items()}
    manifest = parse(raw[MANIFEST])
    if manifest["schema"] != "rt24-executable-cli-archive/1" or manifest["layout"] not in LAYOUTS:
        raise InvalidArchive("unknown_format")
    if manifest["toolchain"] != toolchain:
        raise InvalidArchive("toolchain_changed")
    selected = manifest["entries"]
    if (set(selected) != set(typed.acceptance.PROGRAMS)
            or any(len(artifact) != 64 or any(char not in "0123456789abcdef" for char in artifact)
                   for artifact in selected.values())):
        raise InvalidArchive("invalid_selection")
    names = {entry: f"graph/{identity}.json" for entry, identity in selected.items()}
    expected_files = {MANIFEST, RUNTIME}
    if manifest["layout"] == "packed":
        expected_files.add(PACKED)
    else:
        expected_files.update(names.values())
    if set(paths) != expected_files:
        raise InvalidArchive("different_file_inventory")
    if digest(raw[RUNTIME]) != manifest["runtime_sha256"]:
        raise InvalidArchive("runtime_changed")
    recipe = parse(raw[PACKED]) if manifest["layout"] == "packed" else {
        name: parse(raw[path]) for name, path in names.items()
    }
    try:
        store, snapshot = typed.model.admit(recipe)
    except (KeyError, ValueError) as error:
        raise InvalidArchive("incomplete_recipe") from error
    if snapshot.root_hash != manifest["snapshot"] or snapshot.mapping != selected:
        raise InvalidArchive("selection_mismatch")
    runtime = raw[RUNTIME].decode()
    roundtrip = archive(recipe, runtime, manifest["layout"], toolchain)
    if {path: value.encode() for path, value in roundtrip.items()} != raw:
        raise InvalidArchive("noncanonical_export")
    return store, snapshot, runtime, paths


def mutation(layout, original, echo_hash, fault):
    selection = parse(original[MANIFEST])
    target = PACKED if layout == "packed" else f"graph/{echo_hash}.json"
    if fault == "missing_entry":
        if layout == "per_entry":
            return {target: None}
        content = parse(original[target])
        del content["echo"]
        return {target: canonical(content)}
    if fault == "changed_recipe":
        content = parse(original[target])
        (content["echo"] if layout == "packed" else content)["separator"] = "\t"
        return {target: canonical(content)}
    if fault == "stale_runtime":
        before = original[RUNTIME]
        assert before.count("output.write_all(bytes)") == 1
        return {RUNTIME: before.replace("output.write_all(bytes)",
                                        'output.write_all(b"!").and_then(|_| output.write_all(bytes))')}
    if fault == "stale_toolchain":
        selection["toolchain"]["generator"] = "a" * 64
        return {MANIFEST: canonical(selection)}
    return {"graph/unlisted.json": canonical({"body": "unlisted"})}


def compile_and_check(directory, store, snapshot, runtime, edited):
    directory.mkdir()
    corpus = [replace(case, stdout=b"\t".join(os.fsencode(arg) for arg in case.argv) + b"\n")
              if edited and case.program == "echo" and not case.broken_stdout else case
              for case in typed.acceptance.CASES]
    result = {}
    for opt in (0, 3):
        profile = {}
        for name in typed.acceptance.PROGRAMS:
            recipe = typed.model.body_for(store, snapshot, name)
            source = typed.emit(recipe, snapshot.root_hash, runtime)
            command, fingerprints = typed.compile_rust(directory, f"{name}_o{opt}", source, opt)
            outputs = [typed.observe(command, case) for case in corpus if case.program == name]
            assert all(row["matches"] for row in outputs)
            profile[name] = {"fingerprints": fingerprints, "vectors": outputs}
            Path(command[0]).unlink()
        result[f"O{opt}"] = profile
    return result


def changed_bytes(repo, base, edit):
    before, after = (tree_blobs(repo, revision) for revision in (base, edit))
    new_ids = sorted(set(after.values()) - set(before.values()))
    return {
        "added_blob_count": len(new_ids),
        "added_uncompressed_bytes": sum(int(git(repo, "cat-file", "-s", oid)) for oid in new_ids),
        "removed_path_count": len(set(before) - set(after)),
    }


def study(directory, layout, baseline, change, runtime, toolchain):
    origin = directory / f"origin-{layout}"
    origin.mkdir()
    git(origin, "init", "--quiet", "--template=", "--initial-branch=baseline", "--object-format=sha1")
    original = archive(baseline, runtime, layout, toolchain)
    base = git_fixture.commit(origin, original)
    git(origin, "switch", "--quiet", "-c", "edit", base)
    edited = archive(change, runtime, layout, toolchain)
    edit = git_fixture.commit(origin, {**edited, **dict.fromkeys(set(original) - set(edited))})
    output = {}
    for branch, revision in (("baseline", base), ("edit", edit)):
        isolated = directory / f"clone-{layout}-{branch}"
        clone(origin, isolated, branch, revision)
        store, snapshot, runtime_bytes, paths = restore(isolated, revision, toolchain)
        output[branch] = {"revision": revision, "tree": git(isolated, "rev-parse", "HEAD^{tree}"),
                          "snapshot": snapshot.root_hash, "entries": snapshot.mapping,
                          "blob_hashes": paths, "roundtrip_exact": True,
                          "native": compile_and_check(directory / f"build-{layout}-{branch}", store,
                                                      snapshot, runtime_bytes, branch == "edit")}
    controls = {}
    echo_hash = output["baseline"]["entries"]["echo"]
    for fault in FAULTS:
        branch = fault.replace("_", "-")
        git(origin, "switch", "--quiet", "-c", branch, base)
        revision = git_fixture.commit(origin, mutation(layout, original, echo_hash, fault))
        isolated = directory / f"clone-{layout}-{branch}"
        clone(origin, isolated, branch, revision)
        try:
            restore(isolated, revision, toolchain)
        except InvalidArchive as error:
            reason = str(error)
        else:
            raise AssertionError("Invalid archive reached build")
        controls[fault] = {"revision": revision, "reason": reason}
    assert {name: row["reason"] for name, row in controls.items()} == {
        "missing_entry": "incomplete_recipe" if layout == "packed" else "different_file_inventory",
        "changed_recipe": "selection_mismatch", "stale_runtime": "runtime_changed",
        "stale_toolchain": "toolchain_changed", "unlisted_file": "different_file_inventory",
    }
    counts = {"files": len(original), "bytes": sum(len(blob.encode()) for blob in original.values())}
    return {"layout": layout, "restored": output, "controls": controls,
            "baseline_size": counts, "edit_cost": changed_bytes(origin, base, edit)}


def run(directory):
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    assert version == "git version 2.52.0", version
    recipe = parse((TYPED / "programs.json").read_bytes())
    changed = deepcopy(recipe)
    changed["echo"]["separator"] = "\t"
    runtime = (TYPED / "runtime.rs").read_text()
    toolchain = inputs()
    entries = [study(directory, layout, recipe, changed, runtime, toolchain) for layout in LAYOUTS]
    for branch in ("baseline", "edit"):
        first, second = (case["restored"][branch] for case in entries)
        assert first["tree"] != second["tree"]
        for key in ("snapshot", "entries", "native"):
            assert first[key] == second[key]
    baseline, edited = (entries[0]["restored"][stage] for stage in ("baseline", "edit"))
    assert baseline["snapshot"] != edited["snapshot"]
    assert [name for name in baseline["entries"] if baseline["entries"][name] != edited["entries"][name]] == ["echo"]
    count = sum(len(entry["vectors"]) for case in entries for state in case["restored"].values()
                for profile in state["native"].values() for entry in profile.values())
    return {
        "schema": "llmlang-rt24-clean-clone-cli/1", "python": platform.python_version(), "git": version,
        "runner_sha256": digest(Path(__file__).read_bytes()), "toolchain": toolchain,
        "unmodified_native_runtime_sha256": digest(runtime.encode()),
        "successful_clones": sum(len(case["restored"]) for case in entries),
        "refused_clones": sum(len(case["controls"]) for case in entries),
        "native_vectors": count, "measurements": entries,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-cli-clone-") as scratch:
        result = run(Path(scratch))
    measurements = result.pop("measurements")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "measurements": [')
    print(",\n".join("    " + json.dumps(row) for row in measurements))
    print("  ]\n}")
