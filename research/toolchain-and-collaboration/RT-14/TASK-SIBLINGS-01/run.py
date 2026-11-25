"""Check delegated two-child work against SQLite ownership and lifecycle controls."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier

from group import CHECKS, Evidence, Group, Work

LEFT = Work(1, "base-a", "left", "worker-a", ("A", "B"))
RIGHT = Work(1, "base-a", "right", "worker-b", ("C", "D"))


def proof(work):
    return tuple(Evidence(work, label, "pass") for label in sorted(CHECKS))


def replay_lifecycle(path):
    coordinator = Group(path, initialize=True)
    peer = Group(path)
    results = {}
    try:
        results["scope_expansion"] = coordinator.delegate(replace(LEFT, scope=("A", "outside")))
        results["delegate_left"] = coordinator.delegate(LEFT)
        results["overlapping_sibling"] = peer.delegate(replace(RIGHT, scope=("B", "D")))
        results["delegate_right"] = peer.delegate(RIGHT)
        results["missing_obligation"] = coordinator.settle(LEFT, proof(LEFT)[:-1], "first")
        results["wrong_owner"] = peer.settle(replace(LEFT, actor=RIGHT.actor), proof(LEFT), "first")
        results["settle_left"] = coordinator.settle(LEFT, proof(LEFT), "first")
        results["partial_parent"] = coordinator.complete(1, "base-a")
        results["redelivery_before_cancel"] = peer.settle(LEFT, proof(LEFT)[::-1], "first")
        results["conflicting_redelivery"] = peer.settle(LEFT, proof(LEFT)[:-1], "first")
        peer.move_baseline("base-b")
        results["stale_baseline"] = coordinator.settle(RIGHT, proof(RIGHT), "old-right")
        results["cancel_old_revision"] = coordinator.cancel(1)
        results["new_settlement_after_cancel"] = peer.settle(RIGHT, proof(RIGHT), "old-right")
        results["replay_immutable_old_receipt"] = peer.settle(LEFT, proof(LEFT), "first")
        results["restart"] = peer.restart(1)
        results["old_revision_cannot_delegate"] = coordinator.delegate(LEFT)
        left = replace(LEFT, epoch=2, baseline="base-b")
        right = replace(RIGHT, epoch=2, baseline="base-b")
        results["restart_left"] = coordinator.delegate(left)
        results["restart_right"] = peer.delegate(right)
        results["old_evidence_on_new_revision"] = coordinator.settle(left, proof(LEFT), "new-left")
        results["new_left"] = coordinator.settle(left, proof(left), "new-left")
        results["new_right"] = peer.settle(right, proof(right), "new-right")
        results["complete_current_parent"] = coordinator.complete(2, "base-b")
        assert coordinator.task() == (2, "base-b", "base-b", "complete")
        assert list(coordinator.db.execute("SELECT operation,epoch,child FROM outcome ORDER BY operation")) == [
            ("first", 1, "left"), ("new-left", 2, "left"), ("new-right", 2, "right"),
        ]
        return results
    finally:
        peer.close()
        coordinator.close()


def compete(path, second):
    coordinator = Group(path, initialize=True)
    barrier = Barrier(2)

    def contender(work):
        worker = Group(path)
        try:
            barrier.wait(timeout=10)
            return worker.delegate(work)
        finally:
            worker.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(contender, work) for work in (LEFT, second)]
            outcomes = sorted(future.result() for future in pending)
        owned = list(coordinator.db.execute("SELECT subject FROM ownership ORDER BY subject"))
        return outcomes, len(owned)
    finally:
        coordinator.close()


def cancel_order(path, cancel_first):
    worker = Group(path, initialize=True)
    sender = Group(path)
    try:
        delegated = worker.delegate(LEFT)
        assert delegated == "delegated"
        if cancel_first:
            cancelled = sender.cancel(1)
            settled = worker.settle(LEFT, proof(LEFT), "settlement")
        else:
            settled = worker.settle(LEFT, proof(LEFT), "settlement")
            cancelled = sender.cancel(1)
        assert cancelled == "cancelled"
        assert worker.complete(1, "base-a") == "inactive"
        return settled, worker.db.execute("SELECT count(*) FROM outcome").fetchone()[0]
    finally:
        sender.close()
        worker.close()


def missing_scope(path):
    coordinator = Group(path, initialize=True)
    left, right = replace(LEFT, scope=("A",)), replace(RIGHT, scope=("B",))
    try:
        assert coordinator.delegate(left) == coordinator.delegate(right) == "delegated"
        assert coordinator.settle(left, proof(left), "a") == "settled"
        assert coordinator.settle(right, proof(right), "b") == "settled"
        outcome = coordinator.complete(1, "base-a")
        assert outcome == "pending-scope" and coordinator.task()[-1] == "active"
        return outcome
    finally:
        coordinator.close()


def run(root):
    outcomes = replay_lifecycle(root / "lifecycle.db")
    assert tuple(outcomes.values()) == (
        "scope-expansion", "delegated", "overlap", "delegated", "unsatisfied", "ownership-mismatch",
        "settled", "pending-children", "replayed", "operation-conflict", "stale-baseline",
        "cancelled", "inactive", "replayed", "restarted", "stale-revision", "delegated", "delegated",
        "unsatisfied", "settled", "settled", "complete",
    )
    for repetition in range(8):
        overlapping = compete(root / f"overlap-{repetition}.db", replace(RIGHT, scope=("B", "D")))
        disjoint = compete(root / f"separate-{repetition}.db", RIGHT)
        assert overlapping == (["delegated", "overlap"], 2)
        assert disjoint == (["delegated", "delegated"], 4)
    cancellation_first = cancel_order(root / "cancel-first.db", True)
    completion_first = cancel_order(root / "settle-first.db", False)
    assert (cancellation_first, completion_first) == (("inactive", 0), ("settled", 1))
    return {
        "sqlite": sqlite3.sqlite_version,
        "lifecycle_controls": outcomes, "concurrent_repetitions_per_scope_case": 8,
        "overlapping_delegate_race": overlapping, "disjoint_delegate_race": disjoint,
        "settled_siblings_without_full_scope": missing_scope(root / "scope-gap.db"),
        "cancel_before_settle": cancellation_first, "settle_before_cancel": completion_first,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-task-siblings-") as directory:
        result = run(Path(directory))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
