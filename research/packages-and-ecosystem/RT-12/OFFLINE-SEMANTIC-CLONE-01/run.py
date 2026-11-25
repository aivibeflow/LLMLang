#!/usr/bin/env python3
"""Compare selected-tree portability with explicit historical source access."""

from collections import Counter
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
RESTORE = HERE.parent / "CLOSED-GRAPH-BACKUP-01" / "run.py"
spec = spec_from_file_location("offline_graph_reader", RESTORE)
prior = module_from_spec(spec)
spec.loader.exec_module(prior)

BRANCH = "research/all"
ENV = os.environ | {
    "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
}


def git(directory, *args, required=True):
    result = subprocess.run(
        ["git", *args], cwd=directory, env=ENV, capture_output=True, timeout=30,
    )
    if required and result.returncode:
        raise RuntimeError(result.stderr.decode())
    return result


def commit(origin, label, root, objects, layout):
    object_path = origin / "objects"
    object_path.mkdir(exist_ok=True)
    for existing in object_path.iterdir():
        existing.unlink()
    pack = origin / "bundle.json"
    pack.unlink(missing_ok=True)
    if layout == "files":
        for address, payload in objects.items():
            (object_path / address).write_bytes(payload)
    if layout == "bundle":
        pack.write_bytes(prior.encode({name: data.decode("utf-8") for name, data in objects.items()}))
    (origin / "manifest.json").write_bytes(prior.encode({"root": root, "layout": layout}))
    git(origin, "add", "--all")
    git(origin, "-c", "commit.gpgsign=false", "commit", "-m", label)
    return git(origin, "rev-parse", "HEAD").stdout.decode().strip()


def prepared(origin):
    objects = {}

    def new(kind, value, references=()):
        payload = prior.encode({"kind": kind, "value": value, "references": references})
        address = prior.digest(payload)
        objects[address] = payload
        return address

    shared = new("contract", {"type": "integer", "rule": "pure result"})
    revisions = {}
    for version in (1, 2):
        implementation = new("implementation", {"offset": version}, (shared,))
        revisions[version] = new("snapshot", {"revision": version}, (implementation,))
    origin.mkdir()
    git(origin, "init", "-q", "--object-format=sha1", "--initial-branch", BRANCH)
    first, second = revisions[1], revisions[2]
    first_objects = prior.closure(first, objects.__getitem__)
    second_objects = prior.closure(second, objects.__getitem__)
    return revisions, (first_objects, second_objects), {
        "first": commit(origin, "First closed revision", first, first_objects, "files"),
        "second": commit(origin, "Second closed revision", second, second_objects, "files"),
        "manifest-only": commit(origin, "Pointer without closure", second, {}, "files"),
        "bundle": commit(origin, "Closed portable bundle", second, second_objects, "bundle"),
    }


def checkout(root, origin, label, revision, *, shallow=False):
    path = root / label
    args = ["clone", "-q", "--no-local", "--single-branch", "--no-tags", "--branch", BRANCH]
    if shallow:
        args.extend(("--depth", "1"))
    git(root, *args, origin.as_uri(), str(path))
    if not shallow:
        git(path, "checkout", "-q", "--detach", revision)
    if git(path, "rev-parse", "HEAD").stdout.decode().strip() != revision:
        raise AssertionError("Unexpected checkout revision")
    if (path / ".git" / "objects" / "info" / "alternates").exists():
        raise AssertionError("Clone shares object storage")
    if list((path / ".git" / "objects" / "pack").glob("*.promisor")):
        raise AssertionError("Clone relies on promised objects")
    profile = git(path, "rev-parse", "--is-shallow-repository").stdout.decode().strip()
    if profile != str(shallow).lower():
        raise AssertionError("Clone has the wrong history scope")
    git(path, "remote", "remove", "origin")
    return path


def archive(root, origin, label, revision):
    path = root / label
    path.mkdir()
    data = git(origin, "archive", revision).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(path, filter="data")
    return path


