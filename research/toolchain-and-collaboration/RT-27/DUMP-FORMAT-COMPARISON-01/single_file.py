"""Check and time parallel range reads within a single SPG container."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from record_codecs import PROFILES
from run import (HERE, SELECTION, canonical, digest, duration, file_paths,
                 index_rows, make_record, read_record, write_container)


def read_range(job):
    profile, path, rows = job
    output = sha256()
    with path.open("rb") as payload:
        for slot, offset, size, address in rows:
            read_record(profile, payload.fileno(), offset, size, address)
            output.update(SELECTION.pack(slot, address))
    return output.digest()


def run_jobs(function, jobs, workers):
    if workers == 1:
        return [function(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context("fork")) as pool:
        return list(pool.map(function, jobs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    previous = json.loads(args.evidence.read_text(encoding="utf-8"))
    for name, checksum in previous["source_sha256"].items():
        if digest((HERE / name).read_bytes()).hex() != checksum:
            raise ValueError(f"source revision differs from comparison evidence: {name}")
    seed, count = previous["seed"], previous["objects"]
    repetitions, parallel = previous["repeats"], 2
    source = [(slot, make_record(seed, slot, 0)) for slot in range(count)]
    boundaries = [count * part // 8 for part in range(9)]
    ranges = list(zip(boundaries, boundaries[1:]))
    expected = [digest(b"".join(SELECTION.pack(slot, canonical(value))
                                for slot, value in source[lo:hi]))
                for lo, hi in ranges]
    sizes = {row["profile"]: row["baseline_payload_bytes"] for row in previous["profiles"]}
    report = []
    with TemporaryDirectory(prefix="spg-single-file-") as temp:
        folder = Path(temp)
        index, payload = file_paths(folder)
        for profile in PROFILES:
            manifest = write_container(profile, folder, source)
            if manifest["bytes"] != sizes[profile]:
                raise AssertionError("range test uses a different container size")
            rows = index_rows(index, manifest)
            jobs = [(profile, payload, rows[lo:hi]) for lo, hi in ranges]
            timings = []
            for trial in range(repetitions):
                for workers in (1, parallel) if trial % 2 == 0 else (parallel, 1):
                    start = perf_counter()
                    if run_jobs(read_range, jobs, workers) != expected:
                        raise AssertionError("single-file ranges changed the selection")
                    timings.append({"trial": trial, "workers": workers, "ms": duration(start)})
            report.append({"profile": profile, "file_bytes": payload.stat().st_size,
                           "timings": timings})
    evidence = {
        "source_sha256": digest(Path(__file__).read_bytes()).hex(),
        "comparison_evidence_sha256": digest(args.evidence.read_bytes()).hex(),
        "objects": count, "range_count": len(ranges), "seed": seed,
        "selection_sha256": digest(b"".join(expected)).hex(),
        "visible_cpus": len(os.sched_getaffinity(0)), "profiles": report,
    }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
