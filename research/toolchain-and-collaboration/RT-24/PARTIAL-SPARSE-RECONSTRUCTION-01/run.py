#!/usr/bin/env python3
"""Compare exact Git snapshot reconstruction with sparse trees and promised blobs."""

from dataclasses import dataclass
from hashlib import new, sha256
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
DOMAIN = "llmlang-rt24-partial-sparse-reconstruction/1"
ROOT = "entry/root.json"
CALLER = "callers/start.json"
PROVIDER = "providers/delta.json"
RELEVANT = (ROOT, CALLER, PROVIDER)
FORMATS = ("sha1", "sha256")
POLICIES = ("worktree", "path_cache", "pinned_git", "pinned_git_cache")
INPUTS = (-3, 0, 4, 19)
OLD = 11
CURRENT = 17


@dataclass(frozen=True)
class Case:
    name: str
    partial: bool = False
    sparse: bool = False
    shallow: bool = False
    past_cache: str = "none"
    hydrate: bool = False
    broken: bool = False
    dirty: bool = False
    expected: str = "exact"


CASES = (
    Case("normal_full_clone"),
    Case("sparse_checkout_with_full_objects", sparse=True),
    Case("shallow_current_tree", shallow=True),
    Case("dirty_provider_overlay", dirty=True),
    Case("offline_partial_cold", partial=True, expected="unavailable"),
    Case("offline_sparse_partial", partial=True, sparse=True, expected="unavailable"),
    Case("hydrate_exact_promised_blobs", partial=True, sparse=True, hydrate=True),
    Case("offline_exact_cache", partial=True, sparse=True, past_cache="current"),
    Case("offline_stale_path_cache", partial=True, sparse=True, past_cache="old", expected="unavailable"),
    Case("offline_corrupt_object_cache", partial=True, sparse=True, past_cache="corrupt", expected="corrupt"),
    Case("committed_missing_provider", broken=True, past_cache="current", expected="invalid"),
)


class Incomplete(ValueError):
    def __init__(self, status, path):
        super().__init__(status, path)
        self.status = status
        self.path = path


def digest(data):
    return sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def git_blob_id(object_format, data):
    return new(object_format, b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(repo, *arguments, lazy=False, check=True):
    return subprocess.run(["git", "-C", str(repo), *arguments], check=check, capture_output=True, timeout=30,
                          env={**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                               "GIT_NO_LAZY_FETCH": "0" if lazy else "1", "GIT_ALLOW_PROTOCOL": "file",
                               "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                               "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                               "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"})


def oid(repo, ref):
    return git(repo, "rev-parse", ref).stdout.decode().strip()


def write(repo, path, value):
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(canonical(value))


def program(delta):
    return {ROOT: canonical({"entry": CALLER}), CALLER: canonical({"operation": "add", "provider": PROVIDER}),
            PROVIDER: canonical({"delta": delta})}


def make_source(repo, object_format):
    repo.mkdir()
    git(repo, "init", "-qb", "main", f"--object-format={object_format}")
    git(repo, "config", "uploadpack.allowFilter", "true")
    git(repo, "config", "uploadpack.allowReachableSHA1InWant", "true")
    write(repo, ROOT, {"entry": CALLER})
    write(repo, CALLER, {"operation": "add", "provider": PROVIDER})
    write(repo, PROVIDER, {"delta": OLD})
    write(repo, "ordinary/notes.json", {"note": "out of semantic scope"})
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "old")
    old = oid(repo, "HEAD")
    write(repo, PROVIDER, {"delta": CURRENT})
    git(repo, "add", PROVIDER)
    git(repo, "commit", "-qm", "current")
    current = oid(repo, "HEAD")
    git(repo, "checkout", "-qb", "broken")
    git(repo, "rm", "-q", PROVIDER)
    git(repo, "commit", "-qm", "remove reachable provider")
    broken = oid(repo, "HEAD")
    git(repo, "checkout", "-q", "main")
    return {"old": old, "current": current, "broken": broken}


