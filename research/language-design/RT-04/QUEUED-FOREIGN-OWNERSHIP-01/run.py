#!/usr/bin/env python3
"""Compare release evidence against an independent lock contender after SCM_RIGHTS transfer."""

import argparse
import fcntl
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import select
import signal
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PLANS = ("exit_queued", "kill_queued", "kill_after_one", "close_latest", "close_all")
POLICIES = ("sender", "last_receipt", "all_received", "including_queue")


def planned_events(messages, keep_original, plan):
    tags = tuple(str(index) for index in range(messages))
    initial = ("locked", *(f"send:{tag}" for tag in tags))
    if not keep_original:
        initial += ("local_close",)

    if plan in {"exit_queued", "kill_queued"}:
        receiver = ("kill",) if plan == "kill_queued" else ("exit",)
    elif plan == "kill_after_one":
        receiver = ("receive:0", "kill")
    else:
        received = tuple(f"receive:{tag}" for tag in tags)
        closed = tags[-1:] if plan == "close_latest" else tags
        receiver = (*received, *(f"close:{tag}" for tag in reversed(closed)), "exit")

    return (*initial, *receiver, *(("local_close",) if keep_original else ()))


def contract_trace(events, same_inode):
    """Model queue ownership, receipt ownership and observed termination by message key."""
    sender_open = True
    queued = set()
    received = set()
    last = None
    for event in events:
        action, _, tag = event.partition(":")
        if action == "send":
            queued.add(tag)
        elif action == "receive":
            queued.remove(tag)
            received.add(tag)
            last = tag
        elif action == "close":
            received.remove(tag)
        elif action in {"kill", "exit"}:
            queued.clear()
            received.clear()
        elif action == "local_close":
            sender_open = False

        holds_lock = {
            "sender": sender_open,
            "last_receipt": sender_open or last in received,
            "all_received": sender_open or bool(received),
            "including_queue": sender_open or bool(queued or received),
        }
        yield {
            "event": event,
            "retained": {"sender": sender_open, "queued": sorted(queued), "received": sorted(received)},
            "predictions": {policy: "busy" if same_inode and held else "available"
                            for policy, held in holds_lock.items()},
        }


def read_reply(child):
    readable, _, _ = select.select([child.stdout], [], [], 5)
    if not readable:
        raise TimeoutError("No reply from receiver")
    reply = child.stdout.readline()
    if not reply:
        raise RuntimeError(f"Receiver exited before an expected reply: {child.stderr.read()}")
    return reply.strip()


def ask(child, message):
    child.stdin.write(message + "\n")
    child.stdin.flush()
    return read_reply(child)


def probe_lock(path):
    with path.open("rb") as contender:
        try:
            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "busy"
    return "available"


def native_trace(command, target, contender, events):
    channel, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with target.open("rb") as owner, channel, peer:
        identity = os.fstat(owner.fileno())
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with subprocess.Popen(
            [*command, str(peer.fileno())], pass_fds=(peer.fileno(),), text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) as child:
            peer.close()
            try:
                ready = read_reply(child)
                assert ready == "ready"
                observations = []
                for event in events:
                    action, _, tag = event.partition(":")
                    if action == "send":
                        length = socket.send_fds(channel, [tag.encode("ascii")], [owner.fileno()])
                        assert length == 1
                    elif action == "receive":
                        expected = f"received {tag} {identity.st_dev} {identity.st_ino}"
                        reply = ask(child, "receive")
                        assert reply == expected
                    elif action == "close":
                        reply = ask(child, f"close {tag}")
                        assert reply == f"closed {tag}"
                    elif action in {"kill", "exit"}:
                        if action == "kill":
                            child.kill()
                            expected = -signal.SIGKILL
                        else:
                            child.stdin.write("exit\n")
                            child.stdin.flush()
                            expected = 0
                        status = child.wait(timeout=5)
                        diagnostics = child.stderr.read()
                        assert status == expected and not diagnostics, (status, diagnostics)
                    elif action == "local_close":
                        owner.close()
                    observations.append(probe_lock(contender))
                return observations
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)


def run(compiler):
    if platform.system() != "Linux":
        raise ValueError("This experiment requires Linux descriptor transport and flock")

    records = []
    outcomes = {policy: {"unsafe": 0, "unnecessary_refusal": 0} for policy in POLICIES}
    with TemporaryDirectory(prefix="llmlang-queued-fd-") as scratch:
        work = Path(scratch)
        target = work / "owned"
        alias = work / "alias"
        disjoint = work / "disjoint"
        target.touch()
        disjoint.touch()
        alias.hardlink_to(target)
        assert target.samefile(alias) and not target.samefile(disjoint)

        lib_tool = ["getconf", "GNU_LIBC_VERSION"]
        profiles = {"python": [sys.executable, "-B", str(HERE / "receiver.py")]}
        for level in ("0", "3"):
            native = work / f"receiver-O{level}"
            subprocess.run(
                [compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{level}",
                 str(HERE / "receiver.c"), "-o", str(native)],
                check=True, timeout=30,
            )
            profiles[f"c-O{level}"] = [str(native)]

        checkpoints = 0
        for messages, keep_original, same_inode, plan in product(
            (1, 2), (False, True), (False, True), PLANS
        ):
            events = planned_events(messages, keep_original, plan)
            steps = list(contract_trace(events, same_inode))
            expected = [step["predictions"]["including_queue"] for step in steps]
            for profile, worker in profiles.items():
                actual = native_trace(worker, target, alias if same_inode else disjoint, events)
                if actual != expected:
                    raise ValueError(f"{profile} on {events}: expected {expected}, got {actual}")
            for step, observation in zip(steps, actual, strict=True):
                step["observed"] = observation
                for policy, decision in step["predictions"].items():
                    if decision != observation:
                        kind = "unsafe" if decision == "available" else "unnecessary_refusal"
                        outcomes[policy][kind] += 1
            checkpoints += len(events)
            records.append({
                "messages": messages, "keep_original": keep_original, "same_inode": same_inode,
                "plan": plan, "checkpoints": steps,
            })

        assert outcomes["sender"]["unsafe"] > outcomes["last_receipt"]["unsafe"]
        assert outcomes["last_receipt"]["unsafe"] > outcomes["all_received"]["unsafe"] > 0
        assert not any(outcomes["including_queue"].values())
        return {
            "schema": "llmlang-queued-foreign-ownership/1",
            "platform": {"kernel": platform.release(), "machine": platform.machine(),
                         "libc": subprocess.check_output(lib_tool, text=True, timeout=5).strip(),
                         "filesystem": subprocess.check_output(["stat", "-f", "-c", "%T", work],
                                                               text=True, timeout=5).strip(),
                         "python": platform.python_version(),
                         "compiler": subprocess.check_output([compiler, "--version"],
                                                             text=True, timeout=5).splitlines()[0]},
            "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ("run.py", "receiver.c", "receiver.py")},
            "profiles": list(profiles),
            "schedules_per_profile": len(records),
            "checkpoints_per_profile": checkpoints,
            "checked_native_checkpoints": checkpoints * len(profiles),
            "policy_mismatches_per_profile": outcomes,
            "schedules": records,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    print(json.dumps(run(args.cc), indent=2))
