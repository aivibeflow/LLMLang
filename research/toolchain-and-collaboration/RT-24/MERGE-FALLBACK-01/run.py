"""Compare unavailable merge policies in disposable native Git repositories."""

from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

BASELINE = "5324a4882175d5fe652a7417403d1a106ce195c9"
GIT_ENV = {
    **os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2026-11-25T00:00:00+00:00", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00+00:00",
}
GAP = "\n".join(f"# stable field boundary {i}" for i in range(12))


def git(root, *args, check=True):
    return subprocess.run(["git", *args], cwd=root, env=GIT_ENV, capture_output=True,
                          check=check, text=True, timeout=30)


def single_path(root, left, right):
    (root / "graph.spg").write_text(f"left={left}\n{GAP}\nright={right}\n", encoding="utf-8")


def fixture(root, policy, scope):
    root.mkdir()
    git(root, "init", "-q", "--initial-branch=base", "--object-format=sha1")
    attribute = "merge=llmlang" if policy != "native-binary" else "-merge"
    (root / ".gitattributes").write_text(f"*.spg {attribute}\n")
    if scope == "separate-files":
        for label in ("left", "right"):
            (root / f"{label}.spg").write_text(f"{label}=0\n")
    else:
        single_path(root, 0, 0)
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    origin = git(root, "rev-parse", "HEAD").stdout.strip()

    git(root, "switch", "-qc", "left")
    if scope == "separate-files":
        (root / "left.spg").write_text("left=1\n")
    else:
        single_path(root, 1, 0)
    git(root, "commit", "-qam", "left")
    left = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "switch", "-qc", "right", origin)
    if scope == "separate-files":
        (root / "right.spg").write_text("right=1\n")
    elif scope == "one-sided":
        (root / "notes.txt").write_text("Unrelated edit.\n")
        git(root, "add", "notes.txt")
    else:
        single_path(root, 0, 1)
    git(root, "commit", "-qam", "right")
    right = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "switch", "-q", "left")
    if policy == "missing-command":
        git(root, "config", "merge.llmlang.driver", "./absent-fixture-merge-tool %O %A %B")
    if policy == "refused":
        git(root, "config", "merge.llmlang.driver", "false")
    return origin, left, right


def verify_tree(root, scope, ref=""):
    paths = ("left.spg", "right.spg") if scope == "separate-files" else ("graph.spg",)
    lines = [line for path in paths for line in git(root, "show", f"{ref}:{path}").stdout.splitlines()
             if "=" in line and not line.startswith("#")]
    values = dict(line.split("=", 1) for line in lines)
    return "capacity-ok" if int(values["left"]) + int(values["right"]) <= 1 else "capacity-exceeded"


def replay():
    cases = (
        ("unconfigured-custom", "same-file", 0, "capacity-exceeded"),
        ("missing-command", "same-file", 1, "unmerged"),
        ("refused", "same-file", 1, "unmerged"),
        ("native-binary", "same-file", 1, "unmerged"),
        ("native-binary", "separate-files", 0, "capacity-exceeded"),
        ("native-binary", "one-sided", 0, "capacity-ok"),
    )
    rows = []
    with TemporaryDirectory(prefix="llmlang-merge-fallback-") as work:
        for index, (policy, scope, expected_exit, expected_validation) in enumerate(cases):
            root = Path(work) / str(index)
            commits = fixture(root, policy, scope)
            # Each parent independently meets the capacity rule.
            assert git(root, "rev-parse", "HEAD").stdout.strip() == commits[1]
            assert all(verify_tree(root, scope, commit) == "capacity-ok" for commit in commits)
            result = git(root, "merge", "--no-commit", "--no-ff", "right", check=False)
            raw = git(root, "ls-files", "--unmerged").stdout
            staged = [line.split() for line in raw.splitlines()]
            if expected_exit:
                for i, commit in enumerate(commits, 1):
                    file_hash = git(root, "rev-parse", f"{commit}:graph.spg").stdout.strip()
                    assert any(row[1:] == [file_hash, str(i), "graph.spg"] for row in staged)
                assert len(staged) == 3
                observed = "unmerged"
            else:
                assert not staged
                observed = verify_tree(root, scope)
            assert (result.returncode, observed) == (expected_exit, expected_validation)
            assert git(root, "rev-parse", "HEAD").stdout.strip() == commits[1]
            rows.append({"policy": policy, "edit_scope": scope, "git_exit": result.returncode,
                         "stages": [int(row[2]) for row in staged], "whole_tree_check": observed,
                         "candidate_eligible": observed == "capacity-ok", "input_commits": commits})
    return {
        "schema": "rt24-merge-fallback-admission-v1", "baseline": BASELINE,
        "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "python": platform.python_version(), "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": rows,
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
