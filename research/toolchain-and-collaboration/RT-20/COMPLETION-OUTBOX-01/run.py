"""Replay exact CIP completion through a SQLite outbox and immutable export."""
import argparse
from contextlib import closing
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
RECOVERY = HERE.parents[1] / "RT-24" / "CIP-RECOVERY-01" / "run.py"
spec = spec_from_file_location("fixture_outbox_recovery", RECOVERY)
recovery = module_from_spec(spec)
sys.modules[spec.name] = recovery
spec.loader.exec_module(recovery)
CIP, NATIVE = recovery.cip, recovery.NATIVE
GIT, HEAD, LOOKUP = recovery.GIT, recovery.HEAD, recovery.LOOKUP
SOURCES = ("manifest.json", "state.json")
OPERATION = "complete-change"

BOUNDARIES = {
    "sql-before-commit": ("absent", False, False),
    "sql-prepared": ("prepared", False, False),
    "git-published": ("prepared", True, False),
    "sql-recorded": ("git-accepted", True, False),
    "after-generation-stage": ("git-accepted", True, False),
    "after-export-pointer": ("git-accepted", True, True),
}
SCHEMA = """
CREATE TABLE completion (
    operation TEXT PRIMARY KEY,
    binding TEXT NOT NULL,
    status TEXT NOT NULL,
    commit_id TEXT
);
"""


def connect(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA synchronous=FULL")
    return db


def stop(point, observed):
    if point == observed:
        os._exit(77)


def object_bytes(repo, commit, name):
    return subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:program/{name}"], cwd=repo,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
        check=True, capture_output=True, timeout=10,
    ).stdout


def generation_contents(repo, commit, exact):
    items = {name: object_bytes(repo, commit, name) for name in SOURCES}
    report = {"commit": commit, "request": exact,
              "files": {name: sha256(value).hexdigest() for name, value in items.items()}}
    return {**items, "receipt.json": (recovery.canonical(report) + "\n").encode()}


def validate_generation(directory, expected):
    if not directory.is_dir() or directory.is_symlink():
        return False
    entries = {entry.name: entry for entry in directory.iterdir()}
    return set(entries) == set(expected) and all(
        not entries[name].is_symlink() and entries[name].is_file()
        and entries[name].read_bytes() == contents for name, contents in expected.items()
    )


def export(repo, root, commit, exact, failpoint):
    expected = generation_contents(repo, commit, exact)
    generation = root / ("generation-" + commit)
    pointer = root / "current"
    if not generation.exists():
        with TemporaryDirectory(prefix="staged-", dir=root) as temporary:
            staged = Path(temporary) / "generation"
            staged.mkdir()
            for name, contents in expected.items():
                with (staged / name).open("xb") as handle:
                    handle.write(contents)
                    handle.flush()
                    os.fsync(handle.fileno())
            staged.rename(generation)
    if not validate_generation(generation, expected):
        return "existing-generation-mismatch"
    stop(failpoint, "after-generation-stage")
    if pointer.is_symlink():
        if os.readlink(pointer) != generation.name:
            return "unexpected-current-export"
    elif pointer.exists():
        return "unexpected-current-export"
    else:
        with TemporaryDirectory(prefix="pointer-", dir=root) as temporary:
            linked = Path(temporary) / "link"
            linked.symlink_to(generation.name, target_is_directory=True)
            os.replace(linked, pointer)
    stop(failpoint, "after-export-pointer")
    assert validate_generation(root / os.readlink(pointer), expected)
    return "exported"


def settle(db, repo, root, approval, failpoint):
    exact = recovery.binding(OPERATION, approval)
    key = recovery.canonical(exact)
    statement = "SELECT binding,status,commit_id FROM completion WHERE operation=?"
    record = db.execute(statement, (OPERATION,)).fetchone()
    if record is None:
        def prepare(_, __, audited):
            assert audited.valid
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO completion VALUES (?,?,'prepared',NULL) ON CONFLICT DO NOTHING",
                       (OPERATION, key))
            stored = db.execute(statement, (OPERATION,)).fetchone()
            if stored[0] != key:
                db.execute("ROLLBACK")
                return "operation-conflict", None
            stop(failpoint, "sql-before-commit")
            db.execute("COMMIT")
            return "prepared", stored

        status, record = CIP.gate(repo, approval, approval.candidate_tree, publisher=prepare)
        if status != "prepared":
            return status, None
        stop(failpoint, "sql-prepared")
    elif record[0] != key:
        return "operation-conflict", None

    status, commit = recovery.publish(repo, OPERATION, approval, "normal")
    if status not in ("published", "replayed"):
        return status, None
    stop(failpoint, "git-published")
    if record[2] is not None and record[2] != commit:
        return "journal-commit-mismatch", None
    if record[1] == "prepared":
        db.execute("UPDATE completion SET status='git-accepted',commit_id=? "
                   "WHERE operation=? AND status='prepared'", (commit, OPERATION))
    stop(failpoint, "sql-recorded")
    state = export(repo, root, commit, exact, failpoint)
    if state != "exported":
        return state, None
    db.execute("UPDATE completion SET status='exported' WHERE operation=?", (OPERATION,))
    return "exported", commit


