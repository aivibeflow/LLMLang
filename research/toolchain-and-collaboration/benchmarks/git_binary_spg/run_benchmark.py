#!/usr/bin/env python3
"""Reproducible Git packfile benchmark for immutable SPG-like records.

Uses only the Python standard library and a locally installed Git executable.
"""
from __future__ import annotations
import argparse, hashlib, json, platform, random, shutil, subprocess, sys, tempfile, time
from pathlib import Path

SCENARIOS = ("mutable_append", "mutable_delete_compact", "mutable_delete_tombstones",
             "segments_append", "segments_delete_tombstones")

def git(repo: Path, binary: str, *args: str) -> str:
    p = subprocess.run([binary, "-C", str(repo), *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.stdout.strip()

def record(record_id: int, size: int) -> bytes:
    if size < 16: raise ValueError("record size must be >= 16")
    return record_id.to_bytes(8, "big") + hashlib.shake_256(
        f"spg-benchmark-record:{record_id}".encode()).digest(size - 8)

def write_records(path: Path, ids: list[int], size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for i in ids: f.write(record(i, size))

def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

def init_repo(repo: Path, binary: str, args: argparse.Namespace) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, binary, "init", "--quiet")
    git(repo, binary, "config", "user.name", "SPG benchmark")
    git(repo, binary, "config", "user.email", "spg-benchmark@example.invalid")
    for key, value in (("core.bigFileThreshold", args.big_file_threshold),
                       ("pack.window", str(args.pack_window)),
                       ("pack.depth", str(args.pack_depth)),
                       ("pack.compression", str(args.pack_compression))):
        git(repo, binary, "config", key, value)

def commit(repo: Path, binary: str, message: str) -> str:
    git(repo, binary, "add", "-A")
    git(repo, binary, "commit", "--quiet", "-m", message)
    return git(repo, binary, "rev-parse", "HEAD")

def deleted_ids(count: int, ratio: float, seed: int) -> list[int]:
    n = min(count, max(1, round(count * ratio)))
    return sorted(random.Random(seed).sample(range(count), n))

def initial_state(repo: Path, scenario: str, ids: list[int], size: int) -> None:
    if scenario.startswith("mutable_"):
        write_records(repo / "spg" / "shard-000.bin", ids, size)
    else:
        write_records(repo / "spg" / "segments" / "segment-000.bin", ids, size)
        write_json(repo / "spg" / "manifest.json", {"format": 1, "segments": ["segment-000.bin"]})

def changed_state(repo: Path, scenario: str, initial: list[int], added: list[int],
                  deleted: list[int], size: int) -> None:
    if scenario == "mutable_append":
        write_records(repo / "spg" / "shard-000.bin", initial + added, size)
    elif scenario == "mutable_delete_compact":
        gone = set(deleted)
        write_records(repo / "spg" / "shard-000.bin", [i for i in initial if i not in gone], size)
    elif scenario == "mutable_delete_tombstones":
        write_records(repo / "spg" / "shard-000.bin", initial, size)
        write_json(repo / "spg" / "tombstones.json", {"deleted_ids": deleted})
    elif scenario == "segments_append":
        write_records(repo / "spg" / "segments" / "segment-001.bin", added, size)
        write_json(repo / "spg" / "manifest.json",
                   {"format": 1, "segments": ["segment-000.bin", "segment-001.bin"]})
    elif scenario == "segments_delete_tombstones":
        write_json(repo / "spg" / "tombstones.json", {"deleted_ids": deleted})
    else:
        raise ValueError(f"unknown scenario: {scenario}")

def pack_metrics(repo: Path, binary: str) -> dict:
    git(repo, binary, "gc", "--aggressive", "--prune=now")
    pack_dir = repo / ".git" / "objects" / "pack"
    packs, indexes = list(pack_dir.glob("*.pack")), list(pack_dir.glob("*.idx"))
    verify = []
    for idx in indexes:
        output = git(repo, binary, "verify-pack", "-v", str(idx))
        objects = deltas = delta_bytes = max_depth = 0
        for line in output.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[1] in {"commit", "tree", "blob", "tag"}:
                objects += 1
                if len(fields) >= 7:
                    deltas += 1
                    try:
                        delta_bytes += int(fields[3])
                        max_depth = max(max_depth, int(fields[5]))
                    except ValueError:
                        pass
        verify.append({"index": idx.name, "objects": objects, "deltas": deltas,
                       "delta_representation_bytes": delta_bytes, "max_delta_depth": max_depth})
    return {
        "pack_bytes": sum(p.stat().st_size for p in packs),
        "index_bytes": sum(p.stat().st_size for p in indexes),
        "pack_and_index_bytes": sum(p.stat().st_size for p in packs + indexes),
        "pack_files": len(packs), "verify_pack": verify,
        "count_objects": git(repo, binary, "count-objects", "-v"),
    }

def run_case(root: Path, scenario: str, args: argparse.Namespace, binary: str,
             initial: list[int], added: list[int], deleted: list[int]) -> dict:
    repo = root / scenario
    init_repo(repo, binary, args)
    initial_state(repo, scenario, initial, args.record_size)
    first = commit(repo, binary, "baseline SPG state")
    started = time.perf_counter()
    changed_state(repo, scenario, initial, added, deleted, args.record_size)
    second = commit(repo, binary, scenario + " changed SPG state")
    commit_seconds = time.perf_counter() - started
    started = time.perf_counter()
    metrics = pack_metrics(repo, binary)
    gc_seconds = time.perf_counter() - started
    worktree_bytes = sum(p.stat().st_size for p in repo.rglob("*")
                         if p.is_file() and ".git" not in p.parts)
    return {"scenario": scenario, "initial_commit": first, "changed_commit": second,
            "initial_objects": len(initial),
            "added_objects": len(added) if scenario in {"mutable_append", "segments_append"} else 0,
            "deleted_objects": len(deleted) if "delete" in scenario else 0,
            "commit_seconds": round(commit_seconds, 6), "gc_aggressive_seconds": round(gc_seconds, 6),
            "repository_worktree_bytes": worktree_bytes, "worktree": str(repo), **metrics}

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--objects", type=int, default=30000)
    p.add_argument("--record-size", type=int, default=192)
    p.add_argument("--change-ratio", type=float, default=0.01)
    p.add_argument("--seed", type=int, default=20261123)
    p.add_argument("--git", default="git")
    p.add_argument("--big-file-threshold", default="512m")
    p.add_argument("--pack-window", type=int, default=10)
    p.add_argument("--pack-depth", type=int, default=50)
    p.add_argument("--pack-compression", type=int, default=6)
    p.add_argument("--output", type=Path, default=Path("results.json"))
    p.add_argument("--workdir", type=Path)
    p.add_argument("--keep-workdirs", action="store_true")
    a = p.parse_args()
    if a.objects < 1: p.error("--objects must be positive")
    if not 0 < a.change_ratio <= 1: p.error("--change-ratio must be in (0, 1]")
    if a.record_size < 16: p.error("--record-size must be >= 16")
    git_version = subprocess.run([a.git, "--version"], check=True, capture_output=True, text=True).stdout.strip()
    initial = list(range(a.objects))
    n_add = max(1, round(a.objects * a.change_ratio))
    added = list(range(a.objects, a.objects + n_add))
    deleted = deleted_ids(a.objects, a.change_ratio, a.seed)
    owned = a.workdir is None
    temp = tempfile.TemporaryDirectory(prefix="spg-git-bench-") if owned else None
    root = Path(temp.name) if temp else a.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not owned and any((root / scenario).exists() for scenario in SCENARIOS):
        p.error("--workdir must not already contain benchmark scenario directories; use a fresh or empty directory")
    result = {
        "benchmark": "git-binary-spg-storage-efficiency", "schema_version": 1,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "git_version": git_version,
                        "git_config": {"core.bigFileThreshold": a.big_file_threshold,
                                       "pack.window": a.pack_window, "pack.depth": a.pack_depth,
                                       "pack.compression": a.pack_compression}},
        "fixture": {"objects": a.objects, "record_size_bytes": a.record_size,
                    "initial_payload_bytes": a.objects * a.record_size,
                    "change_ratio": a.change_ratio, "added_objects": n_add,
                    "deleted_objects": len(deleted), "seed": a.seed,
                    "payload_generator": "SHAKE-256 of spg-benchmark-record:<id>"},
        "results": []}
    try:
        for scenario in SCENARIOS:
            result["results"].append(run_case(root, scenario, a, a.git, initial, added, deleted))
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        if temp and a.keep_workdirs:
            print(f"Work directories retained at: {root}", file=sys.stderr)
        elif temp:
            temp.cleanup()
        elif not a.keep_workdirs:
            for scenario in SCENARIOS: shutil.rmtree(root / scenario, ignore_errors=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
