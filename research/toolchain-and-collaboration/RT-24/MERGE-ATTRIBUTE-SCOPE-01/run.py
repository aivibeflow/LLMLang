"""Measure effective Git attributes and retained stages on an identical merge."""

from hashlib import sha256
import json
from pathlib import Path
import platform
import runpy
from tempfile import TemporaryDirectory


REFERENCE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "MERGE-FALLBACK-01/run.py"))
git = REFERENCE["git"]
GAP = REFERENCE["GAP"]
OBJECT = "nested/graph.spg"


def write(root, path, text):
    (root / path).write_text(text, encoding="utf-8")


def graph(root, left, right):
    write(root, OBJECT, f"left={left}\n{GAP}\nright={right}\n")


def commit(root, message):
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD").stdout.strip()


def initialize(root, nested_policy):
    root.mkdir()
    git(root, "init", "-q", "--initial-branch=research/all", "--object-format=sha1")
    (root / "nested").mkdir()
    write(root, ".gitattributes", "*.spg -merge\n")
    if nested_policy:
        write(root, "nested/.gitattributes", "*.spg merge=text\n")
    graph(root, 0, 0)
    base = commit(root, "base")
    graph(root, 1, 0)
    ours = commit(root, "ours")
    git(root, "checkout", "--detach", "-q", base)
    graph(root, 0, 1)
    theirs = commit(root, "theirs")
    git(root, "checkout", "-q", "research/all")
    return base, ours, theirs


def merge_attr(root, *options):
    return git(root, "check-attr", *options, "-z", "merge", "--", OBJECT).stdout.split("\0")[2]


def total(root, tree):
    data = git(root, "show", f"{tree}:{OBJECT}").stdout
    fields = dict(line.split("=", 1) for line in data.splitlines() if line and not line.startswith("#"))
    return int(fields["left"]) + int(fields["right"])


def run_case(root, mode):
    commits = initialize(root, mode in ("nested-text", "info-binary-over-nested"))
    info = root / ".git/info"
    info.mkdir(exist_ok=True)
    if mode == "info-text":
        write(root, ".git/info/attributes", "*.spg merge=text\n")
    if mode == "info-binary-over-nested":
        write(root, ".git/info/attributes", "*.spg -merge\n")
    if mode == "worktree-text":
        write(root, "nested/.gitattributes", "*.spg merge=text\n")

    attributes = {
        "worktree": merge_attr(root),
        "index": merge_attr(root, "--cached"),
        "head_source": merge_attr(root, "--source=HEAD"),
    }
    result = git(root, "merge", "--no-ff", "--no-commit", commits[2], check=False)
    staged = git(root, "ls-files", "--unmerged", "--", OBJECT).stdout.splitlines()
    rows = [row.split() for row in staged]
    stage_numbers = [int(row[2]) for row in rows]
    if rows:
        assert stage_numbers == [1, 2, 3]
        for row, commit_id in zip(rows, commits):
            assert row[1] == git(root, "rev-parse", f"{commit_id}:{OBJECT}").stdout.strip()
        candidate_total = None
    else:
        tree = git(root, "write-tree").stdout.strip()
        candidate_total = total(root, tree)

    assert [total(root, commit_id) for commit_id in commits] == [0, 1, 1]
    assert git(root, "rev-parse", "HEAD").stdout.strip() == commits[1]
    return {
        "attributes": attributes,
        "git_exit": result.returncode,
        "input_commits": commits,
        "unmerged_stages": stage_numbers,
        "staged_candidate_total": candidate_total,
        "admissible_graph": candidate_total is not None and candidate_total <= 1,
    }


def study(root):
    expected = {
        "tracked-binary": (["unset", "unset", "unset"], 1, None),
        "nested-text": (["text", "text", "text"], 0, 2),
        "info-text": (["text", "text", "text"], 0, 2),
        "info-binary-over-nested": (["unset", "unset", "unset"], 1, None),
        "worktree-text": (["text", "unset", "unset"], 0, 2),
    }
    results = {}
    for mode, (attributes, exit_code, candidate) in expected.items():
        row = run_case(root / mode, mode)
        assert list(row["attributes"].values()) == attributes, row
        assert (row["git_exit"], row["staged_candidate_total"]) == (exit_code, candidate), row
        assert row["unmerged_stages"] == ([1, 2, 3] if candidate is None else [])
        assert not row["admissible_graph"]
        results[mode] = row
    assert results["tracked-binary"]["input_commits"] == results["info-text"]["input_commits"]
    assert results["tracked-binary"]["input_commits"] == results["worktree-text"]["input_commits"]
    return {
        "git": git(root, "--version").stdout.strip(),
        "python": platform.python_version(),
        "reused_harness_sha256": sha256(Path(REFERENCE["__file__"]).read_bytes()).hexdigest(),
        "results": results,
    }


if __name__ == "__main__":
    with TemporaryDirectory() as temporary:
        print(json.dumps(study(Path(temporary)), indent=2, sort_keys=True))
