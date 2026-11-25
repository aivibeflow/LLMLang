#!/usr/bin/env python3
"""Compare exact graph admission across native Git and Git LFS object storage."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
DOMAIN = "llmlang-rt24-lfs-object-admission/1"
MANIFEST = "manifest.json"
ARTIFACT = "graph/delta.bin"
MAGIC = b"LLMLANG\0"
POINTER = re.compile(rb"version https://git-lfs\.github\.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize (0|[1-9][0-9]*)\n")
POLICIES = ("git_blob", "worktree", "worktree_path_cache", "exact")
INPUTS = (-7, -1, 0, 13)
OLD, NEW = 11, 17


@dataclass(frozen=True)
class Case:
    name: str
    snapshot: str = "main"
    mode: str = "skip"
    cache: str = "none"
    expected: str = "exact"


CASES = (
    Case("inline_git_object", snapshot="inline"),
    Case("native_smudged_clone", mode="smudge"),
    Case("pointer_only_clone", expected="unavailable"),
    Case("fetch_pinned_media_without_checkout", mode="fetch"),
    Case("native_lfs_pull", mode="pull"),
    Case("fetch_historic_media_after_tip_moved", snapshot="old", mode="fetch"),
    Case("dirty_media_worktree", mode="dirty"),
    Case("verified_separate_media_cache", cache="exact"),
    Case("stale_media_path_cache", cache="old", expected="unavailable"),
    Case("incorrect_media_in_application_cache", cache="wrong-in-object-cache", expected="corrupt"),
    Case("canonical_pointer_with_wrong_size", snapshot="wrong-size", cache="exact", expected="corrupt"),
    Case("conflicting_manifest_digest", snapshot="wrong-manifest", mode="smudge", expected="binding"),
    Case("authorized_origin_unavailable", mode="unavailable", expected="unavailable"),
    Case("unsupported_pointer_grammar", snapshot="invalid-pointer", cache="exact", expected="pointer"),
)


def digest(data):
    return sha256(data).hexdigest()


def canonical(data):
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()


def encode(delta):
    return MAGIC + delta.to_bytes(8, "big", signed=True)


def pointer(data, length=None):
    size = len(data) if length is None else length
    return f"version https://git-lfs.github.com/spec/v1\noid sha256:{digest(data)}\nsize {size}\n".encode()


def git(repo, *arguments, data=None, skip=True, check=True):
    result = subprocess.run(["git", "-C", str(repo), *arguments], input=data, check=False, capture_output=True, timeout=35,
                          env={**os.environ, "LC_ALL": "C", "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
                               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                               "GIT_LFS_SKIP_SMUDGE": "1" if skip else "0", "GIT_CONFIG_COUNT": "0",
                               "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                               "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                               "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"})
    assert not check or result.returncode == 0, (arguments, result.stderr)
    return result


def output(repo, *arguments):
    return git(repo, *arguments).stdout.decode().strip()


def write(repo, path, body):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)


def artifact_manifest(delta, codec="lfs"):
    return canonical({"artifact": ARTIFACT, "codec": codec, "payload_sha256": digest(encode(delta))})


def history(directory):
    repo = directory / "source"
    donor = directory / "origin.git"
    repo.mkdir()
    donor.mkdir()
    git(repo, "init", "-qb", "main", "--object-format=sha1")
    git(donor, "init", "--bare", "-qb", "main", "--object-format=sha1")
    git(repo, "lfs", "install", "--local")
    git(repo, "lfs", "track", "graph/*.bin")
    for label, delta in (("old", OLD), ("current", NEW)):
        write(repo, ARTIFACT, encode(delta))
        write(repo, MANIFEST, artifact_manifest(delta))
        git(repo, "add", "--", ".gitattributes", ARTIFACT, MANIFEST)
        git(repo, "commit", "-qm", label)
        stored = git(repo, "show", f"HEAD:{ARTIFACT}").stdout
        assert stored == pointer(encode(delta))
        if label == "old":
            git(repo, "branch", "old")
    git(repo, "remote", "add", "origin", donor.as_uri())
    git(repo, "push", "-q", "origin", "main", "old")
    for delta in (OLD, NEW):
        assert lfs_media(donor / "lfs/objects", digest(encode(delta))) == encode(delta)
    git(repo, "checkout", "-qb", "inline", "main")
    git(repo, "rm", "-q", ".gitattributes")
    write(repo, ARTIFACT, encode(NEW))
    write(repo, MANIFEST, artifact_manifest(NEW, "inline"))
    git(repo, "add", "--", ARTIFACT, MANIFEST)
    git(repo, "commit", "-qm", "inline")
    assert git(repo, "show", f"HEAD:{ARTIFACT}").stdout == encode(NEW)
    git(repo, "checkout", "-qb", "wrong-manifest", "main")
    write(repo, MANIFEST, artifact_manifest(OLD))
    git(repo, "add", "--", MANIFEST)
    git(repo, "commit", "-qm", "wrong manifest")
    snapshots = ("main", "old", "inline", "wrong-manifest")
    git(repo, "push", "-q", "origin", "inline", "wrong-manifest")
    controls = (("wrong-size", pointer(encode(NEW), len(encode(NEW)) + 1)),
                ("invalid-pointer", pointer(encode(NEW)) + b"\n"))
    for name, fake in controls:
        git(repo, "checkout", "-qfb", name, "main")
        blob = git(repo, "hash-object", "-w", "--stdin", data=fake).stdout.decode().strip()
        git(repo, "update-index", "--cacheinfo", f"100644,{blob},{ARTIFACT}")
        git(repo, "commit", "-qm", name)
        assert git(repo, "show", f"HEAD:{ARTIFACT}").stdout == fake
    git(repo, "-c", "core.hooksPath=/dev/null", "push", "-q", "origin", *(name for name, _ in controls))
    commits = {branch: output(donor, "rev-parse", branch) for branch in (*snapshots, *(name for name, _ in controls))}
    return donor, commits


def lfs_media(root, oid):
    path = root / oid[:2] / oid[2:4] / oid
    return path.read_bytes() if path.is_file() else None


def candidate(data, receipt):
    if data is None or not data.startswith(MAGIC) or len(data) != len(MAGIC) + 8:
        return {"status": "unavailable"}
    delta = int.from_bytes(data[len(MAGIC):], "big", signed=True)
    return {"status": "accepted", "receipt": receipt, "payload_sha256": digest(data), "delta": delta,
            "semantic_root": digest(DOMAIN.encode() + b"\0" + canonical({"op": "add", "delta": delta})),
            "values": [x + delta for x in INPUTS]}


def exact(raw, manifest, media, object_cache):
    expected = manifest["payload_sha256"]
    if manifest["codec"] == "inline":
        if digest(raw) != expected:
            return {"status": "binding"}
        return candidate(raw, "git-inline")
    match = POINTER.fullmatch(raw)
    if not match:
        return {"status": "pointer"}
    object_id, declared_size = match[1].decode(), int(match[2])
    if object_id != expected:
        return {"status": "binding"}
    source = "native-lfs-media"
    payload = lfs_media(media, object_id)
    if payload is None:
        payload = object_cache.get(object_id)
        source = "separate-verified-media-cache"
    if payload is None:
        return {"status": "unavailable"}
    if len(payload) != declared_size or digest(payload) != object_id:
        return {"status": "corrupt"}
    return candidate(payload, source)


def prepare(directory, donor, case, commit):
    repo = directory / case.name
    smudge = case.mode in ("smudge", "dirty")
    git(directory, "-c", "filter.lfs.process=git-lfs filter-process", "-c", "filter.lfs.required=true",
        "clone", "-q", "--no-local", "--single-branch", "--branch", case.snapshot, donor.as_uri(), str(repo), skip=not smudge)
    assert output(repo, "rev-parse", "HEAD") == commit
    git(repo, "lfs", "install", "--local")
    if case.mode == "fetch":
        git(repo, "lfs", "fetch", "origin", commit)
    if case.mode == "pull":
        git(repo, "lfs", "pull", "--include", ARTIFACT)
    if case.mode == "dirty":
        write(repo, ARTIFACT, encode(OLD))
        assert output(repo, "diff", "--name-only", "HEAD") == ARTIFACT
    if case.mode == "unavailable":
        hidden = donor.with_name("origin-offline.git")
        donor.rename(hidden)
        try:
            fetched = git(repo, "lfs", "fetch", "origin", commit, check=False)
            assert fetched.returncode != 0
        finally:
            hidden.rename(donor)
    return repo


def archive_entry(repo, commit, skip=True):
    archived = git(repo, "archive", "--format=tar", commit, skip=skip).stdout
    with tarfile.open(fileobj=BytesIO(archived)) as tar:
        return tar.extractfile(ARTIFACT).read()


def run_case(directory, donor, case, commit):
    repo = prepare(directory, donor, case, commit)
    manifest_bytes = git(repo, "show", f"{commit}:{MANIFEST}").stdout
    manifest = json.loads(manifest_bytes)
    assert canonical(manifest) == manifest_bytes and set(manifest) == {"artifact", "codec", "payload_sha256"}
    assert manifest["artifact"] == ARTIFACT and manifest["codec"] in ("inline", "lfs")
    raw = git(repo, "show", f"{commit}:{ARTIFACT}").stdout
    working = (repo / ARTIFACT).read_bytes()
    git_pointer_check = git(repo, "lfs", "pointer", "--check", "--strict", "--stdin", data=raw, check=False).returncode
    working_pointer_check = git(repo, "lfs", "pointer", "--check", "--strict", "--stdin",
                                data=working, check=False).returncode
    expected_pointer_check = {"inline": 1, "invalid-pointer": 2}.get(case.snapshot, 0)
    assert git_pointer_check == expected_pointer_check
    media = repo / ".git/lfs/objects"
    delta = OLD if case.snapshot == "old" else NEW
    oid = digest(encode(delta))
    native_media = lfs_media(media, oid)
    if case.mode in ("pull", "smudge", "dirty", "fetch"):
        assert native_media == encode(delta)
    else:
        assert native_media is None
    if case.mode in ("pull", "smudge") or case.snapshot == "inline":
        assert working == encode(delta)
    elif case.mode == "dirty":
        assert working == encode(OLD)
    elif case.snapshot == "invalid-pointer":
        assert working == pointer(encode(NEW)) and working_pointer_check == 0
    else:
        assert working == raw, (case.name, working, raw)
    raw_archive = archive_entry(donor, commit)
    filtered_archive = archive_entry(repo, commit)
    assert raw_archive == raw
    expected_archive = pointer(encode(NEW)) if case.snapshot == "invalid-pointer" else raw
    assert filtered_archive == expected_archive, (case.name, filtered_archive, raw)
    smudged_archive = None
    if case.name == "native_smudged_clone":
        smudged_archive = archive_entry(repo, commit, skip=False)
        assert smudged_archive == encode(delta)
    object_cache = {}
    fallback = None
    if case.cache in ("exact", "old", "wrong-in-object-cache"):
        cached_delta = delta if case.cache == "exact" else OLD
        signature = digest(encode(cached_delta))
        fallback = lfs_media(donor / "lfs/objects", signature)
        assert fallback == encode(cached_delta)
        object_cache[oid if case.cache == "wrong-in-object-cache" else signature] = fallback
    path_candidate = candidate(working, "worktree")
    result = {"git_blob": candidate(raw, "git"), "worktree": path_candidate,
              "worktree_path_cache": path_candidate.copy() if path_candidate["status"] == "accepted" else candidate(fallback, "path-cache"),
              "exact": exact(raw, manifest, media, object_cache)}
    for observation in result.values():
        if observation["status"] == "accepted":
            observation["class"] = "exact" if case.expected == "exact" and observation["delta"] == delta else "wrong_acceptance"
        else:
            observation["class"] = "available_refused" if case.expected == "exact" else "expected_refusal"
    strict = result["exact"]
    assert (strict["class"] if strict["status"] == "accepted" else strict["status"]) == case.expected
    assert lfs_media(media, oid) == native_media and (repo / ARTIFACT).read_bytes() == working
    return {"case": case.name, "snapshot": case.snapshot, "commit": commit, "object": output(repo, "rev-parse", f"{commit}:{ARTIFACT}"),
            "manifest": manifest, "git_payload_sha256": digest(raw), "worktree_payload_sha256": digest(working),
            "native_lfs_media": native_media is not None, "archive_contains_media": raw_archive.startswith(MAGIC),
            "filtered_archive_sha256": digest(filtered_archive), "raw_archive_sha256": digest(raw_archive),
            "smudged_archive_sha256": digest(smudged_archive) if smudged_archive is not None else None,
            "native_git_pointer_check": git_pointer_check, "native_worktree_pointer_check": working_pointer_check,
            "expected": case.expected, "policies": result}


def run(directory):
    donor, commits = history(directory)
    rows = [run_case(directory, donor, case, commits[case.snapshot]) for case in CASES]
    classes = ("exact", "wrong_acceptance", "available_refused", "expected_refusal")
    metrics = {policy: {kind: sum(row["policies"][policy]["class"] == kind for row in rows) for kind in classes}
               for policy in POLICIES}
    assert metrics["exact"]["wrong_acceptance"] == metrics["exact"]["available_refused"] == 0
    assert metrics["worktree_path_cache"]["wrong_acceptance"] > metrics["worktree"]["wrong_acceptance"]
    return {"schema": DOMAIN, "python": platform.python_version(), "git": output(directory, "--version"),
            "lfs": output(directory, "lfs", "version"), "source_sha256": digest(Path(__file__).read_bytes()),
            "scenarios": len(rows), "commits": commits, "inputs": INPUTS, "metrics": metrics, "observations": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-lfs-") as scratch:
        result = run(Path(scratch))
    print(json.dumps(result, indent=2))
