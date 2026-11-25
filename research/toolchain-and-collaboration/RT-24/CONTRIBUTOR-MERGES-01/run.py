"""Exercise multi-contributor semantic gates over native, pinned Git trees."""

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from random import Random
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
GROUPS = 24
SIDES = ("left", "right")
PARTS = [(group, side) for group in range(GROUPS) for side in SIDES]
DATE = "2026-11-25T08:00:00+00:00"
HEX = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Contributor:
    group: int
    side: str
    commit: str


def git(repo, *args, payload=None, author="fixture-integrator"):
    env = {
        **os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture-integrator", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": DATE, "GIT_COMMITTER_DATE": DATE,
    }
    result = subprocess.run(["git", *args], cwd=repo, env=env, input=payload,
                            capture_output=True, timeout=30, check=True)
    return result.stdout


def object_id(value):
    result = value.decode("ascii").strip()
    if not HEX.fullmatch(result):
        raise ValueError(result)
    return result


def part(group, side):
    return f"groups/{group:02}/{side}.used"


def set_value(repo, name, amount):
    stored = object_id(git(repo, "hash-object", "-w", "--stdin", payload=f"{amount}\n".encode()))
    git(repo, "update-index", "--add", "--cacheinfo", f"100644,{stored},{name}")


def commit(repo, tree, parents=(), title="fixture", author="fixture-integrator"):
    arguments = [word for parent in parents for word in ("-p", parent)]
    return object_id(git(repo, "commit-tree", tree, *arguments, "-m", title, author=author))


