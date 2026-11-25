"""Measure independent Git commit, tree and typed semantic snapshot identities."""

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"))

from src.spg_admission import validate
from src.spg_representation import Implementation, Operation, Program, compile_program, observe

BASELINE = "5c512275257a35ce867e3b2ecd540c3ac6dc04fd"
SOURCES = {
    "program.json": b'{"binding":"plus","entry":"op(\\"compute\\", x)"}\n',
    "README.md": b"Fixture documentation.\n",
}
INPUTS = (-1, 0, 1)


def git(work, *args, data=None):
    env = os.environ | {
        "LC_ALL": "C", "TZ": "UTC", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    }
    return subprocess.check_output(["git", *args], cwd=work, env=env, input=data, timeout=30)


def make_tree(work, files):
    rows = []
    for path, content in sorted(files.items()):
        blob = git(work, "hash-object", "-w", "--stdin", data=content).strip()
        rows.append(b"100644 blob " + blob + b"\t" + path.encode() + b"\n")
    return git(work, "mktree", data=b"".join(rows)).decode().strip()


def make_commit(work, tree, message, *parents):
    flags = tuple(flag for parent in parents for flag in ("-p", parent))
    return git(work, "commit-tree", tree, *flags, "-m", message).decode().strip()


def from_tree(work, tree):
    entries = git(work, "ls-tree", "-z", tree).rstrip(b"\0").split(b"\0")
    inventory = {}
    for entry in entries:
        description, raw_path = entry.split(b"\t")
        mode, kind, oid = description.split()
        path = raw_path.decode()
        if (mode, kind) != (b"100644", b"blob") or path not in SOURCES:
            raise ValueError("outside the declared closed tree profile")
        inventory[path] = oid.decode()
    if "program.json" not in inventory:
        raise ValueError("missing semantic source")
    declaration = json.loads(git(work, "cat-file", "blob", inventory["program.json"]))
    if set(declaration) != {"binding", "entry"} or declaration["binding"] not in {"plus", "minus"}:
        raise ValueError("invalid program declaration")
    program = Program(
        contracts={"quiet": ((),)},
        operations={"compute": Operation("Compute", ("Int",), "Int", "quiet"),
                    "entry": Operation("Entry", ("Int",), "Int", "quiet")},
        implementations={"plus": Implementation("compute", ("x",), "x + 1"),
                         "minus": Implementation("compute", ("x",), "x - 1"),
                         "entry": Implementation("entry", ("x",), declaration["entry"])},
        bindings={"compute": declaration["binding"]},
    )
    graph = compile_program(program)
    validate(graph)
    return graph.snapshot.root_hash, [observe(graph, "entry", (value,))[0] for value in INPUTS]


def check(work, object_format):
    git(work, "init", "--quiet", "--initial-branch=research/all", "--object-format=" + object_format)
    original = make_tree(work, SOURCES)
    docs = make_tree(work, SOURCES | {"README.md": b"Updated documentation.\n"})
    formatted = make_tree(work, SOURCES | {
        "program.json": json.dumps(json.loads(SOURCES["program.json"]), indent=2).encode() + b"\n",
    })
    changed = make_tree(work, SOURCES | {"program.json": SOURCES["program.json"].replace(b"plus", b"minus")})
    base = make_commit(work, original, "baseline")
    docs_revision = make_commit(work, docs, "docs-only", base)
    changed_revision = make_commit(work, changed, "binding-change", base)
    commits = {
        "baseline": base,
        "different-message": make_commit(work, original, "same tree and parents with new message"),
        "different-tree-docs": docs_revision,
        "different-tree-format": make_commit(work, formatted, "format-only", base),
        "different-binding": changed_revision,
        "restored-tree": make_commit(work, original, "restore", changed_revision),
        "first-merge-order": make_commit(work, original, "merge", docs_revision, changed_revision),
        "reversed-merge-order": make_commit(work, original, "merge", changed_revision, docs_revision),
    }
    rows = {}
    for name, commit in commits.items():
        tree = git(work, "rev-parse", commit + "^{tree}").decode().strip()
        root, observed = from_tree(work, tree)
        parents = git(work, "show", "-s", "--format=%P", commit).decode().split()
        rows[name] = {"commit": commit, "tree": tree, "semantic_root": root, "parents": parents,
                      "values": observed}
    before = rows["baseline"]
    (work / "program.json").write_bytes(b"unrelated worktree data")
    assert from_tree(work, before["tree"]) == (before["semantic_root"], before["values"])
    for name, row in rows.items():
        if name != "different-binding":
            assert row["semantic_root"] == before["semantic_root"] and row["values"] == [0, 1, 2]
    assert rows["different-binding"]["semantic_root"] != before["semantic_root"]
    assert rows["different-binding"]["values"] == [-2, -1, 0]
    assert rows["different-tree-docs"]["tree"] != before["tree"]
    assert rows["different-tree-format"]["tree"] != before["tree"]
    assert rows["restored-tree"]["commit"] != base and rows["restored-tree"]["tree"] == before["tree"]
    assert rows["first-merge-order"]["commit"] != rows["reversed-merge-order"]["commit"]
    refusals = {}
    for name, files in (
        ("missing-program", {"README.md": SOURCES["README.md"]}),
        ("undeclared-file", SOURCES | {"extra.json": b"{}"}),
    ):
        try:
            from_tree(work, make_tree(work, files))
        except ValueError as error:
            refusals[name] = str(error)
        else:
            raise AssertionError(name)
    return {"rows": rows, "refusals": refusals, "ignores_uncommitted_worktree_bytes": True}


def main():
    with tempfile.TemporaryDirectory(prefix="llmlang-git-root-mapping-") as temporary:
        results = {}
        for object_format in ("sha1", "sha256"):
            work = Path(temporary) / object_format
            work.mkdir()
            results[object_format] = check(work, object_format)
    for name, first in results["sha1"]["rows"].items():
        second = results["sha256"]["rows"][name]
        assert first["commit"] != second["commit"] and first["tree"] != second["tree"]
        assert first["semantic_root"] == second["semantic_root"] and first["values"] == second["values"]
    prototype = Path("research/PROTOTYPES/DEPENDENCY-GRAPH-01/src")
    pins = {}
    for name in ("spg_admission.py", "spg_representation.py", "semantic_graph.py", "recursive_identity.py"):
        source = prototype / name
        archived = git(ROOT, "show", f"{BASELINE}:{source}")
        assert archived == (ROOT / source).read_bytes(), name
        pins[name] = hashlib.sha256(archived).hexdigest()
    print(json.dumps({
        "baseline": BASELINE, "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "python": platform.python_version(), "inputs": INPUTS,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "prototype_sha256": pins, "formats": results,
    }, indent=2))


if __name__ == "__main__":
    main()
