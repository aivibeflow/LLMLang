#!/usr/bin/env python3
"""Crash and restart a real SQLite/Git publication transaction fixture."""

import argparse
from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
for parent in HERE.parents:
    candidate = parent / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
    if candidate.is_dir():
        os.environ.setdefault("LLMLANG_DEPENDENCY_GRAPH_PROTOTYPE", str(candidate))
        break

from coordinator import SCHEMA, connect, digest, graph, receipt, semantic_root


BOUNDARIES = {
    "begin_accept": ("base", "none", "base", False),
    "immutable_written": ("base", "none", "base", False),
    "accepted_outbox": ("next", "accepted", "base", False),
    "partial_private_index": ("next", "accepted", "base", False),
    "validated_candidate": ("next", "accepted", "base", False),
    "prepared_outbox": ("next", "prepared", "base", False),
    "git_published": ("next", "prepared", "published", True),
    "sql_outcome": ("next", "recorded", "published", True),
}


@dataclass
class Fixture:
    repo: Path
    db: Path
    request: dict
    request_path: Path
    base_root: str


def declaration(slot, version):
    return graph.row(slot, graph.declaration("contract", f"contract:{slot}", {"version": version}))


def files(version):
    supplemental = "program/second.json"
    return {graph.MANIFEST: json.dumps(graph.manifest(graph.CONTRACT, supplemental)) + "\n",
            graph.CONTRACT: json.dumps([declaration("first", version)]) + "\n",
            supplemental: json.dumps([declaration("second", version)]) + "\n",
            "selected.txt": f"{version} approved regular bytes\n"}


def initialize(directory):
    repo = directory / "repo"
    repo.mkdir()
    graph.git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
    base = graph.commit(repo, {**files("base"), "unrelated.txt": "base unrelated\n", "removed.txt": "delete me\n"})
    _, base_snapshot = graph.import_closed(graph.read_inventory(repo, base))
    db_path = directory / "journal.sqlite"
    with closing(connect(db_path)) as db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO head VALUES (1, 0, ?)", (base_snapshot.root_hash,))
    (repo / "unrelated.txt").write_text("user staged bytes\n", encoding="utf-8")
    graph.git(repo, "add", "--", "unrelated.txt")
    (repo / "unrelated.txt").write_text("user unstaged bytes\n", encoding="utf-8")
    (repo / "selected.txt").write_text("worktree edit outside the request\n", encoding="utf-8")
    request = {"key": "fixture-request-1", "generation": 0, "parent_root": base_snapshot.root_hash,
               "base": base, "files": files("next"), "delete": ["removed.txt"]}
    request_path = directory / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    return Fixture(repo, db_path, request, request_path, base_snapshot.root_hash)


def observe(fixture):
    with closing(connect(fixture.db)) as db:
        head = db.execute("SELECT generation, root FROM head").fetchone()
        row = db.execute("SELECT key, root, tree, candidate, outcome FROM operation").fetchone()
        objects = db.execute("SELECT count(*) FROM object").fetchone()[0]
    head_class = "base" if head["generation"] == 0 else "next"
    wanted_root = fixture.base_root if head_class == "base" else semantic_root(fixture.request["files"])[0]
    if head["root"] != wanted_root or head["generation"] not in (0, 1):
        raise ValueError("Unexpected durable semantic head")
    if objects != int(row is not None):
        raise ValueError("Immutable object and acceptance/outbox were not committed together")
    operation = "none"
    if row is not None:
        if row["root"] != head["root"] or row["key"] != fixture.request["key"]:
            raise ValueError("Unexpected durable request or root")
        operation = "recorded" if row["outcome"] else "prepared" if row["candidate"] else "accepted"
    branch = receipt.ref(fixture.repo, receipt.BRANCH)
    git_receipt = receipt.ref(fixture.repo, f"refs/llmlang/receipts/{digest(fixture.request['key'])}")
    if git_receipt is not None and (row is None or git_receipt != row["candidate"]):
        raise ValueError("Git receipt has no matching durable prepared candidate")
    branch_class = "base" if branch == fixture.request["base"] else "published" if branch == git_receipt else "external"
    return head_class, operation, branch_class, git_receipt is not None


