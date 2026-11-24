"""Run controlled concurrent receives against a local files-backed Git repository."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from gate import git, snapshot


GATE = Path(__file__).with_name("gate.py").resolve()
BASE_ENV = {
    **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "RT-23 fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "RT-23 fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
}


def commit(source, branch, content, message):
    if git(source, "symbolic-ref", "--short", "HEAD") != branch:
        git(source, "switch", "--quiet", branch)
    (source / "contract.json").write_text(json.dumps(content, sort_keys=True) + "\n", encoding="utf-8")
    git(source, "add", "--", "contract.json")
    git(source, "commit", "--quiet", "-m", message)
    return git(source, "rev-parse", "HEAD")


def attach_hook(receiver, hook, *args):
    path = receiver / "hooks" / hook
    command = shlex.join([sys.executable, str(GATE), *map(str, args)])
    path.write_text(f'#!/bin/sh\nexec {command} "$@"\n', encoding="utf-8")
    path.chmod(0o700)


def setup(directory, policy):
    source = directory / "source"
    receiver = directory / "receiver.git"
    git(directory, "init", "--quiet", "--template=", "--object-format=sha1", "-b", "program", str(source))
    program_old = commit(source, "program", {"requires": "A"}, "baseline program")
    git(source, "branch", "catalog")
    catalog_old = commit(source, "catalog", {"offers": ["A", "B"]}, "baseline catalog")
    git(directory, "init", "--bare", "--quiet", "--template=", "--object-format=sha1",
        "--ref-format=files", str(receiver))
    (receiver / "hooks").mkdir()
    git(source, "push", "--quiet", str(receiver), "program:program", "catalog:catalog")
    program_new = commit(source, "program", {"requires": "B"}, "new required contract")
    catalog_new = commit(source, "catalog", {"offers": ["A"]}, "remove alternative")
    git(source, "branch", "paired", catalog_old)
    paired = commit(source, "paired", {"offers": ["B"]}, "coordinated catalog")
    attach_hook(receiver, "pre-receive", "pre", directory, policy)
    attach_hook(receiver, "reference-transaction", "transaction", directory)
    return source, receiver, {"old": {"program": program_old, "catalog": catalog_old},
                              "new": {"program": program_new, "catalog": catalog_new}, "paired": paired}


def start_push(directory, source, receiver, actor, refs, *, pause="", wrapper=False, atomic=False):
    command = ["git", "push", "--quiet"]
    if wrapper:
        receive = shlex.join([sys.executable, str(GATE), "receive", str(directory)])
        command.append(f"--receive-pack={receive}")
    if atomic:
        command.append("--atomic")
    return subprocess.Popen(
        [*command, str(receiver), *refs], cwd=source,
        env={**BASE_ENV, "RT23_RECEIVE_ROLE": actor, "RT23_PAUSE_PHASE": pause},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def finish(process):
    _, errors = process.communicate(timeout=25)
    assert process.returncode in (0, 1, 128), (process.returncode, errors)
    return process.returncode


def wait_checkpoint(process, path):
    deadline = time.monotonic() + 18
    while not path.exists():
        if process.poll() is not None:
            raise AssertionError(("push exited before checkpoint", process.communicate()))
        if time.monotonic() >= deadline:
            raise TimeoutError("push did not enter checkpoint")
        time.sleep(0.01)


def race(policy, peer_uses_wrapper, *, paired=False, atomic=False):
    with TemporaryDirectory(prefix="rt23-concurrent-receive-") as temporary:
        directory = Path(temporary)
        source, receiver, pins = setup(directory, policy)
        before = snapshot(receiver)
        assert before["compatible"] and before["refs"] == pins["old"]
        actions = {}
        if paired:
            actions["joined"] = finish(start_push(directory, source, receiver, "joined",
                                                  ("program:program", "paired:catalog"), wrapper=True, atomic=atomic))
        else:
            pause = "pre-receive" if policy == "none" else "prepared"
            first = start_push(directory, source, receiver, "program", ("program:program",),
                               pause=pause, wrapper=policy == "whole-receive", atomic=atomic)
            try:
                wait_checkpoint(first, directory / "ready")
                assert snapshot(receiver)["refs"] == pins["old"]
                second = start_push(directory, source, receiver, "catalog", ("catalog:catalog",),
                                    wrapper=peer_uses_wrapper, atomic=atomic)
                actions["catalog"] = finish(second)
            finally:
                (directory / "release").touch()
                actions["program"] = finish(first)
            if policy == "whole-receive" and peer_uses_wrapper:
                actions["catalog-retry"] = finish(start_push(directory, source, receiver, "catalog-retry",
                                                             ("catalog:catalog",), wrapper=True))
        after = snapshot(receiver)
        events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
        decisions = [event for event in events if event["phase"] == "pre-receive"]

        decision_pins = [row["refs"] for row in decisions]
        proposed_program = {"program": pins["new"]["program"], "catalog": pins["old"]["catalog"]}
        if paired:
            assert after["compatible"] and after["refs"] == {"program": pins["new"]["program"],
                                                            "catalog": pins["paired"]}
            assert actions == {"joined": 0} and [row["compatible"] for row in decisions] == [True]
            assert decision_pins == [after["refs"]]
        elif policy == "whole-receive" and peer_uses_wrapper:
            assert actions == {"catalog": 128, "program": 0, "catalog-retry": 1}, (actions, events)
            assert any(event["phase"] == "receive-lock-busy" for event in events)
            assert [row["compatible"] for row in decisions] == [True, False]
            assert decision_pins == [proposed_program, pins["new"]]
            assert after["compatible"] and after["refs"] == {"program": pins["new"]["program"],
                                                            "catalog": pins["old"]["catalog"]}
        else:
            assert [row["compatible"] for row in decisions] == [True, True], events
            assert decision_pins == [proposed_program,
                                     {"program": pins["old"]["program"], "catalog": pins["new"]["catalog"]}]
            assert actions == {"catalog": 0, "program": 0} and not after["compatible"]
            assert after["refs"] == pins["new"]
        return {"policy": policy, "peer_uses_wrapper": peer_uses_wrapper, "paired_update": paired,
                "atomic_requested": atomic,
                "before": before, "after": after, "push_exit": actions, "events": events}


def run():
    os.environ.update(BASE_ENV)
    result = [
        race("none", False), race("hook-only", False, atomic=True),
        race("whole-receive", True), race("whole-receive", False),
        race("whole-receive", True, paired=True, atomic=True),
    ]
    return {"format": "rt23-concurrent-receive/1", "git": git(Path.cwd(), "--version"),
            "python": sys.version.split()[0], "results": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
