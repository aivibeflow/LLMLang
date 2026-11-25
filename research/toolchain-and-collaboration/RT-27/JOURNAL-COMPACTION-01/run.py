"""Reconstruct selected logical states and reverse indexes solely from Git."""

import hashlib
import json
import os
from pathlib import Path
import platform
from shutil import rmtree
import subprocess
from tempfile import TemporaryDirectory


def git(directory, *args):
    settings = os.environ | {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Fixture Author",
        "GIT_AUTHOR_EMAIL": "author@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture Author",
        "GIT_COMMITTER_EMAIL": "author@example.invalid",
        "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z",
        "GIT_CONFIG_COUNT": "0",
    }
    return subprocess.check_output(["git", "-C", str(directory), *args], env=settings)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def hash_value(value):
    return hashlib.sha256(encode(value)).hexdigest()


def project_reverse(records):
    reverse = {name: [] for name in sorted(records)}
    for name, record in sorted(records.items()):
        for slot, target in enumerate(record["refs"]):
            reverse[target].append([name, slot])
    return reverse


def put(name, value, refs=(), expected=None):
    return {"name": name, "before": expected, "after": {"value": value, "refs": list(refs)}}


def remove(name, record):
    return {"name": name, "before": hash_value(record), "after": None}


def collect(events, expected_root):
    records = {}
    for event in events:
        name = event["name"]
        before = hash_value(records[name]) if name in records else None
        if before != event["before"]:
            return "wrong-predecessor", {}
        if event["after"] is None:
            if name not in records:
                return "delete-absent", {}
            del records[name]
        else:
            records[name] = event["after"]
    if any(target not in records for row in records.values() for target in row["refs"]):
        return "dangling-reference", {}
    if hash_value(records) != expected_root:
        return "wrong-logical-root", {}
    return "verified", records


def write(directory, path, value):
    (directory / path).write_bytes(encode(value) + b"\n")


def commit(directory, title, events, records, optional_index):
    write(directory, "journal.json", events)
    write(directory, "manifest.json", {"profile": "fixture-1", "root": hash_value(records)})
    path = directory / "reverse.json"
    if optional_index is None:
        path.unlink(missing_ok=True)
    else:
        write(directory, "reverse.json", optional_index)
    git(directory, "add", "-A")
    git(directory, "commit", "-q", "-m", title)
    git(directory, "tag", title)


def restore(directory, ref):
    def read(path):
        return json.loads(git(directory, "show", f"{ref}:{path}"))

    manifest = read("manifest.json")
    assert manifest["profile"] == "fixture-1"
    paths = git(directory, "ls-tree", "--name-only", ref).decode().splitlines()
    events = read("journal.json")
    status, records = collect(events, manifest["root"])
    if status != "verified":
        return {"status": status}
    reverse = project_reverse(records)
    if "reverse.json" not in paths:
        index = "absent-rebuilt"
    else:
        stored = read("reverse.json")
        exact = stored == {"root": manifest["root"], "entries": reverse}
        index = "exact" if exact else "stale-rebuilt"
    return {
        "status": "verified",
        "root": manifest["root"],
        "tracked_paths": paths,
        "event_count": len(events),
        "records": records,
        "reverse": reverse,
        "index": index,
    }


def study(directory):
    repo = directory / "repository"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=research/all", "--object-format=sha1")
    live = [put("legacy", 5), put("current", 7), put("consumer", 1, ("legacy", "legacy"))]
    baseline = {event["name"]: event["after"] for event in live}
    old_index = {"root": hash_value(baseline), "entries": project_reverse(baseline)}
    commit(repo, "initial", live, baseline, old_index)

    update = put("consumer", 1, ("current", "current"), hash_value(baseline["consumer"]))
    delete = remove("legacy", baseline["legacy"])
    after = {"current": baseline["current"], "consumer": update["after"]}
    journal = live + [update, delete]
    commit(repo, "deleted", journal, after, old_index)
    compacted = [put(name, record["value"], record["refs"]) for name, record in sorted(after.items())]
    commit(repo, "compacted", compacted, after, None)
    commit(repo, "index-only-error", compacted, after, {
        "root": hash_value(after),
        "entries": {"consumer": [], "current": [["consumer", 0]]},
    })
    commit(repo, "missing-delete", live + [update], after, None)
    commit(repo, "dangling", live + [delete], after, None)
    wrong_update = update | {"before": hash_value(baseline["current"])}
    commit(repo, "wrong-before", live + [wrong_update, delete], after, None)

    git(directory, "clone", "-q", "--no-local", "--no-checkout", str(repo), "clean")
    rmtree(repo)
    clean = directory / "clean"
    assert not (clean / ".git/objects/info/alternates").exists()
    assert sorted(path.name for path in clean.iterdir()) == [".git"]
    refs = ("initial", "deleted", "compacted", "index-only-error", "missing-delete", "dangling", "wrong-before")
    results = {ref: restore(clean, ref) for ref in refs}
    assert results["initial"]["reverse"]["legacy"] == [["consumer", 0], ["consumer", 1]]
    assert [results[ref]["status"] for ref in refs] == [
        "verified", "verified", "verified", "verified", "wrong-logical-root", "dangling-reference",
        "wrong-predecessor",
    ]
    assert [results[ref]["index"] for ref in refs[:4]] == [
        "exact", "stale-rebuilt", "absent-rebuilt", "stale-rebuilt",
    ]
    assert results["deleted"]["event_count"] == 5
    assert results["compacted"]["event_count"] == 2
    for ref in ("deleted", "compacted", "index-only-error"):
        assert results[ref]["records"] == after
        assert results[ref]["root"] == hash_value(after)
        assert results[ref]["reverse"] == {"consumer": [], "current": [["consumer", 0], ["consumer", 1]]}
    return {
        "git": git(directory, "--version").decode().strip(),
        "runtime": platform.python_version(),
        "checkout_present_during_restore": False,
        "origin_present_during_restore": repo.exists(),
        "revisions": results,
    }


if __name__ == "__main__":
    with TemporaryDirectory() as temporary:
        print(json.dumps(study(Path(temporary)), indent=2, sort_keys=True))
