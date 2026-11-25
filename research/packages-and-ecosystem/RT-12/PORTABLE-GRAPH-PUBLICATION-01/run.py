#!/usr/bin/env python3
"""Check local graph publication and reconstruct indexes from a database-free Git archive."""

from contextlib import closing
from io import BytesIO
import json
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import time

HERE = Path(__file__).resolve().parent
BASE = runpy.run_path(str(HERE.parent / "GRAPH-REPLICA-RECOVERY-01/run.py"))
closure = BASE["closure"]
encode = BASE["encode"]
digest = BASE["digest"]
stage = BASE["stage"]
RestoreError = BASE["RestoreError"]


class Refusal(ValueError):
    pass


def setup(path):
    (path / "local").mkdir(parents=True)
    with closing(database(path)) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.executescript("""
            CREATE TABLE head (name TEXT PRIMARY KEY, root TEXT NOT NULL, inventory TEXT NOT NULL);
            CREATE TABLE reverse (
                root TEXT, target TEXT, source TEXT, occurrence INTEGER,
                PRIMARY KEY (root, source, occurrence)
            );
            CREATE INDEX reverse_target ON reverse (root, target);
        """)


def database(path):
    return sqlite3.connect(path / "catalog.sqlite", isolation_level=None, timeout=10)


def selected(connection):
    return connection.execute("SELECT root, inventory FROM head WHERE name = 'selected'").fetchone()


def project(payloads):
    return sorted((target, source, occurrence)
                  for source, data in payloads.items()
                  for occurrence, target in enumerate(json.loads(data)["references"]))


def build_revision(path, connection, expected, root, load, *, interrupt=False):
    before = selected(connection)
    if (None if before is None else before[0]) != expected:
        raise Refusal("stale-writer")
    objects = closure(root, load)
    for data in objects.values():
        stage(path / "local", data)
    local_objects = closure(root, lambda addr: (path / "local" / addr).read_bytes())
    assert local_objects == objects
    if interrupt == "objects":
        os._exit(31)
    projection = project(local_objects)
    stamp = digest(encode(sorted(local_objects)))
    connection.execute("DELETE FROM reverse WHERE root = ?", (root,))
    connection.executemany("INSERT INTO reverse VALUES (?, ?, ?, ?)",
                           ((root, target, source, ordinal) for target, source, ordinal in projection))
    connection.execute("""
        INSERT INTO head VALUES ('selected', ?, ?)
        ON CONFLICT(name) DO UPDATE SET root = excluded.root, inventory = excluded.inventory
    """, (root, stamp))
    if interrupt == "metadata":
        os._exit(32)
    return stamp


