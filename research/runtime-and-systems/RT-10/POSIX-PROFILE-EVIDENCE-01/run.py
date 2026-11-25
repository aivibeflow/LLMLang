"""Build an exact-scoped conformance catalog from two pinned native receipts."""

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import platform


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "descriptors": (
        "POSIX-EDITION-DESCRIPTORS-01/evidence.json",
        "3c6bf9fb2245f9fd9a78bdbe900a512896c8757a55c68e6eda8822bb011afe11",
    ),
    "cancellation": (
        "LIBC-SYSCALL-CANCELLATION-01/evidence.json",
        "82c0f47f7ebad66ff43bdd33c864aa176722f82d645f9d3433213b39a809497f",
    ),
}


@dataclass(frozen=True)
class Scope:
    kernel: str
    arch: str
    libc_archive: str
    request: str
    entry: str
    condition: str


def decode_pinned(raw, expected):
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("receipt-digest-mismatch")
    return json.loads(raw)


def load(label):
    relative, expected = SOURCES[label]
    return decode_pinned((ROOT / relative).read_bytes(), expected)


def descriptor_scope(evidence, libc, request):
    return Scope(evidence["kernel"], "x86_64", evidence["libc_archives_sha256"][libc],
                 request, "libc", "descriptor-fixture")


def cancellation_scope(evidence, libc, entry):
    return Scope(evidence["kernel"], "x86_64", evidence["libc_archive_sha256"][libc],
                 "gnu_extension", entry, "queued-deferred-cancel-ready-pipe")


def catalog_for(descriptors, cancellation):
    catalog = {}
    for lane, features in descriptors["cases"].items():
        libc, request = lane.split("-", 1)
        scope = descriptor_scope(descriptors, libc, request)
        for feature, verdict in features.items():
            visible = verdict["header"] == "visible"
            catalog[(scope, feature, "header")] = "observed" if visible else "unsupported"
            assert visible == (verdict["runtime"] is not None)
            if visible:
                catalog[(scope, feature, "runtime")] = "observed"
    for libc in cancellation["libc_archive_sha256"]:
        for entry in ("libc", "syscall"):
            scope = cancellation_scope(cancellation, libc, entry)
            exact = cancellation["results"][f"{libc}-O0"][f"{entry}-pending"]
            assert exact == cancellation["results"][f"{libc}-O2"][f"{entry}-pending"]
            assert exact["terminal"] == "cancelled"
            catalog[(scope, "read", "join-cancelled")] = "observed"
            assert exact["leftover"] in ("0", "1")
            catalog[(scope, "read", "byte-retained")] = "observed" if exact["leftover"] == "1" else "contradicted"
    return catalog


def study():
    descriptors = load("descriptors")
    cancellation = load("cancellation")
    assert descriptors["libc_archives_sha256"] == cancellation["libc_archive_sha256"]
    catalog = catalog_for(descriptors, cancellation)
    glibc_issue8 = descriptor_scope(descriptors, "glibc", "issue8_request")
    musl_issue8 = descriptor_scope(descriptors, "musl", "issue8_request")
    glibc_gnu = descriptor_scope(descriptors, "glibc", "gnu_extension")
    libc_read = cancellation_scope(cancellation, "glibc", "libc")
    raw_read = cancellation_scope(cancellation, "glibc", "syscall")
    controls = {
        "older_version_baseline_under_new_request": (glibc_issue8, "base", "runtime", "observed"),
        "glibc_posix_macro_pipe2_header": (glibc_issue8, "pipe2", "header", "unsupported"),
        "glibc_posix_macro_pipe2_runtime": (glibc_issue8, "pipe2", "runtime", "unknown"),
        "glibc_gnu_pipe2_runtime": (glibc_gnu, "pipe2", "runtime", "observed"),
        "musl_posix_macro_pipe2_runtime": (musl_issue8, "pipe2", "runtime", "observed"),
        "musl_close_on_fork_header": (musl_issue8, "clofork", "header", "unsupported"),
        "musl_close_on_fork_runtime": (musl_issue8, "clofork", "runtime", "unknown"),
        "glibc_posix_full_edition": (glibc_issue8, "POSIX.1-2024", "runtime", "unknown"),
        "different_kernel": (replace(glibc_gnu, kernel="different"), "pipe2", "runtime", "unknown"),
        "different_architecture": (replace(glibc_gnu, arch="aarch64"), "pipe2", "runtime", "unknown"),
        "different_archive": (replace(musl_issue8, libc_archive="different"), "pipe2", "runtime", "unknown"),
        "libc_join": (libc_read, "read", "join-cancelled", "observed"),
        "raw_join": (raw_read, "read", "join-cancelled", "observed"),
        "libc_stream": (libc_read, "read", "byte-retained", "observed"),
        "raw_stream": (raw_read, "read", "byte-retained", "contradicted"),
        "blocking_read": (replace(libc_read, condition="blocked-read"), "read", "byte-retained", "unknown"),
    }
    results = {}
    for name, (scope, operation, observation, expected) in controls.items():
        outcome = catalog.get((scope, operation, observation), "unknown")
        assert outcome == expected, (name, outcome)
        results[name] = outcome
    path, expected = SOURCES["descriptors"]
    try:
        decode_pinned((ROOT / path).read_bytes() + b" ", expected)
    except ValueError as error:
        assert str(error) == "receipt-digest-mismatch"
    else:
        raise AssertionError("changed receipt passed exact pin")
    results["changed_receipt_bytes"] = "receipt-digest-mismatch"
    return {
        "python": platform.python_version(),
        "sources": SOURCES,
        "catalog_entries": len(catalog),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
