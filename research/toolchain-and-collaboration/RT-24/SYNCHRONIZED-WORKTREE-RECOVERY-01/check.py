"""Exercise synchronized worktree materialization and reachable exact Git receipts."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


BASE = "525bfbe0a935728710c9c7ade026bfe5687f4473"
REF = "refs/heads/main"
RECEIPT = "llmlang-receipt.json"
INITIAL = {
    "semantic.json": b'{"operation":"old","provider":1}\n',
    "mapping.json": b'{"entry":"old"}\n',
    "selected.txt": b"old ordinary file\n",
    "retain.txt": b"unchanged\n",
}
SELECTED = {
    "semantic.json": b'{"operation":"new","provider":2}\n',
    "mapping.json": b'{"entry":"new"}\n',
    "selected.txt": b"new ordinary file\n",
}


@dataclass(frozen=True)
class Request:
    expected_ref: str
    generation: str
    semantic: str
    mapping: str
    evidence: str
    regular_files: tuple[tuple[str, str], ...]


def sha(data):
    return sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def git(repo, *args, input=None, check=True):
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "LC_ALL": "C",
           "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@local.example",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@local.example",
           "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"}
    return subprocess.run(["git", *args], cwd=repo, input=input, capture_output=True, check=check,
                          env=env, timeout=15)


def read_git(repo, *args, input=None):
    return git(repo, *args, input=input).stdout


def oid(repo, ref):
    return read_git(repo, "rev-parse", ref).decode().strip()


def generation(repo):
    return sha(encoded({path: sha((repo / path).read_bytes()) for path in sorted(INITIAL)}))


def stage(repo, files):
    for path, content in files.items():
        (repo / path).write_bytes(content)
    git(repo, "add", "--", *sorted(files))


def initialize(repo, fmt):
    git(repo, "init", "-q", "-b", "main", f"--object-format={fmt}")
    stage(repo, INITIAL)
    git(repo, "commit", "-qm", "baseline")
    return oid(repo, REF)


def prepared(repo, request, partial=False):
    if oid(repo, REF) != request.expected_ref or generation(repo) != request.generation:
        return None
    record = encoded({"request": asdict(request), "operation": sha(encoded(asdict(request)))})
    if partial:
        stage(repo, {"semantic.json": SELECTED["semantic.json"]})
    else:
        stage(repo, {**SELECTED, RECEIPT: record})
    tree = oid(repo, read_git(repo, "write-tree").decode().strip())
    expected = {**INITIAL, **SELECTED, RECEIPT: record}
    if set(read_git(repo, "ls-tree", "-r", "--name-only", tree).decode().splitlines()) != set(expected):
        return None
    for path, data in expected.items():
        if git(repo, "show", f"{tree}:{path}", check=False).stdout != data:
            return None
    return read_git(repo, "commit-tree", tree, "-p", request.expected_ref,
                    input=b"exact fixture publication\n").decode().strip()


def recover(repo, request):
    operation = sha(encoded(asdict(request)))
    for commit in read_git(repo, "rev-list", REF).decode().splitlines():
        entry = git(repo, "show", f"{commit}:{RECEIPT}", check=False)
        if entry.returncode:
            continue
        receipt = json.loads(entry.stdout)
        if receipt["operation"] != operation:
            continue
        parent = oid(repo, f"{commit}^")
        if parent != request.expected_ref or receipt != json.loads(encoded({"request": asdict(request),
                                                                           "operation": operation})):
            raise ValueError("receipt scope mismatch")
        selected_digests = {"semantic.json": request.semantic, "mapping.json": request.mapping,
                            **dict(request.regular_files)}
        for path, digest in selected_digests.items():
            if sha(read_git(repo, "show", f"{commit}:{path}")) != digest:
                raise ValueError("published content mismatch")
        return commit
    return None


def child(repo, new, former, interruption):
    if interruption == "before":
        os._exit(81)
    git(repo, "update-ref", REF, new, former)
    if interruption == "after":
        os._exit(82)


def check_case(repo, fmt, mode):
    original = initialize(repo, fmt)
    request = Request(original, generation(repo), sha(SELECTED["semantic.json"]),
                      sha(SELECTED["mapping.json"]), "checked-fixture-obligation",
                      (("selected.txt", sha(SELECTED["selected.txt"])),))
    if mode == "stale-worktree":
        (repo / "retain.txt").write_bytes(b"independent late edit\n")
    elif mode == "stale-ref":
        git(repo, "commit", "--allow-empty", "-qm", "intervening ref")
    elif mode == "unexpected-staged":
        stage(repo, {"extra.txt": b"out-of-scope staged content\n"})
    old = oid(repo, REF)
    candidate = prepared(repo, request, partial=mode == "partial-export")
    if candidate is None:
        assert mode in {"stale-worktree", "stale-ref", "partial-export", "unexpected-staged"}
        assert oid(repo, REF) == old and recover(repo, request) is None
        return {"initial": "withheld", "retry": "uncommitted"}
    interrupt = {"before-ref": "before", "after-ref": "after"}.get(mode, "none")
    request_call = [sys.executable, "-B", __file__, "child", repo, candidate, original, interrupt]
    status = subprocess.run(request_call, check=False, timeout=15).returncode
    assert status == {"before": 81, "after": 82, "none": 0}[interrupt]
    first = recover(repo, request)
    assert first == (None if interrupt == "before" else candidate)
    if first is None:
        assert oid(repo, REF) == original and oid(repo, "HEAD") == original
        assert all((repo / path).read_bytes() == value for path, value in SELECTED.items())
        assert read_git(repo, "write-tree").decode().strip() == oid(repo, f"{candidate}^{{tree}}")
        child(repo, candidate, original, "none")
    else:
        assert oid(repo, REF) == candidate
    assert recover(repo, request) == candidate
    assert len(read_git(repo, "rev-list", REF).splitlines()) == 2
    assert not read_git(repo, "status", "--porcelain")
    clone = repo.parent / "clone"
    git(repo.parent, "clone", "-q", "--no-local", str(repo), str(clone))
    git(clone, "remote", "remove", "origin")
    assert recover(clone, request) == candidate and not read_git(clone, "status", "--porcelain")
    return {"initial": "uncommitted" if first is None else "committed-exact",
            "retry": "committed-exact", "clean_clone": True, "committed_history_length": 2}


def run():
    rows = {}
    for fmt, mode in product(("sha1", "sha256"), ("normal", "before-ref", "after-ref", "partial-export",
                                                  "stale-ref", "stale-worktree", "unexpected-staged")):
        with TemporaryDirectory() as folder:
            repo = Path(folder) / "original"
            repo.mkdir()
            rows[f"{fmt}/{mode}"] = check_case(repo, fmt, mode)
    return {
        "baseline": BASE, "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "runner_sha256": sha(Path(__file__).read_bytes()), "cases": rows,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        child(Path(sys.argv[2]), *sys.argv[3:])
    else:
        print(json.dumps(run(), sort_keys=True, indent=2))
