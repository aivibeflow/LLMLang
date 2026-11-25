"""Compare persisted byte counts and exact root reconstruction across storage layouts."""

from contextlib import closing
import dbm.dumb
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
from tempfile import TemporaryDirectory


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def identity(payload):
    return hashlib.sha256(payload).hexdigest()


def build_graph(count):
    objects = {}
    ids = []
    forward = []
    for index in range(count):
        edges = []
        if index > 0:
            edges.append(("invoke", ids[-1]))
        if index > 1:
            edges.append(("requires", ids[index // 2]))
        payload = encode({"kind": "fixture-node", "local": index, "edges": edges})
        address = identity(payload)
        ids.append(address)
        objects[address] = payload
        forward.extend((address, target, role, occurrence)
                       for occurrence, (role, target) in enumerate(edges))
    return ids, objects, forward


def traverse(root, read):
    reached = {}
    stack = [root]
    while stack:
        address = stack.pop()
        if address in reached:
            continue
        payload = read(address)
        assert identity(payload) == address
        reached[address] = payload
        stack.extend(target for _, target in json.loads(payload)["edges"])
    return reached


def profile_access(root, objects, forward, targets, read, reverse_lookup=None):
    reached = traverse(root, read)
    assert reached == objects
    rows_by_target = {}
    for target in targets:
        expected = sorted(edge for edge in forward if edge[1] == target)
        if reverse_lookup:
            rows = reverse_lookup(target)
        else:
            rows = sorted(
                (address, found, role, occurrence)
                for address, payload in reached.items()
                for occurrence, (role, found) in enumerate(json.loads(payload)["edges"])
                if found == target
            )
        assert rows == expected
        rows_by_target[target] = rows
    return {"reached_objects": len(reached), "matched_query_counts": [len(rows_by_target[k]) for k in targets]}


def filesystem(directory, root, objects, forward, targets):
    def path(address):
        return directory / address[:2] / address[2:]

    for address, payload in objects.items():
        target = path(address)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(payload)
    return profile_access(root, objects, forward, targets, lambda address: path(address).read_bytes())


def dbm_kv(directory, root, objects, forward, targets):
    location = directory / "objects"
    with dbm.dumb.open(str(location), "n") as db:
        for address, payload in objects.items():
            db[address] = payload
    with dbm.dumb.open(str(location), "r") as db:
        return profile_access(root, objects, forward, targets, lambda address: db[address])


def sqlite_layout(directory, root, objects, forward, targets, *, indexed):
    location = directory / "objects.sqlite"
    with closing(sqlite3.connect(location)) as db:
        db.execute("PRAGMA page_size=4096")
        db.execute("CREATE TABLE objects(address TEXT PRIMARY KEY,payload BLOB NOT NULL) WITHOUT ROWID")
        db.executemany("INSERT INTO objects VALUES (?,?)", objects.items())
        if indexed:
            db.execute("CREATE TABLE edges(source TEXT,target TEXT,role TEXT,occurrence INTEGER)")
            db.executemany("INSERT INTO edges VALUES (?,?,?,?)", forward)
            db.execute("CREATE INDEX reverse_lookup ON edges(target,role)")
        db.commit()
        db.execute("VACUUM")
    with closing(sqlite3.connect(location)) as db:
        def read(address):
            return db.execute("SELECT payload FROM objects WHERE address=?", (address,)).fetchone()[0]

        def reverse_lookup(target):
            return sorted(db.execute(
                "SELECT source,target,role,occurrence FROM edges WHERE target=?", (target,)
            ).fetchall())

        return profile_access(root, objects, forward, targets, read, reverse_lookup if indexed else None)


def persisted(directory):
    files = [path for path in directory.rglob("*") if path.is_file()]
    return {"regular_files": len(files), "regular_file_bytes": sum(path.stat().st_size for path in files)}


def main():
    layouts = {
        "filesystem_cas": filesystem, "stdlib_dbm_kv": dbm_kv,
        "sqlite_kv": lambda *args: sqlite_layout(*args, indexed=False),
        "sqlite_with_reverse_index": lambda *args: sqlite_layout(*args, indexed=True),
    }
    result = {}
    with TemporaryDirectory(prefix="llmlang-storage-layouts-") as scratch:
        for count in (32, 256, 1024):
            ids, objects, forward = build_graph(count)
            targets = (ids[0], ids[count // 2], ids[-1], identity(b"absent target"))
            profiles = {}
            for name, layout in layouts.items():
                directory = Path(scratch) / str(count) / name
                directory.mkdir(parents=True)
                (directory / "root.txt").write_text(ids[-1] + "\n", encoding="ascii")
                root = (directory / "root.txt").read_text().strip()
                access = layout(directory, root, objects, forward, targets)
                assert access["reached_objects"] == count
                profiles[name] = access | persisted(directory)
            assert len({tuple(r["matched_query_counts"]) for r in profiles.values()}) == 1
            result[count] = {
                "root": ids[-1], "canonical_payload_bytes": sum(map(len, objects.values())),
                "edge_count": len(forward), "queried_targets": targets, "layouts": profiles,
            }
    return {"schema": "llmlang-rt12-concrete-storage-layouts/1", "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version, "dbm": "CPython stdlib dbm.dumb",
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "storage": "sum of persisted regular-file byte lengths after close", "results": result}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
