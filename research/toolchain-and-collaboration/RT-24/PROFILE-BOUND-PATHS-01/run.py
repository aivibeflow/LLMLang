#!/usr/bin/env python3
"""Compare name-profile checks on native Git merges and clean Linux clones."""

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory
import unicodedata

HERE = Path(__file__).resolve().parent
POLICIES = ("physical", "ascii_paths", "unicode_paths", "unicode_prefixes")
ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
BASE_PATH = "repo.profile"


@dataclass(frozen=True)
class Case:
    name: str
    left: str
    right: str
    expected: str


CASES = (
    Case("ascii_disjoint", "src/alpha.ll", "src/beta.ll", "accepted"),
    Case("different_directories", "left/item.ll", "right/item.ll", "accepted"),
    Case("exact_shared_directory", "Src/util/A.ll", "Src/util/b.ll", "accepted"),
    Case("dotted_i", "src/İ.ll", "src/i.ll", "accepted"),
    Case("width_variant", "src/Ａ.ll", "src/A.ll", "accepted"),
    Case("mixed_scripts", "src/a.ll", "src/а.ll", "accepted"),
    Case("ascii_leaf", "src/Rate.ll", "src/rate.ll", "file-alias"),
    Case("canonical_unicode_leaf", "src/Café.ll", "src/Cafe\u0301.ll", "file-alias"),
    Case("casefold_unicode_leaf", "src/Straße.ll", "src/STRASSE.ll", "file-alias"),
    Case("ascii_directory", "Pkg/one.ll", "pkg/two.ll", "directory-alias"),
    Case("canonical_unicode_directory", "lib/Café/a.ll", "lib/Cafe\u0301/b.ll", "directory-alias"),
    Case("ascii_file_directory", "Doc", "doc/api.ll", "kind-alias"),
    Case("unicode_file_directory", "straße", "STRASSE/api.ll", "kind-alias"),
    Case("nested_converging_path", "Pkg/Rate.ll", "pkg/rate.ll", "directory-alias"),
    Case("native_same_file_conflict", "src/main.ll", "src/main.ll", "git-conflict"),
    Case("native_file_directory_conflict", "Type", "Type/value.ll", "git-conflict"),
)


def digest(data):
    return sha256(data).hexdigest()


def git(repo, *arguments, check=True):
    process = subprocess.run(["git", "-C", str(repo), *arguments], check=check, capture_output=True, timeout=30,
                             env={**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                                  "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "Fixture",
                                  "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Fixture",
                                  "GIT_COMMITTER_EMAIL": "fixture@example.invalid", "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z",
                                  "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"})
    return process


def output(repo, *arguments):
    return git(repo, *arguments).stdout


def resolve(repo, expression):
    return output(repo, "rev-parse", expression).decode().strip()


def commit(repo, path, data, message):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    git(repo, "add", "--", path)
    git(repo, "commit", "-q", "-m", message)
    return resolve(repo, "HEAD")


def tree_rows(repo, ref):
    rows = {}
    for entry in output(repo, "ls-tree", "-rz", ref).split(b"\0")[:-1]:
        metadata, path = entry.split(b"\t", maxsplit=1)
        mode, kind, object_id = metadata.decode().split()
        assert mode == "100644" and kind == "blob"
        rows[path.decode("utf-8")] = object_id
    return rows


def projected(component):
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", component).casefold())


def admission(paths, policy):
    names = {}
    for raw in sorted(paths):
        parts = raw.split("/")
        if policy == "physical":
            keys = parts
        elif policy == "ascii_paths":
            keys = [part.translate(ASCII_LOWER) for part in parts]
        else:
            keys = [projected(part) for part in parts]
        checked_prefixes = range(1, len(parts) + 1) if policy == "unicode_prefixes" else (len(parts),)
        for size in checked_prefixes:
            key = "/".join(keys[:size])
            raw_prefix = "/".join(parts[:size])
            kind = "file" if size == len(parts) else "directory"
            value = (raw_prefix, kind)
            prior = names.setdefault(key, value)
            if prior != value:
                status = f"{kind}-alias" if kind == prior[1] else "kind-alias"
                return {"status": status, "key": key, "entries": [prior, value]}
    return {"status": "accepted"}


def materialized(repo):
    return {str(path.relative_to(repo)): digest(path.read_bytes())
            for path in sorted(repo.rglob("*")) if path.is_file() and ".git" not in path.relative_to(repo).parts}