def worker(fixture, *, failpoint=None, path=None):
    command = [sys.executable, "-B", str(HERE / "coordinator.py"), str(fixture.repo), str(fixture.db),
               str(path or fixture.request_path)]
    if failpoint:
        command += ["--failpoint", failpoint]
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def result(process, *, crash=False):
    stdout, stderr = process.communicate(timeout=35)
    wanted_code = 74 if crash else 0
    if process.returncode != wanted_code or stderr:
        raise ValueError(f"Unexpected worker exit {process.returncode}: {stdout!r} {stderr!r}")
    if crash:
        if stdout:
            raise ValueError("Worker replied after its injected abrupt exit")
        return None
    return json.loads(stdout)


def verify_publication(fixture, publication, *, head=None):
    if publication["status"] != "published" or publication["generation"] != 1:
        raise ValueError("Missing first publication outcome")
    repo, request = fixture.repo, fixture.request
    published = publication["commit"]
    if receipt.ref(repo, receipt.BRANCH) != (head or published):
        raise ValueError("Branch moved unexpectedly")
    exact = graph.read_inventory(repo, published)
    _, snapshot = graph.import_closed(exact)
    if exact.tree != publication["tree"] or snapshot.root_hash != publication["root"]:
        raise ValueError("Recovery receipt cannot reconstruct the exact tree/root")
    if graph.git(repo, "rev-list", "--first-parent", "--count", published) != b"2\n":
        raise ValueError("Retry produced duplicate commits")
    if graph.git(repo, "show", f"{published}:unrelated.txt") != b"base unrelated\n":
        raise ValueError("Unapproved regular file was exported")
    if graph.git(repo, "ls-tree", published, "--", "removed.txt"):
        raise ValueError("Approved deletion was omitted")
    for path, content in request["files"].items():
        if graph.git(repo, "show", f"{published}:{path}") != content.encode("utf-8"):
            raise ValueError(f"The published blob was not the accepted one: {path}")


def after_crash(directory, point, expected):
    fixture = initialize(directory)
    repo = fixture.repo
    index = (repo / ".git/index").read_bytes()
    result(worker(fixture, failpoint=point), crash=True)
    state = observe(fixture)
    if state != expected:
        raise ValueError(f"Unexpected state after {point}: {state}, expected {expected}")
    recovered = result(worker(fixture))
    again = result(worker(fixture))
    if recovered != again or observe(fixture) != ("next", "recorded", "published", True):
        raise ValueError(f"Idempotent recovery failed at {point}")
    verify_publication(fixture, recovered)
    if (repo / ".git/index").read_bytes() != index or (repo / "unrelated.txt").read_bytes() != b"user unstaged bytes\n":
        raise ValueError("Publication touched the user's index or unrelated worktree")
    if (repo / "selected.txt").read_bytes() != b"worktree edit outside the request\n":
        raise ValueError("Publication rewrote the live selected file")
    return {"state_after_exit": state, "recovered": recovered, "retry_matched": True}


