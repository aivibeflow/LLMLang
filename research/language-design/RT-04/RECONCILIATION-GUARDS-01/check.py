"""Check exact terminal reconciliation and defensive coverage gates."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from threading import Barrier


BASE = "16f21b6df3ef3668477973bfad94e5974177c2f2"


@dataclass(frozen=True)
class Subject:
    provider: str
    allocation: str
    invocation: str
    snapshot_generation: int
    disposition: str


def token(subject):
    return json.dumps(asdict(subject), sort_keys=True, separators=(",", ":"))


def guard(alias_state, reentry_state, effects):
    if "unknown" in (alias_state, reentry_state) or effects == "unmodeled":
        return "unknown"
    if (alias_state, reentry_state) != ("clear", "closed") or effects != "scoped":
        return "refused"
    return "authorized"


def guard_cases():
    count = Counter()
    for aliases, reentry, effect in product(("clear", "live", "unknown"), ("closed", "active", "unknown"),
                                            ("scoped", "unmodeled", "widened")):
        actual = guard(aliases, reentry, effect)
        supported = aliases != "unknown" and reentry != "unknown" and effect != "unmodeled"
        expected = {"clear": "authorized" if reentry == "closed" and effect == "scoped" else "refused",
                    "live": "refused", "unknown": "unknown"}[aliases] if supported else "unknown"
        assert actual == expected
        count[actual] += 1
    return dict(count)


def deliver(path, proposal, barrier):
    with sqlite3.connect(path, timeout=10) as connection:
        barrier.wait(timeout=10)
        connection.execute("BEGIN IMMEDIATE")
        authorized, applied = connection.execute("SELECT subject, closed FROM current_invocation").fetchone()
        if token(proposal) != authorized:
            return "stale-or-unrelated"
        if applied:
            return "idempotent"
        connection.execute("UPDATE current_invocation SET closed = 1")
        return "closed"


def native_delivery():
    results = {}
    with TemporaryDirectory() as work, ThreadPoolExecutor(max_workers=2) as executor:
        for provider, invalid in product(("provider-c", "provider-py"), ("none", "provider", "allocation",
                                                                       "invocation", "generation", "disposition")):
            current = Subject(provider, "resource-a", "invocation-a", 8, "released")
            restored_from = replace(current, snapshot_generation=7)
            variants = {
                "none": current, "provider": replace(current, provider="other"),
                "allocation": replace(current, allocation="other"), "invocation": replace(current, invocation="other"),
                "generation": restored_from,
                "disposition": replace(current, disposition="accepted-not-yet-released"),
            }
            path = Path(work) / f"{provider}-{invalid}.db"
            with sqlite3.connect(path) as database:
                assert database.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
                database.execute("CREATE TABLE current_invocation(subject TEXT NOT NULL, closed INTEGER NOT NULL)")
                database.execute("INSERT INTO current_invocation VALUES (?, 0)", (token(restored_from),))
            with sqlite3.connect(path) as database:
                database.execute("UPDATE current_invocation SET subject = ? WHERE subject = ?",
                                 (token(current), token(restored_from)))
            barrier = Barrier(2)
            jobs = [executor.submit(deliver, path, item, barrier) for item in (current, variants[invalid])]
            observed = sorted(job.result(timeout=12) for job in jobs)
            assert observed == ["closed", "idempotent" if invalid == "none" else "stale-or-unrelated"]
            with sqlite3.connect(path) as database:
                assert database.execute("SELECT * FROM current_invocation").fetchall() == [(token(current), 1)]
            results[f"{provider}/{invalid}"] = observed
    return results


def prior():
    paths = (
        "research/language-design/RT-04/QUEUED-FOREIGN-OWNERSHIP-01/evidence.json",
        "research/language-design/RT-04/RESEARCH-SCENARIO-125-CLOSE-REENTRY-AND-COVERAGE.md",
        "research/runtime-and-systems/RT-10/RESEARCH-SCENARIO-129-CANCELLATION-AND-INVOCATION-EVIDENCE.md",
        "research/runtime-and-systems/RT-10/RESEARCH-SCENARIO-130-DURABLE-INVOCATION-RESULTS.md",
    )
    return {path: sha256(subprocess.check_output(["git", "show", f"{BASE}:{path}"])).hexdigest()
            for path in paths}


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "sqlite": sqlite3.sqlite_version, "guard_cases": guard_cases(),
        "delivery_cases": native_delivery(), "prior_sha256": prior(),
    }, sort_keys=True, indent=2))