def create(repo):
    git(repo, "init", "-q", "--initial-branch=research/all", "--object-format=sha1")
    set_value(repo, "capacity", 4)
    for group, side in PARTS:
        set_value(repo, part(group, side), 1)
    baseline = commit(repo, object_id(git(repo, "write-tree")), title="Initial quota ledger")
    git(repo, "update-ref", "refs/heads/research/all", baseline)
    proposals = []
    for index, (group, side) in enumerate(PARTS):
        git(repo, "read-tree", baseline)
        set_value(repo, part(group, side), 3 if group < GROUPS // 2 else 2)
        tree = object_id(git(repo, "write-tree"))
        label = f"contributor-{index:02}"
        proposals.append(Contributor(group, side, commit(repo, tree, (baseline,), label, label)))
    return baseline, proposals


def select_tree(repo, base, head, proposed):
    result = git(repo, "merge-tree", "--write-tree", f"--merge-base={base}", head, proposed)
    return object_id(result)


def paths_for(groups):
    return ("capacity", *(part(group, side) for group in groups for side in SIDES))


def read_tree_values(repo, tree, paths):
    stream = git(repo, "cat-file", "--batch",
                 payload="".join(f"{tree}:{name}\n" for name in paths).encode())
    totals = {}
    cursor = 0
    for path in paths:
        end = stream.index(b"\n", cursor)
        _, kind, length = stream[cursor:end].split()
        if kind != b"blob":
            raise ValueError((path, kind))
        start = end + 1
        cursor = start + int(length) + 1
        if stream[cursor - 1:cursor] != b"\n":
            raise ValueError("Invalid Git object boundary")
        totals[path] = int(stream[start:cursor - 1])
    if cursor != len(stream):
        raise ValueError("Unexpected Git data")
    return totals


def violations(repo, tree, groups):
    contents = read_tree_values(repo, tree, paths_for(groups))
    exceeded = [index for index in groups
                if sum(contents[part(index, side)] for side in SIDES) > contents["capacity"]]
    return exceeded, len(contents)


def changed_groups(repo, current, proposed):
    raw = git(repo, "diff", "--name-only", "-z", current, proposed)
    changes = raw.decode().split("\0")[:-1]
    groups = set()
    for name in changes:
        match = re.fullmatch(r"groups/([0-9]{2})/(left|right)\.used", name)
        if not match or int(match[1]) >= GROUPS:
            raise ValueError(("edit outside declared scope", name))
        groups.add(int(match[1]))
    return tuple(sorted(groups))


def compare(repo, base, proposals, order):
    textual = checked = base
    counts = {"native_merges": 0, "accepted": 0, "refused": 0, "full_group_reads": 0,
              "scoped_group_reads": 0}
    whole = tuple(range(GROUPS))
    for index in order:
        edit = proposals[index]
        pure_tree = select_tree(repo, base, textual, edit.commit)
        textual = commit(repo, pure_tree, (textual, edit.commit), "text-only candidate")
        checked_tree = select_tree(repo, base, checked, edit.commit)
        scope = changed_groups(repo, checked, checked_tree)
        if scope != (edit.group,):
            raise ValueError((scope, edit))
        overall, full_reads = violations(repo, checked_tree, whole)
        scoped, scoped_reads = violations(repo, checked_tree, scope)
        if overall != scoped:
            raise ValueError(("scoped verdict disagreed with full graph", edit, overall, scoped))
        counts["native_merges"] += 2
        counts["full_group_reads"] += full_reads
        counts["scoped_group_reads"] += scoped_reads
        if scoped:
            counts["refused"] += 1
        else:
            checked = commit(repo, checked_tree, (checked, edit.commit), "validated candidate")
            counts["accepted"] += 1
    text_invalid, _ = violations(repo, textual, whole)
    result, _ = violations(repo, checked, whole)
    if text_invalid != list(range(GROUPS // 2)) or result:
        raise AssertionError((text_invalid, result))
    if (counts["accepted"], counts["refused"]) != (36, 12):
        raise ValueError(counts)
    return checked, {
        **counts,
        "order": list(order),
        "text_only_invalid_groups": text_invalid,
        "textual_tree": object_id(git(repo, "rev-parse", f"{textual}^{{tree}}")),
        "checked_tree": object_id(git(repo, "rev-parse", f"{checked}^{{tree}}")),
    }


def invalid_baseline_control(repo, baseline, proposals):
    git(repo, "read-tree", baseline)
    set_value(repo, part(23, "left"), 9)
    parent = commit(repo, object_id(git(repo, "write-tree")), (baseline,), "Unvalidated prior head")
    changed = select_tree(repo, baseline, parent, proposals[0].commit)
    groups = changed_groups(repo, parent, changed)
    scoped, _ = violations(repo, changed, groups)
    full, _ = violations(repo, changed, tuple(range(GROUPS)))
    if scoped or full != [23]:
        raise AssertionError((scoped, full))
    return {"scope": groups, "scoped_violations": scoped, "full_violations": full}


def evaluate(work):
    repo = work / "repository"
    repo.mkdir()
    baseline, proposed = create(repo)
    for contribution in proposed:
        invalid, _ = violations(repo, contribution.commit, tuple(range(GROUPS)))
        if invalid:
            raise ValueError(("invalid individual proposal", contribution))

    indices = list(range(len(proposed)))
    schedules = [indices, list(reversed(indices))]
    rng = Random(334)
    for _ in range(4):
        schedules.append(rng.sample(indices, len(indices)))
    runs = []
    head = None
    for schedule in schedules:
        head, result = compare(repo, baseline, proposed, schedule)
        runs.append(result)

    control = invalid_baseline_control(repo, baseline, proposed)
    git(repo, "update-ref", "refs/heads/research/all", head, baseline)
    git(work, "clone", "-q", "--no-local", "--branch", "research/all", str(repo), "restored")
    restored = work / "restored"
    restored_head = object_id(git(restored, "rev-parse", "HEAD"))
    if restored_head != head or violations(restored, restored_head, tuple(range(GROUPS)))[0]:
        raise AssertionError("The clean clone lost validated graph state")
    if not git(restored, "show-ref", "--verify", "refs/heads/research/all"):
        raise AssertionError("The clone lacks the selected head")

    return {
        "git": git(repo, "--version").decode().strip(),
        "runner_sha256": sha256(HERE.joinpath("run.py").read_bytes()).hexdigest(),
        "baseline": baseline,
        "contributors": len(proposed),
        "groups": GROUPS,
        "schedules": runs,
        "native_merges": sum(row["native_merges"] for row in runs),
        "scoped_matches_full": sum(row["accepted"] + row["refused"] for row in runs),
        "unique_textual_roots": len({row["textual_tree"] for row in runs}),
        "unique_checked_roots": len({row["checked_tree"] for row in runs}),
        "recovered_clean_clone": restored_head,
        "invalid_baseline_control": control,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-native-contributors-") as temporary:
        print(json.dumps(evaluate(Path(temporary)), indent=2))
