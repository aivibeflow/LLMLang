#!/usr/bin/env python3
"""Compare Git-visible graph layouts and KV-independent reconstruction."""

from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import runpy
import sqlite3
import sys
import tarfile
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
RT12 = HERE.parents[2] / "packages-and-ecosystem/RT-12"
FIXTURE = runpy.run_path(str(RT12 / "PORTABLE-GRAPH-PUBLICATION-01/run.py"))
git = FIXTURE["git"]
digest = FIXTURE["digest"]
encode = FIXTURE["encode"]
closure = FIXTURE["closure"]
project = FIXTURE["project"]
RestoreError = FIXTURE["RestoreError"]
LAYOUTS = ("one-file-per-object", "packed-records", "external-kv")


class Refusal(ValueError):
    pass


def members(repository, ref):
    table = {}
    with tarfile.open(fileobj=BytesIO(git(repository, "archive", "--format=tar", ref)), mode="r:") as archive:
        for entry in archive:
            if entry.isdir():
                continue
            assert entry.isfile() and entry.name not in table
            table[entry.name] = archive.extractfile(entry).read()
    return table


def graph_data():
    payloads = {}

    def node(kind, value, *references):
        raw = encode({"kind": kind, "value": value, "references": references})
        address = digest(raw)
        payloads[address] = raw
        return address

    signatures = [node("contract", {"index": number, "result": "u32"}) for number in range(6)]
    providers = [node("implementation", {"index": number, "language": "C"},
                      signatures[number % len(signatures)]) for number in range(36)]
    first = node("snapshot", {"entry": "main"}, *providers)
    providers[7] = node("implementation", {"index": 7, "language": "Rust"}, signatures[1])
    second = node("snapshot", {"entry": "main"}, *providers)
    return [(root, closure(root, payloads.__getitem__)) for root in (first, second)]


def carrier(layout, root, objects):
    files = {
        "semantic/manifest.json": encode({
            "schema": "closed-semantic-repository/1", "layout": layout, "root": root,
            "inventory": sorted(objects), "reverse": digest(encode(project(objects))),
        }),
        "semantic/reverse.json": encode(project(objects)),
    }
    if layout == "one-file-per-object":
        for address, raw in objects.items():
            files["semantic/objects/" + address] = raw
    if layout == "packed-records":
        files["semantic/objects.jsonl"] = b"".join(
            encode([address, objects[address].decode("utf-8")]) + b"\n" for address in sorted(objects)
        )
    return files


def decode_records(payload):
    table = {}
    for line in payload.splitlines(keepends=True):
        row = json.loads(line)
        if (type(row) is not list or len(row) != 2 or not all(type(value) is str for value in row)
                or row[0] in table or line != encode(row) + b"\n"):
            raise Refusal("bad record envelope")
        table[row[0]] = row[1].encode("utf-8")
    if sorted(table) != list(table):
        raise Refusal("records out of order")
    return table


def verify(files, expected, kv=None):
    manifest_raw = files["semantic/manifest.json"]
    manifest = json.loads(manifest_raw)
    if manifest_raw != encode(manifest) or manifest["schema"] != "closed-semantic-repository/1":
        raise Refusal("wrong manifest schema or bytes")
    if manifest["root"] != expected:
        raise Refusal("wrong semantic root")
    layout = manifest["layout"]
    if layout == "one-file-per-object":
        stored = {name.rsplit("/", 1)[1]: payload for name, payload in files.items()
                  if name.startswith("semantic/objects/")}
        loader = stored.__getitem__
    elif layout == "packed-records":
        stored = decode_records(files["semantic/objects.jsonl"])
        loader = stored.__getitem__
    elif layout == "external-kv":
        if kv is None:
            raise Refusal("required KV bytes unavailable")
        stored = None

        def loader(identity):
            row = kv.execute("SELECT raw FROM objects WHERE identity = ?", (identity,)).fetchone()
            if row is None:
                raise KeyError(identity)
            return row[0]
    else:
        raise Refusal("unknown layout")
    payloads = closure(expected, loader)
    if sorted(payloads) != manifest["inventory"] or (stored is not None and set(stored) != set(payloads)):
        raise Refusal("wrong closed inventory")
    reverse = encode(project(payloads))
    if files.get("semantic/reverse.json") != reverse or manifest["reverse"] != digest(reverse):
        raise Refusal("wrong required reverse metadata")
    return payloads