def clone_source(parent, source, object_format, case):
    clone = parent / case.name
    flags = ["--single-branch", "--branch", "broken" if case.broken else "main"]
    if case.partial:
        flags.append("--filter=blob:none")
    if case.sparse or case.partial:
        flags.append("--no-checkout")
    if case.shallow:
        flags.append("--depth=1")
    git(parent, "clone", "-q", "--no-local", *flags, source.as_uri(), str(clone), lazy=True)
    if case.sparse:
        git(clone, "sparse-checkout", "set", "--cone", "entry", lazy=True)
        git(clone, "checkout", "-q", "--force", lazy=True)
    assert git(clone, "rev-parse", "--show-object-format").stdout.decode().strip() == object_format
    assert (git(clone, "rev-parse", "--is-shallow-repository").stdout == b"true\n") == case.shallow
    promisor = git(clone, "config", "--bool", "remote.origin.promisor", check=False)
    assert (promisor.stdout == b"true\n") == case.partial
    assert bool(list((clone / ".git/objects/pack").glob("*.promisor"))) == case.partial
    return clone


def inventory(repo, commit):
    rows = {}
    raw = git(repo, "ls-tree", "-rz", commit).stdout
    for line in raw.split(b"\0")[:-1]:
        metadata, path = line.split(b"\t", 1)
        mode, kind, object_id = metadata.decode().split()
        assert mode == "100644" and kind == "blob"
        rows[path.decode()] = object_id
    return rows


def local_blob(repo, object_id):
    result = git(repo, "cat-file", "blob", object_id, lazy=False, check=False)
    return result.stdout if result.returncode == 0 else None


def availability(repo, pinned):
    return {path: "absent" if path not in pinned else "present" if local_blob(repo, pinned[path]) is not None
            else "promised_unavailable" for path in RELEVANT}


def materialized(repo):
    return [path for path in RELEVANT if (repo / path).is_file()]


def caches(name, source, commits, object_format, pinned):
    if name == "none":
        return {}, {}
    old = name in ("old", "corrupt")
    snapshot = inventory(source, commits["old" if old else "current"])
    by_path = {path: local_blob(source, snapshot[path]) for path in RELEVANT}
    assert by_path == program(OLD if old else CURRENT)
    by_object = {snapshot[path]: value for path, value in by_path.items()}
    assert all(git_blob_id(object_format, value) == object_id for object_id, value in by_object.items())
    if name == "corrupt":
        by_object[pinned[PROVIDER]] = by_path[PROVIDER]
    return by_path, by_object


def import_graph(read):
    def document(path):
        value = read(path)
        parsed = json.loads(value)
        assert canonical(parsed) == value
        return parsed
    root = document(ROOT)
    assert root == {"entry": CALLER}
    member = document(root["entry"])
    assert member == {"operation": "add", "provider": PROVIDER}
    target = document(member["provider"])
    delta = target["delta"]
    assert target == {"delta": delta} and type(delta) is int
    semantic = digest(DOMAIN.encode() + b"\0" + canonical({"operation": "add", "delta": delta}))
    return {"status": "accepted", "semantic_root": semantic, "delta": delta, "results": [v + delta for v in INPUTS]}


def perform(policy, repo, object_format, pinned, by_path, by_object):
    reads = []

    def path_read(path):
        source = repo / path
        if source.is_file():
            reads.append((path, "worktree"))
            return source.read_bytes()
        if policy == "path_cache" and path in by_path:
            reads.append((path, "path_cache"))
            return by_path[path]
        raise Incomplete("unavailable", path)

    def object_read(path):
        if path not in pinned:
            raise Incomplete("invalid", path)
        object_id = pinned[path]
        raw = local_blob(repo, object_id)
        if raw is not None:
            assert git_blob_id(object_format, raw) == object_id
            reads.append((path, "git"))
            return raw
        if policy == "pinned_git_cache" and object_id in by_object:
            raw = by_object[object_id]
            if git_blob_id(object_format, raw) != object_id:
                raise Incomplete("corrupt", path)
            reads.append((path, "verified_object_cache"))
            return raw
        raise Incomplete("unavailable", path)

    try:
        result = import_graph(path_read if policy in ("worktree", "path_cache") else object_read)
    except Incomplete as failure:
        result = {"status": failure.status, "blocked_path": failure.path}
    return {**result, "reads": reads}


