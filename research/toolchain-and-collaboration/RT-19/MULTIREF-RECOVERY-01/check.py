"""Study prepared two-ref publication and independent recovery decisions."""

from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REFS = ("refs/heads/research/all", "refs/llmlang-fixture/secondary")
ENV = {**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_AUTHOR_NAME": "Local Fixture", "GIT_COMMITTER_NAME": "Local Fixture",
       "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
       "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}


def git(repo, args, payload=None, check=True):
    return subprocess.run(["git", *args], input=payload, cwd=repo, text=True, capture_output=True,
                          env=ENV, timeout=25, check=check)


def stdout(repo, *args, payload=None):
    return git(repo, args, payload).stdout.strip()


def heads(repo):
    return tuple(stdout(repo, "rev-parse", ref) for ref in REFS)


def move(repo, batch):
    lines = ["start", *(f"update {ref} {after} {before}" for ref, before, after in batch),
             "prepare", "commit", ""]
    return git(repo, ("update-ref", "--stdin"), "\n".join(lines), check=False).returncode == 0


def observe(repo, journal, observation_grant, mutation_grants):
    # Permission to observe an already published state is independent of permission to mutate it.
    if not observation_grant:
        return "observation-unavailable"
    identifier, encoded, state = journal.execute("SELECT request, operations, state FROM requests").fetchone()
    batch = json.loads(encoded)
    expected = tuple(change[1] for change in batch)
    desired = tuple(change[2] for change in batch)
    actual = heads(repo)
    if state == "recorded":
        return "recorded"
    if actual == desired:
        journal.execute("UPDATE requests SET state='recorded' WHERE request=?", (identifier,))
        return "reconciled"
    if actual != expected:
        return "diverged"
    if set(mutation_grants) != set(REFS):
        return "mutation-unavailable"
    if not move(repo, batch):
        return "compare-and-swap-refused"
    journal.execute("UPDATE requests SET state='recorded' WHERE request=?", (identifier,))
    return "published"


def scenario(work, shape, observation, grants):
    repo = work / "repo"
    repo.mkdir(parents=True)
    stdout(repo, "init", "--quiet", "--bare", "-b", "research/all", "--object-format=sha256")
    tree = stdout(repo, "mktree", payload="")
    original = tuple(stdout(repo, "commit-tree", tree, "-m", f"original {side}") for side in "ab")
    requested = tuple(stdout(repo, "commit-tree", tree, "-p", original[i], "-m", f"candidate {side}")
                      for i, side in enumerate("ab"))
    alternative = stdout(repo, "commit-tree", tree, "-p", original[1], "-m", "other")
    for ref, revision in zip(REFS, original, strict=True):
        stdout(repo, "update-ref", ref, revision)
    batch = list(zip(REFS, original, requested, strict=True))
    record = json.dumps(batch, separators=(",", ":"))
    db = work / "journal.sqlite"
    request_id = sha256(record.encode()).hexdigest()
    with closing(sqlite3.connect(db, isolation_level=None)) as journal:
        journal.execute("CREATE TABLE requests (request TEXT PRIMARY KEY, operations TEXT, state TEXT)")
        journal.execute("INSERT INTO requests VALUES (?, ?, 'prepared')", (request_id, record))
    # Reopen the independently committed durable journal after each modeled stop point.
    if shape in ("visible", "settled"):
        assert move(repo, batch)
    if shape == "mixed":
        stdout(repo, "update-ref", REFS[0], requested[0], original[0])
        assert not move(repo, batch)
        assert heads(repo) == (requested[0], original[1])
    if shape == "external":
        stdout(repo, "update-ref", REFS[1], alternative, original[1])
        assert not move(repo, batch)
        assert heads(repo) == (original[0], alternative)

    before = heads(repo)
    with closing(sqlite3.connect(db, isolation_level=None)) as journal:
        if shape == "settled":
            journal.execute("UPDATE requests SET state='recorded'")
        outcome = observe(repo, journal, observation, grants)
        state, = journal.execute("SELECT state FROM requests").fetchone()

    after = heads(repo)
    assert after == (requested if outcome == "published" else before)
    assert (state == "recorded") == (shape == "settled" or outcome in ("published", "reconciled"))
    roles = {oid: name for name, oid in zip(("old-a", "old-b", "new-a", "new-b", "external"),
                                           (*original, *requested, alternative), strict=True)}
    return {"decision": outcome, "before": [roles[head] for head in before],
            "after": [roles[head] for head in after], "journal": state, "request": request_id}


def collect(root):
    scenarios = {
        "prepared_current": ("prepared", True, REFS, "published"),
        "prepared_partial_grant": ("prepared", True, REFS[:1], "mutation-unavailable"),
        "prepared_no_observation": ("prepared", False, REFS, "observation-unavailable"),
        "unrecorded_published": ("visible", True, (), "reconciled"),
        "published_no_observation": ("visible", False, REFS, "observation-unavailable"),
        "recorded_retry": ("settled", True, (), "recorded"),
        "one_ref_externally_advanced": ("external", True, REFS, "diverged"),
        "mixed_batch": ("mixed", True, REFS, "diverged"),
    }
    results = {}
    for name, (shape, observation, grants, expected) in scenarios.items():
        work = root / name
        work.mkdir()
        results[name] = scenario(work, shape, observation, grants)
        assert results[name]["decision"] == expected
    assert len({row["request"] for row in results.values()}) == 1
    return {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "git": stdout(root, "--version"), "scenarios": results,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="rt19-multiref-") as temp:
        print(json.dumps(collect(Path(temp)), sort_keys=True, indent=2))
