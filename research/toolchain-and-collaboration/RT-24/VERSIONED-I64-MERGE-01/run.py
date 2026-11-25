#!/usr/bin/env python3
"""Compare versioned import and semantic three-way merge on real Git histories."""

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
POLICIES = ("single_v2", "rounded", "exact_unbound", "exact_bound")
SLOTS = ("a", "b")
PATH = "graph.json"
WIDE = 2**53 + 1
LIMITS = (2**63 - 1, -(2**63))
ZERO_ROOT = "0" * 64


@dataclass(frozen=True)
class Snapshot:
    version: int
    values: tuple[int, int]
    mutation: str = ""


@dataclass(frozen=True)
class Scenario:
    name: str
    base: Snapshot
    ours: Snapshot
    theirs: Snapshot
    expected: tuple[int, int] | None
    strict_status: str


BASE = Snapshot(1, (WIDE, -3))
UPGRADE = Snapshot(2, BASE.values)
SCENARIOS = (
    Scenario("upgrade_disjoint_wide", BASE, UPGRADE, Snapshot(1, (WIDE, 4)), (WIDE, 4), "merged"),
    Scenario("upgrade_with_edit", BASE, Snapshot(2, (WIDE, 4)), Snapshot(1, (WIDE + 2, -3)),
             (WIDE + 2, 4), "merged"),
    Scenario("legacy_write_no_upgrade", BASE, Snapshot(1, (WIDE, 4)), Snapshot(1, BASE.values),
             (WIDE, 4), "merged"),
    Scenario("all_upgraded", UPGRADE, Snapshot(2, (WIDE, 4)), Snapshot(2, (WIDE + 2, -3)),
             (WIDE + 2, 4), "merged"),
    Scenario("stale_root_after_lossy_write", BASE, UPGRADE,
             Snapshot(1, (WIDE - 1, 4), "root_before_rounding"), None, "root"),
    Scenario("stale_root_on_hex_branch", BASE, Snapshot(2, (WIDE, 4), "stale_root"),
             Snapshot(1, (WIDE + 2, -3)), None, "root"),
    Scenario("same_slot_conflict", BASE, Snapshot(2, (WIDE + 2, -3)), Snapshot(1, (WIDE + 4, -3)),
             None, "conflict"),
    Scenario("same_edit_two_versions", BASE, Snapshot(2, (WIDE + 2, -3)), Snapshot(1, (WIDE + 2, -3)),
             (WIDE + 2, -3), "merged"),
    Scenario("signed_limits", Snapshot(1, LIMITS), Snapshot(2, LIMITS),
             Snapshot(1, (LIMITS[0], LIMITS[1] + 1)), (LIMITS[0], LIMITS[1] + 1), "merged"),
    Scenario("noncanonical_number", BASE, UPGRADE, Snapshot(1, (WIDE, 4), "exponent"), None, "syntax"),
    Scenario("unknown_version", BASE, UPGRADE, Snapshot(3, (WIDE, 4)), None, "version"),
    Scenario("noncanonical_key_order", BASE, UPGRADE, Snapshot(1, (WIDE, 4), "order"), None, "noncanonical"),
)


def digest(data):
    return sha256(data).hexdigest()


def root(values):
    payload = b"".join(slot.encode() + b"\0" + value.to_bytes(8, "big", signed=True)
                       for slot, value in zip(SLOTS, values, strict=True))
    return digest(b"rt24-versioned-i64-graph/1\0" + payload)


def encode(snapshot):
    version, values, mutation = snapshot.version, snapshot.values, snapshot.mutation
    nodes = {slot: value if version == 1 else value.to_bytes(8, "big", signed=True).hex()
             for slot, value in zip(SLOTS, values, strict=True)}
    declared = root(values)
    if mutation == "root_before_rounding":
        declared = root((WIDE, values[1]))
    if mutation == "stale_root":
        declared = ZERO_ROOT
    if mutation == "order":
        nodes = dict(reversed(tuple(nodes.items())))
    wire = json.dumps({"version": version, "nodes": nodes, "root": declared}, separators=(",", ":")) + "\n"
    return wire.replace('"b":4', '"b":4e0') if mutation == "exponent" else wire


def import_python(wire):
    """Independently reconstruct a canonical accepted snapshot with CPython integers."""
    data = json.loads(wire)
    version = data["version"]
    assert version in (1, 2)
    encoded = [data["nodes"][slot] for slot in SLOTS]
    values = tuple(encoded) if version == 1 else tuple(
        int.from_bytes(bytes.fromhex(value), "big", signed=True) for value in encoded)
    assert encode(Snapshot(version, values)) == wire
    return values


def command(*args, cwd=None, data=None, check=True):
    return subprocess.run(args, cwd=cwd, input=data, capture_output=True, text=True, check=check, timeout=30,
                          env={**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                               "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                               "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                               "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"})


def git(repo, *args, data=None):
    return command("git", "-C", str(repo), *args, data=data).stdout


def commit(repo, snapshot, message):
    (repo / PATH).write_text(encode(snapshot), encoding="utf-8")
    git(repo, "add", PATH)
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def read_node(queries):
    result = command("node", str(HERE / "read.js"), data=json.dumps(queries))
    return json.loads(result.stdout)


