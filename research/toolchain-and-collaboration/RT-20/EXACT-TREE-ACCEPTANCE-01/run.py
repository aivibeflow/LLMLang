"""Replay exact-tree acceptance and retries with native Git ref transactions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from threading import Barrier

HERE = Path(__file__).resolve().parent
HEAD = "refs/heads/research/all"
RECEIPTS = "refs/llmlang/research/all/receipts/"
VALIDATOR = "typed-add-v1"
ENV = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "LLMLang fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "LLMLang fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2026-11-25T12:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-11-25T12:00:00+00:00",
    "LC_ALL": "C",
}


def git(repo, *args, payload=None, check=True):
    result = subprocess.run(
        ["git", "-c", "core.filesRefLockTimeout=1000", *args], cwd=repo,
        input=payload, text=True, capture_output=True, env=ENV, check=check, timeout=15,
    )
    return result.stdout.strip() if check else result


def lookup(repo, ref):
    answer = git(repo, "rev-parse", "--quiet", "--verify", ref, check=False)
    if answer.returncode == 1:
        return None
    answer.check_returncode()
    return answer.stdout.strip()


@dataclass(frozen=True)
class Request:
    key: str
    baseline: str
    tree: str

    @property
    def receipt(self):
        return RECEIPTS + sha256(self.key.encode()).hexdigest()

    @property
    def text(self):
        return json.dumps({"operation": self.key, "baseline": self.baseline,
                           "tree": self.tree, "validator": VALIDATOR}, sort_keys=True)


def tree(repo, required, implemented, note=None):
    entries = {"contract.json": json.dumps({"add": required}),
               "implementation.txt": str(implemented)}
    if note is not None:
        entries["notes.txt"] = note
    rows = []
    for path, content in sorted(entries.items()):
        blob = git(repo, "hash-object", "-w", "--stdin", payload=content + "\n")
        rows.append(f"100644 blob {blob}\t{path}\n")
    return git(repo, "mktree", payload="".join(rows))


def validates(repo, candidate):
    members = set(git(repo, "ls-tree", "--name-only", candidate).splitlines())
    if not {"contract.json", "implementation.txt"} <= members <= {
        "contract.json", "implementation.txt", "notes.txt",
    }:
        return False
    try:
        contract = json.loads(git(repo, "show", candidate + ":contract.json"))
        implementation = int(git(repo, "show", candidate + ":implementation.txt"))
    except ValueError:
        return False
    return (
        isinstance(contract, dict) and set(contract) == {"add"}
        and type(contract["add"]) is int and contract["add"] == implementation
    )


def check_receipt(repo, request, commit):
    if git(repo, "show", "-s", "--format=%B", commit) != request.text:
        return "key-conflict", None
    parents = git(repo, "show", "-s", "--format=%P", commit).split()
    exact_tree = git(repo, "show", "-s", "--format=%T", commit)
    if parents != [request.baseline] or exact_tree != request.tree:
        return "receipt-mismatch", None
    return "replayed", commit


def publish(repo, request, after_validation=lambda: None):
    prior = lookup(repo, request.receipt)
    if prior is not None:
        return check_receipt(repo, request, prior)
    if not validates(repo, request.tree):
        return "invalid", None

    after_validation()
    commit = git(repo, "commit-tree", request.tree, "-p", request.baseline,
                 payload=request.text + "\n")
    result = git(repo, "update-ref", "--stdin", check=False, payload=(
        f"start\nupdate {HEAD} {commit} {request.baseline}\n"
        f"create {request.receipt} {commit}\nprepare\ncommit\n"
    ))
    if result.returncode == 0:
        return "published", commit
    prior = lookup(repo, request.receipt)
    if prior is not None:
        return check_receipt(repo, request, prior)
    if lookup(repo, HEAD) != request.baseline:
        return "stale-baseline", None
    return "retry", None


def setup(repo, object_format, ref_format):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=research/all",
        f"--object-format={object_format}", f"--ref-format={ref_format}")
    base = git(repo, "commit-tree", tree(repo, 0, 0), payload="baseline\n")
    git(repo, "update-ref", HEAD, base)
    git(repo, "read-tree", "-u", "--reset", base)
    return base


def assert_commit(repo, request, commit):
    assert lookup(repo, request.receipt) == commit
    observed = git(repo, "cat-file", "-p", commit).splitlines()
    assert observed[:2] == [f"tree {request.tree}", f"parent {request.baseline}"]
    assert json.loads(observed[-1]) == json.loads(request.text)


def history_size(repo):
    return int(git(repo, "rev-list", "--count", HEAD))


def commit_objects(repo):
    listing = git(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objecttype)")
    return listing.splitlines().count("commit")


def single(repo, base):
    invalid = Request("invalid", base, tree(repo, 1, 2))
    count = commit_objects(repo)
    refused = publish(repo, invalid)
    assert refused == ("invalid", None)
    assert commit_objects(repo) == count
    assert lookup(repo, HEAD) == base and lookup(repo, invalid.receipt) is None

    request = Request("exact", base, tree(repo, 3, 3))

    def change_worktree():
        (repo / "implementation.txt").write_text("999\n")

    status, commit = publish(repo, request, change_worktree)
    assert status == "published" and lookup(repo, HEAD) == commit
    assert_commit(repo, request, commit)
    assert git(repo, "show", commit + ":implementation.txt") == "3"
    assert (repo / "implementation.txt").read_text() == "999\n"
    assert publish(repo, request) == ("replayed", commit)

    same_key = Request(request.key, base, tree(repo, 3, 3, "same behavior, different tree"))
    assert publish(repo, same_key) == ("key-conflict", None)
    stale = Request("stale", base, tree(repo, 4, 4))
    assert publish(repo, stale) == ("stale-baseline", None)
    assert lookup(repo, stale.receipt) is None and history_size(repo) == 2

    next_request = Request("next", commit, tree(repo, 5, 5))
    status, later = publish(repo, next_request)
    assert status == "published" and lookup(repo, HEAD) == later
    assert publish(repo, request) == ("replayed", commit)
    assert history_size(repo) == 3
    return {
        "failed_validation": "invalid with no commit object or ref updates",
        "worktree_changed_after_validation": "frozen tree published",
        "same_operation_retry": "original commit",
        "same_key_different_tree": "key-conflict",
        "stale_base": "stale-baseline without receipt",
        "retry_after_new_head": "original commit without head change",
    }


def race(repo, base, same_key):
    first = Request("concurrent-1", base, tree(repo, 6, 6))
    second = first if same_key else Request("concurrent-2", base, tree(repo, 7, 7))
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as workers:
        jobs = [(request, workers.submit(publish, repo, request, lambda: barrier.wait(timeout=8)))
                for request in (first, second)]
        initial = [(request, job.result()) for request, job in jobs]
    final = [(request, publish(repo, request) if result[0] == "retry" else result)
             for request, result in initial]
    statuses = sorted(result[0] for _, result in final)
    expected = ["published", "replayed" if same_key else "stale-baseline"]
    assert statuses == expected and history_size(repo) == 2
    head = lookup(repo, HEAD)
    for request, (status, commit) in final:
        if status == "stale-baseline":
            assert commit is None and lookup(repo, request.receipt) is None
        else:
            assert commit == head
            assert_commit(repo, request, commit)
    return statuses


def mismatched_receipt(repo, base):
    request = Request("test-receipt", base, tree(repo, 1, 1))
    different_tree = tree(repo, 2, 2)
    stored = git(repo, "commit-tree", different_tree, "-p", base,
                 payload=request.text + "\n")
    git(repo, "update-ref", request.receipt, stored)
    result = publish(repo, request)
    assert result == ("receipt-mismatch", None)
    assert lookup(repo, HEAD) == base and lookup(repo, request.receipt) == stored
    return result[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    records = []
    for object_format in ("sha1", "sha256"):
        for ref_format in ("files", "reftable"):
            with TemporaryDirectory(prefix="llmlang-exact-tree-") as directory:
                repo = Path(directory)
                cases = {"ordinary": single, "mismatched-receipt": mismatched_receipt}
                for name, same_key in (("same-key-race", True), ("distinct-key-race", False)):
                    cases[name] = lambda repo, base, same_key=same_key: race(repo, base, same_key)
                for name, run in cases.items():
                    case = repo / name
                    case.mkdir()
                    base = setup(case, object_format, ref_format)
                    records.append({"object_format": object_format, "ref_format": ref_format,
                                    "case": name, "outcome": run(case, base)})
    args.output.write_text(json.dumps({"git": git(HERE, "--version"), "cases": records}, indent=2) + "\n")


if __name__ == "__main__":
    main()
