"""Compare binary package tables with the exact logical and streaming index oracle."""

from contextlib import ExitStack
from copy import deepcopy
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-INDEX-01"
sys.path.insert(0, str(PROTOTYPE))
from package_index import TABLES, IndexError as LogicalError, _canonical, key, logical_hash, merge, merge_sorted_indexes, normalize
from tables import HEADER, MAGIC, VERSION, U32, Table, WireError, encode_row, write_table


MODULES = ("z", "aa", "a", "é", "e\u0301", "中", "beta", "math")
NAMES = ("read", "rz", "raaa", "é", "中", "e\u0301", "α", "beta")


def content(name):
    return "sha256:" + sha256(name.encode("utf-8")).hexdigest()


def provider(indices):
    index = {table: [] for table in TABLES}
    for number in indices:
        module = MODULES[number]
        members = [content(f"{module}/{name}") for name in NAMES]
        index["modules"].append({"module_id": module, "members": list(reversed(members))})
        for ordinal, (name, member) in enumerate(zip(NAMES, members, strict=True)):
            index["objects"].append({"hash": member, "kind": "function", "size": 20 + ordinal})
            index["exports"].append({"module_id": module, "name": name, "object_hash": member})
            dependency = {
                "source_hash": member, "edge_id": "next", "kind": "required",
                "target_hash": members[(ordinal + 1) % len(members)], "included": True,
            }
            if ordinal == 0:
                dependency["condition"] = {"optional": [True, None], "name": "é"}
            index["dependencies"].append(dependency)
    return normalize(index)


def write_index(root, tables):
    root.mkdir()
    for table, rows in tables.items():
        write_table(root / table, table, rows)


def merge_archives(output, roots):
    output.mkdir()
    with ExitStack() as resources:
        opened = [{name: resources.enter_context(Table(path / name, name)) for name in TABLES}
                  for path in roots]
        result = merge_sorted_indexes([{name: table.rows() for name, table in tables.items()}
                                       for tables in opened])
        for name, rows in result.items():
            write_table(output / name, name, rows)


def decode_index(root):
    index = {}
    for name in TABLES:
        with Table(root / name, name) as archive:
            index[name] = list(archive.rows())
    return normalize(index)


def unchecked_bytes(table, records):
    offsets = [0]
    for row in records:
        offsets.append(offsets[-1] + len(row))
    return (HEADER.pack(MAGIC, VERSION, TABLES.index(table), len(records))
            + b"".join(U32.pack(value) for value in offsets) + b"".join(records))


def rejection_checks(root, reference):
    exports = reference["exports"]
    single = encode_row("exports", exports[0])
    other = encode_row("exports", exports[1])
    module = encode_row("modules", reference["modules"][0])
    reversed_members = module[:-64] + module[-32:] + module[-64:-32]
    dependency = encode_row("dependencies", reference["dependencies"][0])
    bool_byte = 32 + 2 + len(reference["dependencies"][0]["edge_id"].encode("utf-8")) + 1 + 32
    bad_bool = dependency[:bool_byte] + b"\2" + dependency[bool_byte + 1:]
    valid = unchecked_bytes("exports", [single, other])
    mutations = {
        "wrong-table-tag": ("modules", valid),
        "first-offset-not-zero": ("exports", valid[:HEADER.size] + U32.pack(1) + valid[HEADER.size + U32.size:]),
        "offset-beyond-row-section": (
            "exports", valid[:HEADER.size + U32.size] + U32.pack(len(valid))
            + valid[HEADER.size + 2 * U32.size:]
        ),
        "short-row-body": ("exports", valid[:-1]),
        "untracked-tail-bytes": ("exports", valid + b"X"),
        "duplicate-keys": ("exports", unchecked_bytes("exports", [single, single])),
        "reversed-keys": ("exports", unchecked_bytes("exports", [other, single])),
        "invalid-utf8": ("exports", unchecked_bytes("exports", [b"\x00\x01\xff" + single[3:]])),
        "unsorted-module-members": ("modules", unchecked_bytes("modules", [reversed_members])),
        "bad-dependency-boolean": ("dependencies", unchecked_bytes("dependencies", [bad_bool])),
    }
    for label, (table, data) in mutations.items():
        path = root / label
        path.write_bytes(data)
        try:
            with Table(path, table):
                pass
        except WireError:
            continue
        raise AssertionError((label, "malformed wire was accepted"))

    forbidden = deepcopy(reference)
    forbidden["objects"][0]["size"] += 1
    left, right = root / "conflict-left", root / "conflict-right"
    write_index(left, reference)
    write_index(right, forbidden)
    destination = root / "existing"
    destination.write_bytes(b"preserved publication")
    try:
        with Table(left / "objects", "objects") as first, Table(right / "objects", "objects") as second:
            streams = [{name: () for name in TABLES} for _ in range(2)]
            streams[0]["objects"] = first.rows()
            streams[1]["objects"] = second.rows()
            write_table(destination, "objects", merge_sorted_indexes(streams)["objects"])
    except LogicalError:
        if destination.read_bytes() != b"preserved publication":
            raise AssertionError("Failed merge changed the destination")
    else:
        raise AssertionError("Conflicting records merged cleanly")
    return {"malformed_tables_refused": sorted(mutations), "conflicting_merge_preserved_destination": True}


