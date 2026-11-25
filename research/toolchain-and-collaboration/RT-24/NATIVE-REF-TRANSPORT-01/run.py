"""Exercise ordinary Git ref transport with a closed typed snapshot reader."""

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "COMMIT-TREE-SEMANTIC-ROOT-01"))
from run import SOURCES, from_tree, git

BASELINE = "e1695217c29d59437e306748bc9faf2dfd7e4353"
BRANCH = "research/all"


def oid(repo, expression):
    return git(repo, "rev-parse", "--verify", expression).decode().strip()


def read(repo, expression):
    commit = oid(repo, expression + "^{commit}")
    tree = oid(repo, commit + "^{tree}")
    root, observations = from_tree(repo, tree)
    return {
        "commit": commit, "tree": tree, "semantic_root": root,
        "observations": observations,
        "parents": git(repo, "show", "-s", "--format=%P", commit).decode().split(),
    }


def absent(repo, ref):
    try:
        git(repo, "show-ref", "--verify", "--quiet", ref)
    except subprocess.CalledProcessError as error:
        assert error.returncode == 1
    else:
        raise AssertionError(f"unexpected ref {ref}")


def commit(repo, message):
    git(repo, "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", message)


def exercise(directory, object_format):
    origin, publisher, reader = (directory / name for name in ("origin", "publisher", "reader"))
    directory.mkdir()
    git(directory, "init", "--quiet", "--bare", f"--object-format={object_format}",
        f"--initial-branch={BRANCH}", str(origin))
    git(directory, "init", "--quiet", f"--object-format={object_format}",
        f"--initial-branch={BRANCH}", str(publisher))
    git(publisher, "remote", "add", "origin", origin.as_uri())
    for name, content in SOURCES.items():
        (publisher / name).write_bytes(content)
    git(publisher, "add", *SOURCES)
    commit(publisher, "Initial program")
    git(publisher, "push", "--quiet", "origin", BRANCH)
    git(directory, "clone", "--quiet", origin.as_uri(), str(reader))
    initial = read(reader, "HEAD")
    assert initial == read(origin, BRANCH)
    assert oid(reader, "refs/remotes/origin/HEAD") == initial["commit"]
    assert initial["observations"] == [0, 1, 2]
    assert not (reader / ".git" / "hooks" / "pre-push").exists()

    git(publisher, "switch", "--quiet", "-c", "preview")
    (publisher / "program.json").write_bytes(SOURCES["program.json"].replace(b"plus", b"minus"))
    git(publisher, "add", "program.json")
    commit(publisher, "Select subtraction")
    git(publisher, "-c", "tag.gpgsign=false", "tag", "-a", "v1", "-m", "Subtraction release")
    git(publisher, "push", "--quiet", "origin", "preview", "refs/tags/v1")
    absent(reader, "refs/remotes/origin/preview")
    absent(reader, "refs/tags/v1")
    git(reader, "fetch", "--quiet", "--no-tags", "origin")
    preview = read(reader, "origin/preview")
    assert preview == read(origin, "preview")
    assert preview["parents"] == [initial["commit"]]
    assert preview["observations"] == [-2, -1, 0]
    assert preview["semantic_root"] != initial["semantic_root"]
    assert read(reader, "HEAD") == initial
    absent(reader, "refs/tags/v1")
    git(reader, "fetch", "--quiet", "origin", "refs/tags/v1:refs/tags/v1")
    tag = oid(reader, "refs/tags/v1")
    assert tag == oid(origin, "refs/tags/v1") and tag != preview["commit"]
    assert git(reader, "cat-file", "-t", tag).strip() == b"tag"
    assert read(reader, "refs/tags/v1") == preview

    git(publisher, "switch", "--quiet", BRANCH)
    git(publisher, "merge", "--quiet", "--ff-only", "preview")
    git(publisher, "push", "--quiet", "origin", BRANCH)
    git(reader, "fetch", "--quiet", "origin")
    assert read(reader, f"origin/{BRANCH}") == preview
    assert read(reader, "HEAD") == initial
    git(reader, "merge", "--quiet", "--ff-only", f"origin/{BRANCH}")
    assert read(reader, "HEAD") == preview

    (publisher / "program.json").write_bytes(SOURCES["program.json"])
    git(publisher, "add", "program.json")
    commit(publisher, "Restore addition")
    git(publisher, "push", "--quiet", "origin", BRANCH)
    try:
        git(reader, "push", "--porcelain", "origin", f"HEAD:refs/heads/{BRANCH}")
    except subprocess.CalledProcessError as error:
        assert error.returncode == 1 and b"[rejected]" in error.output
        assert b"(fetch first)" in error.output or b"(non-fast-forward)" in error.output
    else:
        raise AssertionError("stale push overwrote history")

    git(publisher, "push", "--quiet", "origin", "--delete", "preview")
    git(reader, "fetch", "--quiet", "--prune", "origin")
    absent(reader, "refs/remotes/origin/preview")
    git(reader, "merge", "--quiet", "--ff-only", f"origin/{BRANCH}")
    restored = read(reader, "HEAD")
    assert restored == read(origin, BRANCH)
    assert restored["commit"] != initial["commit"]
    assert restored["parents"] == [preview["commit"]]
    for key in ("tree", "semantic_root", "observations"):
        assert restored[key] == initial[key]
    assert read(reader, "refs/tags/v1") == preview
    history = git(reader, "rev-list", BRANCH).decode().splitlines()
    assert history == [row["commit"] for row in (restored, preview, initial)]
    git(reader, "fsck", "--full")
    return {
        "initial": initial, "preview": preview, "restored": restored, "annotated_tag": tag,
        "branch_history": history, "ordinary_stale_push_rejected": True,
        "deleted_preview_branch_pruned": True, "tag_survived_prune": True,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="llmlang-ref-transport-") as temp:
        results = {fmt: exercise(Path(temp) / fmt, fmt) for fmt in ("sha1", "sha256")}
    for name in ("initial", "preview", "restored"):
        a, b = (results[fmt][name] for fmt in ("sha1", "sha256"))
        assert a["commit"] != b["commit"] and a["tree"] != b["tree"]
        assert a["semantic_root"] == b["semantic_root"] and a["observations"] == b["observations"]
    helper = HERE.parent / "COMMIT-TREE-SEMANTIC-ROOT-01" / "run.py"
    root = HERE.parents[3]
    sources = [helper, *(
        root / "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src" / name
        for name in ("spg_admission.py", "spg_representation.py", "semantic_graph.py",
                     "recursive_identity.py")
    )]
    pins = {}
    for source in sources:
        relative = str(source.relative_to(root))
        archived = git(root, "show", f"{BASELINE}:{relative}")
        assert archived == source.read_bytes(), relative
        pins[relative] = hashlib.sha256(archived).hexdigest()
    print(json.dumps({
        "baseline": BASELINE, "git": git(root, "--version").decode().strip(),
        "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": pins, "formats": results,
    }, indent=2))


if __name__ == "__main__":
    main()
