"""Replay coordinated reader/publication operations on an actual filesystem."""
import argparse
import fcntl
from hashlib import sha256
from itertools import combinations
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory


FILES = ("spec.txt", "body.txt", "evidence.txt")
MANIFEST = "manifest.json"
NAMES = (MANIFEST, *FILES)


def make_generation(label):
    files = {name: f"{label}:{name}\n".encode() for name in FILES}
    hashes = {name: sha256(contents).hexdigest() for name, contents in files.items()}
    return {**files, MANIFEST: json.dumps({"files": hashes}, sort_keys=True).encode()}


GENERATIONS = {name: make_generation(name) for name in ("old", "new")}


def stage(directory, generation):
    directory.mkdir()
    for name, contents in GENERATIONS[generation].items():
        (directory / name).write_bytes(contents)


def interleave(writer, reader):
    for positions in combinations(range(len(writer) + len(reader)), len(writer)):
        writers = iter(writer)
        readers = iter(reader)
        yield tuple(next(writers) if i in positions else next(readers)
                    for i in range(len(writer) + len(reader)))


def read_member(path, name, directory_fd):
    try:
        if directory_fd is None:
            return (path / name).read_bytes()
        descriptor = os.open(name, os.O_RDONLY, dir_fd=directory_fd)
        with os.fdopen(descriptor, "rb") as stream:
            return stream.read()
    except FileNotFoundError:
        return None


def verify(observed):
    if any(contents is None for contents in observed.values()):
        return False
    manifest = json.loads(observed[MANIFEST])
    actual = {name: sha256(observed[name]).hexdigest() for name in FILES}
    return manifest == {"files": actual}


def classify(observed):
    complete = [label for label, generation in GENERATIONS.items() if observed == generation]
    assert verify(observed) == bool(complete)
    if complete:
        return complete[0]
    if any(contents is None for contents in observed.values()):
        return "unavailable"
    return "inconsistent"


def inplace(root, schedule):
    live = root / "live"
    stage(live, "old")
    observed = {}
    for operation, name in schedule:
        if operation == "write":
            replacement = root / "stage-file"
            replacement.write_bytes(GENERATIONS["new"][name])
            os.replace(replacement, live / name)
        else:
            observed[name] = read_member(live, name, None)
    return classify(observed), False


def retire(root, use_lease):
    with (root / "lease").open("rb") as lease:
        if use_lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
        shutil.rmtree(root / "old")
        return True


def pointer(root, schedule, mode):
    stage(root / "old", "old")
    stage(root / "new", "new")
    live = root / "live"
    live.symlink_to("old", target_is_directory=True)
    (root / "lease").touch()
    pinned = None
    lease = None
    retired = False
    deferred = False
    observed = {}
    try:
        for operation, name in schedule:
            if operation == "pin":
                if mode == "leased":
                    lease = (root / "lease").open("rb")
                    fcntl.flock(lease, fcntl.LOCK_SH)
                if mode != "resolve-each":
                    pinned = os.open(live, os.O_RDONLY | os.O_DIRECTORY)
            elif operation == "switch":
                link = root / "next-link"
                link.symlink_to("new", target_is_directory=True)
                os.replace(link, live)
            elif operation == "retire":
                retired = retire(root, mode == "leased")
                deferred = not retired
            else:
                observed[name] = read_member(live, name, pinned)
    finally:
        if pinned is not None:
            os.close(pinned)
        if lease is not None:
            lease.close()
    if not retired:
        assert mode == "leased" and deferred
        retired = retire(root, use_lease=True)
    assert retired and not (root / "old").exists()
    assert (live / MANIFEST).read_bytes() == GENERATIONS["new"][MANIFEST]
    outcome = classify(observed)
    selected = "old" if schedule.index(("pin", "live")) < schedule.index(("switch", "live")) else "new"
    if mode == "leased":
        assert outcome == selected
    elif mode == "pin-directory":
        assert outcome in (selected, "unavailable")
    return outcome, deferred


def collect():
    rows = []
    reads = tuple(("read", name) for name in NAMES)
    writes = tuple(("write", name) for name in (*FILES, MANIFEST))
    for schedule in interleave(writes, reads):
        with TemporaryDirectory(prefix="llmlang-inplace-") as directory:
            outcome, deferred = inplace(Path(directory), schedule)
        rows.append({"policy": "in-place", "schedule": [f"{action}:{name}" for action, name in schedule], "outcome": outcome,
                     "retirement_deferred": deferred})
    for mode in ("resolve-each", "pin-directory", "leased"):
        writer = (("switch", "live"), ("retire", "old"))
        for schedule in interleave(writer, (("pin", "live"), *reads)):
            with TemporaryDirectory(prefix="llmlang-publication-") as directory:
                outcome, deferred = pointer(Path(directory), schedule, mode)
            rows.append({"policy": mode, "schedule": [f"{action}:{name}" for action, name in schedule], "outcome": outcome,
                         "retirement_deferred": deferred})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cases = collect()
    counts = {}
    for policy in ("in-place", "resolve-each", "pin-directory", "leased"):
        rows = [row for row in cases if row["policy"] == policy]
        counts[policy] = {
            outcome: sum(row["outcome"] == outcome for row in rows)
            for outcome in ("old", "new", "inconsistent", "unavailable")
        }
        counts[policy]["retirement_deferred"] = sum(row["retirement_deferred"] for row in rows)
    assert len(cases) == 133
    assert counts == {
        "in-place": dict(old=5, new=1, inconsistent=64, unavailable=0, retirement_deferred=0),
        "resolve-each": dict(old=1, new=11, inconsistent=9, unavailable=0, retirement_deferred=0),
        "pin-directory": dict(old=5, new=6, inconsistent=0, unavailable=10, retirement_deferred=0),
        "leased": dict(old=15, new=6, inconsistent=0, unavailable=0, retirement_deferred=20),
    }
    args.output.write_text(json.dumps({"counts": counts, "cases": cases}, indent=2) + "\n")


if __name__ == "__main__":
    main()
