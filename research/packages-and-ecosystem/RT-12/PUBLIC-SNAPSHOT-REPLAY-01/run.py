"""Verify the public Provider protocol against a pinned SQLite WAL snapshot."""

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-INDEX-01"
IDENTITY = PROTOTYPE.with_name("PACKAGE-IDENTITY-01")
sys.path[:0] = [str(PROTOTYPE), str(IDENTITY)]
from content_store import SQLiteContentStore, SnapshotClosed, content_hash
from package_archive import verify_archive
from package_provider import ProviderError, build_archive_from_snapshot
from test_content_store import make_manifest


ROOT_PAYLOAD = bytes(range(256)) * 8200
TARGET_PAYLOAD = b"bound target payload"
APPEND_PAYLOAD = b"unrelated object written while the stream is open"
EXISTING = b"existing publication"
ROOT_HASH = content_hash(ROOT_PAYLOAD)
TARGET_HASH = content_hash(TARGET_PAYLOAD)
APPENDED_HASH = content_hash(APPEND_PAYLOAD)
EDGES = tuple({"edge_id": f"call-{index:03}", "kind": "required", "target_hash": TARGET_HASH}
              for index in range(131))
PAYLOADS = {ROOT_HASH: ROOT_PAYLOAD, TARGET_HASH: TARGET_PAYLOAD}
OBJECTS = {key: {"hash": key, "kind": "function", "size": len(value)}
           for key, value in PAYLOADS.items()}


class MemorySnapshot:
    snapshot_id = "memory-fixture"

    def get_object(self, exact_hash):
        return OBJECTS[exact_hash]

    def get_dependencies(self, source_hash):
        return iter(EDGES if source_hash == ROOT_HASH else ())

    def open_object(self, exact_hash):
        return BytesIO(PAYLOADS[exact_hash])


class Stream:
    def __init__(self, delegate, audit, after_first):
        self.delegate = delegate
        self.audit = audit
        self.after_first = after_first

    def read(self, limit):
        if not 0 < limit <= 1024 * 1024:
            raise AssertionError(("read outside streaming bound", limit))
        payload = self.delegate.read(limit)
        self.audit["stream_reads"] += 1
        self.audit["bytes_read"] += len(payload)
        self.audit["largest_read_returned"] = max(self.audit["largest_read_returned"], len(payload))
        if payload and self.after_first is not None:
            notify = self.after_first
            self.after_first = None
            notify()
        return payload

    def close(self):
        self.delegate.close()
        self.audit["streams_closed"] += 1


class PublicSnapshot:
    """Expose only the three required public reads to the Provider."""

    __slots__ = ("__delegate", "audit", "notify")

    def __init__(self, delegate, notify=None):
        self.__delegate = delegate
        self.audit = Counter()
        self.notify = notify

    @property
    def snapshot_id(self):
        return self.__delegate.snapshot_id

    def __getattr__(self, name):
        if name in {"get_exports", "get_modules"}:
            raise AttributeError(name)
        raise AssertionError(("Provider attempted an undeclared snapshot attribute", name))

    def get_object(self, exact_hash):
        self.audit["metadata_reads"] += 1
        return self.__delegate.get_object(exact_hash)

    def get_dependencies(self, source_hash):
        self.audit["dependency_reads"] += 1
        for edge in self.__delegate.get_dependencies(source_hash):
            self.audit["edges_streamed"] += 1
            yield edge

    def open_object(self, exact_hash):
        self.audit["streams_opened"] += 1
        notify = self.notify if exact_hash == ROOT_HASH else None
        return Stream(self.__delegate.open_object(exact_hash), self.audit, notify)


def package(snapshot, manifest, destination):
    return build_archive_from_snapshot([ROOT_HASH], snapshot, manifest, str(destination),
                                       policy="closure", max_records_in_memory=5, sqlite_cache_kib=64)


def missing_object(call):
    try:
        call()
    except KeyError:
        return True
    return False


def verify_output(path):
    if not verify_archive(path, max_records_in_memory=5):
        raise AssertionError("Independent package verifier rejected a published archive")
    with ZipFile(path) as package_file:
        present = {name for name in package_file.namelist() if name.startswith("objects/")}
        expected = {f"objects/{key.split(':', 1)[1]}" for key in PAYLOADS}
        if present != expected:
            raise AssertionError((present, expected))
        for name in present:
            digest = sha256()
            with package_file.open(name) as payload:
                for chunk in iter(lambda: payload.read(131072), b""):
                    digest.update(chunk)
            if name != f"objects/{digest.hexdigest()}":
                raise AssertionError("ZIP payload hash mismatch")
    return sha256(path.read_bytes()).hexdigest()


