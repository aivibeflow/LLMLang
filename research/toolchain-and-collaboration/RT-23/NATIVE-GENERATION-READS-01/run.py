"""Compare pinned multi-file views, retention, and exact Git reads on Linux."""
import argparse
from contextlib import ExitStack
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import select
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import canonical_bytes
from tests import test_rt24_merge_tree_gate as tree

LEFT, RIGHT = "program/left.json", "program/right.json"
FILES = (LEFT, RIGHT)
BRANCH = "refs/heads/main"
CASES = (
    ("path", "switch", "mixed"),
    ("directory-fd", "switch", "old"),
    ("directory-fd", "mutate-old", "mixed"),
    ("directory-fd", "reclaim-old", "missing"),
    ("directory-lease", "reclaim-old", "old"),
    ("manifest", "switch", "digest-mismatch"),
    ("current-ref", "publish-git", "mixed"),
    ("pinned-git", "publish-git", "old"),
)


def git(repo, *args):
    return tree.git(repo, *args).decode().strip()


def content_sha(data):
    return sha256(data).hexdigest()


def bootstrap(directory):
    repo = directory / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
    revisions = {}
    for generation in ("old", "new"):
        sources = {
            path: [tree.row(path, tree.declaration(
                "contract", f"contract:{path}", {"generation": generation},
            ))]
            for path in FILES
        }
        if generation == "old":
            sources[tree.MANIFEST] = tree.manifest(*FILES)
        pin = tree.commit(repo, sources)
        root = tree.import_closed(tree.read_inventory(repo, pin))[1].root_hash
        revisions[generation] = {"commit": pin, "root": root}
        for path in FILES:
            output = directory / generation / path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(tree.git(repo, "show", f"{pin}:{path}"))
        manifest = {path: content_sha((directory / generation / path).read_bytes()) for path in FILES}
        (directory / generation / "digest.json").write_bytes(canonical_bytes(manifest))
        (directory / f"{generation}.lease").touch()
    assert revisions["old"]["root"] != revisions["new"]["root"]
    git(repo, "update-ref", BRANCH, revisions["old"]["commit"], revisions["new"]["commit"])
    git(repo, "fsck", "--full")
    os.symlink("old", directory / "current")
    return revisions


def path_reader(directory, stack, strategy):
    if strategy == "directory-lease":
        view = os.readlink(directory / "current")
        lock = stack.enter_context((directory / f"{view}.lease").open("rb"))
        fcntl.flock(lock, fcntl.LOCK_SH)
        base = directory / view
    else:
        base = directory / "current"

    if strategy in {"directory-fd", "directory-lease"}:
        descriptor = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
        stack.callback(os.close, descriptor)

        def pinned(path):
            with os.fdopen(os.open(path, os.O_RDONLY, dir_fd=descriptor), "rb") as source:
                return source.read()

        return pinned
    return lambda path: (base / path).read_bytes()


def read(directory, strategy):
    with ExitStack() as stack:
        if strategy in {"pinned-git", "current-ref"}:
            repo = directory / "repo"
            pin = git(repo, "rev-parse", BRANCH) if strategy == "pinned-git" else BRANCH

            def available(path):
                return tree.git(repo, "show", f"{pin}:{path}")
        else:
            available = path_reader(directory, stack, strategy)

        digest_manifest = json.loads(available("digest.json")) if strategy == "manifest" else None
        left = available(LEFT)
        print("first-file-read", flush=True)
        if sys.stdin.readline() != "continue\n":
            raise ValueError("missing controller acknowledgment")
        try:
            right = available(RIGHT)
        except FileNotFoundError:
            return {"status": "missing", "root": None}
        payloads = dict(zip(FILES, (left, right), strict=True))
        generations, declarations = {}, {}
        for path, raw in payloads.items():
            row, = json.loads(raw)
            declarations[row["slot"]] = row["declaration"]
            generations[path] = row["declaration"]["content"]["generation"]
        if digest_manifest and digest_manifest != {path: content_sha(raw) for path, raw in payloads.items()}:
            return {"status": "digest-mismatch", "generations": generations, "root": None}
        _, snapshot = tree.import_closed(tree.Inventory("filesystem-fixture", "", declarations))
        status = generations[LEFT] if generations[LEFT] == generations[RIGHT] else "mixed"
        return {"status": status, "generations": generations, "root": snapshot.root_hash}


def switch(directory):
    temporary = directory / "next-pointer"
    os.symlink("new", temporary)
    os.replace(temporary, directory / "current")


def try_reclaim(directory):
    with (directory / "old.lease").open("rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "reader-holds-lease"
        (directory / "old" / RIGHT).unlink()
        return "reclaimed"


def intervene(directory, transition, pins):
    if transition == "publish-git":
        git(directory / "repo", "update-ref", BRANCH, pins["new"]["commit"], pins["old"]["commit"])
        return "ref-published"
    if transition == "mutate-old":
        fresh = directory / "mutated.json"
        fresh.write_bytes((directory / "new" / RIGHT).read_bytes())
        os.replace(fresh, directory / "old" / RIGHT)
        switch(directory)
        return "old-file-replaced"
    switch(directory)
    if transition == "reclaim-old":
        return try_reclaim(directory)
    return "pointer-switched"


def trial(directory, strategy, transition, expected):
    directory.mkdir()
    pins = bootstrap(directory)
    with subprocess.Popen([sys.executable, __file__, "--reader", strategy, "--directory", str(directory)],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as child:
        try:
            ready, _, _ = select.select([child.stdout], [], [], 10)
            assert ready and child.stdout.readline() == "first-file-read\n"
            observed_transition = intervene(directory, transition, pins)
            result, error = child.communicate(input="continue\n", timeout=10)
            assert child.returncode == 0, error
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
    observation = json.loads(result)
    assert observation["status"] == expected, observation
    if expected == "old":
        assert observation["root"] == pins["old"]["root"]
    if expected == "mixed":
        assert observation["root"] not in {row["root"] for row in pins.values()}
        assert observation["generations"] == {LEFT: "old", RIGHT: "new"}
    after_release = None
    if strategy == "directory-lease":
        assert observed_transition == "reader-holds-lease"
        after_release = try_reclaim(directory)
        assert after_release == "reclaimed"
    if transition == "reclaim-old" and strategy != "directory-lease":
        assert observed_transition == "reclaimed"
    return {"observation": observation, "transition": observed_transition, "after_release": after_release,
            "pins": pins}


def replay(directory):
    results = {}
    for strategy, transition, expected in CASES:
        name = f"{strategy}/{transition}"
        results[name] = trial(directory / f"{strategy}-{transition}", strategy, transition, expected)
    mixed_roots = {row["observation"]["root"] for row in results.values() if row["observation"]["status"] == "mixed"}
    assert len(mixed_roots) == 1
    version = git(directory, "--version")
    assert version == "git version 2.52.0" and sys.platform == "linux"
    return {"format": "rt23-native-generation-reads/1", "python": sys.version.split()[0],
            "git": version, "cases": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--reader")
    args = parser.parse_args()
    if args.reader is not None:
        print(json.dumps(read(args.directory, args.reader)))
    else:
        with TemporaryDirectory(prefix="llmlang-native-generation-reads-") as scratch:
            evidence = replay(Path(scratch))
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
