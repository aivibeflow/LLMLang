"""Measure bounded repository lifecycle stages against the same exact expected graph."""

import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import tempfile
from time import perf_counter_ns


def git(repo, *args):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Fixture",
         "-c", "user.email=fixture@local.example", *args],
        cwd=repo, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        capture_output=True, check=True, timeout=30,
    ).stdout


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def module(index, revision=0):
    return {"id": index, "provider_revision": revision,
            "requires": [] if index == 0 else [(index - 1) // 2], "type": "i64"}


def path(index):
    return f"module-{index:05d}.json"


def export(repo, graph):
    for index, record in graph.items():
        (repo / path(index)).write_bytes(encode(record))


def import_graph(repo, size):
    graph = {i: json.loads((repo / path(i)).read_bytes()) for i in range(size)}
    for index, record in graph.items():
        assert record["id"] == index and record["type"] == "i64"
        assert record["requires"] == module(index)["requires"]
        assert all(target in graph for target in record["requires"])
    return graph


def set_up(repo, graph, left, right):
    git(repo, "init", "-q", "-b", "main")
    export(repo, graph)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD").decode().strip()
    for label, edits in (("left", left), ("right", right)):
        git(repo, "switch", "-qc", label, base)
        export(repo, edits)
        git(repo, "commit", "-qam", label)
    git(repo, "switch", "-q", "left")


def rebuild(store, graph):
    with sqlite3.connect(store) as conn:
        conn.execute("CREATE TABLE module (id INTEGER PRIMARY KEY, payload BLOB, digest TEXT)")
        conn.executemany("INSERT INTO module VALUES (?, ?, ?)",
                         ((i, encode(record), digest(record)) for i, record in graph.items()))


def verify_store(store, expected):
    with sqlite3.connect(store) as conn:
        rows = conn.execute("SELECT id, payload, digest FROM module").fetchall()
    assert {i: (payload, mark) for i, payload, mark in rows} == {
        i: (encode(record), digest(record)) for i, record in expected.items()
    }


def case(size, changed, number):
    with tempfile.TemporaryDirectory(prefix="repository-cost-") as temp:
        root = Path(temp)
        repo = root / "repo"
        full, incremental = root / "full", root / "incremental"
        for folder in (repo, full, incremental):
            folder.mkdir()
        graph = {i: module(i) for i in range(size)}
        left = {i: module(i, 1) for i in range(changed)}
        right = {i: module(i, 2) for i in range(size - changed, size)}
        expected = {**graph, **left, **right}
        set_up(repo, graph, left, right)
        export(incremental, graph)
        durations = {}

        def timed(stage, action):
            start = perf_counter_ns()
            result = action()
            durations[stage] = perf_counter_ns() - start
            return result

        timed("native_git_merge", lambda: git(repo, "merge", "--no-ff", "-qm", "merge", "right"))
        imported = timed("full_semantic_import", lambda: import_graph(repo, size))
        assert imported == expected
        exports = [("full_semantic_export", full, imported),
                   ("incremental_worktree_sync", incremental, {i: imported[i] for i in left | right})]
        if number % 2:
            exports.reverse()
        for stage, folder, records in exports:
            timed(stage, lambda: export(folder, records))
        assert import_graph(full, size) == import_graph(incremental, size) == imported
        store = root / "cache.sqlite3"
        timed("fresh_sqlite_cache_rebuild", lambda: rebuild(store, imported))
        verify_store(store, expected)

    return {"tracked_modules": size, "changed_modules": changed * 2, "sample": number,
            "expected_root": digest(expected), "ns": durations}


def main():
    sizes_and_edits = [(32, 2), (32, 8), (256, 2), (256, 32), (1024, 2), (1024, 128)]
    rows = []
    for number in range(9):
        order = sizes_and_edits if number % 2 == 0 else list(reversed(sizes_and_edits))
        rows.extend(case(size, changed, number) for size, changed in order)
    cpu = next(
        (line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
         if line.startswith("model name")), "unknown",
    )
    print(json.dumps({
        "host": {"platform": platform.platform(), "cpu": cpu, "python": platform.python_version(),
                 "git": subprocess.check_output(["git", "--version"], text=True).strip(),
                 "sqlite": sqlite3.sqlite_version,
                 "temp_filesystem": subprocess.check_output(
                     ["stat", "-f", "-c", "%T", tempfile.gettempdir()], text=True).strip(),
                 "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "samples": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