def verify(work):
    database = work / "store.sqlite"
    store = SQLiteContentStore(database)
    assert store.put_object(ROOT_PAYLOAD, "function", EDGES) == ROOT_HASH
    manifest = make_manifest(ROOT_HASH, list(OBJECTS.values()), [(ROOT_HASH, edge) for edge in EDGES])
    destination = work / "old-output.llpkg"
    destination.write_bytes(EXISTING)
    with store.open_snapshot() as old:
        assert store.put_object(TARGET_PAYLOAD, "function", ()) == TARGET_HASH
        assert missing_object(lambda: old.get_object(TARGET_HASH))
        try:
            package(PublicSnapshot(old), manifest, destination)
        except ProviderError as exc:
            if "missing exact dependency object" not in str(exc):
                raise
        else:
            raise AssertionError("A stale view admitted the missing dependency")
        if destination.read_bytes() != EXISTING:
            raise AssertionError("Rejected publish changed the original file")

    writer_effects = []

    def append_during_read():
        writer = subprocess.run([sys.executable, "-B", str(HERE / "run.py"), "--append", str(database)],
                                check=True, capture_output=True, text=True, timeout=30)
        if writer.stdout.strip() != APPENDED_HASH:
            raise AssertionError(writer.stdout)
        writer_effects.append(writer.stdout.strip())

    with store.open_snapshot() as stable:
        stable_id = stable.snapshot_id
        audited = PublicSnapshot(stable, notify=append_during_read)
        pinned_path = work / "pinned.llpkg"
        package(audited, manifest, pinned_path)
        if writer_effects != [APPENDED_HASH] or stable.snapshot_id != stable_id:
            raise AssertionError("Writer or pinned snapshot identity changed unexpectedly")
        assert missing_object(lambda: stable.get_object(APPENDED_HASH))
        pinned_digest = verify_output(pinned_path)

    try:
        stable.get_object(ROOT_HASH)
    except SnapshotClosed:
        closed_rejects = True
    else:
        raise AssertionError("Post-close metadata read was accepted")
    with store.open_snapshot() as latest:
        if latest.snapshot_id == stable_id or latest.get_object(APPENDED_HASH)["hash"] != APPENDED_HASH:
            raise AssertionError("A new snapshot did not see the committed append")
        latest_path = work / "latest.llpkg"
        latest_public = PublicSnapshot(latest)
        package(latest_public, manifest, latest_path)
        latest_digest = verify_output(latest_path)

    memory_path = work / "memory.llpkg"
    memory = PublicSnapshot(MemorySnapshot())
    package(memory, manifest, memory_path)
    memory_digest = verify_output(memory_path)
    if pinned_digest != latest_digest or latest_digest != memory_digest:
        raise AssertionError("Equivalent closure produced different archive bytes")
    for observed in (audited.audit, latest_public.audit, memory.audit):
        if (observed["edges_streamed"] != len(EDGES) or observed["streams_opened"] != 2
                or observed["streams_closed"] != 2 or observed["bytes_read"] != sum(map(len, PAYLOADS.values()))
                or observed["largest_read_returned"] != 1024 * 1024):
            raise AssertionError(observed)

    sources = (HERE / "run.py", PROTOTYPE / "content_store.py", PROTOTYPE / "package_provider.py",
               PROTOTYPE / "package_archive.py", PROTOTYPE / "package_index.py", PROTOTYPE / "test_content_store.py",
               IDENTITY / "package_identity.py")
    return {
        "sqlite": sqlite3.sqlite_version,
        "missing_dependency_refused_in_old_snapshot": True,
        "existing_destination_preserved": True,
        "writer_committed_during_blob_read": True,
        "old_snapshot_hid_append": True,
        "later_snapshot_observed_append": True,
        "closed_snapshot_refused_new_metadata": closed_rejects,
        "checked_archives": {"pinned": pinned_digest, "latest": latest_digest, "memory": memory_digest},
        "public_api_calls": {"pinned": audited.audit, "latest": latest_public.audit, "memory": memory.audit},
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in sources},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--append", type=Path)
    args = parser.parse_args()
    if args.append is not None:
        print(SQLiteContentStore(args.append).put_object(APPEND_PAYLOAD, "function", ()))
    else:
        with TemporaryDirectory(prefix="llmlang-public-snapshot-") as temp:
            print(json.dumps(verify(Path(temp)), indent=2))