def observe(work):
    empties = work / "empty"
    empty_index = {name: [] for name in TABLES}
    write_index(empties, empty_index)
    if decode_index(empties) != empty_index:
        raise AssertionError("An empty table changed the logical index")
    with Table(empties / "modules", "modules") as empty:
        assert empty.lookup(("none",)) == (None, 0)
    indexes = (provider(range(4)), provider(range(2, 6)), provider(range(4, 8)))
    reference = merge(*indexes)
    paths = tuple(work / f"source-{index}" for index in range(len(indexes)))
    for path, index in zip(paths, indexes, strict=True):
        write_index(path, index)
        if decode_index(path) != index:
            raise AssertionError("Binary round trip differs from the logical input")
    identities = set()
    bytes_by_table = {}
    maximum = {}
    query_count = 0
    missing = {"objects": (b"\xff" * 32,), "dependencies": (reference["objects"][0]["hash"], "none"),
               "exports": (MODULES[0], "does-not-exist"), "modules": ("zzz",)}
    for order, permutation in enumerate(permutations(paths)):
        destination = work / f"merge-{order}"
        merge_archives(destination, permutation)
        if decode_index(destination) != reference:
            raise AssertionError("Streamed binary merge differs from logical oracle")
        identities.add(tuple(sha256((destination / table).read_bytes()).hexdigest() for table in TABLES))
        for name, rows in reference.items():
            with Table(destination / name, name) as table:
                queries = [(key(name, row), row) for row in rows] + [(missing[name], None)]
                comparison = [table.lookup(target) for target, _ in queries]
                if [cell for cell, _ in comparison] != [expected for _, expected in queries]:
                    raise AssertionError("Binary lookup differs from the independent inventory")
                checked_maximum = max(probes for _, probes in comparison)
                if checked_maximum > len(rows).bit_length():
                    raise AssertionError((name, checked_maximum))
                maximum[name] = checked_maximum
                query_count += len(queries)
            bytes_by_table[name] = {
                "binary": (destination / name).stat().st_size,
                "compact_jsonl": sum(len(_canonical(row)) + 1 for row in rows),
                "rows": len(rows),
            }
    if len(identities) != 1:
        raise AssertionError("Input permutations changed physical bytes")
    sources = (HERE / "run.py", HERE / "tables.py", PROTOTYPE / "package_index.py")
    return {
        "empty_tables_round_trip": len(TABLES),
        "input_providers": len(paths),
        "input_permutations": 6,
        "lookup_observations": query_count,
        "max_decoded_rows_per_lookup": maximum,
        "logical_index_sha256": logical_hash(reference),
        "binary_table_sha256": dict(zip(TABLES, identities.pop(), strict=True)),
        "table_sizes": bytes_by_table,
        "negative": rejection_checks(work, reference),
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in sources},
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-binary-index-") as scratch:
        print(json.dumps(observe(Path(scratch)), indent=2))
