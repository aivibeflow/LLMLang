"""Invoke a bound artifact in a pinned, preauthorized fixture Snapshot."""
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess


# Linux UAPI constants for CPython builds that omit the sealing definitions.
ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
REQUIRED_SEALS = (
    getattr(fcntl, "F_SEAL_SEAL", 0x0001)
    | getattr(fcntl, "F_SEAL_SHRINK", 0x0002)
    | getattr(fcntl, "F_SEAL_GROW", 0x0004)
    | getattr(fcntl, "F_SEAL_WRITE", 0x0008)
)


def canonical_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Binding:
    snapshot: str
    function: str
    contract: str
    artifact: str


def resolve(catalog, bound, root, contract):
    if canonical_digest(catalog) != root:
        raise ValueError("snapshot-digest")
    if bound.snapshot != root or bound.contract != contract:
        raise ValueError("binding-scope")
    entry = catalog.get(bound.function)
    if entry is None or entry["contract"] != contract:
        raise ValueError("function-selection")
    if bound.artifact != entry["artifact"]:
        raise ValueError("artifact-selection")
    return entry["artifact"]


def invoke(store: Path, catalog, bound, root, contract, argument):
    digest = resolve(catalog, bound, root, contract)
    if len(digest) != 64 or not set(digest) <= set("0123456789abcdef"):
        raise ValueError("artifact-name")
    try:
        selected = (store / digest).read_bytes()
    except FileNotFoundError:
        raise ValueError("artifact-unavailable") from None
    if sha256(selected).hexdigest() != digest:
        raise ValueError("artifact-digest")
    descriptor = os.memfd_create("llmlang-bound-test", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    with os.fdopen(descriptor, "wb") as image:
        image.write(selected)
        image.flush()
        fcntl.fcntl(descriptor, ADD_SEALS, REQUIRED_SEALS)
        if fcntl.fcntl(descriptor, GET_SEALS) & REQUIRED_SEALS != REQUIRED_SEALS:
            raise ValueError("artifact-seals")
        process = subprocess.run([f"/proc/self/fd/{descriptor}", str(argument)],
                                 pass_fds=(descriptor,), env={"LC_ALL": "C"},
                                 capture_output=True, check=True, text=True, timeout=10)
    return int(process.stdout)
