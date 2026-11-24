"""Interrupt native Git after ref prepare and inspect exact-tree retry behavior."""

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
from tests import test_rt24_merge_tree_gate as fixture


def git(repo, *args):
    return fixture.git(repo, *args).decode("utf-8").strip()


def setup(repo, backend):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=main",
        "--object-format=sha1", f"--ref-format={backend}")

    def declaration(version):
        value = fixture.declaration("contract", "contract:item", {"version": version})
        return fixture.row("contract", value)

    baseline = fixture.commit(repo, {
        fixture.MANIFEST: fixture.manifest(fixture.CONTRACT),
        fixture.CONTRACT: [declaration("before")],
        "selected.txt": "before publication\n",
    })
    git(repo, "switch", "--quiet", "-c", "preparation", baseline)
    authored = fixture.commit(repo, {
        fixture.CONTRACT: [declaration("after")],
        "selected.txt": "prepared publication\n",
    })
    inventory = fixture.read_inventory(repo, authored)
    _, snapshot = fixture.import_closed(inventory)
    candidate = recovery.commit_object(repo, inventory.tree, (baseline,), "prepared publication")
    return recovery.Prepared("prepared crash", inventory.tree, snapshot.root_hash, (baseline,), candidate)


def install_control(repo):
    directory = repo / ".git"
    hooks = directory / "hooks"
    hooks.mkdir(exist_ok=True)
    control = hooks / "reference-transaction"
    control.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = prepared ]; then\n'
        '  cat > .git/transaction.ready\n'
        '  printf ready > .git/transaction.waiting\n'
        '  IFS= read -r disposition < .git/transaction.fifo\n'
        '  [ "$disposition" = proceed ] || exit 1\n'
        'fi\n',
        encoding="utf-8",
    )
    control.chmod(0o755)
    os.mkfifo(directory / "transaction.fifo", 0o600)
    return control


def observe(repo, plan):
    dot_git = repo / ".git"
    return {
        "branch": recovery.ref(repo, recovery.BRANCH),
        "receipt": recovery.ref(repo, plan.receipt),
        "inspection": recovery.inspect(repo, plan),
        "locks": sorted(path.relative_to(dot_git).as_posix() for path in dot_git.rglob("*.lock")),
    }


def await_prepare(repo, process, plan):
    waiting = repo / ".git" / "transaction.waiting"
    deadline = time.monotonic() + 10
    while not waiting.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError("Git did not reach the prepared ref hook")
        time.sleep(0.01)
    rows = (repo / ".git" / "transaction.ready").read_text().splitlines()
    observed = {tuple(line.split()) for line in rows}
    if (plan.parents[0], plan.candidate, recovery.BRANCH) not in observed or (
        "0" * 40, plan.candidate, plan.receipt
    ) not in observed:
        raise AssertionError("Hook did not see both exact ref updates")
    return sorted(rows)


