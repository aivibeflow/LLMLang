#!/usr/bin/env python3
"""Check canonical typed bytes at the immutable storage boundary."""

from contextlib import closing
import json
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WIRE_PATH = HERE.parents[2] / "semantic-representation/RT-05/CANONICAL-WIRE-01/run.py"
WIRE = runpy.run_path(str(WIRE_PATH))
CAS = runpy.run_path(str(HERE.parent / "IMMUTABLE-INSERTION-01/run.py"))
compact = WIRE["compact"]
digest = WIRE["hash_bytes"]


class Refusal(ValueError):
    pass


def typed(raw, domain, claim, *, algorithm="sha256"):
    if type(claim) is not str:
        raise Refusal("address")
    if domain not in WIRE["DOMAINS"]:
        raise Refusal("domain")
    request = WIRE["frame"]("storage", raw, (), domain=domain, claim=claim, algorithm=algorithm)
    strict, _, _ = WIRE["python_status"](request)
    if strict != "accept":
        raise Refusal(strict)
    return claim


def wrapper(raw, domain, version):
    if type(version) is not int:
        raise Refusal("unsupported storage envelope")
    address = typed(raw, domain, digest(raw))
    if version == 1:
        return compact(["llmlang.fixture-store/1", domain, address, raw.hex()])
    if version == 2:
        return compact(["llmlang.fixture-store/2", domain, address, len(raw), raw.hex()])
    raise Refusal("unsupported storage envelope")


def unwrap(payload, domain, version):
    try:
        fields = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise Refusal("malformed storage envelope") from error
    if type(version) is not int or version not in (1, 2):
        raise Refusal("unsupported storage envelope")
    max_fields = 4 if version == 1 else 5
    if (type(fields) is not list or len(fields) != max_fields
            or fields[0] != f"llmlang.fixture-store/{version}" or fields[1] != domain
            or type(fields[-1]) is not str):
        raise Refusal("storage scope mismatch")
    try:
        raw = bytes.fromhex(fields[-1])
    except ValueError as error:
        raise Refusal("invalid stored bytes") from error
    typed(raw, domain, fields[2])
    if wrapper(raw, domain, version) != payload:
        raise Refusal("noncanonical storage envelope")
    return raw


