"""Check a local, read-only doctor for exact native merge coordinator context."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


BASE = "79b1a1c4c40c623a3b41ad4147eb448684255873"
DRIVER = "fixture-semantic-driver"
MERGETOOL = "fixture-semantic-review"
PATH = "source/entry.llm"
EXPECTED = {
    "merge.llmlang.driver": DRIVER,
    "mergetool.llmlang.cmd": MERGETOOL,
    "mergetool.llmlang.trustExitCode": "false",
}


def git(workspace, *args, check=True):
    env = {**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    return subprocess.run(["git", *args], cwd=workspace, check=check,
                          capture_output=True, env=env, timeout=10)


def setup(repo, fmt):
    git(repo, "init", "-q", "-b", "main", f"--object-format={fmt}")
    for key, value in EXPECTED.items():
        git(repo, "config", key, value)
    (repo / ".gitattributes").write_text("*.llm merge=llmlang\n")
    (repo / PATH).parent.mkdir()
    (repo / PATH).write_text("fixture source\n")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@local.example", "commit", "-qm", "base")
    return git(repo, "rev-parse", "HEAD^{tree}").stdout.decode().strip()


def attribute(repo, pinned=False):
    source = ("--source", "HEAD") if pinned else ()
    data = git(repo, "check-attr", "-z", *source, "merge", "--", PATH).stdout.split(b"\0")
    assert data[:2] == [PATH.encode(), b"merge"]
    return data[2].decode()


def doctor(repo, tree, executable_available):
    if tree is None or tree != git(repo, "rev-parse", "HEAD^{tree}").stdout.decode().strip():
        return "required-tree-unavailable"
    pinned, effective = attribute(repo, True), attribute(repo)
    if pinned != "llmlang" or effective != pinned:
        return "attribute-scope-mismatch"
    for key, expected in EXPECTED.items():
        observed = git(repo, "config", "--get", key, check=False)
        if observed.returncode or observed.stdout.decode().strip() != expected:
            return "configuration-mismatch"
    if not executable_available:
        return "coordinator-unavailable"
    return "ready-for-candidate-check"


def run():
    cases = {
        "exact": "ready-for-candidate-check",
        "untracked-override": "attribute-scope-mismatch",
        "local-info-override": "attribute-scope-mismatch",
        "unconfigured-driver": "configuration-mismatch",
        "different-driver": "configuration-mismatch",
        "trusted-ui-exit": "configuration-mismatch",
        "missing-coordinator": "coordinator-unavailable",
        "wrong-tree": "required-tree-unavailable",
        "absent-tree": "required-tree-unavailable",
    }
    archive = {}
    for fmt, (name, expected) in product(("sha1", "sha256"), cases.items()):
        with TemporaryDirectory() as temporary:
            repo = Path(temporary)
            actual_tree = setup(repo, fmt)
            requested = actual_tree
            if name == "untracked-override":
                (repo / "source/.gitattributes").write_text("*.llm -merge\n")
            elif name == "local-info-override":
                (repo / ".git/info/attributes").write_text("*.llm -merge\n")
            elif name == "unconfigured-driver":
                git(repo, "config", "--unset", "merge.llmlang.driver")
            elif name == "different-driver":
                git(repo, "config", "merge.llmlang.driver", "another-fixture-driver")
            elif name == "trusted-ui-exit":
                git(repo, "config", "mergetool.llmlang.trustExitCode", "true")
            elif name == "wrong-tree":
                requested = "0" * len(actual_tree)
            elif name == "absent-tree":
                requested = None
            before = (repo / PATH).read_bytes(), git(repo, "rev-parse", "HEAD").stdout
            state = doctor(repo, requested, name != "missing-coordinator")
            assert state == expected, (name, state)
            assert before == ((repo / PATH).read_bytes(), git(repo, "rev-parse", "HEAD").stdout)
            archive[f"{fmt}/{name}"] = state

    versions = subprocess.check_output(["git", "--version"], text=True).strip()
    return {"baseline": BASE, "git": versions, "cases": archive, "counts": dict(Counter(archive.values())),
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
