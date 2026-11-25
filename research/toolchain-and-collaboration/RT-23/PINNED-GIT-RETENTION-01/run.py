"""Compare pinned Git commits with explicit native retention after branch rewrite."""
import argparse
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt24_merge_tree_gate as tree

BRANCH = recovery.BRANCH
LEASE = "refs/llmlang/readers/first"
PEER = "refs/llmlang/readers/second"
JOURNAL = "refs/llmlang/journal/main"
MODES = ("oid-only", "verified-lease", "late-verified-lease", "late-explicit-lease", "journal-parent")


def git(repo, *args, stdin=None):
    return tree.git(repo, *args, stdin=stdin).decode().strip()


def transaction(repo, commands):
    records = ("start", *commands, "prepare", "commit", "")
    git(repo, "update-ref", "--stdin", stdin="\n".join(records).encode())


def initialize(repo, backend):
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet", "--template=", "--initial-branch=main",
        "--object-format=sha1", f"--ref-format={backend}")
    git(repo, "config", "core.logAllRefUpdates", "false")

    def record(generation):
        return [tree.row("contract", tree.declaration("contract", "contract:leased", {"generation": generation}))]

    old = tree.commit(repo, {tree.MANIFEST: tree.manifest(tree.CONTRACT), tree.CONTRACT: record("old")})
    child = tree.commit(repo, {tree.CONTRACT: record("new")})
    next_tree = git(repo, "rev-parse", f"{child}^{{tree}}")
    replacement = recovery.commit_object(repo, next_tree, (), "unrelated replacement")
    git(repo, "update-ref", BRANCH, old, child)
    assert git(repo, "for-each-ref", "--format=%(refname)") == BRANCH
    assert git(repo, "reflog", "show", "--all") == ""
    return old, replacement, next_tree


def observation(repo, commit):
    try:
        git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
    except subprocess.CalledProcessError as error:
        assert b"Not a valid object name" in error.stderr
        return None
    return tree.import_closed(tree.read_inventory(repo, commit))[1].root_hash


def collect(repo):
    # Every fixture has one controller. Mutations are finished before pruning.
    git(repo, "gc", "--prune=now", "--quiet")
    git(repo, "fsck", "--full")
    assert git(repo, "reflog", "show", "--all") == ""


def rejects(action):
    try:
        action()
    except subprocess.CalledProcessError as error:
        assert error.returncode != 0
    else:
        raise AssertionError("expected the native ref transaction to refuse")


def clone_view(repository, directory, pin, kept):
    clone = directory / "clone"
    git(directory, "clone", "--quiet", "--no-local", str(repository), str(clone))
    absent = observation(clone, pin) is None
    assert absent and recovery.ref(clone, kept) is None
    git(clone, "fetch", "--quiet", "origin", f"{kept}:{kept}")
    git(clone, "fsck", "--full")
    return {"default_clone_lacks_pin": absent, "after_explicit_fetch": observation(clone, pin)}


def trial(directory, backend, mode):
    repo = directory / "repo"
    old, next_commit, next_tree = initialize(repo, backend)
    prior = observation(repo, old)
    later = observation(repo, next_commit)
    assert prior is not None and later is not None and prior != later
    retention_ref = None
    if mode == "verified-lease":
        transaction(repo, (f"verify {BRANCH} {old}", f"create {LEASE} {old}", f"create {PEER} {old}"))
        retention_ref = LEASE
    if mode == "journal-parent":
        journal = recovery.commit_object(repo, next_tree, (next_commit, old), "retain exact prior semantic state")
        transaction(repo, (f"verify {BRANCH} {old}", f"create {JOURNAL} {journal}"))
        retention_ref = JOURNAL
    git(repo, "update-ref", BRANCH, next_commit, old)
    assert git(repo, "rev-list", BRANCH) == next_commit
    after_rewrite = observation(repo, old)
    assert after_rewrite == prior

    refused_stale = mode == "late-verified-lease"
    if refused_stale:
        rejects(lambda: transaction(repo, (f"verify {BRANCH} {old}", f"create {LEASE} {old}")))
        assert recovery.ref(repo, LEASE) is None
    if mode == "late-explicit-lease":
        transaction(repo, (f"create {LEASE} {old}",))
        retention_ref = LEASE

    collect(repo)
    retained = observation(repo, old)
    no_lease_after_prune = False
    if retention_ref is None:
        assert retained is None
        rejects(lambda: transaction(repo, (f"create {LEASE} {old}",)))
        assert recovery.ref(repo, LEASE) is None
        no_lease_after_prune = True
    else:
        assert retained == prior
    assert observation(repo, next_commit) == later

    fetched = None
    if mode in {"verified-lease", "journal-parent"}:
        fetched = clone_view(repo, directory, old, retention_ref)
        assert fetched["after_explicit_fetch"] == prior
    peer_retains = None
    if mode == "verified-lease":
        git(repo, "update-ref", "-d", LEASE, old)
        collect(repo)
        peer_retains = observation(repo, old)
        assert peer_retains == prior
        git(repo, "update-ref", "-d", PEER, old)
    if mode == "late-explicit-lease":
        git(repo, "update-ref", "-d", LEASE, old)
    if mode == "journal-parent":
        git(repo, "update-ref", "-d", JOURNAL, journal)
    collect(repo)
    after_release = observation(repo, old)
    assert after_release is None and observation(repo, next_commit) == later
    return {
        "old_commit": old, "old_root": prior, "published_commit": next_commit, "published_root": later,
        "after_rewrite_before_gc": after_rewrite, "after_gc": retained, "after_release_and_gc": after_release,
        "peer_retains_after_first_release": peer_retains, "stale_verified_acquisition_rejected": refused_stale,
        "acquisition_after_prune_rejected": no_lease_after_prune, "clone": fetched,
    }


def replay(directory):
    version = git(directory, "--version")
    assert version == "git version 2.52.0" and sys.platform == "linux"
    cases = {}
    for backend, mode in product(("files", "reftable"), MODES):
        name = f"{backend}/{mode}"
        cases[name] = trial(directory / f"{backend}-{mode}", backend, mode)
    assert len({row["old_root"] for row in cases.values()}) == 1
    assert len({row["published_root"] for row in cases.values()}) == 1
    return {"format": "rt23-pinned-git-retention/1", "python": sys.version.split()[0],
            "git": version, "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-pinned-git-retention-") as scratch:
        data = replay(Path(scratch))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
