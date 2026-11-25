#!/usr/bin/env python3
"""Check scoped native-runtime authority using only temporary fixture descriptors."""

from dataclasses import asdict, dataclass, replace
import errno
import fcntl
import hmac
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread


class Refusal(ValueError):
    pass


@dataclass(frozen=True)
class Grant:
    actor: str
    resource: str
    operation: str
    epoch: int
    runtime: str


def signature(key, grant):
    payload = json.dumps(asdict(grant), sort_keys=True, separators=(",", ":")).encode()
    return hmac.digest(key, payload, "sha256")


def file_identity(fd):
    record = os.fstat(fd)
    return (record.st_dev, record.st_ino)


class Broker:
    def __init__(self, key, descriptors):
        self.key = key
        self.epoch = 1
        self.runtime = "fixture-runtime/1"
        self.registry = {name: (fd, file_identity(fd)) for name, fd in descriptors.items()}
        self.gate = Lock()

    def revoke(self):
        with self.gate:
            self.epoch += 1

    def effect(self, grant, supplied, *, actor, resource, operation):
        if not hmac.compare_digest(signature(self.key, grant), supplied):
            raise Refusal("bad-grant")
        if (grant.actor, grant.resource, grant.operation, grant.runtime) != (
            actor, resource, operation, self.runtime
        ):
            raise Refusal("wrong-authority-scope")
        with self.gate:
            if grant.epoch != self.epoch:
                raise Refusal("stale-grant")
            fd, original = self.registry[resource]
            if file_identity(fd) != original:
                raise Refusal("wrong-native-object")
            mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
            if operation == "read":
                if mode == os.O_WRONLY:
                    raise Refusal("native-right-insufficient")
                return os.pread(fd, 1, 0).decode()
            if operation == "write":
                if mode == os.O_RDONLY:
                    raise Refusal("native-right-insufficient")
                return os.pwrite(fd, b"R", 0)
            raise Refusal("unsupported-operation")


def experiment(work):
    first = work / "first"
    second = work / "second"
    replacement = work / "replacement"
    first.write_bytes(b"A")
    second.write_bytes(b"B")
    replacement.write_bytes(b"C")
    # Only synthetic data and a temporary test authority ever enter the broker.
    fd = os.open(first, os.O_RDONLY)
    writer = os.open(second, os.O_WRONLY)
    original_copy = os.dup(fd)
    authority = os.urandom(32)
    broker = Broker(authority, {"first": fd, "second": writer})
    base = Grant("actor-A", "first", "read", 1, broker.runtime)
    signed = signature(authority, base)
    rows = []

    def effect(grant=base, signed_value=signed, **scope):
        return broker.effect(grant, signed_value, **({"actor": "actor-A", "resource": "first",
                                                      "operation": "read"} | scope))

    def decision(label, expected, callback):
        try:
            result = callback()
        except Refusal as error:
            result = str(error)
        assert result == expected, (label, result)
        rows.append({"case": label, "result": result})

    try:
        decision("exact read permission", "A", effect)
        decision("invalid grant integrity", "bad-grant", lambda: effect(signed_value=bytes(32)))
        decision("altered actor inside signed grant", "bad-grant",
                 lambda: effect(replace(base, actor="actor-B")))
        decision("wrong external actor", "wrong-authority-scope", lambda: effect(actor="actor-B"))
        decision("wrong requested resource", "wrong-authority-scope", lambda: effect(resource="second"))
        decision("permission cannot amplify from read to write", "wrong-authority-scope",
                 lambda: effect(operation="write"))
        profile = replace(base, runtime="fixture-runtime/other")
        decision("wrong runtime profile", "wrong-authority-scope",
                 lambda: effect(profile, signature(authority, profile)))
        read_only_write = replace(base, operation="write")
        decision("grant cannot write through a read-only descriptor", "native-right-insufficient",
                 lambda: effect(read_only_write, signature(authority, read_only_write), operation="write"))
        try:
            os.pwrite(original_copy, b"Z", 0)
        except OSError as error:
            assert error.errno == errno.EBADF
            rows.append({"case": "native read-only right", "result": "EBADF"})
        else:
            raise AssertionError("write to read-only fixture")

        valid_write = replace(base, resource="second", operation="write")
        decision("exact mediated write", 1, lambda: effect(
            valid_write, signature(authority, valid_write), resource="second", operation="write"))
        assert second.read_bytes() == b"R" and first.read_bytes() == b"A"
        wrong_direction = replace(base, resource="second")
        decision("write-only descriptor refuses reading", "native-right-insufficient",
                 lambda: effect(wrong_direction, signature(authority, wrong_direction), resource="second"))

        waiting = Event()
        resume = Event()
        result = []

        def worker():
            waiting.set()
            if not resume.wait(timeout=5):
                return
            try:
                result.append(effect())
            except Refusal as error:
                result.append(str(error))

        child = Thread(target=worker)
        child.start()
        assert waiting.wait(timeout=5)
        broker.revoke()
        resume.set()
        child.join(timeout=5)
        assert not child.is_alive() and result == ["stale-grant"]
        rows.append({"case": "submit after scheduled revocation", "result": result[0]})
        assert os.pread(original_copy, 1, 0) == b"A"
        rows.append({"case": "already transferred raw descriptor keeps kernel lifetime", "result": "A"})

        refreshed = replace(base, epoch=2)
        decision("current grant after explicit reissue", "A",
                 lambda: effect(refreshed, signature(authority, refreshed)))
        moved = os.open(replacement, os.O_RDONLY)
        try:
            # Reuse a number owned by this process to exercise the identity guard.
            os.dup2(moved, fd)
            decision("descriptor number is reused for a different fixture file", "wrong-native-object",
                     lambda: effect(refreshed, signature(authority, refreshed)))
        finally:
            os.close(moved)
    finally:
        for owned in (fd, writer, original_copy):
            os.close(owned)
    assert replacement.read_bytes() == b"C"
    return {"format": "mediated-descriptors-01", "host": os.uname().machine, "rows": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-mediated-descriptors-") as directory:
        evidence = experiment(Path(directory))
    out = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(out, encoding="utf-8")
    else:
        print(out, end="")
