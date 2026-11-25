"""Compare exact checkout observations with normalized Git objects."""
import argparse
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import stat
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASE_TIME = 1_700_000_000_000_000_000
ENV = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "LC_ALL": "C",
}


def git(repo, *args, index=None):
    environment = ENV if index is None else {**ENV, "GIT_INDEX_FILE": str(index)}
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "core.filemode=true", *args],
        cwd=repo, env=environment, check=True, capture_output=True, timeout=10,
    )
    return result.stdout


def timestamp(path, when=BASE_TIME):
    os.utime(path, ns=(when, when), follow_symlinks=False)
    assert path.lstat().st_mtime_ns == when


def start(directory, width, ending):
    repo = directory / "worktree"
    repo.mkdir()
    git(repo, "init", "--quiet", "--template=", "--initial-branch=research/all",
        "--object-format=sha1")
    (directory / "external-a").write_bytes(b"external version A\n")
    (directory / "external-b").write_bytes(b"external version B\n")
    newline = b"\r\n" if ending == "crlf" else b"\n"
    (repo / "source.txt").write_bytes(b"A" * width + newline + b"second" + newline)
    (repo / "script.sh").write_bytes(b"exit 0\n")
    (repo / "script.sh").chmod(0o644)
    (repo / ".gitattributes").write_bytes(b"*.txt text eol=lf\n")
    (repo / "external").symlink_to("../external-a")
    for path in exported(repo):
        timestamp(path)
    git(repo, "add", "--all")
    return repo


def exported(repo):
    return sorted(path for path in repo.iterdir() if path.name != ".git")


@dataclass(frozen=True)
class Observation:
    stat_key: tuple
    raw_key: tuple
    tree: str
    source_blob: str


def collect(repo, index):
    stats = []
    raw = []
    for path in exported(repo):
        metadata = path.lstat()
        stats.append((path.name, metadata.st_size, metadata.st_mtime_ns))
        if stat.S_ISLNK(metadata.st_mode):
            raw.append((path.name, "symlink", os.readlink(path)))
        elif stat.S_ISREG(metadata.st_mode):
            executable = bool(metadata.st_mode & stat.S_IXUSR)
            raw.append((path.name, "regular", executable, sha256(path.read_bytes()).hexdigest()))
        else:
            raise ValueError(f"unsupported fixture path kind: {path}")
    git(repo, "add", "--all", index=index)
    tree = git(repo, "write-tree", index=index).decode().strip()
    source = git(repo, "ls-tree", tree, "--", "source.txt").decode().split()
    actual_link = git(repo, "ls-tree", tree, "--", "external").decode().split()
    assert actual_link[:2] == ["120000", "blob"]
    literal = git(repo, "cat-file", "blob", actual_link[2])
    assert literal == os.fsencode(os.readlink(repo / "external"))
    return Observation(tuple(stats), tuple(raw), tree, source[2] if source else "")


def mutate(repo, name, ending):
    source = repo / "source.txt"
    script = repo / "script.sh"
    link = repo / "external"
    if name == "unchanged":
        return
    if name == "stat-touch":
        timestamp(source, BASE_TIME + 5_000_000_000)
    elif name == "same-stat-content":
        source.write_bytes(b"B" + source.read_bytes()[1:])
        timestamp(source)
    elif name == "newline-projection":
        data = source.read_bytes()
        converted = data.replace(b"\r\n", b"\n") if ending == "crlf" else data.replace(b"\n", b"\r\n")
        source.write_bytes(converted)
        timestamp(source)
    elif name == "executable":
        script.chmod(0o755)
    elif name == "external-referent":
        (repo.parent / "external-a").write_bytes(b"external version C\n")
    elif name == "external-link-text":
        link.unlink()
        link.symlink_to("../external-b")
        timestamp(link)
    elif name == "rename":
        script.rename(repo / "renamed\t script.sh")
    elif name == "delete":
        source.unlink()
    elif name == "add":
        (repo / "new file.txt").write_bytes(b"new export\n")
    elif name == "replace-equal-bytes":
        replacement = repo / "replacement.tmp"
        replacement.write_bytes(source.read_bytes())
        timestamp(replacement)
        replacement.replace(source)
    elif name == "attribute-policy":
        attributes = repo / ".gitattributes"
        attributes.write_bytes(b"*.txt -text\n")
        timestamp(attributes)
    else:
        raise ValueError(name)


def outcomes(initial, current, external_referent_changed):
    values = (
        initial.stat_key != current.stat_key,
        initial.raw_key != current.raw_key,
        initial.tree != current.tree,
        initial.source_blob != current.source_blob,
        external_referent_changed,
    )
    names = ("weak_stat_change", "checkout_edit", "canonical_tree_edit",
             "canonical_source_blob_edit", "external_referent_edit")
    return dict(zip(names, values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    # Independent truth table: stat, raw checkout, canonical tree, source blob, referent.
    expected = {
        "unchanged": (0, 0, 0, 0, 0),
        "stat-touch": (1, 0, 0, 0, 0),
        "same-stat-content": (0, 1, 1, 1, 0),
        "newline-projection": (1, 1, 0, 0, 0),
        "executable": (0, 1, 1, 0, 0),
        "external-referent": (0, 0, 0, 0, 1),
        "external-link-text": (0, 1, 1, 0, 1),
        "rename": (1, 1, 1, 0, 0),
        "delete": (1, 1, 1, 1, 0),
        "add": (1, 1, 1, 0, 0),
        "replace-equal-bytes": (0, 0, 0, 0, 0),
        "attribute-policy": (1, 1, 1, None, 0),
    }
    rows = []
    for width, ending, mutation in product((1, 33, 1024), ("lf", "crlf"), expected):
        with TemporaryDirectory(prefix="llmlang-worktree-edit-") as directory:
            parent = Path(directory)
            repo = start(parent, width, ending)
            live_index = repo / ".git" / "index"
            original_index = live_index.read_bytes()
            original_external = (repo / "external").read_bytes()
            before = collect(repo, parent / "before.index")
            mutate(repo, mutation, ending)
            after = collect(repo, parent / "after.index")
            assert live_index.read_bytes() == original_index
            external_changed = (repo / "external").read_bytes() != original_external
        result = outcomes(before, after, external_changed)
        truth = list(expected[mutation])
        if mutation == "attribute-policy":
            truth[3] = ending == "crlf"
        assert tuple(result.values()) == tuple(truth), (width, ending, mutation, result)
        rows.append({"width": width, "starting_endings": ending, "mutation": mutation,
                     "base_tree": before.tree, "observed_tree": after.tree, **result})
    counts = {
        "cases": len(rows),
        "stat_missed_checkout_edits": sum(r["checkout_edit"] and not r["weak_stat_change"] for r in rows),
        "stat_false_checkout_alerts": sum(not r["checkout_edit"] and r["weak_stat_change"] for r in rows),
        "canonical_tree_missed_checkout_edits": sum(r["checkout_edit"] and not r["canonical_tree_edit"] for r in rows),
        "referent_only_edits": sum(r["external_referent_edit"] and not r["checkout_edit"] for r in rows),
    }
    assert list(counts.values()) == [72, 18, 6, 6, 6]
    version = git(HERE, "--version").decode().strip()
    args.output.write_text(json.dumps({"git": version, "counts": counts, "cases": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