def cut(repo, plan, mode):
    hook = install_control(repo)
    commands = (f"start\nupdate {recovery.BRANCH} {plan.candidate} {plan.parents[0]}\n"
                f"create {plan.receipt} {plan.candidate}\nprepare\ncommit\n").encode()
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    with subprocess.Popen(["git", "update-ref", "--stdin"], cwd=repo, env=environment,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        try:
            process.stdin.write(commands)
            process.stdin.close()
            process.stdin = None
            updates = await_prepare(repo, process, plan)
            prepared_view = observe(repo, plan)
            if mode == "kill":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                control_fd = os.open(repo / ".git" / "transaction.fifo", os.O_RDWR)
                try:
                    os.write(control_fd, ("proceed\n" if mode == "complete" else "reject\n").encode())
                    process.wait(timeout=10)
                finally:
                    os.close(control_fd)
            stdout, stderr = process.communicate(timeout=10)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            hook.unlink()
    expected = {"kill": -signal.SIGKILL, "veto": 128, "complete": 0}[mode]
    if process.returncode != expected:
        raise AssertionError((mode, process.returncode, stdout, stderr))
    return {"prepared_view": prepared_view, "updates": updates, "return_code": process.returncode}


def classify(write):
    try:
        return write()
    except subprocess.CalledProcessError as error:
        if b"lock" not in error.stderr.lower():
            raise
        return "blocked_by_lock"


def retry(repo, plan):
    return classify(lambda: recovery.publish(repo, plan))


def try_unrelated_write(repo, baseline):
    name = "refs/heads/unrelated"
    result = classify(lambda: git(repo, "update-ref", name, baseline) or "written")
    expected = baseline if result == "written" else None
    if recovery.ref(repo, name) != expected:
        raise AssertionError("Unexpected unrelated ref state")
    return result


def run_case(repo, backend, mode):
    plan = setup(repo, backend)
    interrupted = cut(repo, plan, mode)
    after = observe(repo, plan)
    prepared = interrupted["prepared_view"]
    if (prepared["branch"], prepared["receipt"], prepared["inspection"]) != (
        plan.parents[0], None, "retryable",
    ) or not prepared["locks"]:
        raise AssertionError(("prepared view", backend, prepared))
    if mode == "complete":
        if (after["branch"], after["receipt"], after["inspection"], after["locks"]) != (
            plan.candidate, plan.candidate, "published", [],
        ):
            raise AssertionError(("completed view", backend, after))
    else:
        if (after["branch"], after["receipt"], after["inspection"]) != (plan.parents[0], None, "retryable"):
            raise AssertionError(("interrupted view", backend, mode, after))

    ordinary = retry(repo, plan)
    remedied = None
    unrelated = None
    removed_locks = []
    if mode == "kill":
        if ordinary != "blocked_by_lock" or after["locks"] != prepared["locks"]:
            raise AssertionError(("abrupt retry", backend, ordinary, after, prepared))
        unrelated = try_unrelated_write(repo, plan.parents[0])
        if unrelated != {"files": "written", "reftable": "blocked_by_lock"}[backend]:
            raise AssertionError((backend, "unrelated write", unrelated))
        # The fixture owns both repository and writers. Remove only the observed
        # locks after Git and its hook are dead and the branch/receipt are verified.
        if observe(repo, plan) != after:
            raise AssertionError("Repository unexpectedly changed before isolated repair")
        for lock in after["locks"]:
            (repo / ".git" / lock).unlink()
            removed_locks.append(lock)
        remedied = retry(repo, plan)
        if remedied != "published":
            raise AssertionError(("retry after isolated repair", backend, remedied))
    elif ordinary != "published" or after["locks"]:
        raise AssertionError(("ordinary retry", backend, mode, ordinary, after))

    final = observe(repo, plan)
    if (final["branch"], final["receipt"], final["inspection"], final["locks"]) != (
        plan.candidate, plan.candidate, "published", [],
    ) or not recovery.matches_candidate(repo, plan):
        raise AssertionError(("exact result", backend, mode, final))
    return {**interrupted, "plan": asdict(plan), "after": after, "ordinary_retry": ordinary,
            "unrelated_write_after_crash": unrelated, "isolated_removed_locks": removed_locks,
            "isolated_retry": remedied, "final": final}


def verify():
    with TemporaryDirectory(prefix="llmlang-ref-crash-") as scratch:
        root = Path(scratch)
        git_version = git(root, "--version")
        if git_version != "git version 2.52.0" or sys.platform != "linux":
            raise ValueError((git_version, sys.platform))
        cases = {}
        for backend in ("files", "reftable"):
            for mode in ("veto", "complete", "kill"):
                path = root / f"{backend}-{mode}"
                path.mkdir()
                cases[f"{backend}/{mode}"] = run_case(path, backend, mode)
        return {"format": "rt23-git-prepared-crash/1", "git": git_version,
                "python": sys.version.split()[0], "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
