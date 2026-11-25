#!/usr/bin/env python3
"""Check multi-ref readers and immutable generation receipts with native Git."""
import argparse
from collections import Counter
from itertools import combinations, product
import json
import os
from pathlib import Path
import re
import select
import subprocess
import tempfile


REFS = ("refs/llmlang/fixture/alpha", "refs/llmlang/fixture/beta")
HEAD = "refs/llmlang/fixture/published"
ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
ENV.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2001-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2001-01-01T00:00:00+00:00", "LC_ALL": "C"})


def canonical(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"


class Repository:
    def __init__(self, path, storage, hashes):
        self.path = path
        self.length = {"sha1": 40, "sha256": 64}[hashes]
        path.mkdir()
        self.git("init", "--quiet", "--bare", "--initial-branch=research/all",
                 f"--ref-format={storage}", f"--object-format={hashes}")

    def git(self, *args, data=None):
        command = ["git", *args]
        result = subprocess.run(command, cwd=self.path, env=ENV, input=data, text=True,
                                capture_output=True, timeout=10)
        assert result.returncode == 0, (args, result.stdout, result.stderr)
        return result.stdout

    def commit(self, filename, content, parents=()):
        blob = self.git("hash-object", "-w", "--stdin", data=content).strip()
        tree = self.git("mktree", data=f"100644 blob {blob}\t{filename}\n").strip()
        history = [item for parent in parents for item in ("-p", parent)]
        return self.git("commit-tree", tree, *history, "-m", filename).strip()

    def get(self, name):
        return self.git("rev-parse", "--verify", name).strip()

    def set(self, name, new, old=None):
        suffix = [] if old is None else [old]
        self.git("update-ref", name, new, *suffix)

    def oid(self, value):
        return isinstance(value, str) and re.fullmatch(rf"[a-f0-9]{{{self.length}}}", value)

    def receipt(self, generation, prior, tips, *, parents=None):
        manifest = {"generation": generation, "previous": prior, "refs": dict(zip(REFS, tips)),
                    "schema": "rt19-ref-generation-v1"}
        closure = tuple(tips) if prior is None else (prior, *tips)
        return self.commit("publication.json", canonical(manifest),
                           closure if parents is None else parents)

    def read(self, published):
        assert self.oid(published)
        raw = self.git("cat-file", "blob", f"{published}:publication.json")
        obj = json.loads(raw)
        assert raw == canonical(obj)
        assert set(obj) == {"generation", "previous", "refs", "schema"}
        assert obj["schema"] == "rt19-ref-generation-v1"
        assert type(obj["generation"]) is int and obj["generation"] >= 0
        assert set(obj["refs"]) == set(REFS)
        tips = tuple(obj["refs"][name] for name in REFS)
        assert all(self.oid(tip) for tip in tips)
        prior = obj["previous"]
        if obj["generation"] == 0:
            assert prior is None
            parents = tips
        else:
            assert self.oid(prior)
            previous = json.loads(self.git("cat-file", "blob", f"{prior}:publication.json"))
            assert previous["generation"] == obj["generation"] - 1
            parents = (prior, *tips)
        recorded = self.git("show", "-s", "--format=%P", published).split()
        assert list(parents) == recorded
        assert all(self.git("cat-file", "-t", tip).strip() == "commit" for tip in tips)
        return tips


def schedules(reader, writer):
    for positions in combinations(range(len(reader) + len(writer)), len(writer)):
        remaining_reader, remaining_writer = iter(reader), iter(writer)
        yield [next(remaining_writer) if pos in positions else next(remaining_reader)
               for pos in range(len(reader) + len(writer))]


def prepare_commands(previous, following):
    names = (*REFS, HEAD)
    commands = [f"update {name} {new} {old}"
                for name, old, new in zip(names, previous, following)]
    return "\n".join(["start", *commands, "prepare", ""])


def atomic(repo, previous, following):
    repo.git("update-ref", "--stdin", data=prepare_commands(previous, following) + "commit\n")


def prepared_visibility(repo, previous, following):
    with subprocess.Popen(["git", "update-ref", "--stdin"], cwd=repo.path, env=ENV,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          bufsize=0) as process:
        try:
            process.stdin.write(prepare_commands(previous, following).encode())
            for expected in (b"start: ok\n", b"prepare: ok\n"):
                ready, _, _ = select.select([process.stdout], [], [], 10)
                assert ready and process.stdout.readline() == expected
            assert tuple(repo.get(name) for name in (*REFS, HEAD)) == previous
            stdout, stderr = process.communicate(input=b"commit\n", timeout=10)
            assert process.returncode == 0 and b"commit: ok" in stdout, stderr
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
    assert tuple(repo.get(name) for name in (*REFS, HEAD)) == following


def run_schedule(repo, events, previous, following, reader):
    for name, value in zip((*REFS, HEAD), previous):
        repo.set(name, value)
    reads = {}
    for event in events:
        if event == "publish":
            atomic(repo, previous, following)
        elif event.startswith("write-"):
            index = ["write-alpha", "write-beta", "write-head"].index(event)
            repo.set((*REFS, HEAD)[index], following[index], previous[index])
        elif event == "read-alpha":
            reads["alpha"] = repo.get(REFS[0])
        elif event == "read-beta":
            reads["beta"] = repo.get(REFS[1])
        elif event == "pin":
            reads["first"] = repo.get(HEAD)
        elif event == "recheck":
            reads["last"] = repo.get(HEAD)
        elif event == "read-receipt":
            reads["snapshot"] = repo.read(reads["first"])
        else:
            raise AssertionError(event)
    assert tuple(repo.get(name) for name in (*REFS, HEAD)) == following
    if reader == "pinned":
        snapshot = reads["snapshot"]
    else:
        snapshot = (reads["alpha"], reads["beta"])
    pair = tuple("new" if value == following[index] else
                 "old" if value == previous[index] else "unexpected"
                 for index, value in enumerate(snapshot))
    assert "unexpected" not in pair
    coherent = pair[0] == pair[1]
    result = {"events": events, "pair": pair, "coherent": coherent}
    if reader != "direct":
        first, last = reads["first"], reads["last"]
        result["fresh_at_recheck"] = first == last
        exact = snapshot == repo.read(first)
        result["matches_pinned_receipt"] = exact
        if reader == "bracket":
            result["epoch_admitted"] = first == last
            result["manifest_admitted"] = first == last and exact
        else:
            assert coherent and exact
    return result


def controls(repo, first, second, competing):
    # Synthesized candidate receipt with a valid Git type and invalid binding.
    invalid = repo.receipt(1, first[2], second[:2], parents=(first[2], *first[:2]))
    try:
        repo.read(invalid)
    except AssertionError:
        invalid_disposition = "receipt-parent-mismatch"
    else:
        raise AssertionError("accepted an unretained manifest")
    malformed = repo.commit("publication.json", '{"generation":0,"generation":0}\n')
    try:
        repo.read(malformed)
    except AssertionError:
        malformed_disposition = "noncanonical-receipt"
    else:
        raise AssertionError("accepted a duplicate JSON member")
    for name, value in zip((*REFS, HEAD), first):
        repo.set(name, value)
    prepared_visibility(repo, first, second)
    atomic(repo, second, first)
    start = repo.get(HEAD)
    alpha = repo.get(REFS[0])
    atomic(repo, first, second)
    beta = repo.get(REFS[1])
    atomic(repo, second, first)
    assert start == repo.get(HEAD) and (alpha, beta) == (first[0], second[1])
    assert (alpha, beta) != repo.read(start)

    runners = [subprocess.Popen(["git", "update-ref", HEAD, new, first[2]],
                                cwd=repo.path, env=ENV, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
               for new in (second[2], competing[2])]
    for process in runners:
        process.communicate(timeout=10)
    assert sorted(process.returncode == 0 for process in runners) == [False, True]
    winner = next(index for index, process in enumerate(runners) if process.returncode == 0)
    assert repo.get(HEAD) == (second[2], competing[2])[winner]
    assert repo.read(repo.get(HEAD)) == (second[:2], competing[:2])[winner]
    # Exact old-hash CAS fails on retry. An observer gets its idempotent result by
    # identifying the durable winning receipt and reading it without an update.
    retry = subprocess.run(["git", "update-ref", HEAD, repo.get(HEAD), first[2]],
                           cwd=repo.path, env=ENV, capture_output=True, timeout=10)
    assert retry.returncode != 0 and repo.read(repo.get(HEAD)) == (second[:2], competing[:2])[winner]
    repo.set(HEAD, second[2])
    repo.git("reflog", "expire", "--expire=all", "--all")
    repo.git("gc", "--prune=now", "--quiet")
    assert repo.read(first[2]) == first[:2] and repo.read(second[2]) == second[:2]
    assert all(repo.git("cat-file", "blob", f"{tip}:value").strip() in {"A0", "B0"}
               for tip in repo.read(first[2]))
    return {"invalid_parent_closure": invalid_disposition, "malformed_json": malformed_disposition,
            "prepared_transaction_visibility": {"prepared": "old", "committed": "new"},
            "rollback_aba": {"epoch_matches": True, "pair": ["old", "new"],
                             "manifest_matches": False},
            "contended_cas": {"successes": 1, "refusals": 1},
            "repeat_old_cas": "refused", "observe_winning_receipt": "exact",
            "old_snapshot_after_reflog_expire_and_gc": "exact"}


def test_profile(path, storage, hashes):
    repo = Repository(path, storage, hashes)

    def tips(suffix):
        return tuple(repo.commit("value", f"{name}{suffix}\n") for name in ("A", "B"))

    old, new, different = (tips(suffix) for suffix in (0, 1, 2))
    origin = (*old, repo.receipt(0, None, old))
    following = (*new, repo.receipt(1, origin[2], new))
    competing = (*different, repo.receipt(1, origin[2], different))
    plans = {
        "direct": ("read-alpha", "read-beta"),
        "bracket": ("pin", "read-alpha", "read-beta", "recheck"),
        "pinned": ("pin", "read-receipt", "recheck"),
    }
    writer_plans = {
        "atomic": ("publish",),
        "split": ("write-alpha", "write-beta", "write-head"),
    }
    rows, counters = {}, {}
    for (writer, writer_steps), (reader, reader_steps) in product(writer_plans.items(), plans.items()):
        key = f"{writer}/{reader}"
        data = [run_schedule(repo, events, origin, following, reader)
                for events in schedules(reader_steps, writer_steps)]
        rows[key] = data
        counter = Counter({"runs": len(data), "mixed": 0, "epoch_admitted_mixed": 0,
                           "epoch_admitted_wrong_generation": 0, "manifest_refused": 0,
                           "pinned_stale_at_recheck": 0})
        for row in data:
            counter["mixed"] += not row["coherent"]
            if reader == "bracket":
                counter["epoch_admitted_mixed"] += row["epoch_admitted"] and not row["coherent"]
                counter["epoch_admitted_wrong_generation"] += row["epoch_admitted"] and not row["matches_pinned_receipt"]
                counter["manifest_refused"] += not row["manifest_admitted"]
                assert not row["manifest_admitted"] or row["coherent"]
            if reader == "pinned":
                counter["pinned_stale_at_recheck"] += not row["fresh_at_recheck"]
        counters[key] = dict(counter)
    assert counters["atomic/direct"]["mixed"] > 0
    assert counters["atomic/bracket"]["epoch_admitted_mixed"] == 0
    assert counters["split/bracket"]["epoch_admitted_mixed"] > 0
    return {"object_format": hashes, "ref_format": storage, "receipts": [origin[2], following[2]],
            "summary": counters, "schedules": rows, "controls": controls(repo, origin, following, competing)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt19-snapshot-") as scratch:
        root = Path(scratch)
        tool = subprocess.check_output(["git", "--version"], cwd=root, env=ENV, text=True).strip()
        profiles = [test_profile(root / f"{storage}-{hashes}", storage, hashes)
                    for storage, hashes in product(("files", "reftable"), ("sha1", "sha256"))]
        assert all(record["summary"] == profiles[0]["summary"] for record in profiles)
        report = {"git": tool, "profile_summaries_match": True, "profiles": profiles}
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
