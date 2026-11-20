"""Reproducible resource benchmark for the disk-backed package provider.

Run from this directory:
  PYTHONPATH=../PACKAGE-IDENTITY-01 python benchmark_package_provider.py --sizes 1000 5000

Each measurement runs in a fresh subprocess so ru_maxrss is per case. Results
are exploratory measurements, not performance guarantees or CI thresholds.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from package_archive import verify_archive
from package_identity import logical_index_hash, package_content_root, parse_manifest
from package_index import normalize
from package_provider import build_archive_from_snapshot


class SyntheticSnapshot:
    def __init__(self, size: int, shape: str):
        self.snapshot_id = f"synthetic-{shape}-{size}"
        self.payloads = [f"llmlang-object-{i}".encode() for i in range(size)]
        self.hashes = ["sha256:" + hashlib.sha256(payload).hexdigest()
                       for payload in self.payloads]
        self.payload_by_hash = dict(zip(self.hashes, self.payloads))
        self.objects = {
            h: {"hash": h, "kind": "function", "size": len(payload)}
            for h, payload in zip(self.hashes, self.payloads)
        }
        self.edges: dict[str, list[dict[str, str]]] = {h: [] for h in self.hashes}
        adjacency: list[list[int]] = [[] for _ in range(size)]

        if shape == "chain":
            for i in range(size - 1):
                adjacency[i].append(i + 1)
        elif shape == "fanout":
            adjacency[0].extend(range(1, size))
        elif shape == "diamond":
            for base in range(0, size - 3, 4):
                left, right, join = base + 1, base + 2, base + 3
                adjacency[base].extend((left, right))
                adjacency[left].append(join)
                adjacency[right].append(join)
                if base + 4 < size:
                    adjacency[join].append(base + 4)
            last = max(0, size - 4)
            for i in range(last, size - 1):
                if not adjacency[i]:
                    adjacency[i].append(i + 1)
        elif shape == "many-dependencies":
            degree = min(16, max(0, size - 1))
            for i in range(size):
                adjacency[i].extend(range(i + 1, min(size, i + degree + 1)))
        else:
            raise ValueError(f"unknown graph shape: {shape}")

        for source, targets in enumerate(adjacency):
            self.edges[self.hashes[source]] = [
                {"edge_id": f"edge-{target}", "kind": "required",
                 "target_hash": self.hashes[target]}
                for target in targets
            ]
        self.edge_count = sum(map(len, adjacency))

    def get_object(self, content_hash):
        return self.objects[content_hash]

    def get_dependencies(self, source_hash):
        return self.edges[source_hash]

    def open_object(self, content_hash):
        return io.BytesIO(self.payload_by_hash[content_hash])


def make_manifest(snapshot: SyntheticSnapshot) -> bytes:
    index = normalize({
        "objects": list(snapshot.objects.values()),
        "dependencies": [
            {"source_hash": source, "edge_id": edge["edge_id"],
             "kind": edge["kind"], "target_hash": edge["target_hash"],
             "included": True}
            for source in snapshot.hashes for edge in snapshot.edges[source]
        ],
        "exports": [], "modules": [],
    })
    raw = f'''format = "llmlang.package"
schema_version = 1

[package]
name = "provider-benchmark"

[content]
roots = ["{snapshot.hashes[0]}"]
dependency_policy = "closure"
content_root = "sha256:{"0" * 64}"

[index]
path = "index"
format_version = 1
logical_hash = "{logical_index_hash(index)}"
'''.encode()
    root = package_content_root(parse_manifest(raw), index)
    return raw.replace(("sha256:" + "0" * 64).encode(), root.encode())


def directory_size(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except FileNotFoundError:
                pass
    return total


def run_case(shape: str, size: int) -> dict:
    case_started = time.perf_counter()
    preparation_started = time.perf_counter()
    snapshot = SyntheticSnapshot(size, shape)
    manifest = make_manifest(snapshot)
    preparation_seconds = time.perf_counter() - preparation_started
    peak_temp_bytes = 0
    original_tempdir = tempfile.TemporaryDirectory

    class TrackedTemporaryDirectory:
        def __init__(self, *args, **kwargs):
            self.inner = original_tempdir(*args, **kwargs)

        def __enter__(self):
            return self.inner.__enter__()

        def __exit__(self, exc_type, exc, tb):
            nonlocal peak_temp_bytes
            peak_temp_bytes = max(peak_temp_bytes, directory_size(self.inner.name))
            return self.inner.__exit__(exc_type, exc, tb)

    with original_tempdir(prefix="llmlang-provider-benchmark-output-") as out:
        archive = os.path.join(out, "package.llpkg")
        tempfile.TemporaryDirectory = TrackedTemporaryDirectory
        tracemalloc.start()
        started = time.perf_counter()
        try:
            build_archive_from_snapshot(
                [snapshot.hashes[0]], snapshot, manifest, archive,
                policy="closure", max_records_in_memory=1024, sqlite_cache_kib=4096,
            )
            build_seconds = time.perf_counter() - started
            _, peak_python_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            tempfile.TemporaryDirectory = original_tempdir
        verification_started = time.perf_counter()
        if not verify_archive(archive):
            raise RuntimeError("provider produced an archive that failed verification")
        verification_seconds = time.perf_counter() - verification_started
        archive_bytes = os.path.getsize(archive)

    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_bytes = int(peak_rss if platform.system() == "Darwin" else peak_rss * 1024)
    total_worker_seconds = time.perf_counter() - case_started
    return {
        "shape": shape,
        "objects": size,
        "dependency_edges": snapshot.edge_count,
        "preparation_seconds": round(preparation_seconds, 6),
        "provider_build_seconds": round(build_seconds, 6),
        "archive_verification_seconds": round(verification_seconds, 6),
        "total_worker_seconds": round(total_worker_seconds, 6),
        "provider_objects_per_second": round(size / build_seconds, 2) if build_seconds else None,
        "manifest_bytes": len(manifest),
        "peak_traced_python_bytes": peak_python_bytes,
        "process_peak_rss_bytes": peak_rss_bytes,
        "peak_provider_tempdir_bytes": peak_temp_bytes,
        "archive_bytes": archive_bytes,
        "verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[1000, 5000])
    parser.add_argument("--shapes", nargs="+",
                        default=["chain", "diamond", "fanout", "many-dependencies"])
    parser.add_argument("--worker", nargs=2, metavar=("SHAPE", "SIZE"))
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(run_case(args.worker[0], int(args.worker[1])), sort_keys=True))
        return
    if any(size < 1 for size in args.sizes):
        parser.error("sizes must be positive")

    results = []
    for shape in args.shapes:
        for size in args.sizes:
            process_started = time.perf_counter()
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()),
                 "--worker", shape, str(size)],
                check=True, capture_output=True, text=True,
            )
            process_wall_seconds = time.perf_counter() - process_started
            result = json.loads(completed.stdout)
            result["subprocess_wall_seconds"] = round(process_wall_seconds, 6)
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    print(json.dumps({"benchmark": "disk-backed-provider", "cases": len(results)}))


if __name__ == "__main__":
    main()