def make_history(repo, case):
    git(repo, "init", "-q", "-b", "main", "--object-format=sha1")
    base = commit(repo, case.base, "base")
    git(repo, "checkout", "-q", "-b", "ours")
    ours = commit(repo, case.ours, "ours")
    git(repo, "checkout", "-q", "-b", "theirs", base)
    theirs = commit(repo, case.theirs, "theirs")
    git(repo, "checkout", "-q", "ours")
    assert git(repo, "merge-base", ours, theirs).strip() == base
    merged = command("git", "-C", str(repo), "merge", "--no-ff", "--no-commit", theirs, check=False)
    assert merged.returncode in (0, 1), merged.stdout + merged.stderr
    assert git(repo, "rev-parse", "MERGE_HEAD").strip() == theirs
    commits = (base, ours, theirs)
    objects = tuple(git(repo, "rev-parse", f"{oid}:{PATH}").strip() for oid in commits)
    wires = tuple(git(repo, "cat-file", "blob", oid) for oid in objects)
    stages = {}
    for line in git(repo, "ls-files", "--stage", PATH).splitlines():
        metadata, path = line.split("\t")
        mode, oid, stage = metadata.split()
        assert mode == "100644" and path == PATH
        stages[int(stage)] = oid
    if merged.returncode:
        assert stages == dict(zip((1, 2, 3), objects, strict=True))
    else:
        assert set(stages) == {0}
    git(repo, "merge", "--abort")
    return commits, objects, wires, stages


def merge_values(parent_values):
    result = []
    for base, ours, theirs in zip(*parent_values, strict=True):
        if ours == theirs or theirs == base:
            result.append(ours)
        elif ours == base:
            result.append(theirs)
        else:
            return None
    return tuple(result)


def verify_candidate(repo, policy, parents, values):
    wire = encode(Snapshot(2, values))
    blob = git(repo, "hash-object", "-w", "--stdin", data=wire).strip()
    tree = git(repo, "mktree", data=f"100644 blob {blob}\t{PATH}\n").strip()
    candidate = git(repo, "commit-tree", tree, "-p", parents[0], "-p", parents[1], "-m", policy).strip()
    branch = f"candidate-{policy}"
    git(repo, "update-ref", f"refs/heads/{branch}", candidate)
    clone = repo.with_name(f"{repo.name}-{policy}")
    command("git", "clone", "-q", "--no-local", "--single-branch", "--branch", branch, str(repo), str(clone))
    assert git(clone, "rev-list", "--parents", "-n", "1", "HEAD").split() == [candidate, *parents]
    assert git(clone, "ls-tree", "--name-only", "HEAD").splitlines() == [PATH]
    checked = (clone / PATH).read_bytes().decode()
    assert checked == wire and import_python(checked) == values
    strict, = read_node([("exact_bound", checked)])
    assert strict == {"status": "accepted", "version": 2, "digest": root(values),
                      "nodes": [str(value) for value in values]}
    git(clone, "fsck", "--full", "--no-progress")
    return {"commit": candidate, "tree": tree, "blob": blob, "root": strict["digest"], "wire_sha256": digest(wire.encode())}


def run_case(repo, case):
    commits, blobs, wires, stages = make_history(repo, case)
    observations = read_node([(policy, wire) for policy in POLICIES for wire in wires])
    policies = {}
    for index, policy in enumerate(POLICIES):
        inputs = observations[3 * index:3 * (index + 1)]
        failure = next((row["status"] for row in inputs if row["status"] != "accepted"), None)
        if failure:
            policies[policy] = {"status": failure, "class": "valid_refused" if case.expected else "expected_refusal",
                                "inputs": inputs}
            continue
        parent_values = [tuple(map(int, row["nodes"])) for row in inputs]
        for values, row, wire in zip(parent_values, inputs, wires, strict=True):
            assert root(values) == row["digest"]
            if policy == "exact_bound":
                assert import_python(wire) == values
        candidate = merge_values(parent_values)
        if candidate is None:
            policies[policy] = {"status": "conflict", "class": "valid_refused" if case.expected else "expected_refusal",
                                "inputs": inputs}
            continue
        classification = "exact" if candidate == case.expected else "wrong_published"
        artifact = verify_candidate(repo, policy, commits[1:], candidate)
        policies[policy] = {"status": "merged", "class": classification, "inputs": inputs,
                            "artifact": artifact, "candidate": [str(value) for value in candidate]}
    strict = policies["exact_bound"]
    assert strict["status"] == case.strict_status, (case.name, strict)
    assert strict["class"] == ("exact" if case.expected else "expected_refusal"), (case.name, strict)
    return {"case": case.name, "parents": commits, "parent_blobs": blobs, "parent_wires": wires,
            "parent_wire_sha256": [digest(wire.encode()) for wire in wires], "git_index": stages,
            "expected": None if case.expected is None else [str(value) for value in case.expected], "policies": policies}


def run(directory):
    rows = []
    for case in SCENARIOS:
        repo = directory / case.name
        repo.mkdir()
        rows.append(run_case(repo, case))
    counts = ("exact", "valid_refused", "wrong_published", "expected_refusal")
    metrics = {policy: {kind: sum(row["policies"][policy]["class"] == kind for row in rows) for kind in counts}
               for policy in POLICIES}
    assert metrics["rounded"]["wrong_published"] > metrics["exact_unbound"]["wrong_published"] > 0
    assert sum(len(row["git_index"]) == 1 for row in rows) > 0
    assert rows[0]["parent_blobs"][0] != rows[0]["parent_blobs"][1]
    assert rows[0]["policies"]["exact_bound"]["inputs"][0]["digest"] == rows[0]["policies"]["exact_bound"]["inputs"][1]["digest"]
    return {"schema": "llmlang-rt24-versioned-i64-merge/1", "python": platform.python_version(),
            "git": command("git", "--version").stdout.strip(), "node": command("node", "--version").stdout.strip(),
            "v8": command("node", "-p", "process.versions.v8").stdout.strip(),
            "sources": {name: digest((HERE / name).read_bytes()) for name in ("run.py", "read.js")},
            "scenarios": len(rows), "metrics": metrics, "observations": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-i64-") as scratch:
        print(json.dumps(run(Path(scratch)), indent=2))