def current(path, expected):
    manifest = json.loads((path / "manifest.json").read_bytes())
    if manifest["root"] != expected:
        raise prior.RestoreError("unexpected selected root")
    if manifest["layout"] == "files":
        return prior.closure(expected, lambda address: (path / "objects" / address).read_bytes())
    if manifest["layout"] != "bundle":
        raise prior.RestoreError("unrecognized current storage layout")
    objects = {address: text.encode("utf-8")
               for address, text in json.loads((path / "bundle.json").read_bytes()).items()}
    verified = prior.closure(expected, objects.__getitem__)
    if objects != verified:
        raise prior.RestoreError("unexpected bundle closure")
    return verified


def historical(path, revision, expected):
    result = git(path, "show", f"{revision}:manifest.json", required=False)
    if result.returncode:
        raise prior.RestoreError("historical tree unavailable")
    manifest = json.loads(result.stdout)
    if manifest["root"] != expected:
        raise prior.RestoreError("historical root mismatch")
    if manifest["layout"] != "files":
        raise prior.RestoreError("unsupported historical carrier")

    def load(address):
        blob = git(path, "show", f"{revision}:objects/{address}", required=False)
        if blob.returncode:
            raise FileNotFoundError(address)
        return blob.stdout

    return prior.closure(expected, load)


def compare():
    cases = []
    with TemporaryDirectory(prefix="llmlang-offline-semantic-clone-") as directory:
        root = Path(directory)
        source = root / "origin"
        revisions, objects, commits = prepared(source)
        first, second = revisions[1], revisions[2]
        closed = checkout(root, source, "full-closed", commits["second"])
        pointer = checkout(root, source, "full-pointer", commits["manifest-only"])
        archived_pointer = archive(root, source, "pointer-archive", commits["manifest-only"])
        archived_closed = archive(root, source, "closed-archive", commits["second"])
        shallow_bundle = checkout(root, source, "shallow-bundle", commits["bundle"], shallow=True)
        archived_bundle = archive(root, source, "bundle-archive", commits["bundle"])
        source.rename(root / "origin-unavailable")

        def check(label, desired, operation, expected_objects=None):
            try:
                admitted = operation()
            except prior.RestoreError as error:
                outcome = str(error)
                detail = {}
            else:
                outcome = "restored"
                if admitted != expected_objects:
                    raise AssertionError(f"{label}: restored wrong bytes")
                detail = {"objects": sorted(admitted), "logical_bytes": sum(map(len, admitted.values()))}
            if outcome != desired:
                raise AssertionError((label, outcome, desired))
            cases.append({"case": label, "outcome": outcome, **detail})

        check("current closure in independent full clone", "restored", lambda: current(closed, second), objects[1])
        check("historical closure in independent full clone", "restored",
              lambda: historical(closed, commits["first"], first), objects[0])
        check("current tree archive without Git history", "restored",
              lambda: current(archived_closed, second), objects[1])
        check("pointer-only current tree despite complete history", "missing object", lambda: current(pointer, second))
        check("pointer-only archive with no history", "missing object", lambda: current(archived_pointer, second))
        check("approved historical carrier for exact pointer root", "restored",
              lambda: historical(pointer, commits["second"], second), objects[1])
        check("wrong historical root remains refused", "historical root mismatch",
              lambda: historical(pointer, commits["first"], second))
        check("shallow clone contains closed current bundle", "restored",
              lambda: current(shallow_bundle, second), objects[1])
        check("shallow clone cannot restore pruned historical revision", "historical tree unavailable",
              lambda: historical(shallow_bundle, commits["first"], first))
        check("bundle tree archive restores without any database", "restored",
              lambda: current(archived_bundle, second), objects[1])
        version = git(root, "--version").stdout.decode().strip()
    return {
        "schema": "llmlang-offline-semantic-clone/1", "python": platform.python_version(), "git": version,
        "source_sha256": {name: sha256(path.read_bytes()).hexdigest()
                          for name, path in (("run.py", Path(__file__)), ("closed_graph_reader", RESTORE))},
        "commits": commits, "roots": revisions, "cases": cases,
        "counts": dict(Counter(row["outcome"] for row in cases)),
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
