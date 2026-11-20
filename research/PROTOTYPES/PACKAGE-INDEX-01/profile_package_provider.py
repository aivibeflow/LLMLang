"""Profile one disk-backed Provider build without profiling snapshot setup or verification.

Run from this directory:
  PYTHONPATH=../PACKAGE-IDENTITY-01 python profile_package_provider.py --shape many-dependencies --size 5000
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import tempfile
import time
from pathlib import Path

from benchmark_package_provider import SyntheticSnapshot, make_manifest
from package_provider import build_archive_from_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shape", default="many-dependencies")
    parser.add_argument("--size", type=int, default=5000)
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()
    if args.size < 1 or args.top < 1:
        parser.error("size and top must be positive")

    snapshot = SyntheticSnapshot(args.size, args.shape)
    manifest = make_manifest(snapshot)
    profiler = cProfile.Profile()
    archive_bytes = None
    with tempfile.TemporaryDirectory(prefix="llmlang-provider-profile-") as directory:
        archive = str(Path(directory) / "profile.llpkg")
        started = time.perf_counter()
        profiler.enable()
        try:
            build_archive_from_snapshot(
                [snapshot.hashes[0]], snapshot, manifest, archive,
                policy="closure", max_records_in_memory=1024, sqlite_cache_kib=4096,
            )
        finally:
            profiler.disable()
        elapsed = time.perf_counter() - started
        archive_bytes = Path(archive).stat().st_size

    print(json.dumps({
        "profile": "disk-backed-provider-build",
        "shape": args.shape,
        "objects": args.size,
        "dependency_edges": snapshot.edge_count,
        "provider_build_seconds": round(elapsed, 6),
        "archive_bytes": archive_bytes,
    }, sort_keys=True))
    output = io.StringIO()
    stats = pstats.Stats(profiler, stream=output).strip_dirs()
    stats.sort_stats("cumulative").print_stats(args.top)
    print(output.getvalue())


if __name__ == "__main__":
    main()