def publish(path, expected, root, load, *, interrupt=False):
    with closing(database(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        stamp = build_revision(path, connection, expected, root, load, interrupt=interrupt)
        connection.commit()
        if interrupt == "committed":
            os._exit(33)
    return stamp


def verify(path, root):
    with closing(database(path)) as connection:
        connection.execute("BEGIN")
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        objects = closure(root, lambda addr: (path / "local" / addr).read_bytes())
        stamp = digest(encode(sorted(objects)))
        assert selected(connection) == (root, stamp)
        index = connection.execute("""
            SELECT target, source, occurrence FROM reverse WHERE root = ?
            ORDER BY target, source, occurrence
        """, (root,)).fetchall()
        assert index == project(objects)
    return {"root": root, "inventory": stamp, "objects": len(objects), "reverse_rows": len(index)}


def git(repository, *args):
    env = {
        "PATH": os.environ["PATH"], "LANG": "C", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    }
    return subprocess.run(["git", *args], cwd=repository, env=env, check=True,
                          capture_output=True).stdout


def export_archive(repository, objects, root):
    repository.mkdir()
    git(repository, "init", "-q", "-b", "research/all")
    semantic = repository / "semantic"
    directory = semantic / "objects"
    directory.mkdir(parents=True)
    (semantic / "manifest.json").write_bytes(encode({
        "schema": "fixture-closed-storage-export/1", "root": root, "objects": sorted(objects),
    }))
    for address, data in objects.items():
        (directory / address).write_bytes(data)
    git(repository, "add", "semantic")
    git(repository, "-c", "commit.gpgsign=false", "commit", "-m", "export exact graph")
    assert git(repository, "branch", "--show-current").strip() == b"research/all"
    return git(repository, "archive", "--format=tar", "HEAD")


def import_archive(raw, local, expected):
    files = {}
    with tarfile.open(fileobj=BytesIO(raw), mode="r:") as archive:
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile() or member.name in files:
                raise Refusal("unsupported archive entry")
            files[member.name] = archive.extractfile(member).read()
    manifest = json.loads(files.pop("semantic/manifest.json"))
    if manifest["schema"] != "fixture-closed-storage-export/1" or manifest["root"] != expected:
        raise Refusal("export scope mismatch")
    objects = {
        address: files[f"semantic/objects/{address}"]
        for address in manifest["objects"] if f"semantic/objects/{address}" in files
    }
    if len(objects) != len(files):
        raise Refusal("extra export bytes")
    reachable = closure(expected, objects.__getitem__)
    if sorted(reachable) != manifest["objects"]:
        raise Refusal("incomplete export inventory")
    return publish(local, None, expected, reachable.__getitem__)


def exchange_file(directory, before, root):
    path = directory / "handoff.json"
    path.write_bytes(encode({"previous": before, "root": root}))
    return path


def child_arguments(local, shared, handoff, when):
    return [sys.executable, __file__, "--writer", str(local), str(shared), str(handoff), when]


def experiment(work):
    shared = work / "shared"
    shared.mkdir()
    local = work / "repo"
    setup(local)

    def make(kind, caption, *references):
        data = encode({"kind": kind, "value": caption, "references": references})
        stage(shared, data)
        return digest(data)

    common = make("contract", "common")
    first_leaf = make("implementation", "first", common)
    first = make("snapshot", "first", first_leaf)
    next_leaf = make("implementation", "second", common)
    second = make("snapshot", "second", next_leaf, common)
    final_leaf = make("implementation", "third", next_leaf)
    third = make("snapshot", "third", final_leaf)
    competing_leaf = make("implementation", "competitor", common)
    competing = make("snapshot", "competing", competing_leaf)

    def read_shared(address):
        repository_file = local / "local" / address
        return repository_file.read_bytes() if repository_file.exists() else (shared / address).read_bytes()

    publish(local, None, first, read_shared)
    before = verify(local, first)
    rows = [{"event": "bootstrap", **before}]
    request = exchange_file(work, first, second)
    for when, code in (("objects", 31), ("metadata", 32), ("committed", 33)):
        subprocess_result = subprocess.run(child_arguments(local, shared, request, when), check=False,
                                           capture_output=True)
        assert subprocess_result.returncode == code
        assert not subprocess_result.stdout and not subprocess_result.stderr
        active = second if when == "committed" else first
        if active == first:
            with closing(database(local)) as connection:
                assert connection.execute("SELECT COUNT(*) FROM reverse WHERE root=?", (second,)).fetchone() == (0,)
            assert (local / "local" / second).is_file()
        rows.append({"event": f"exit-{when}", "exit": code, **verify(local, active)})

    request = exchange_file(work, second, competing)
    marker = work / "ready"
    with closing(database(local)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        prober = subprocess.Popen(child_arguments(local, shared, request, str(marker)),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists():
                assert time.monotonic() < deadline and prober.poll() is None
                time.sleep(0.01)
            build_revision(local, writer, second, third, read_shared)
            writer.commit()
            stdout, stderr = prober.communicate(timeout=10)
            assert prober.returncode == 34 and stdout == b"stale-writer\n" and not stderr
        finally:
            if prober.poll() is None:
                prober.kill()
                prober.communicate()
    expected = verify(local, third)
    rows.append({"event": "competing-writer-after-head-change", "loser": "stale-writer", **expected})

    shared.rename(work / "unavailable-shared")
    assert verify(local, third) == expected
    raw = closure(third, lambda addr: (local / "local" / addr).read_bytes())
    archive = export_archive(work / "git-export", raw, third)
    restore = work / "restored"
    setup(restore)
    assert import_archive(archive, restore, third) == expected["inventory"]
    assert verify(restore, third) == expected
    rows.append({"event": "offline-database-free-archive-rebuild", **verify(restore, third)})

    try:
        import_archive(archive, restore, second)
    except Refusal as refusal:
        assert str(refusal) == "export scope mismatch"
    else:
        raise AssertionError("imported archive under a wrong requested root")
    assert verify(restore, third) == expected
    incomplete = export_archive(work / "git-incomplete", {third: raw[third]}, third)
    empty_restore = work / "incomplete-restore"
    setup(empty_restore)
    try:
        import_archive(incomplete, empty_restore, third)
    except RestoreError as refusal:
        assert str(refusal) == "missing object"
    else:
        raise AssertionError("partial archive admitted")
    with closing(database(empty_restore)) as connection:
        assert selected(connection) is None
    rows.append({"event": "partial-offline-archive", "decision": "missing object"})
    return {"format": "portable-graph-publication-01", "sqlite": sqlite3.sqlite_version,
            "git": git(work, "--version").decode().strip(),
            "export": digest(archive), "rows": rows, "wrong_root": "export scope mismatch"}


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "--writer":
        path, shared, handoff = map(Path, sys.argv[2:5])
        event = sys.argv[5]
        request = json.loads(handoff.read_bytes())
        if event not in ("objects", "metadata", "committed"):
            with closing(sqlite3.connect(path / "catalog.sqlite", isolation_level=None, timeout=0)) as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as error:
                    assert error.sqlite_errorcode == sqlite3.SQLITE_BUSY
                else:
                    raise AssertionError("fixture writer lock was unavailable to the control")
            Path(event).touch()
        try:
            publish(path, request["previous"], request["root"],
                    lambda addr: (shared / addr).read_bytes(), interrupt=event)
        except Refusal as error:
            print(error)
            sys.exit(34)
        sys.exit(1)
    with TemporaryDirectory(prefix="llmlang-portable-storage-") as directory:
        evidence = experiment(Path(directory))
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
