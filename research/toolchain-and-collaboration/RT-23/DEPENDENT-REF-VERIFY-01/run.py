"""Compare checks performed before and inside exact native Git ref transactions."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


HOOK = Path(__file__).with_name("checkpoint.py").resolve()
P = "refs/llmlang/program"
C = "refs/llmlang/catalog"
GIT = ["git", "-c", "core.filesRefLockTimeout=0", "-c", "reftable.lockTimeout=0"]
ENV = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def invoke(repo, *args, data=None, check=True):
    return subprocess.run([*GIT, *args], cwd=repo, env=ENV, input=data, text=True,
                          capture_output=True, timeout=20, check=check)


def git(repo, *args, data=None):
    return invoke(repo, *args, data=data).stdout.strip()


def read(repo):
    pins = {role: git(repo, "rev-parse", role) for role in (P, C)}
    required = json.loads(git(repo, "cat-file", "blob", pins[P]))["requires"]
    offered = json.loads(git(repo, "cat-file", "blob", pins[C]))["offers"]
    return {"refs": pins, "compatible": required in offered}


def setup(directory, backend):
    repo = directory / "repo.git"
    git(directory, "init", "--bare", "--quiet", "--template=", "--object-format=sha1",
        f"--ref-format={backend}", str(repo))
    def save(data):
        return git(repo, "hash-object", "-w", "--stdin", data=json.dumps(data, sort_keys=True) + "\n")
    old = {P: save({"requires": "A"}), C: save({"offers": ["A", "B"]})}
    new = {P: save({"requires": "B"}), C: save({"offers": ["A"]})}
    git(repo, "update-ref", P, old[P])
    git(repo, "update-ref", C, old[C])
    (repo / "hooks").mkdir()
    command = shlex.join([sys.executable, str(HOOK), str(directory)])
    hook = repo / "hooks" / "reference-transaction"
    hook.write_text(f'#!/bin/sh\nexec {command} "$@"\n', encoding="utf-8")
    hook.chmod(0o700)
    return repo, old, new


def plan(target, old, new, verify_peer):
    peer = C if target == P else P
    commands = ["start", f"update {target} {new[target]} {old[target]}"]
    if verify_peer:
        commands.append(f"verify {peer} {old[peer]}")
    commands.extend(["prepare", "commit"])
    return "\n".join(commands) + "\n"


def outcome(status, diagnostic):
    if status == 0:
        return "committed"
    if "but expected" in diagnostic:
        return "stale-verified-ref"
    if "locked" in diagnostic.lower() or "lock" in diagnostic.lower():
        return "ref-lock-unavailable"
    raise AssertionError((status, diagnostic))


def set_peer(repo, old, new, *, verified):
    child = invoke(repo, "update-ref", "--stdin", data=plan(C, old, new, verified), check=False)
    return outcome(child.returncode, child.stderr)


def pause_primary(repo, old, new, verify_peer):
    process = subprocess.Popen([*GIT, "update-ref", "--stdin"], cwd=repo,
                               env={**ENV, "RT23_ACTOR": "primary"}, text=True,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.stdin.write(plan(P, old, new, verify_peer))
    process.stdin.close()
    process.stdin = None
    return process


def await_prepared(process, directory):
    marker = directory / "checkpoint.json"
    deadline = time.monotonic() + 13
    while not marker.exists():
        if process.poll() is not None:
            raise AssertionError(process.communicate())
        if time.monotonic() >= deadline:
            raise TimeoutError("primary process never reached prepared")
        time.sleep(0.01)
    return json.loads(marker.read_text(encoding="utf-8"))


def run_case(backend, schedule, verify_peer):
    with TemporaryDirectory(prefix="rt23-dependent-ref-") as temporary:
        directory = Path(temporary)
        repo, old, new = setup(directory, backend)
        before = read(repo)
        assert before == {"refs": old, "compatible": True}
        prepared = None
        retry = None
        catalog_loose_lock = None
        if schedule == "before-prepare":
            peer = set_peer(repo, old, new, verified=True)
            process = invoke(repo, "update-ref", "--stdin", data=plan(P, old, new, verify_peer), check=False)
            primary = outcome(process.returncode, process.stderr)
        else:
            process = pause_primary(repo, old, new, verify_peer)
            try:
                prepared = await_prepared(process, directory)
                expected = [[old[P], new[P], P]]
                if verify_peer:
                    expected.append([old[C], "0" * len(old[C]), C])
                assert prepared == expected, prepared
                assert read(repo) == before
                if backend == "files":
                    catalog_loose_lock = (repo / f"{C}.lock").is_file()
                peer = set_peer(repo, old, new, verified=False)
            finally:
                (directory / "release").touch()
                _, diagnostic = process.communicate(timeout=20)
            primary = outcome(process.returncode, diagnostic)
            if peer == "ref-lock-unavailable":
                retry = set_peer(repo, old, new, verified=True)
        after = read(repo)
        return {"ref_backend": backend, "schedule": schedule, "verify_peer_in_transaction": verify_peer,
                "primary": primary, "peer": peer, "verified_peer_retry": retry, "before": before,
                "after": after, "prepared_refs": prepared, "files_peer_lock_at_checkpoint": catalog_loose_lock}


def compare():
    results = [
        run_case(backend, timing, verify)
        for backend in ("files", "reftable")
        for timing in ("before-prepare", "while-prepared")
        for verify in (False, True)
    ]
    for row in results:
        if row["schedule"] == "before-prepare":
            assert row["peer"] == "committed"
            assert row["primary"] == ("stale-verified-ref" if row["verify_peer_in_transaction"] else "committed")
        elif row["verify_peer_in_transaction"]:
            assert row["primary"] == "committed"
            assert row["peer"] == "ref-lock-unavailable" and row["verified_peer_retry"] == "stale-verified-ref"
        if row["schedule"] == "while-prepared":
            expected_peer = ("committed" if row["ref_backend"] == "files"
                             and not row["verify_peer_in_transaction"] else "ref-lock-unavailable")
            assert row["peer"] == expected_peer
            if row["ref_backend"] == "files":
                assert row["files_peer_lock_at_checkpoint"] == row["verify_peer_in_transaction"]
        assert row["after"]["compatible"] == (row["peer"] != "committed" or row["primary"] != "committed")
    return {"format": "rt23-dependent-ref-verify/1", "git": git(Path.cwd(), "--version"),
            "python": sys.version.split()[0], "outcomes": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