def clean_clone(directory, repo, case, flag, commit_oid, paths):
    clone = directory / f"{case.name}-ignorecase-{flag}"
    git(directory, "clone", "-q", "--no-local", "--single-branch", "--branch", "ours",
        "--config", f"core.ignorecase={flag}", str(repo), str(clone))
    assert output(clone, "config", "--bool", "core.ignorecase").decode().strip() == flag
    assert resolve(clone, "HEAD") == commit_oid
    committed = {path: digest(output(clone, "cat-file", "blob", oid)) for path, oid in paths.items()}
    checked = materialized(clone)
    assert checked == committed
    assert not output(clone, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    staged = git(clone, "add", "-A", check=False)
    expected_status = 128 if case.name == "nested_converging_path" and flag == "true" else 0
    assert staged.returncode == expected_status, (case.name, flag, staged.stderr)
    if staged.returncode:
        assert b"file alias" in staged.stderr, staged.stderr
    assert not output(clone, "diff", "--cached", "--name-only", "-z")
    git(clone, "fsck", "--full", "--no-progress")
    return {"materialized_sha256": checked, "index_remains_exact": True,
            "git_add_exit": staged.returncode, "git_add_diagnostic": staged.stderr.decode().strip()}


def run_case(directory, case):
    repo = directory / case.name
    repo.mkdir()
    git(repo, "init", "-qb", "main", "--object-format=sha1")
    git(repo, "config", "core.ignorecase", "false")
    base = commit(repo, BASE_PATH, b"fixture-profile-v1\n", "base")
    git(repo, "checkout", "-qb", "ours")
    ours = commit(repo, case.left, b"provider-ours\n", "ours")
    git(repo, "checkout", "-qb", "theirs", base)
    theirs = commit(repo, case.right, b"provider-theirs\n", "theirs")
    git(repo, "checkout", "-q", "ours")
    assert resolve(repo, "HEAD") == ours
    assert output(repo, "merge-base", ours, theirs).decode().strip() == base
    for parent, path in ((ours, case.left), (theirs, case.right)):
        names = tree_rows(repo, parent)
        assert set(names) == {BASE_PATH, path}
        assert admission(names, "unicode_prefixes")["status"] == "accepted"
    merge = git(repo, "merge", "-q", "--no-ff", "-m", "merge", theirs, check=False)
    record = {"case": case.name, "ours_path": case.left, "theirs_path": case.right,
              "expected": case.expected, "inputs": [base, ours, theirs]}
    if case.expected == "git-conflict":
        assert merge.returncode == 1 and output(repo, "ls-files", "-u", "-z")
        assert resolve(repo, "HEAD") == ours
        return {**record, "git": "conflict", "checkout": {}}
    assert merge.returncode == 0, merge.stdout + merge.stderr
    candidate = resolve(repo, "HEAD")
    assert output(repo, "rev-list", "--parents", "-n", "1", candidate).decode().split() == [candidate, ours, theirs]
    paths = tree_rows(repo, candidate)
    assert set(paths) == {BASE_PATH, case.left, case.right}
    assert output(repo, "cat-file", "blob", paths[case.left]) == b"provider-ours\n"
    assert output(repo, "cat-file", "blob", paths[case.right]) == b"provider-theirs\n"
    policies = {policy: admission(paths, policy) for policy in POLICIES}
    assert policies["unicode_prefixes"]["status"] == case.expected, (case.name, policies)
    checkout = {flag: clean_clone(directory, repo, case, flag, candidate, paths) for flag in ("false", "true")}
    return {**record, "git": "clean", "candidate": candidate, "tree": resolve(repo, "HEAD^{tree}"),
            "blobs": paths, "policy": policies, "checkout": checkout}


def run(directory):
    rows = [run_case(directory, case) for case in CASES]
    native = [row for row in rows if row["git"] == "clean"]
    metrics = {}
    for policy in POLICIES:
        accepted_valid = wrongly_accepted = correctly_refused = refused_valid = 0
        for row in native:
            valid = row["expected"] == "accepted"
            accepted = row["policy"][policy]["status"] == "accepted"
            accepted_valid += valid and accepted
            refused_valid += valid and not accepted
            wrongly_accepted += not valid and accepted
            correctly_refused += not valid and not accepted
        metrics[policy] = {"accepted_valid": accepted_valid, "wrongly_accepted": wrongly_accepted,
                           "correctly_refused": correctly_refused, "refused_valid": refused_valid}
    assert metrics["physical"]["wrongly_accepted"] > metrics["ascii_paths"]["wrongly_accepted"]
    assert metrics["unicode_paths"]["wrongly_accepted"] > metrics["unicode_prefixes"]["wrongly_accepted"] == 0
    return {"schema": "llmlang-rt24-profile-bound-paths/1", "python": platform.python_version(),
            "unicode_data": unicodedata.unidata_version, "git": output(directory, "--version").decode().strip(),
            "system": platform.system(), "source_sha256": digest(Path(__file__).read_bytes()),
            "histories": len(rows), "native_clean": len(native), "native_conflicts": len(rows) - len(native),
            "clean_clones": sum(len(row["checkout"]) for row in rows),
            "git_add_refusals": sum(p["git_add_exit"] != 0 for row in rows for p in row["checkout"].values()),
            "metrics": metrics, "observations": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-path-profile-") as scratch:
        result = run(Path(scratch))
    print(json.dumps(result, indent=2, ensure_ascii=False))