def additional(directory):
    with TemporaryDirectory(prefix="branch-moves-", dir=directory) as temp:
        fixture = initialize(Path(temp))
        result(worker(fixture, failpoint="git_published"), crash=True)
        first = receipt.ref(fixture.repo, receipt.BRANCH)
        tree = receipt.ref(fixture.repo, f"{first}^{{tree}}")
        later = receipt.commit_object(fixture.repo, tree, (fixture.request["base"],), "external divergent commit")
        graph.git(fixture.repo, "update-ref", receipt.BRANCH, later, first)
        recovered = result(worker(fixture))
        verify_publication(fixture, recovered, head=later)
        retry = result(worker(fixture))
        if recovered != retry or recovered["commit"] != first:
            raise ValueError("Moving main lost the original outcome")
        changed_path = fixture.request_path.with_name("changed.json")
        changed = {**fixture.request, "files": {**fixture.request["files"], "selected.txt": "changed\n"}}
        changed_path.write_text(json.dumps(changed), encoding="utf-8")
        if result(worker(fixture, path=changed_path)) != {"status": "key-conflict"}:
            raise ValueError("Same key accepted distinct canonical bytes")

    with TemporaryDirectory(prefix="stale-git-", dir=directory) as temp:
        fixture = initialize(Path(temp))
        result(worker(fixture, failpoint="accepted_outbox"), crash=True)
        base = fixture.request["base"]
        tree = receipt.ref(fixture.repo, f"{base}^{{tree}}")
        moved = receipt.commit_object(fixture.repo, tree, (base,), "unexpected ref advance")
        graph.git(fixture.repo, "update-ref", receipt.BRANCH, moved, base)
        if result(worker(fixture)) != {"status": "stale"} or observe(fixture) != ("next", "prepared", "external", False):
            raise ValueError("Git CAS failure did not preserve pending accepted state")

    with TemporaryDirectory(prefix="competing-requests-", dir=directory) as temp:
        fixture = initialize(Path(temp))
        second = {**fixture.request, "key": "fixture-request-2", "files": files("alternative")}
        other = fixture.request_path.with_name("second.json")
        other.write_text(json.dumps(second), encoding="utf-8")
        a, b = worker(fixture), worker(fixture, path=other)
        outputs = [result(a), result(b)]
        if sorted(outcome["status"] for outcome in outputs) != ["published", "stale-acceptance"]:
            raise ValueError(f"Expected exactly one independent winner: {outputs}")
        first_won = outputs[0]["status"] == "published"
        if not first_won:
            fixture.request = second
        verify_publication(fixture, outputs[0 if first_won else 1])

    with TemporaryDirectory(prefix="same-request-race-", dir=directory) as temp:
        fixture = initialize(Path(temp))
        a, b = worker(fixture), worker(fixture)
        first, second = result(a), result(b)
        if first != second or observe(fixture) != ("next", "recorded", "published", True):
            raise ValueError("Concurrent identical requests did not share the outcome")
        verify_publication(fixture, first)

    with TemporaryDirectory(prefix="bad-inventory-", dir=directory) as temp:
        fixture = initialize(Path(temp))
        changed = {**fixture.request, "files": {name: text for name, text in fixture.request["files"].items()
                                                if name != graph.CONTRACT}}
        fixture.request_path.write_text(json.dumps(changed), encoding="utf-8")
        if result(worker(fixture)) != {"status": "invalid-inventory"} or observe(fixture) != (
                "base", "none", "base", False):
            raise ValueError("Incomplete source was durably accepted")

    with TemporaryDirectory(prefix="clone-", dir=directory) as temp:
        root = Path(temp)
        fixture = initialize(root)
        accepted = result(worker(fixture))
        graph.git(root, "clone", "--quiet", "--no-local", str(fixture.repo), "fresh")
        fresh = root / "fresh"
        imported = graph.read_inventory(fresh, "HEAD")
        _, snapshot = graph.import_closed(imported)
        if (imported.tree, snapshot.root_hash) != (accepted["tree"], accepted["root"]):
            raise ValueError("Git-only reconstruction did not match")
    return {"historical_receipt_after_divergence": True, "different_payload_rejected": True,
            "stale_git_keeps_outbox_pending": True, "competing_writers": ["published", "stale-acceptance"],
            "concurrent_identical_outcome": True, "incomplete_inventory_rejected": True, "fresh_clone_exact": True}


def replay():
    with TemporaryDirectory(prefix="llmlang-rt19-crash-") as temporary:
        directory = Path(temporary)
        cases = {}
        for point, expected in BOUNDARIES.items():
            case = directory / point
            case.mkdir()
            cases[point] = after_crash(case, point, expected)
        extra = additional(directory)
    prototype = Path(os.environ["LLMLANG_DEPENDENCY_GRAPH_PROTOTYPE"]).resolve()
    imports = {}
    for module in tuple(sys.modules.values()):
        location = getattr(module, "__file__", None)
        if location is None:
            continue
        source = Path(location).resolve()
        if source.suffix == ".py" and source.is_relative_to(prototype):
            imports[str(source.relative_to(prototype))] = sha256(source.read_bytes()).hexdigest()
    return {"schema": "llmlang-rt19-real-crash-boundaries-v1", "git": subprocess.check_output(["git", "--version"],
            text=True).strip(), "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "inputs": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in ("coordinator.py", "run.py")},
            "prototype_input_sha256": dict(sorted(imports.items())), "cases": cases, "controls": extra}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), indent=2) + "\n", encoding="utf-8")