def run_case(directory, source, commits, object_format, case):
    repo = clone_source(directory, source, object_format, case)
    commit = oid(repo, "HEAD")
    assert commit == commits["broken" if case.broken else "current"]
    if case.dirty:
        write(repo, PROVIDER, {"delta": OLD})
        changed = git(repo, "diff", "--name-only", "-z", "HEAD").stdout
        assert changed == PROVIDER.encode() + b"\0"
    pinned = inventory(repo, commit)
    assert (PROVIDER not in pinned) == case.broken
    before = availability(repo, pinned)
    view = materialized(repo)
    expected_before = dict.fromkeys(RELEVANT, "present")
    if case.broken:
        expected_before[PROVIDER] = "absent"
    if case.partial:
        expected_before = dict.fromkeys(RELEVANT, "promised_unavailable")
        if case.sparse:
            expected_before[ROOT] = "present"
    assert before == expected_before, (case.name, before)
    assert view == ([ROOT] if case.sparse else [] if case.partial else [p for p in RELEVANT if p in pinned])
    if case.hydrate:
        for path, state in before.items():
            if state == "promised_unavailable":
                object_id = pinned[path]
                data = git(repo, "cat-file", "blob", object_id, lazy=True).stdout
                assert git_blob_id(object_format, data) == object_id
    after_hydration = availability(repo, pinned)
    assert after_hydration == (dict.fromkeys(RELEVANT, "present") if case.hydrate else before)
    by_path, by_object = caches(case.past_cache, source, commits, object_format, pinned)
    observed = {policy: perform(policy, repo, object_format, pinned, by_path, by_object) for policy in POLICIES}
    assert availability(repo, pinned) == after_hydration and materialized(repo) == view
    reference = import_graph(program(CURRENT).__getitem__)
    for result in observed.values():
        got = result["status"]
        if got == "accepted":
            matches = all(result[key] == expected for key, expected in reference.items())
            result["classification"] = "exact" if matches and not case.broken else "wrong_acceptance"
        else:
            result["classification"] = "available_refused" if case.expected == "exact" else "refused"
    strict = observed["pinned_git_cache"]
    assert (strict["classification"] if strict["status"] == "accepted" else strict["status"]) == case.expected
    return {"case": case.name, "format": object_format, "commit": commit, "tree": oid(repo, "HEAD^{tree}"),
            "inventory": pinned, "visible": view, "initial_availability": before, "hydrated_availability": after_hydration,
            "expected": case.expected, "dirty_overlay": case.dirty, "policies": observed}


def run(directory):
    rows = []
    for object_format in FORMATS:
        group = directory / object_format
        group.mkdir()
        source = group / "source"
        commits = make_source(source, object_format)
        for case in CASES:
            rows.append(run_case(group, source, commits, object_format, case))
    classifications = ("exact", "wrong_acceptance", "available_refused", "refused")
    metrics = {policy: {name: sum(row["policies"][policy]["classification"] == name for row in rows)
                        for name in classifications} for policy in POLICIES}
    assert metrics["path_cache"]["wrong_acceptance"] >= len(FORMATS) * 2
    assert metrics["pinned_git_cache"]["wrong_acceptance"] == metrics["pinned_git_cache"]["available_refused"] == 0
    return {"schema": DOMAIN, "python": platform.python_version(), "git": git(directory, "--version").stdout.decode().strip(),
            "source_sha256": digest(Path(__file__).read_bytes()), "object_formats": FORMATS, "scenarios": len(rows),
            "metrics": metrics, "observations": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-partial-sparse-") as scratch:
        outcome = run(Path(scratch))
    print(json.dumps(outcome, indent=2))