class Store:
    def __init__(self, root):
        self.root = root
        self.objects = root / "cas"
        self.objects.mkdir()
        self.catalog = root / "catalog.db"
        with closing(sqlite3.connect(self.catalog)) as connection:
            connection.executescript("""
                CREATE TABLE addresses (address TEXT PRIMARY KEY, domain TEXT NOT NULL,
                    version INTEGER NOT NULL);
                CREATE TABLE refs (name TEXT PRIMARY KEY, address TEXT NOT NULL);
            """)

    def ingest(self, raw, domain, version, claimed):
        typed(raw, domain, claimed)
        payload = wrapper(raw, domain, version)
        address = digest(payload)
        result = CAS["insert"](self.objects, address, payload)
        if result not in ("already-exact", "published"):
            raise Refusal(result)
        with closing(sqlite3.connect(self.catalog)) as connection, connection:
            connection.execute("INSERT OR IGNORE INTO addresses VALUES (?, ?, ?)", (address, domain, version))
        return address, result

    def read(self, address, domain, versions):
        with closing(sqlite3.connect(self.catalog)) as connection:
            scope = connection.execute("SELECT domain, version FROM addresses WHERE address = ?",
                                       (address,)).fetchone()
        if scope is None or scope[0] != domain:
            raise Refusal("unknown exact address or domain")
        version = scope[1]
        if version not in versions:
            raise Refusal("reader format unsupported")
        raw = (self.objects / address).read_bytes()
        if digest(raw) != address:
            raise Refusal("corrupt exact address")
        return unwrap(raw, domain, version)

    def set_ref(self, name, expected, replacement, domain):
        self.read(replacement, domain, {1, 2})
        with closing(sqlite3.connect(self.catalog, isolation_level=None)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT address FROM refs WHERE name = ?", (name,)).fetchone()
            if (None if current is None else current[0]) != expected:
                raise Refusal("stale reference")
            connection.execute(
                "INSERT INTO refs VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET address=excluded.address",
                (name, replacement),
            )
            connection.commit()


def experiment(root):
    store = Store(root)
    controls = WIRE["controls"]()
    node = subprocess.run(["node", WIRE_PATH.with_name("decode.mjs")],
                          input=json.dumps(controls), capture_output=True, check=True, text=True)
    node_results = json.loads(node.stdout)
    classifications = []
    for case, statuses in zip(controls, node_results, strict=True):
        python = WIRE["python_status"](case)
        assert python == tuple(statuses) == case["expected"]
        if case["algorithm"] == "sha256":
            try:
                committed, disposition = store.ingest(
                    bytes.fromhex(case["raw_hex"]), case["expected_domain"], 1, case["digest"]
                )
            except Refusal as error:
                result = str(error)
            else:
                assert disposition in {"published", "already-exact"}
                assert store.read(committed, case["expected_domain"], {1}) == bytes.fromhex(case["raw_hex"])
                result = "accept"
        else:
            try:
                typed(bytes.fromhex(case["raw_hex"]), case["expected_domain"], case["digest"],
                      algorithm=case["algorithm"])
            except Refusal as error:
                result = str(error)
            else:
                raise AssertionError("unsupported address algorithm admitted")
        assert result == python[0]
        classifications.append({"case": case["name"], "decision": result})

    domain = "operation"
    operation = compact([WIRE["PROFILE"], domain, ["text", "archive"]])
    next_operation = compact([WIRE["PROFILE"], domain, ["text", "changed"]])
    first, first_state = store.ingest(operation, domain, 1, digest(operation))
    assert first_state == "published"
    assert store.ingest(operation, domain, 1, digest(operation)) == (first, "already-exact")
    second, second_state = store.ingest(operation, domain, 2, digest(operation))
    assert second_state == "published" and first != second
    third, third_state = store.ingest(next_operation, domain, 2, digest(next_operation))
    assert third_state == "published"
    assert store.read(first, domain, {1}) == store.read(second, domain, {2}) == operation
    store.set_ref("entry", None, first, domain)
    store.set_ref("entry", first, second, domain)
    store.set_ref("entry", second, third, domain)
    assert store.read(first, domain, {1}) == operation and store.read(third, domain, {2}) == next_operation

    exercises = []

    def refuse(label, reason, function):
        try:
            function()
        except Refusal as error:
            assert str(error) == reason
        else:
            raise AssertionError(label)
        exercises.append({"case": label, "decision": reason})

    refuse("v1 reader addresses v2 object", "reader format unsupported", lambda: store.read(second, domain, {1}))
    refuse("wrong read domain", "unknown exact address or domain", lambda: store.read(second, "contract", {2}))
    refuse("stale reference update", "stale reference", lambda: store.set_ref("entry", first, second, domain))
    refuse("new storage format is unrecognized", "unsupported storage envelope",
           lambda: store.ingest(operation, domain, 3, digest(operation)))
    refuse("Boolean storage version", "unsupported storage envelope",
           lambda: store.ingest(operation, domain, True, digest(operation)))
    envelope = json.loads(wrapper(operation, domain, 2))
    envelope[2] = 17
    refuse("non-string inner address", "address",
           lambda: unwrap(compact(envelope), domain, 2))
    envelope[2] = digest(operation)
    envelope[3] += 1
    refuse("transport length is false", "noncanonical storage envelope", lambda: unwrap(compact(envelope), domain, 2))

    corrupt = store.objects / first
    corrupt.write_bytes(b"damaged fixture output")
    refuse("old address bytes changed", "corrupt exact address", lambda: store.read(first, domain, {1}))
    refuse("ordinary repeat cannot overwrite damage", "occupied-invalid",
           lambda: store.ingest(operation, domain, 1, digest(operation)))
    assert corrupt.read_bytes() == b"damaged fixture output"
    assert store.read(second, domain, {2}) == operation and store.read(third, domain, {2}) == next_operation
    with closing(sqlite3.connect(store.catalog)) as connection:
        assert connection.execute("SELECT address FROM refs WHERE name='entry'").fetchone() == (third,)
    return {
        "format": "typed-object-lifecycle-01",
        "sqlite": sqlite3.sqlite_version,
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "typed_controls": classifications,
        "lifecycle_refusals": exercises,
        "v1_object": first, "v2_same_inner_object": second, "v2_new_inner_object": third,
        "common_typed_identity": digest(operation),
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-typed-store-") as work:
        evidence = experiment(Path(work))
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
