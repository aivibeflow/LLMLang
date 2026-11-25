"""Check exact-byte admission and interruption around a filesystem CAS insert."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Barrier


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(store, address, expected):
    try:
        raw = (store / address).read_bytes()
    except FileNotFoundError:
        return "absent"
    return "exact" if raw == expected and digest(raw) == address else "invalid"


def stage(store, data):
    with NamedTemporaryFile(dir=store, prefix=".staged-", delete=False) as writer:
        writer.write(data)
        return Path(writer.name)


def publish(store, address, staged, expected):
    if digest(expected) != address or staged.read_bytes() != expected:
        return "input-mismatch"
    try:
        os.link(staged, store / address)
    except FileExistsError:
        return "already-exact" if read(store, address, expected) == "exact" else "occupied-invalid"
    return "published"


def insert(store, address, data, rendezvous=None):
    staged = stage(store, data)
    try:
        if rendezvous is not None:
            rendezvous.wait(timeout=10)
        return publish(store, address, staged, data)
    finally:
        staged.unlink()


def interrupt(store, address, data, phase):
    if phase == "direct-partial":
        with open(store / address, "wb", buffering=0) as writer:
            writer.write(data[: len(data) // 2])
            os._exit(42)
    staged = stage(store, data)
    if phase == "linked":
        assert publish(store, address, staged, data) == "published"
    else:
        assert phase == "staged"
    os._exit(42)


def check_interruption(root, phase, address, payload):
    store = root / phase
    store.mkdir()
    # Direct rewrite is tested against a verified existing object.
    if phase == "direct-partial":
        assert insert(store, address, payload) == "published"
    child = subprocess.run(
        [sys.executable, __file__, phase, str(store), address, payload.hex()],
        timeout=10,
        check=False,
    )
    assert child.returncode == 42
    before = read(store, address, payload)
    leftover = list(store.glob(".staged-*"))
    retry = insert(store, address, payload)
    for staged in leftover:
        staged.unlink()
    return {
        "immediately_after_exit": before,
        "staged_after_exit": len(leftover),
        "retry": retry,
        "after_retry_and_staging_cleanup": read(store, address, payload),
    }


def study(root):
    store = root / "objects"
    store.mkdir()
    fixture = {"kind": "contract", "name": "élément", "args": [1, 2]}
    payload = encode(fixture)
    reversed_keys = dict(reversed(list(fixture.items())))
    alternate_bytes = json.dumps(reversed_keys, ensure_ascii=True).encode()
    address = digest(payload)
    assert encode(reversed_keys) == payload
    assert json.loads(alternate_bytes) == fixture and alternate_bytes != payload
    assert digest(alternate_bytes) != address

    assert insert(store, address, alternate_bytes) == "input-mismatch"
    assert read(store, address, payload) == "absent"
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(insert, store, address, payload, barrier)
        second = pool.submit(insert, store, address, payload, barrier)
        writers = sorted([first.result(), second.result()])
    assert writers == ["already-exact", "published"]
    assert read(store, address, payload) == "exact"
    inode = (store / address).stat().st_ino
    assert insert(store, address, payload) == "already-exact"
    assert (store / address).stat().st_ino == inode
    assert not list(store.glob(".staged-*"))

    revised = encode(fixture | {"args": [2, 1]})
    revised_address = digest(revised)
    assert revised_address != address
    assert insert(store, revised_address, revised) == "published"
    assert read(store, address, payload) == read(store, revised_address, revised) == "exact"

    interruptions = {
        phase: check_interruption(root, phase, address, payload)
        for phase in ("staged", "linked", "direct-partial")
    }
    observations = (
        "immediately_after_exit",
        "staged_after_exit",
        "retry",
        "after_retry_and_staging_cleanup",
    )
    for phase, expected in {
        "staged": ("absent", 1, "published", "exact"),
        "linked": ("exact", 1, "already-exact", "exact"),
        "direct-partial": ("invalid", 0, "occupied-invalid", "invalid"),
    }.items():
        assert tuple(interruptions[phase][key] for key in observations) == expected
    return {
        "runtime": platform.python_version(),
        "canonical_address": address,
        "equal_decoded_noncanonical_address": digest(alternate_bytes),
        "equal_decoded_noncanonical_under_canonical_address": "input-mismatch",
        "duplicate_writers": writers,
        "duplicate_retry_preserves_inode": True,
        "revised_address": revised_address,
        "old_and_revised_read_exact": True,
        "interruptions": interruptions,
    }


if __name__ == "__main__":
    if len(sys.argv) == 1:
        with TemporaryDirectory() as temporary:
            print(json.dumps(study(Path(temporary)), indent=2, sort_keys=True))
    else:
        _, phase, store, address, encoded = sys.argv
        interrupt(Path(store), address, bytes.fromhex(encoded), phase)
