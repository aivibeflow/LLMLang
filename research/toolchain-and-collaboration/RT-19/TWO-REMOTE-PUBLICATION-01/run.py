#!/usr/bin/env python3
"""Replay local Git two-target delivery, publication and process crash recovery."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


BRANCH = "refs/heads/research/all"
WITNESS = "refs/llmlang/fixture/intent/batch-01"
RELEASED = "refs/llmlang/fixture/release/batch-01"
NAMES = ("alpha", "beta")
ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
ENV.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2001-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2001-01-01T00:00:00+00:00", "LC_ALL": "C"})


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


def git(directory, *args, data=None, check=True):
    result = subprocess.run(["git", *args], cwd=directory, env=ENV, input=data, text=True,
                            capture_output=True, timeout=15)
    if check:
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


class Fixture:
    def __init__(self, root):
        self.root = root
        self.sender = root / "sender"
        self.journal = root / "intent.sqlite"

    def remote(self, name):
        assert name in NAMES
        return (self.root / name).as_uri()

    def write_commit(self, file, text, parents=()):
        blob = git(self.sender, "hash-object", "-w", "--stdin", data=text).stdout.strip()
        tree = git(self.sender, "mktree", data=f"100644 blob {blob}\t{file}\n").stdout.strip()
        args = [part for value in parents for part in ("-p", value)]
        return git(self.sender, "commit-tree", tree, *args, "-m", file).stdout.strip()

    def initialize(self, storage):
        for name in ("sender", *NAMES):
            path = self.root / name
            path.mkdir()
            git(path, "init", "--quiet", "--bare", "--initial-branch=research/all", f"--ref-format={storage}")
        participants = {}
        for name in NAMES:
            old = self.write_commit("content", name + "-old\n")
            new = self.write_commit("content", name + "-new\n", [old])
            other = self.write_commit("content", name + "-independent\n", [new])
            evidence = {"request": "batch-01", "participant": name, "ref": BRANCH, "old": old, "new": new}
            witness = self.write_commit("participant.json", canonical(evidence), [new])
            participants[name] = {"old": old, "new": new, "witness": witness, "other": other}
            git(self.sender, "push", self.remote(name), f"{old}:{BRANCH}")
        release = self.write_commit(
            "release.json", canonical({"request": "batch-01", "members": [
                {"name": name, "tip": participants[name]["new"], "witness": participants[name]["witness"]}
                for name in NAMES]}), [participants[name]["witness"] for name in NAMES])
        with sqlite3.connect(self.journal) as database:
            assert database.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
            database.execute("PRAGMA synchronous=FULL")
            database.execute("CREATE TABLE prepared (id TEXT PRIMARY KEY, intent TEXT NOT NULL, state TEXT NOT NULL)")
            database.execute("INSERT INTO prepared VALUES ('batch-01', ?, 'prepared')",
                             (canonical({"participants": participants, "release": release}),))

    def journal_row(self):
        with sqlite3.connect(self.journal) as database:
            row = database.execute("SELECT intent, state FROM prepared WHERE id='batch-01'").fetchone()
        assert row
        encoded, state = row
        parsed = json.loads(encoded)
        assert canonical(parsed) == encoded and state in ("prepared", "settled")
        return parsed, state

    def observe(self, name, participant):
        result = git(self.sender, "ls-remote", "--refs", self.remote(name), BRANCH, WITNESS, check=False)
        if result.returncode != 0:
            return "unavailable"
        visible = {key: value for value, key in
                   (line.split("\t") for line in result.stdout.splitlines())}
        actual = (visible.get(BRANCH), visible.get(WITNESS))
        if actual == (participant["old"], None):
            return "untouched"
        if actual == (participant["new"], participant["witness"]):
            return "exact"
        if actual == (participant["new"], None):
            return "unwitnessed"
        return "diverged"

    def publish_participant(self, name, participant):
        result = git(self.sender, "push", "--porcelain", "--atomic",
                     f"--force-with-lease={BRANCH}:{participant['old']}",
                     f"--force-with-lease={WITNESS}:", self.remote(name),
                     f"{participant['new']}:{BRANCH}", f"{participant['witness']}:{WITNESS}",
                     check=False)
        return result.returncode == 0

    def outside_write(self, name, use_new=False):
        participant = self.journal_row()[0]["participants"][name]
        target = participant["new" if use_new else "other"]
        git(self.sender, "push", self.remote(name), f"{target}:{BRANCH}")

    def released(self):
        result = git(self.sender, "rev-parse", "--verify", RELEASED, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def validate_release(self, actual, intent):
        assert actual == intent["release"]
        raw = git(self.sender, "cat-file", "blob", f"{actual}:release.json").stdout
        members = []
        for name in NAMES:
            row = intent["participants"][name]
            witness = row["witness"]
            record = {"request": "batch-01", "participant": name, "ref": BRANCH,
                      "old": row["old"], "new": row["new"]}
            assert git(self.sender, "cat-file", "blob", f"{witness}:participant.json").stdout == canonical(record)
            assert git(self.sender, "show", "-s", "--format=%P", witness).stdout.split() == [row["new"]]
            members.append({"name": name, "tip": row["new"], "witness": witness})
        assert raw == canonical({"request": "batch-01", "members": members})
        assert git(self.sender, "show", "-s", "--format=%P", actual).stdout.split() == [
            item["witness"] for item in members]

    def settle(self, intent, *, observer, append, seal, crash=None, before_seal=None):
        if not observer:
            return {"outcome": "denied"}
        outcome = self.released()
        if outcome:
            if outcome != intent["release"]:
                return {"outcome": "release-conflict"}
            self.validate_release(outcome, intent)
        else:
            statuses = {name: self.observe(name, row) for name, row in intent["participants"].items()}
            if any(status in ("diverged", "unwitnessed") for status in statuses.values()):
                return {"outcome": "conflict", "participants": statuses}
            if "unavailable" in statuses.values():
                return {"outcome": "pending-observation", "participants": statuses}
            if not append and "untouched" in statuses.values():
                return {"outcome": "pending-append", "participants": statuses}
            for name, status in statuses.items():
                if status != "untouched":
                    continue
                if not self.publish_participant(name, intent["participants"][name]):
                    return {"outcome": "target-refused", "target": name}
                if crash == f"after-{name}":
                    os._exit(73)
            statuses = {name: self.observe(name, row) for name, row in intent["participants"].items()}
            if "unavailable" in statuses.values():
                return {"outcome": "pending-observation", "participants": statuses}
            if set(statuses.values()) != {"exact"}:
                return {"outcome": "conflict", "participants": statuses}
            if not seal:
                return {"outcome": "pending-seal", "participants": statuses}
            if before_seal:
                before_seal()
            outcome = intent["release"]
            self.validate_release(outcome, intent)
            # Create only. A concurrent exact publication can be observed and settled.
            git(self.sender, "update-ref", RELEASED, outcome, "0" * len(outcome), check=False)
            if self.released() != outcome:
                return {"outcome": "release-conflict"}
            if crash == "after-seal":
                os._exit(73)
        with sqlite3.connect(self.journal) as database:
            database.execute("PRAGMA synchronous=FULL")
            database.execute("UPDATE prepared SET state='settled' WHERE id='batch-01'")
        return {"outcome": "settled", "release": outcome}

    def snapshot(self):
        intent, state = self.journal_row()
        return {"state": state, "published": bool(self.released()),
                "participants": {name: self.observe(name, row)
                                 for name, row in intent["participants"].items()}}

    def recover(self, *, observer=True, append=True, seal=True, before_seal=None):
        return self.settle(self.journal_row()[0], observer=observer, append=append,
                           seal=seal, before_seal=before_seal)


def stopped_worker(fixture, point):
    worker = subprocess.run([sys.executable, "-B", __file__, "--worker", str(fixture.root),
                             "--crash", point], capture_output=True, text=True, timeout=25)
    assert worker.returncode == 73, (worker.returncode, worker.stdout, worker.stderr)


def trial(root, storage, name):
    root.mkdir()
    fixture = Fixture(root)
    fixture.initialize(storage)
    steps = {}
    if name in ("before-delivery", "after-alpha", "after-beta", "after-seal"):
        stopped_worker(fixture, name)
        steps["after_process_exit"] = fixture.snapshot()
        expected = {
            "before-delivery": ("untouched", "untouched", False, "pending-append"),
            "after-alpha": ("exact", "untouched", False, "pending-append"),
            "after-beta": ("exact", "exact", False, "pending-seal"),
            "after-seal": ("exact", "exact", True, "settled"),
        }[name]
        snapshot = steps["after_process_exit"]
        assert (*snapshot["participants"].values(), snapshot["published"]) == expected[:3]
        assert snapshot["state"] == "prepared"
        steps["denied_observer"] = fixture.recover(observer=False)
        assert steps["denied_observer"] == {"outcome": "denied"} and fixture.snapshot() == snapshot
        steps["observer_only"] = fixture.recover(append=False, seal=False)
        assert steps["observer_only"]["outcome"] == expected[3]
        settled = fixture.recover(append=name != "after-beta")
        assert settled["outcome"] == "settled"
        steps["terminal"] = fixture.snapshot()
        assert steps["terminal"] == {"state": "settled", "published": True,
                                      "participants": {"alpha": "exact", "beta": "exact"}}
    elif name in ("diverged-beta", "unwitnessed-beta", "diverged-alpha"):
        stopped_worker(fixture, "after-alpha")
        fixture.outside_write("alpha" if name == "diverged-alpha" else "beta",
                              use_new=name == "unwitnessed-beta")
        steps["before_recovery"] = fixture.snapshot()
        steps["recovery"] = fixture.recover()
        assert steps["recovery"]["outcome"] == "conflict"
        assert fixture.snapshot() == steps["before_recovery"]
    elif name == "receiver-refusal":
        hook = fixture.root / "beta" / "hooks" / "update"
        hook.write_text(f'#!/bin/sh\nif [ "$1" = "{WITNESS}" ]; then exit 1; fi\n')
        hook.chmod(0o700)
        steps["first"] = fixture.recover()
        assert steps["first"] == {"outcome": "target-refused", "target": "beta"}
        steps["after_hook_failure"] = fixture.snapshot()
        assert steps["after_hook_failure"] == {"state": "prepared", "published": False,
                                              "participants": {"alpha": "exact", "beta": "untouched"}}
        hook.unlink()
        steps["recovered"] = fixture.recover()
        assert steps["recovered"]["outcome"] == "settled"
    elif name == "receiver-unavailable":
        stopped_worker(fixture, "after-alpha")
        visible = fixture.root / "beta"
        dormant = fixture.root / "beta-dormant"
        visible.rename(dormant)
        try:
            steps["unavailable"] = fixture.snapshot()
            steps["recovery"] = fixture.recover()
            assert steps["recovery"] == {"outcome": "pending-observation",
                                         "participants": {"alpha": "exact", "beta": "unavailable"}}
            assert fixture.snapshot() == steps["unavailable"]
        finally:
            dormant.rename(visible)
        steps["recovered"] = fixture.recover()
        assert steps["recovered"]["outcome"] == "settled"
    elif name == "different-release-present":
        wrong = fixture.journal_row()[0]["participants"]["alpha"]["witness"]
        git(fixture.sender, "update-ref", RELEASED, wrong, "0" * len(wrong))
        steps["before_recovery"] = fixture.snapshot()
        steps["recovery"] = fixture.recover()
        assert steps["recovery"] == {"outcome": "release-conflict"}
        assert fixture.released() == wrong and fixture.snapshot() == steps["before_recovery"]
    elif name == "released-and-live-head-diverged":
        steps["released"] = fixture.recover()
        assert steps["released"]["outcome"] == "settled"
        fixture.outside_write("alpha")
        steps["observer"] = fixture.recover(append=False, seal=False)
        assert steps["observer"] == steps["released"]
        steps["physical"] = fixture.snapshot()
        assert steps["physical"]["participants"] == {"alpha": "diverged", "beta": "exact"}
    elif name == "between-probes-and-release":
        steps["released"] = fixture.recover(before_seal=lambda: fixture.outside_write("alpha"))
        assert steps["released"]["outcome"] == "settled"
        steps["physical"] = fixture.snapshot()
        assert steps["physical"]["participants"] == {"alpha": "diverged", "beta": "exact"}
    else:
        raise AssertionError(name)
    return steps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--crash")
    args = parser.parse_args()
    if args.worker:
        if args.crash == "before-delivery":
            os._exit(73)
        fixture = Fixture(args.worker)
        fixture.settle(fixture.journal_row()[0], observer=True, append=True,
                       seal=True, crash=args.crash)
        raise AssertionError("unreached exit point")
    assert args.out
    scenarios = ("before-delivery", "after-alpha", "after-beta", "after-seal",
                 "diverged-alpha", "diverged-beta", "unwitnessed-beta", "receiver-refusal",
                 "receiver-unavailable", "different-release-present",
                 "released-and-live-head-diverged", "between-probes-and-release")
    with tempfile.TemporaryDirectory(prefix="rt19-two-remotes-") as directory:
        root = Path(directory)
        outcomes = {storage: {name: trial(root / f"{storage}-{name}", storage, name)
                              for name in scenarios} for storage in ("files", "reftable")}
        assert outcomes["files"] == outcomes["reftable"]
        result = {"git": git(root, "--version").stdout.strip(), "sqlite": sqlite3.sqlite_version,
                  "scenarios_per_storage": len(scenarios), "ref_storage_outcomes": outcomes}
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
