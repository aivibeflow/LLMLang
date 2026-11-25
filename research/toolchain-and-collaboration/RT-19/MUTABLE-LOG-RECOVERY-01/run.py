#!/usr/bin/env python3
"""Check exact receipt recovery for a cooperatively updated mutable Linux log."""

from collections import Counter
from contextlib import contextmanager
import fcntl
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import selectors
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
TASK = "planned-op"
PAYLOAD = "alpha"
POLICIES = ("blind_retry", "latest_payload", "exact_log")
CASES = {
    "before_effect": "before",
    "after_effect": "append",
    "interleaved_after_effect": "append",
    "foreign_tail_after_effect": "append",
    "other_same_payload": "before",
    "known_prefix": "prefix",
    "unknown_prefix": "short",
    "conflicting_record": "before",
    "changed_target": "before",
    "cached_receipt": "receipt",
    "changed_target_after_receipt": "receipt",
    "truncated_after_receipt": "receipt",
    "concurrent_retry": "append",
}
SUCCESS = {"cached", "appended", "present", "latest_matches", "completed_prefix"}


def digest(payload):
    return sha256(payload).hexdigest()


def frame(operation, payload):
    return json.dumps({"id": operation, "payload": payload}, separators=(",", ":"), sort_keys=True).encode() + b"\n"


def read_log(fd):
    size = os.fstat(fd).st_size
    return os.pread(fd, size, 0)


def split(data):
    *lines, tail = data.split(b"\n")
    records = []
    for line in lines:
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeError):
            return records, tail, False
        if not isinstance(row, dict) or set(row) != {"id", "payload"}:
            return records, tail, False
        if not all(isinstance(value, str) for value in row.values()) or frame(row["id"], row["payload"]) != line + b"\n":
            return records, tail, False
        records.append(row)
    return records, tail, True


@contextmanager
def log_handle(root):
    fd = os.open(root / "effects.log", os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        os.close(fd)


@contextmanager
def database(root):
    db = sqlite3.connect(root / "journal.sqlite", isolation_level=None)
    try:
        db.execute("PRAGMA synchronous=FULL")
        yield db
    finally:
        db.close()


def identities(fd):
    stat = os.fstat(fd)
    return stat.st_dev, stat.st_ino


def append(fd, bytes_):
    assert os.write(fd, bytes_) == len(bytes_)
    os.fsync(fd)


def initialize(root, case):
    root.mkdir()
    path = root / "effects.log"
    path.write_bytes(b"")
    with log_handle(root) as fd, database(root) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        db.execute("CREATE TABLE intent(id TEXT PRIMARY KEY, frame BLOB, dev INTEGER, ino INTEGER, at_offset INTEGER)")
        db.execute("CREATE TABLE receipt(id TEXT PRIMARY KEY, frame_sha256 TEXT)")
        if case == "other_same_payload":
            append(fd, frame("other", PAYLOAD))
        if case == "conflicting_record":
            append(fd, frame(TASK, "conflicting"))
        db.execute("INSERT INTO intent VALUES (?,?,?,?,?)",
                   (TASK, frame(TASK, PAYLOAD), *identities(fd), os.fstat(fd).st_size))


def prepare_read(db):
    desired, dev, ino, offset = db.execute("SELECT frame, dev, ino, at_offset FROM intent WHERE id=?",
                                          (TASK,)).fetchone()
    row = db.execute("SELECT frame_sha256 FROM receipt WHERE id=?", (TASK,)).fetchone()
    return desired, (dev, ino), offset, row[0] if row else None


def receipt(db, encoded):
    db.execute("INSERT INTO receipt VALUES (?,?)", (TASK, digest(encoded)))


def crash(root, stage):
    with log_handle(root) as fd, database(root) as db:
        desired, target, offset, present = prepare_read(db)
        assert identities(fd) == target and not present and os.fstat(fd).st_size == offset
        if stage == "short":
            append(fd, desired[:1])
        elif stage == "prefix":
            cut = desired.index(b',"payload"') + len(b',"payload":"a')
            append(fd, desired[:cut])
        elif stage in {"append", "receipt"}:
            append(fd, desired)
            if stage == "receipt":
                receipt(db, desired)
        else:
            assert stage == "before"
        os._exit(71)


def check_exact(fd, desired, expected_target, offset, cached):
    if identities(fd) != expected_target:
        return "target_changed"
    raw = read_log(fd)
    records, tail, well_formed = split(raw)
    if not well_formed:
        return "malformed_log"
    own = [row for row in records if row["id"] == TASK]
    expected = json.loads(desired)
    if own and own != [expected]:
        return "conflicting_operation"
    if own and tail:
        return "foreign_tail"
    if cached:
        return "cached" if own == [expected] and cached == digest(desired) else "stale_receipt"
    if own == [expected]:
        return "present"
    if tail:
        identity_end = desired.index(b',"payload"')
        if len(tail) < identity_end or not desired.startswith(tail) or len(raw) - len(tail) < offset:
            return "unidentified_prefix"
        append(fd, desired[len(tail):])
        return "completed_prefix"
    append(fd, desired)
    return "appended"


def recover(root, policy):
    with log_handle(root) as fd, database(root) as db:
        desired, target, offset, cached = prepare_read(db)
        if policy == "exact_log":
            status = check_exact(fd, desired, target, offset, cached)
        elif cached:
            status = "cached"
        else:
            records, _, _ = split(read_log(fd))
            if policy == "latest_payload" and records and records[-1]["payload"] == PAYLOAD:
                status = "latest_matches"
            else:
                append(fd, desired)
                status = "appended"
        if status in SUCCESS and not cached:
            receipt(db, desired)
        return status


def statuses(root, policy, concurrent):
    args = [sys.executable, "-B", __file__, "--recover", str(root), policy]
    if not concurrent:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=10, check=True)
        return [completed.stdout.strip()]
    race = [*args[:3], "--recover-race", *args[4:]]
    runners = [subprocess.Popen(race, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True) for _ in range(2)]
    for runner in runners:
        with selectors.DefaultSelector() as waiting:
            waiting.register(runner.stdout, selectors.EVENT_READ)
            assert waiting.select(timeout=5) and runner.stdout.readline() == "ready\n"
    for runner in runners:
        runner.stdin.write("go\n")
        runner.stdin.flush()
    states = []
    for runner in runners:
        stdout, stderr = runner.communicate(timeout=10)
        assert runner.returncode == 0 and not stderr
        states.append(stdout.strip())
    return sorted(states)


