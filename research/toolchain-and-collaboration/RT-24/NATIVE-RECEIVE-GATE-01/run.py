"""Compare Git ref-update policies using native push and receives in local fixtures."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from tests.test_rt24_merge_tree_gate import (
    CALLEE, CALLER, GraphImportError, MergeTreeGateExperiment, commit, git, import_closed,
    read_inventory, row,
)


HOOK = Path(__file__).with_name("receive.py").resolve()
LANES = ("good", "bad")


def invoke(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                                       "GIT_CONFIG_GLOBAL": os.devnull},
        capture_output=True, timeout=30,
    )


def ref(repo, name):
    result = invoke(repo, "rev-parse", "--verify", f"refs/heads/{name}")
    if result.returncode != 0:
        return None
    return result.stdout.decode().strip()


def graph(repo, revision):
    if revision is None:
        return None
    try:
        _, snapshot = import_closed(read_inventory(repo, revision))
    except GraphImportError:
        return "unclosed"
    return snapshot.root_hash


def prepare(fixture):
    repo = fixture.repo
    git(repo, "switch", "--quiet", "-c", "good", fixture.base)
    good = commit(repo, {"notes.txt": "independent change\n"})
    git(repo, "switch", "--quiet", "-c", "bad", fixture.base)
    bad = commit(repo, {CALLEE: [row("callee", fixture.new)], CALLER: [row("caller", fixture.caller)]})
    git(repo, "switch", "--quiet", "-c", "repaired", bad)
    repaired = commit(repo, {CALLER: []})
    assert graph(repo, bad) == "unclosed"
    assert all(graph(repo, pin) not in (None, "unclosed") for pin in (fixture.base, good, repaired))
    return {"base": fixture.base, "good": good, "bad": bad, "repaired": repaired}


def install(receiver, mode, ledger):
    hook = receiver / "hooks" / ("update" if mode == "update" else "pre-receive")
    command = shlex.join([sys.executable, str(HOOK), mode, str(ledger)])
    hook.write_text(f'#!/bin/sh\nexec {command} "$@"\n', encoding="utf-8")
    hook.chmod(0o700)


REQUESTS = {
    "mixed": ("good:refs/heads/good", "bad:refs/heads/bad"),
    "repaired": ("repaired:refs/heads/good",),
    "duplicate-tip": ("good:refs/heads/good", "good:refs/heads/bad"),
    "delete": (":refs/heads/bad",),
}


def trial(mode, request, expected, *, atomic=False, preexisting=False):
    fixture = MergeTreeGateExperiment()
    fixture.setUp()
    try:
        sender = fixture.repo
        source = prepare(fixture)
        with TemporaryDirectory(prefix="rt24-receive-") as base:
            base = Path(base)
            receiver = base / "receiver.git"
            git(base, "init", "--bare", "--quiet", "--template=", "--object-format=sha1", str(receiver))
            (receiver / "hooks").mkdir()
            seeds = [f'{source["base"]}:refs/heads/{lane}' for lane in LANES]
            if preexisting:
                seeds.append("bad:refs/heads/imported")
            git(sender, "push", str(receiver), *seeds)
            ledger = base / "observations.ndjson"
            if mode != "none":
                install(receiver, mode, ledger)
            options = ["--atomic"] if atomic else []
            result = invoke(sender, "push", *options, str(receiver), *REQUESTS[request])
            calls = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
            selected = {lane: ref(receiver, lane) for lane in LANES}
            wanted_status, wanted_good, wanted_bad = expected
            assert result.returncode == wanted_status, (mode, request, result.stderr)
            assert selected == {"good": source.get(wanted_good), "bad": source.get(wanted_bad)}, selected

            reachable = set(git(receiver, "rev-list", "--all").decode().splitlines())
            available = invoke(receiver, "cat-file", "-e", source["bad"]).returncode == 0
            shapes = {lane: graph(receiver, pin) for lane, pin in selected.items()}
            for observation in calls:
                assert observation["quarantine"] == (mode != "update" and request != "delete")
            return {"mode": mode, "request": request, "atomic": atomic, "preexisting_unclosed": preexisting,
                    "pushed_commits": source, "push_status": result.returncode, "selected_refs": selected,
                    "selected_graphs": shapes, "unclosed_object_available": available,
                    "unclosed_commit_reachable": source["bad"] in reachable, "hook_calls": calls}
    finally:
        fixture.doCleanups()


def evaluate():
    result = [
        trial("none", "mixed", (0, "good", "bad")),
        trial("update", "mixed", (1, "good", "base")),
        trial("update", "mixed", (1, "base", "base"), atomic=True),
        trial("tips", "mixed", (1, "base", "base")),
        trial("history", "mixed", (1, "base", "base")),
        trial("tips", "repaired", (0, "repaired", "base")),
        trial("history", "repaired", (1, "base", "base")),
        trial("history", "repaired", (0, "repaired", "base"), preexisting=True),
        trial("history", "duplicate-tip", (0, "good", "good")),
        trial("history", "delete", (0, "base", None)),
    ]
    assert all(not result[index]["unclosed_object_available"] for index in (3, 4, 6))
    assert result[5]["unclosed_commit_reachable"] and result[7]["unclosed_commit_reachable"]
    assert len(result[8]["hook_calls"][0]["checked"]) == 1
    assert result[9]["hook_calls"][0]["checked"] == []
    return {"format": "rt24-native-receive-gate/1",
            "git": subprocess.check_output(["git", "--version"], text=True).strip(),
            "python": sys.version.split()[0], "results": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(evaluate(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
