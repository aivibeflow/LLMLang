#!/usr/bin/env python3
"""Exercise standard Git ref transport and bounded active SPG segment growth."""

import json
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASE = runpy.run_path(str(HERE.parent / "DIVERGENT-GIT-HISTORY-01/run.py"))
git, encode, digest = (BASE[name] for name in ("git", "encode", "digest"))
fixture, write_rev, row_data = (BASE[name] for name in ("fixture", "write_rev", "row_data"))
read_view, rebuild, commit = (BASE[name] for name in ("read_view", "rebuild", "commit"))
project = BASE["BASE"]["project"]
LAYOUT = "immutable-segments"


def physical(files):
    return sum(map(len, files.values()))


def encoded_live(view):
    return sum(len(row_data(((address, raw),))) for address, raw in view["records"].items())


def publish(repository, view, files, previous, index):
    next_files = write_rev(repository, LAYOUT, view, files)
    live = encoded_live(view)
    before_compaction = physical(next_files)
    if before_compaction * 20 > live * 21:
        next_files = write_rev(repository, LAYOUT, view, next_files, compact=True)
        assert physical(next_files) == live
    active = physical(next_files)
    assert active * 20 <= live * 21
    old = set() if previous is None else set(previous["records"])
    new = set(view["records"])
    log = {"prior": None if previous is None else previous["root"], "selected": view["root"],
           "added": sorted(new - old), "retired": sorted(old - new)}
    (repository / "changes.json").write_bytes(encode(log))
    projection = encode(project(view["records"]))
    direct = repository / "reverse.json"
    if index == 4:
        direct.unlink(missing_ok=True)
    else:
        direct.write_bytes(projection)
    label = f"selected properties {index}"
    return commit(repository, label), next_files, {
        "active_bytes": active, "live_bytes": live, "pre_compaction_bytes": before_compaction,
        "compacted": active < before_compaction, "added": len(log["added"]), "retired": len(log["retired"]),
        "root": view["root"],
    }


def verify(repo, pin, expected, previous, require_index):
    manifest, segments = read_view(repo, pin)
    objects = rebuild(manifest, segments)
    assert objects == expected["records"]
    log = json.loads(git(repo, "show", pin + ":changes.json"))
    old = set() if previous is None else set(previous["records"])
    assert log["prior"] == (None if previous is None else previous["root"])
    assert log["selected"] == manifest["root"] == expected["root"]
    assert log["added"] == sorted(objects.keys() - old)
    assert log["retired"] == sorted(old - objects.keys())
    assert (old - set(log["retired"])) | set(log["added"]) == set(objects)
    expected_meta = encode(project(objects))
    tracked = git(repo, "ls-tree", "--name-only", pin, "reverse.json").strip()
    assert bool(tracked) == require_index
    if tracked:
        assert git(repo, "show", pin + ":reverse.json") == expected_meta
    return {"derived_index": digest(expected_meta), "source": "verified" if tracked else "reconstructed"}


def experiment(work):
    common, _, alternate = fixture()
    origin = work / "origin"
    writer = work / "writer"
    observer = work / "observer"
    stale = work / "stale"
    origin.mkdir()
    writer.mkdir()
    git(origin, "init", "--bare", "--quiet", "-b", "research/all", "--object-format=sha1")
    git(writer, "init", "--quiet", "-b", "research/all", "--object-format=sha1")
    git(writer, "remote", "add", "origin", str(origin))
    initial, previous_files, record = publish(writer, common[0], {}, None, 0)
    git(writer, "push", "--quiet", "-u", "origin", "refs/heads/research/all")
    for clone in (observer, stale):
        git(work, "clone", "--quiet", "--no-local", str(origin), str(clone))
        assert git(clone, "branch", "--show-current").strip() == b"research/all"
    return_rows = [record | {"pin": initial}]
    tag = "historic-typed-snapshot"
    files = previous_files
    for index, view in enumerate(common[1:], 1):
        pin, files, row = publish(writer, view, files, common[index - 1], index)
        return_rows.append(row | {"pin": pin})
        if index == 4:
            git(writer, "tag", tag, pin)
    final = return_rows[-1]["pin"]
    git(writer, "push", "--quiet", "--tags", "origin", "refs/heads/research/all")
    stale_pin, _, _ = publish(stale, alternate[0], previous_files, common[0], 1)
    try:
        git(stale, "push", "origin", "refs/heads/research/all")
    except subprocess.CalledProcessError as error:
        assert b"rejected" in error.stderr and b"fetch first" in error.stderr
    else:
        raise AssertionError("stale ref update was accepted")
    assert git(origin, "rev-parse", "refs/heads/research/all").decode().strip() == final

    git(observer, "fetch", "--quiet", "--prune", "--tags", "origin")
    git(observer, "merge", "--quiet", "--ff-only", "origin/research/all")
    assert git(observer, "rev-parse", "HEAD").decode().strip() == final
    assert git(observer, "rev-parse", f"refs/tags/{tag}").decode().strip() == return_rows[4]["pin"]
    git(observer, "remote", "remove", "origin")
    origin.rename(work / "origin-offline")
    git(observer, "fsck", "--full")
    observed = git(observer, "rev-list", "research/all").decode().splitlines()
    assert observed == [row["pin"] for row in reversed(return_rows)] and stale_pin not in observed

    for index, row in enumerate(return_rows):
        predecessor = None if index == 0 else common[index - 1]
        row.update(verify(observer, row["pin"], common[index], predecessor, index != 4))
    compactions = sum(row["compacted"] for row in return_rows)
    assert compactions >= 2
    return {
        "format": "segmented-git-transport-01", "git": git(work, "--version").decode().strip(),
        "rows": return_rows, "retained_tag": return_rows[4]["pin"], "compactions": compactions,
        "stale_push": "refused", "stale_pin": stale_pin,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-segmented-transport-") as temp:
        evidence = experiment(Path(temp))
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
