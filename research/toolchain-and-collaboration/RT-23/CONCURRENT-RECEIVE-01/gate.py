"""Two-ref receive validation and a lock spanning the native receiver."""
import argparse
from contextlib import nullcontext
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REFS = ("refs/heads/program", "refs/heads/catalog")
ROLES = ("program", "catalog")


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True, timeout=15).strip()


def snapshot(repo, updates=None):
    updates = {} if updates is None else updates
    pins = {role: updates[ref] if ref in updates else git(repo, "rev-parse", ref)
            for role, ref in zip(ROLES, REFS, strict=True)}
    required = json.loads(git(repo, "show", f'{pins["program"]}:contract.json'))["requires"]
    offered = json.loads(git(repo, "show", f'{pins["catalog"]}:contract.json'))["offers"]
    return {"refs": pins, "required": required, "offered": offered, "compatible": required in offered}


def append(directory, event):
    role = os.environ.get("RT23_RECEIVE_ROLE", "unknown")
    with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"actor": role, **event}, sort_keys=True) + "\n")


def checkpoint(directory, location):
    if os.environ.get("RT23_PAUSE_PHASE") != location:
        return
    (directory / "ready").touch()
    expires = time.monotonic() + 20
    while not (directory / "release").exists():
        if time.monotonic() >= expires:
            raise TimeoutError(f"fixture did not release the {location} checkpoint")
        time.sleep(0.01)


def pre_receive(directory, policy):
    incoming = {ref: new for _, new, ref in (line.split() for line in sys.stdin)}
    if not set(incoming) <= set(REFS) or any(set(new) == {"0"} for new in incoming.values()):
        return 1
    manager = (directory / "admission.lock").open("wb") if policy == "hook-only" else nullcontext()
    with manager as lock:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        current = snapshot(Path.cwd(), incoming)
        append(directory, {"phase": "pre-receive", "ref_names": sorted(incoming), **current})
        checkpoint(directory, "pre-receive")
    return int(not current["compatible"])


def reference_transaction(directory, stage):
    edits = [ref for _, _, ref in (line.split() for line in sys.stdin) if ref in REFS]
    if edits:
        append(directory, {"phase": stage, "ref_names": sorted(edits)})
        if stage == "prepared":
            checkpoint(directory, "prepared")
    return 0


def receive_wrapper(directory, target):
    handle = os.open(directory / "receive.lock", os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        append(directory, {"phase": "receive-lock-busy"})
        os.close(handle)
        return 1
    os.set_inheritable(handle, True)
    os.execvp("git", ("git", "receive-pack", target))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("pre", "transaction", "receive"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("argument")
    args = parser.parse_args()
    if args.phase == "pre":
        status = pre_receive(args.directory, args.argument)
    elif args.phase == "transaction":
        status = reference_transaction(args.directory, args.argument)
    else:
        status = receive_wrapper(args.directory, args.argument)
    sys.exit(status)
