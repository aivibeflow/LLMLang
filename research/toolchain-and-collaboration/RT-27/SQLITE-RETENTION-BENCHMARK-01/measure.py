"""Measure a synthetic SQLite object store's incoming index and retained-root GC."""

import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from random import Random
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns


HERE = Path(__file__).resolve().parent
SIZES = (2048, 8192)
VARIANTS = ("scan", "indexed")
MARK = """
WITH RECURSIVE reachable(id) AS (
  SELECT id FROM root WHERE keep = 1 OR ?
  UNION
  SELECT dependency.dst FROM dependency JOIN reachable ON dependency.src = reachable.id
)
SELECT id FROM reachable
"""
INCOMING = "SELECT src FROM dependency WHERE dst = ? ORDER BY src"


def payload(i):
    return sha256(i.to_bytes(8, "little")).digest() * 8


def edges_for(i):
    if i < 4:
        return ()
    if i < 8:
        return (i - 4,)
    return (i - 4, i % 4)


def timed(callback):
    started = perf_counter_ns()
    result = callback()
    return result, perf_counter_ns() - started


def prepare(connection, size):
    connection.executescript("""
    PRAGMA page_size=4096;
    PRAGMA journal_mode=DELETE;
    PRAGMA synchronous=FULL;
    PRAGMA foreign_keys=ON;
    PRAGMA automatic_index=OFF;
    CREATE TABLE value (id INTEGER PRIMARY KEY, data BLOB NOT NULL);
    CREATE TABLE dependency (
      src INTEGER NOT NULL REFERENCES value ON DELETE CASCADE,
      dst INTEGER NOT NULL REFERENCES value ON DELETE CASCADE,
      PRIMARY KEY (src, dst)
    ) WITHOUT ROWID;
    CREATE TABLE root (id INTEGER PRIMARY KEY REFERENCES value, keep INTEGER NOT NULL);
    """)
    with connection:
        connection.executemany("INSERT INTO value VALUES (?, ?)", ((i, payload(i)) for i in range(size)))
        connection.executemany("INSERT INTO dependency VALUES (?, ?)",
                               ((i, p) for i in range(size) for p in edges_for(i)))
        # The active root and a retained reader root cover separate chains.
        connection.executemany("INSERT INTO root VALUES (?, ?)", ((size - 4, 1), (size - 3, 0)))


def gc(connection):
    with connection:
        connection.execute("CREATE TEMP TABLE live(id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO live " + MARK, (True,))
        marked = connection.execute("SELECT count(*) FROM live").fetchone()[0]
        removed = connection.execute("DELETE FROM value WHERE id NOT IN (SELECT id FROM live)").rowcount
    return marked, removed


def verify(connection, size):
    actual = connection.execute("SELECT id, data FROM value ORDER BY id").fetchall()
    oracle = [(i, payload(i)) for i in range(size) if i % 4 in (0, 1)]
    if actual != oracle:
        raise ValueError("surviving object contents did not match the independent retention rule")
    expected_edges = sorted((i, p) for i, _ in oracle for p in edges_for(i))
    if connection.execute("SELECT src, dst FROM dependency ORDER BY src, dst").fetchall() != expected_edges:
        raise ValueError("surviving dependency edges changed")
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or [
        *connection.execute("PRAGMA foreign_key_check")
    ]:
        raise ValueError("database integrity check failed")
    digest = sha256()
    for i, value in actual:
        digest.update(i.to_bytes(8, "big") + value)
    for source, target in expected_edges:
        digest.update(source.to_bytes(8, "big") + target.to_bytes(8, "big"))
    return digest.hexdigest()


def probe(variant, size, path):
    connection = sqlite3.connect(path)
    try:
        _, load_ns = timed(lambda: prepare(connection, size))

        def create_index():
            connection.execute("CREATE INDEX incoming ON dependency(dst, src)")
            connection.commit()

        index_ns = timed(create_index)[1] if variant == "indexed" else 0
        plan = connection.execute("EXPLAIN QUERY PLAN " + INCOMING, (0,)).fetchall()
        if ("incoming" in str(plan)) != (variant == "indexed"):
            raise ValueError(plan)
        before = path.stat().st_size
        targets = (*range(4), *(offset * size // 8 + shift for offset in range(1, 6) for shift in range(4)))
        answers, query_ns = timed(lambda: [connection.execute(INCOMING, (target,)).fetchall() for target in targets])
        expected = [[(i,) for i in range(size) if target in edges_for(i)] for target in targets]
        if answers != expected:
            raise ValueError("reverse lookup did not match the fixture")
        active_only = {row[0] for row in connection.execute(MARK, (False,))}
        held = {i for i in range(size) if i % 4 == 1}
        if active_only != {i for i in range(size) if i % 4 == 0} or active_only & held:
            raise ValueError("active-root-only negative control changed")

        (live, removed), collect_ns = timed(lambda: gc(connection))
        if (live, removed) != (size // 2, size // 2):
            raise ValueError((live, removed))
        after_sweep = path.stat().st_size
        free_pages = connection.execute("PRAGMA freelist_count").fetchone()[0]
        before_vacuum = verify(connection, size)
        _, vacuum_ns = timed(lambda: connection.execute("VACUUM"))
        after_vacuum = path.stat().st_size
        after_digest = verify(connection, size)
        if before_vacuum != after_digest or after_vacuum >= after_sweep or free_pages <= 0:
            raise ValueError("physical compaction changed semantic results")
        return {
            "variant": variant, "objects": size, "edges": sum(len(edges_for(i)) for i in range(size)),
            "queries": len(targets), "load_ns": load_ns, "index_ns": index_ns, "query_ns": query_ns,
            "collect_ns": collect_ns, "vacuum_ns": vacuum_ns, "before_bytes": before,
            "after_sweep_bytes": after_sweep, "after_vacuum_bytes": after_vacuum,
            "retained_ignored_by_active_only": len(held), "free_pages": free_pages,
            "survivor_sha256": after_digest, "removed": removed,
        }
    finally:
        connection.close()


def counters():
    return {key: int(number) for key, number in
            map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())}


def collect(args):
    if args.trials < 2 or args.cpu not in os.sched_getaffinity(0):
        raise ValueError("invalid logical CPU or trial count")
    os.sched_setaffinity(0, {args.cpu})
    before = counters()
    random = Random(args.seed)
    rows = []
    with TemporaryDirectory(prefix="rt27-sqlite-gc-") as temp:
        stage = Path(temp)
        for block in range(args.trials):
            combinations = [(variant, size) for variant in VARIANTS for size in SIZES]
            random.shuffle(combinations)
            for position, (variant, size) in enumerate(combinations):
                db = stage / "probe.db"
                child = subprocess.run([sys.executable, __file__, "--child", variant, str(size), db],
                                       check=True, text=True, capture_output=True, timeout=90)
                if child.stderr:
                    raise ValueError(child.stderr)
                rows.append({"block": block, "position": position, **json.loads(child.stdout)})
                db.unlink()
    after = counters()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "samples.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    config = {
        "cpu": args.cpu, "trials": args.trials, "seed": args.seed, "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "kernel": platform.release(),
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "counter_delta": {key: after[key] - before[key] for key in before},
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (args.output / "config.json").write_text(json.dumps(config, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--child":
        print(json.dumps(probe(sys.argv[2], int(sys.argv[3]), Path(sys.argv[4]))))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        for field in ("cpu", "seed", "trials"):
            parser.add_argument(f"--{field}", required=True, type=int)
        parser.add_argument("--output", required=True, type=Path)
        collect(parser.parse_args())
