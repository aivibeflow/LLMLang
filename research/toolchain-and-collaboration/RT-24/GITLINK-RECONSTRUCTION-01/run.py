#!/usr/bin/env python3
"""Compare exact external Git dependencies with native submodule clone and update paths."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import platform

HERE = Path(__file__).resolve().parent
MODULE = "vendor/provider"
DECLARATION = "requirement.json"
PAYLOAD = "delta.json"
POLICIES = ("worktree", "nested_head", "upstream_tip", "exact_gitlink")
SAMPLES = (-5, -1, 0, 9)
DOMAIN = "llmlang-rt24-gitlink-reconstruction/1"


@dataclass(frozen=True)
class Case:
    name: str
    snapshot: str = "old"
    hydration: str = "none"
    status: str = "exact"
    allow_origin: bool = True


CASES = (
    Case("plain_clone_offline", status="unavailable", allow_origin=False),
    Case("authorized_recursive_checkout", hydration="recursive"),
    Case("explicit_pinned_checkout_after_clone", hydration="pinned"),
    Case("authorized_blob_store_without_checkout", hydration="object_store"),
    Case("remote_update_moves_worktree", hydration="remote"),
    Case("other_commit_same_payload", hydration="equivalent"),
    Case("dirty_nested_worktree", hydration="dirty"),
    Case("explicit_gitlink_upgrade", snapshot="new", hydration="pinned"),
    Case("declaration_and_gitlink_disagree", snapshot="mismatch", hydration="pinned", status="mismatch"),
    Case("new_origin_contains_same_git_objects", snapshot="other_origin", hydration="pinned", status="authority"),
    Case("regular_file_in_place_of_dependency", snapshot="regular", status="invalid"),
    Case("pinned_commit_does_not_contain_value", snapshot="missing", hydration="pinned", status="invalid"),
    Case("authorized_origin_unavailable", hydration="unavailable", status="unavailable"),
)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data):
    return sha256(data).hexdigest()


def git(repo, *arguments, check=True):
    return subprocess.run(["git", "-C", str(repo), *arguments], check=check, capture_output=True, timeout=30,
                          env={**os.environ, "LC_ALL": "C", "GIT_ALLOW_PROTOCOL": "file",
                               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_LAZY_FETCH": "1",
                               "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                               "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                               "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"})


def output(repo, *arguments):
    return git(repo, *arguments).stdout.decode().strip()


def file(repo, path, data):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def ordinary_commit(repo, path, data, message):
    file(repo, path, data)
    git(repo, "add", "--", path)
    git(repo, "commit", "-qm", message)
    return output(repo, "rev-parse", "HEAD")


def provider_history(repo):
    repo.mkdir()
    git(repo, "init", "-qb", "main", "--object-format=sha1")
    old = ordinary_commit(repo, PAYLOAD, canonical({"delta": 11}), "old provider")
    new = ordinary_commit(repo, PAYLOAD, canonical({"delta": 17}), "new provider")
    git(repo, "checkout", "-qb", "missing")
    git(repo, "rm", "-q", PAYLOAD)
    git(repo, "commit", "-qm", "missing provider value")
    missing = output(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-qb", "equivalent", old)
    equivalent = ordinary_commit(repo, "notes.json", canonical({"provenance": "another revision"}), "equivalent value")
    git(repo, "checkout", "-q", "main")
    return {"old": old, "new": new, "missing": missing, "equivalent": equivalent}


def modules(relative):
    return f'[submodule "provider"]\n\tpath = {MODULE}\n\turl = {relative}\n'.encode()


def super_history(repo, providers):
    repo.mkdir()
    git(repo, "init", "-qb", "main", "--object-format=sha1")
    snapshots = {}
    for name, declared, pinned, relative in (
        ("old", "old", "old", "../provider"),
        ("new", "new", "new", "../provider"),
        ("mismatch", "new", "old", "../provider"),
        ("other_origin", "old", "old", "../mirror"),
        ("missing", "missing", "missing", "../provider"),
        ("regular", "old", None, "../provider"),
    ):
        git(repo, "checkout", "-qb", name)
        file(repo, ".gitmodules", modules(relative))
        file(repo, DECLARATION, canonical({"path": MODULE, "commit": providers[declared], "operation": "add"}))
        git(repo, "add", "--", ".gitmodules", DECLARATION)
        if pinned is not None:
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{providers[pinned]},{MODULE}")
        else:
            git(repo, "update-index", "--force-remove", "--", MODULE)
            file(repo, f"{MODULE}/{PAYLOAD}", canonical({"delta": 11}))
            git(repo, "add", "--", f"{MODULE}/{PAYLOAD}")
        git(repo, "commit", "-qm", name)
        snapshots[name] = output(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "old")
    return snapshots


def native_view(clone):
    path = (clone / MODULE).resolve()
    if not path.is_dir():
        return None
    prefix = git(path, "rev-parse", "--show-toplevel", check=False)
    if prefix.returncode or Path(prefix.stdout.decode().strip()) != path:
        return None
    return path


def read_blob(repo, commit, path):
    value = git(repo, "show", f"{commit}:{path}", check=False)
    return value.stdout if value.returncode == 0 else None


def value(raw, receipt):
    if raw is None:
        return {"status": "unavailable"}
    doc = json.loads(raw)
    delta = doc["delta"]
    assert type(delta) is int and canonical({"delta": delta}) == raw
    semantic = digest(DOMAIN.encode() + b"\0" + canonical({"operation": "add", "delta": delta}))
    return {"status": "accepted", "receipt": receipt, "semantic_root": semantic, "delta": delta,
            "observations": [sample + delta for sample in SAMPLES]}


def root_context(clone, expected_commit):
    assert output(clone, "rev-parse", "HEAD") == expected_commit
    tree = output(clone, "rev-parse", f"{expected_commit}^{{tree}}")
    raw = output(clone, "ls-tree", expected_commit, "--", MODULE)
    label, path = raw.split("\t", 1)
    mode, kind, oid = label.split()
    assert path == MODULE and (mode, kind) in (("160000", "commit"), ("040000", "tree"))
    declaration = read_blob(clone, expected_commit, DECLARATION)
    stated = json.loads(declaration)
    assert stated["path"] == MODULE and stated["operation"] == "add" and canonical(stated) == declaration
    module_config = read_blob(clone, expected_commit, ".gitmodules")
    with tarfile.open(fileobj=BytesIO(git(clone, "archive", "--format=tar", expected_commit).stdout)) as archive:
        archived = set(archive.getnames())
    assert {DECLARATION, ".gitmodules"} <= archived
    assert (f"{MODULE}/{PAYLOAD}" in archived) == (mode == "040000")
    return {"tree": tree, "mode": mode, "pin": oid, "declared": stated["commit"],
            "module_config": module_config.decode(), "super_archive_includes_payload": f"{MODULE}/{PAYLOAD}" in archived}


def hydrate(parent, clone, provider, providers, case):
    if case.hydration == "none":
        return None, "not-requested"
    if case.hydration == "recursive":
        initialized = native_view(clone)
        assert initialized is not None
        return initialized, "recursive"
    if case.hydration == "object_store":
        objects = parent / f"{case.name}-objects"
        git(parent, "clone", "-q", "--bare", "--no-local", provider.as_uri(), str(objects))
        assert native_view(clone) is None
        return objects, "object-store"
    if case.hydration == "unavailable":
        offline = provider.with_name("temporarily-unavailable")
        provider.rename(offline)
        try:
            result = git(clone, "submodule", "update", "--init", "--", MODULE, check=False)
            assert result.returncode and b"clone" in result.stderr
            assert native_view(clone) is None
        finally:
            offline.rename(provider)
        return None, "origin-unavailable"
    flags = ["--remote"] if case.hydration == "remote" else []
    git(clone, "submodule", "update", "--init", *flags, "--", MODULE)
    initialized = native_view(clone)
    assert initialized is not None
    if case.hydration == "equivalent":
        git(initialized, "checkout", "-q", "--detach", providers["equivalent"])
    if case.hydration == "dirty":
        file(initialized, PAYLOAD, canonical({"delta": 99}))
        assert output(initialized, "diff", "--name-only", "HEAD") == PAYLOAD
    return initialized, case.hydration


def exact_context(context, objects, provider):
    if context["mode"] != "160000":
        return {"status": "invalid-tree-entry"}
    if context["pin"] != context["declared"]:
        return {"status": "mismatch"}
    if context["module_config"] != modules("../provider").decode():
        return {"status": "authority"}
    if objects is None:
        return {"status": "unavailable"}
    if output(objects, "remote", "get-url", "origin") != provider.as_uri():
        return {"status": "authority"}
    pin = context["pin"]
    if git(objects, "cat-file", "-e", f"{pin}^{{commit}}", check=False).returncode:
        return {"status": "unavailable"}
    raw = read_blob(objects, pin, PAYLOAD)
    if raw is None:
        return {"status": "invalid-dependency-inventory"}
    return value(raw, pin)


def run_case(parent, source, provider, mirror, snapshots, providers, case):
    clone = parent / case.name
    flags = ["--recurse-submodules"] if case.hydration == "recursive" else []
    git(parent, "clone", "-q", "--no-local", "--single-branch", "--branch", case.snapshot, *flags,
        source.as_uri(), str(clone))
    assert (native_view(clone) is None) == (case.hydration != "recursive")
    context = root_context(clone, snapshots[case.snapshot])
    objects, hydration = hydrate(parent, clone, provider, providers, case)
    nested = native_view(clone)
    head = output(nested, "rev-parse", "HEAD") if nested else None
    if case.hydration == "remote":
        assert head == providers["new"] and head != context["pin"]
    if case.hydration in ("pinned", "dirty", "recursive"):
        assert head == context["pin"]
    if case.hydration == "equivalent":
        assert head == providers["equivalent"] and head != context["pin"]
        assert read_blob(nested, head, PAYLOAD) == read_blob(nested, context["pin"], PAYLOAD)
    if case.hydration == "object_store":
        assert head is None and not (clone / MODULE / PAYLOAD).exists()
    path = clone / MODULE / PAYLOAD
    raw = path.read_bytes() if path.is_file() else None
    live = None
    if case.allow_origin and case.hydration != "unavailable":
        donor = mirror if case.snapshot == "other_origin" else provider
        live = output(donor, "rev-parse", "refs/heads/main")
        live_result = value(read_blob(donor, live, PAYLOAD), live)
    else:
        live_result = {"status": "unavailable"}
    observed = {
        "worktree": value(raw, "visible-by-path"),
        "nested_head": value(read_blob(nested, head, PAYLOAD), head) if nested else {"status": "unavailable"},
        "upstream_tip": live_result,
        "exact_gitlink": exact_context(context, objects, provider),
    }
    expected_delta = 17 if case.snapshot == "new" else 11
    observed_commits = {"worktree": head, "nested_head": head, "upstream_tip": live, "exact_gitlink": context["pin"]}
    for policy, result in observed.items():
        if result["status"] == "accepted":
            exact = case.status == "exact" and result["delta"] == expected_delta and observed_commits[policy] == context["pin"]
            result["class"] = "exact" if exact else "wrong_acceptance"
        else:
            result["class"] = "available_refused" if case.status == "exact" else "expected_refusal"
    strict = observed["exact_gitlink"]
    assert strict["class"] == ("exact" if case.status == "exact" else "expected_refusal"), (case.name, strict)
    if case.status == "invalid":
        assert strict["status"].startswith("invalid-")
    elif case.status != "exact":
        assert strict["status"] == case.status
    assert output(clone, "rev-parse", "HEAD") == snapshots[case.snapshot]
    return {"case": case.name, "snapshot": snapshots[case.snapshot], "context": context, "hydration": hydration,
            "nested_head": head, "upstream_tip": live, "expected": case.status, "policies": observed}


def run(parent):
    provider = parent / "provider"
    providers = provider_history(provider)
    mirror = parent / "mirror"
    git(parent, "clone", "-q", "--mirror", "--no-local", provider.as_uri(), str(mirror))
    source = parent / "super"
    snapshots = super_history(source, providers)
    rows = [run_case(parent, source, provider, mirror, snapshots, providers, case) for case in CASES]
    classes = ("exact", "wrong_acceptance", "available_refused", "expected_refusal")
    metrics = {policy: {kind: sum(row["policies"][policy]["class"] == kind for row in rows) for kind in classes}
               for policy in POLICIES}
    assert metrics["exact_gitlink"] == {"exact": 7, "wrong_acceptance": 0, "available_refused": 0, "expected_refusal": 6}
    assert metrics["upstream_tip"]["wrong_acceptance"] > metrics["nested_head"]["wrong_acceptance"] > 0
    return {"schema": DOMAIN, "git": output(parent, "--version"), "python": platform.python_version(),
            "source_sha256": digest(Path(__file__).read_bytes()), "provider_commits": providers,
            "samples": SAMPLES, "scenarios": len(rows), "metrics": metrics, "observations": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-gitlink-") as scratch:
        result = run(Path(scratch))
    print(json.dumps(result, indent=2))