def worker(words):
    repo, database, destination, common, baseline, incoming, tree, failpoint = words
    workspace = Path(repo)
    approval = CIP.make_plan(workspace, baseline, common, incoming, tree)
    with closing(connect(database)) as db:
        print(json.dumps(settle(db, workspace, Path(destination), approval, failpoint)), flush=True)


def spawn(repo, database, destination, request, point, code=0):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(repo),
               str(database), str(destination), *request, point]
    process = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)
    assert process.returncode == code, process.stderr
    return json.loads(process.stdout) if code == 0 else None


def observed(repo, database, destination):
    with closing(connect(database)) as db:
        state = db.execute("SELECT status FROM completion").fetchone()
    return (state[0] if state else "absent", LOOKUP(repo, recovery.receipt_ref(OPERATION)) is not None,
            (destination / "current").is_symlink())


def run_case(parent, label):
    directory = parent / label
    directory.mkdir()
    repo, database, destination = directory / "repo", directory / "completion.db", directory / "export"
    destination.mkdir()
    common, baseline, first, revised = CIP.prepare(repo)
    current = (common, baseline, *first)
    changed = (common, baseline, *revised)
    with closing(connect(database)) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        db.executescript(SCHEMA)

    if label in BOUNDARIES:
        spawn(repo, database, destination, current, label, code=77)
        assert observed(repo, database, destination) == BOUNDARIES[label]
        expected_directories = int(label in ("after-generation-stage", "after-export-pointer"))
        assert len(list(destination.glob("generation-*"))) == expected_directories
    accepted = LOOKUP(repo, recovery.receipt_ref(OPERATION))
    later = None
    if label == "after-export-pointer":
        binding = recovery.binding(OPERATION, CIP.make_plan(repo, baseline, common, *first))
        visible = destination / os.readlink(destination / "current")
        assert validate_generation(visible, generation_contents(repo, accepted, binding))
    if accepted is not None:
        later = NATIVE.object_commit(repo, revised[1], "unrelated later publication", (accepted,))
        GIT(repo, "update-ref", HEAD, later, accepted)
    status, result = spawn(repo, database, destination, current, "normal")
    assert status == "exported" and (accepted is None or accepted == result)
    assert observed(repo, database, destination) == ("exported", True, True)
    assert LOOKUP(repo, HEAD) == (result if later is None else later)
    exact = recovery.binding(OPERATION, CIP.make_plan(repo, baseline, common, *first))
    generation = destination / os.readlink(destination / "current")
    assert validate_generation(generation, generation_contents(repo, result, exact))
    assert GIT(repo, "rev-parse", f"{result}^{{tree}}") == first[1]
    if later is not None:
        assert (generation / "state.json").read_bytes() != object_bytes(repo, later, "state.json")
    assert spawn(repo, database, destination, current, "normal") == ["exported", result]
    assert spawn(repo, database, destination, changed, "normal") == ["operation-conflict", None]
    assert len(list(destination.glob("generation-*"))) == 1
    details = {"case": label, "git_commit": result, "tree": first[1], "advanced_head": later,
               "final_state": "exported", "exact_retry": "same-result", "different_retry": "operation-conflict"}
    if label == "normal":
        (generation / "state.json").write_bytes(b"changed outside the exporter\n")
        assert spawn(repo, database, destination, current, "normal") == ["existing-generation-mismatch", None]
        details["damaged_generation"] = "refused"
    else:
        details["interrupted_observation"] = BOUNDARIES[label]
    return details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--worker", nargs=8)
    args = parser.parse_args()
    if args.worker is not None:
        worker(args.worker)
    elif args.output is not None:
        with TemporaryDirectory(prefix="llmlang-completion-outbox-") as directory:
            root = Path(directory)
            cases = [run_case(root, label) for label in ("normal", *BOUNDARIES)]
            version = GIT(root, "--version")
        args.output.write_text(json.dumps({"git": version, "sqlite": sqlite3.sqlite_version, "cases": cases},
                                           indent=2) + "\n")
    else:
        parser.error("output is required outside worker mode")


if __name__ == "__main__":
    main()
