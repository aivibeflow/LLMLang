"""Exercise exact conflict stages and whole-graph validation in native Git."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


BASE = "a3f892f"
OPERATIONS = ("merge", "cherry-pick", "rebase")
SCENARIOS = ("same-slot", "disjoint-incompatible", "independent")


def invoke(repo, *args, check=True):
    environment = {**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "GIT_EDITOR": "true", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z",
                   "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z"}
    return subprocess.run(["git", *args], cwd=repo, env=environment, capture_output=True,
                          check=check, timeout=10)


def put(repo, path, value):
    (repo / path).write_bytes((str(value) + "\n").encode())


def commit(repo, title):
    invoke(repo, "add", "--all")
    invoke(repo, "commit", "-qm", title)


def setup(repo, format_name, autocrlf, scenario):
    invoke(repo, "init", "-q", "-b", "primary", f"--object-format={format_name}")
    for option, value in (("user.name", "Fixture"), ("user.email", "fixture@local.example"),
                          ("core.autocrlf", autocrlf)):
        invoke(repo, "config", option, value)
    (repo / ".gitattributes").write_text("semantic.slot -merge\n*.txt text eol=lf\n")
    put(repo, "semantic.slot", "shared")
    put(repo, "contract.txt", 10)
    put(repo, "provider.txt", 4)
    put(repo, "note.txt", "initial")
    commit(repo, "base")
    invoke(repo, "branch", "feature")
    if scenario == "same-slot":
        put(repo, "semantic.slot", "primary choice")
    else:
        put(repo, "contract.txt", 5)
    commit(repo, "primary edits")

    invoke(repo, "switch", "-q", "feature")
    if scenario == "same-slot":
        put(repo, "semantic.slot", "feature choice")
    elif scenario == "disjoint-incompatible":
        put(repo, "provider.txt", 7)
    else:
        put(repo, "note.txt", "independent update")
    commit(repo, "feature edits")


def compare(repo, operation, format_name, autocrlf, scenario):
    setup(repo, format_name, autocrlf, scenario)
    if operation == "rebase":
        native = invoke(repo, "rebase", "primary", check=False)
    else:
        invoke(repo, "switch", "-q", "primary")
        args = (("merge", "--no-edit", "feature") if operation == "merge" else ("cherry-pick", "feature"))
        native = invoke(repo, *args, check=False)
    unmerged = invoke(repo, "ls-files", "-u").stdout.decode().splitlines()
    if scenario == "same-slot":
        assert native.returncode != 0 and len(unmerged) == 3
        by_stage = {record.split()[2]: record.split()[3] for record in unmerged}
        assert by_stage == {"1": "semantic.slot", "2": "semantic.slot", "3": "semantic.slot"}
        original, left, right = (invoke(repo, "show", f":{index}:semantic.slot").stdout.decode().strip()
                                 for index in (1, 2, 3))
        assert original == "shared" and {left, right} == {"primary choice", "feature choice"}
        return "unmerged-preserved"

    assert native.returncode == 0 and not unmerged
    expected = 5, 7 if scenario == "disjoint-incompatible" else 4
    contract, provider = (int(invoke(repo, "show", f"HEAD:{path}").stdout)
                          for path in ("contract.txt", "provider.txt"))
    assert (contract, provider) == expected
    assert invoke(repo, "show", "HEAD:contract.txt").stdout == b"5\n"
    return "typed-refusal" if provider > contract else "typed-eligible"


def run():
    results = {}
    with TemporaryDirectory() as directory:
        for operation, format_name, autocrlf, scenario in product(
            OPERATIONS, ("sha1", "sha256"), ("false", "true"), SCENARIOS,
        ):
            name = "/".join((operation, format_name, autocrlf, scenario))
            repo = Path(directory) / name.replace("/", "-")
            repo.mkdir()
            results[name] = compare(repo, operation, format_name, autocrlf, scenario)
    counts = Counter(results.values())
    assert len(results) == 36 and set(counts.values()) == {12}
    return {
        "baseline": BASE, "from_native_git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "python": platform.python_version(), "kernel": platform.release(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": counts, "cases": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