def exercise(root, case, policy):
    initialize(root, case)
    stopped = subprocess.run([sys.executable, "-B", __file__, "--crash", str(root), CASES[case]],
                             capture_output=True, timeout=10)
    assert stopped.returncode == 71 and not stopped.stdout and not stopped.stderr
    active = root / "effects.log"
    if case in {"interleaved_after_effect", "foreign_tail_after_effect"}:
        peer = frame("other", "beta")
        with log_handle(root) as fd:
            append(fd, peer if case == "interleaved_after_effect" else peer[:12])
    if case in {"changed_target", "changed_target_after_receipt"}:
        active.rename(root / "former.log")
        active.write_bytes(b"")
    if case == "truncated_after_receipt":
        original = active.stat().st_ino
        active.write_bytes(b"")
        assert active.stat().st_ino == original
    before = active.read_bytes()
    responses = statuses(root, policy, case == "concurrent_retry")
    data = active.read_bytes()
    records, tail, complete = split(data)
    with log_handle(root) as fd, database(root) as db:
        desired, target, _, cached = prepare_read(db)
        same_target = identities(fd) == target
    successes = sum(status in SUCCESS for status in responses)
    matches = sum(row == {"id": TASK, "payload": PAYLOAD} for row in records)
    conflicting = sum(row["id"] == TASK and row["payload"] != PAYLOAD for row in records)
    valid_receipt = same_target and complete and not tail and matches == 1 and not conflicting
    wrong_successes = successes if not valid_receipt else 0
    if policy == "exact_log":
        assert wrong_successes == 0 and matches <= 1
        if successes:
            assert cached == digest(desired)
        else:
            assert before == data
    return {
        "case": case, "policy": policy, "crash_phase": CASES[case], "responses": responses,
        "before_hex": before.hex(), "after_hex": data.hex(), "former_log_preserved": (
            digest((root / "former.log").read_bytes()) if (root / "former.log").exists() else None),
        "target_identity_matches": same_target, "matching_records": matches, "conflicting_records": conflicting,
        "complete_canonical_log": complete and not tail, "recorded_receipt": cached is not None,
        "wrong_successes": wrong_successes, "duplicate_records": max(0, matches - 1), "refusals": len(responses) - successes,
    }


def run(directory):
    rows = [exercise(directory / f"{name}-{policy}", name, policy) for name, policy in product(CASES, POLICIES)]
    exact = {row["case"]: row for row in rows if row["policy"] == "exact_log"}
    assert exact["concurrent_retry"]["responses"] == ["cached", "present"]
    assert exact["known_prefix"]["responses"] == ["completed_prefix"]
    assert exact["unknown_prefix"]["responses"] == ["unidentified_prefix"]
    assert exact["foreign_tail_after_effect"]["responses"] == ["foreign_tail"]
    assert exact["conflicting_record"]["responses"] == ["conflicting_operation"]
    assert exact["changed_target"]["responses"] == ["target_changed"]
    assert exact["changed_target_after_receipt"]["responses"] == ["target_changed"]
    assert exact["truncated_after_receipt"]["responses"] == ["stale_receipt"]
    totals = {}
    for policy in POLICIES:
        counts = Counter()
        for row in rows:
            if row["policy"] == policy:
                for field in ("wrong_successes", "duplicate_records", "refusals"):
                    counts[field] += row[field]
                counts["successful_calls"] += len(row["responses"]) - row["refusals"]
        totals[policy] = dict(counts)
    return {
        "schema": "llmlang-rt19-mutable-log/1", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "linux": platform.release(),
        "runner_sha256": digest(Path(__file__).read_bytes()), "scenario_count": len(rows),
        "retry_calls": sum(len(row["responses"]) for row in rows), "metrics": totals, "observations": rows,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        flag, path, phase = sys.argv[1:]
        if flag == "--crash":
            crash(Path(path), phase)
        elif flag in {"--recover", "--recover-race"}:
            if flag == "--recover-race":
                print("ready", flush=True)
                assert input() == "go"
            print(recover(Path(path), phase))
        else:
            raise SystemExit("Unknown fixture invocation")
    else:
        with TemporaryDirectory(prefix="llmlang-rt19-mutable-log-") as scratch:
            result = run(Path(scratch))
        observations = result.pop("observations")
        print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
        print(",\n".join("    " + json.dumps(row) for row in observations))
        print("  ]\n}")
