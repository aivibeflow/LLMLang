"""Observe exact Git branch and receipt during a controlled commit-phase cut."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt24_merge_tree_gate as source


def git(repo, *args):
    return source.git(repo, *args).decode("utf-8").strip()


def setup(repo, backend):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=main",
        "--object-format=sha1", f"--ref-format={backend}")
    manifest = source.manifest(source.CONTRACT)

    def row(revision):
        return source.row("contract", source.declaration("contract", "contract:receipt", {"revision": revision}))

    first = source.commit(repo, {source.MANIFEST: manifest, source.CONTRACT: [row("old")]})
    git(repo, "switch", "--quiet", "-c", "preparation")
    prepared = source.commit(repo, {source.CONTRACT: [row("new")]})
    inventory = source.read_inventory(repo, prepared)
    _, snapshot = source.import_closed(inventory)
    return recovery.Prepared("ref visibility", inventory.tree, snapshot.root_hash, (first,), prepared)


def refs(repo, plan):
    return {"branch": recovery.ref(repo, recovery.BRANCH),
            "receipt": recovery.ref(repo, plan.receipt),
            "inspection": recovery.inspect(repo, plan),
            "single_command": git(repo, "for-each-ref", "--format=%(refname) %(objectname)",
                                  recovery.BRANCH, plan.receipt).splitlines()}


def await_stop(process):
    expiration = time.monotonic() + 10
    while time.monotonic() < expiration:
        pid, status = os.waitpid(process.pid, os.WNOHANG | os.WUNTRACED)
        if not pid:
            time.sleep(0.01)
            continue
        if os.WIFSTOPPED(status) and os.WSTOPSIG(status) == signal.SIGSTOP:
            return
        if os.WIFEXITED(status) or os.WIFSIGNALED(status):
            process.returncode = os.waitstatus_to_exitcode(status)
        raise RuntimeError("Git exited or stopped before the expected successful rename")
    raise TimeoutError("Git did not reach the commit cut")


def cut(repo, plan, preload, suffix, kill):
    commands = (f"start\nupdate {recovery.BRANCH} {plan.candidate} {plan.parents[0]}\n"
                f"create {plan.receipt} {plan.candidate}\nprepare\ncommit\n").encode()
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "LD_PRELOAD": str(preload), "LLMLANG_PAUSE_RENAME_SUFFIX": suffix}
    with subprocess.Popen(["git", "update-ref", "--stdin"], cwd=repo, env=environment,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            process.stdin.write(commands)
            process.stdin.close()
            process.stdin = None
            await_stop(process)
            value = refs(repo, plan)
            process.send_signal(signal.SIGKILL if kill else signal.SIGCONT)
            stdout, stderr = process.communicate(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    expected = -signal.SIGKILL if kill else 0
    if process.returncode != expected:
        raise AssertionError((process.returncode, stdout, stderr))
    return value, process.returncode


def verify(directory):
    version = git(directory, "--version")
    gcc = subprocess.check_output(["gcc", "-dumpfullversion"], text=True).strip()
    if version != "git version 2.52.0" or sys.platform != "linux":
        raise ValueError((version, sys.platform))
    preload = directory / "pause_rename.so"
    subprocess.run(["gcc", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", str(HERE / "pause_rename.c"),
                    "-o", str(preload), "-ldl"], check=True, timeout=10)
    cases = {}
    for backend, phase, kill, expected_view in (
        ("files", "branch_rename", False, "partial"),
        ("files", "receipt_rename", False, "new"),
        ("files", "branch_rename", True, "partial"),
        ("reftable", "new_table_rename", False, "old"),
        ("reftable", "table_list_rename", False, "new"),
        ("reftable", "new_table_rename", True, "old"),
    ):
        name = f"{backend}/{phase}/{'kill' if kill else 'resume'}"
        repo = directory / name.replace("/", "-")
        repo.mkdir()
        plan = setup(repo, backend)
        suffix = {
            "branch_rename": "/.git/refs/heads/main",
            "receipt_rename": f"/.git/{plan.receipt}",
            "new_table_rename": ".ref",
            "table_list_rename": "/.git/reftable/tables.list",
        }[phase]
        expected = {
            "old": (plan.parents[0], None, "retryable"),
            "partial": (plan.candidate, None, "stale"),
            "new": (plan.candidate, plan.candidate, "published"),
        }

        def validate(row, view):
            branch, receipt, result = expected[view]
            listed = [f"{recovery.BRANCH} {branch}"]
            if receipt is not None:
                listed.append(f"{plan.receipt} {receipt}")
            if (row["branch"], row["receipt"], row["inspection"], row["single_command"]) != (
                branch, receipt, result, listed,
            ):
                raise AssertionError((name, view, row))

        prior = refs(repo, plan)
        validate(prior, "old")
        paused, returncode = cut(repo, plan, preload, suffix, kill)
        validate(paused, expected_view)
        final = refs(repo, plan)
        validate(final, expected_view if kill else "new")
        if not recovery.matches_candidate(repo, plan):
            raise AssertionError("Expected exact candidate tree and semantic root")
        cases[name] = {"plan": asdict(plan), "before": prior, "at_cut": paused, "after": final,
                       "returncode": returncode,
                       "branch_before_receipt_after": [prior["branch"], final["receipt"]]}
    return {"format": "rt23-ref-commit-visibility/1", "git": version, "gcc": gcc,
            "python": sys.version.split()[0], "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-ref-commit-visibility-") as scratch:
        evidence = verify(Path(scratch))
    arguments.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