def history(repository, layout, algorithm, revisions):
    repository.mkdir()
    git(repository, "init", "-q", "-b", "research/all", "--object-format=" + algorithm)
    results = []
    previous = set()
    for number, (root, objects) in enumerate(revisions, 1):
        files = carrier(layout, root, objects)
        for discarded in previous - set(files):
            (repository / discarded).unlink()
        for name, data in files.items():
            path = repository / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        git(repository, "add", "-A")
        git(repository, "-c", "commit.gpgsign=false", "commit", "-m", f"graph {number}")
        commit = git(repository, "rev-parse", "HEAD").decode().strip()
        tree = git(repository, "rev-parse", "HEAD^{tree}").decode().strip()
        assert members(repository, commit) == files
        results.append((commit, tree))
        previous = set(files)
    assert git(repository, "branch", "--show-current").strip() == b"research/all"
    return results


def experiment(directory):
    revisions = graph_data()
    rows = []
    refusals = []
    with closing(sqlite3.connect(directory / "external.db")) as kv:
        kv.execute("CREATE TABLE objects (identity TEXT PRIMARY KEY, raw BLOB NOT NULL)")
        kv.executemany("INSERT OR IGNORE INTO objects VALUES (?, ?)",
                       (item for _, objects in revisions for item in objects.items()))
        kv.commit()

        def refused(name, expected, callback):
            try:
                callback()
            except (Refusal, RestoreError) as error:
                assert str(error) == expected, (name, error)
            else:
                raise AssertionError(name)
            refusals.append({"case": name, "decision": expected})

        for algorithm in ("sha1", "sha256"):
            for layout in LAYOUTS:
                name = algorithm + "-" + layout
                source = directory / (name + "-source")
                clone = directory / (name + "-clone")
                commits = history(source, layout, algorithm, revisions)
                git(directory, "clone", "--quiet", "--no-local", str(source), str(clone))
                git(clone, "remote", "remove", "origin")
                git(clone, "fsck", "--full")
                source.rename(directory / (name + "-unavailable"))
                for (root, objects), (commit, tree) in zip(revisions, commits, strict=True):
                    files = members(clone, commit)
                    assert len(git(clone, "ls-tree", "-r", "-z", commit).split(b"\0")) == len(files) + 1
                    row = {"git_format": algorithm, "layout": layout, "commit": commit, "tree": tree,
                           "root": root, "tracked_files": len(files), "closure_objects": len(objects)}
                    if layout == "external-kv":
                        refused(f"{name}/{root}/offline", "required KV bytes unavailable",
                                lambda: verify(files, root))
                        assert verify(files, root, kv) == objects
                        row["available"] = "closed-with-KV"
                    else:
                        assert verify(files, root) == objects
                        row["available"] = "closed-offline"
                    rows.append(row)
                final_root, final_objects = revisions[-1]
                files = members(clone, commits[-1][0])
                if layout == "packed-records":
                    stale = files | {"semantic/reverse.json": encode(project(revisions[0][1]))}
                    assert stale["semantic/reverse.json"] != files["semantic/reverse.json"]
                    refused(f"{name}/stale-index", "wrong required reverse metadata",
                            lambda: verify(stale, final_root))
                    unordered = b"".join(reversed(files["semantic/objects.jsonl"].splitlines(keepends=True)))
                    refused(f"{name}/unordered-pack", "records out of order",
                            lambda: verify(files | {"semantic/objects.jsonl": unordered}, final_root))
                if layout == "external-kv":
                    original = final_objects[final_root]
                    kv.execute("UPDATE objects SET raw = ? WHERE identity = ?",
                               (b"altered fixture bytes", final_root))
                    refused(f"{name}/corrupt-KV", "object digest mismatch",
                            lambda: verify(files, final_root, kv))
                    kv.execute("UPDATE objects SET raw = ? WHERE identity = ?", (original, final_root))
                    kv.commit()

    assert len({row["root"] for row in rows}) == 2
    assert len({row["tree"] for row in rows}) == len(rows)
    assert all(row["tracked_files"] < row["closure_objects"] for row in rows if row["layout"] == "packed-records")
    return {
        "format": "git-closed-representation-01", "git": git(directory, "--version").decode().strip(),
        "sqlite": sqlite3.sqlite_version, "recovered": rows, "refusals": refusals,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-git-representation-") as temporary:
        evidence = experiment(Path(temporary))
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
