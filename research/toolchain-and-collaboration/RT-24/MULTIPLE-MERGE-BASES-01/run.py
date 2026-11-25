#!/usr/bin/env python3
"""Compare semantic merge decisions across all real bases and native Git's virtual base."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BACKENDS = ("files", "reftable")
EVENTS = {"ab": ("a", "b"), "ba": ("b", "a"), "cb": ("c", "b"), "da": ("d", "a")}


@dataclass(frozen=True)
class State:
    result: int
    events: str

    @property
    def observation(self):
        return self.result, EVENTS[self.events]


def states(*specifications):
    return tuple(State(result, effects) for result, effects in specifications)


CASES = {
    "convergent": states((0, "ab"), (1, "ab"), (0, "ba"), (3, "ba"), (3, "ba")),
    "convergent_effects": states((0, "ab"), (0, "ba"), (0, "ab"), (2, "da"), (2, "da")),
    "ancestral_result_disagreement": states((0, "ab"), (1, "ab"), (2, "ab"), (1, "ab"), (2, "ab")),
    "ancestral_trace_disagreement": states((0, "ab"), (0, "ba"), (0, "cb"), (0, "ba"), (0, "cb")),
    "synthetic_selects_new_result": states((0, "ab"), (1, "ab"), (0, "ba"), (1, "ba"), (2, "ba")),
    "synthetic_selects_new_trace": states((0, "ab"), (0, "ba"), (1, "ab"), (1, "ba"), (1, "cb")),
    "synthetic_with_two_refusals": states((0, "ab"), (1, "ab"), (0, "ba"), (3, "ba"), (1, "da")),
}
OID = re.compile(r"[0-9a-f]{40}")
ENVIRONMENT = {
    **os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-10T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-10T00:00:00Z",
    "LC_ALL": "C",
}


class Repository:
    def __init__(self, git, location, backend):
        self.git = git
        self.location = location
        self.call("init", "-q", "--bare", "--object-format=sha1", f"--ref-format={backend}")
        assert self.call("rev-parse", "--show-ref-format") == backend

    def command(self, *arguments, data=None, expected=(0,)):
        completed = subprocess.run([self.git, *arguments], cwd=self.location, env=ENVIRONMENT,
                                   capture_output=True, input=data, text=True, timeout=20)
        if completed.returncode not in expected or completed.stderr:
            raise RuntimeError(completed.stderr or completed.stdout or str(arguments))
        return completed.returncode, completed.stdout.strip()

    def call(self, *arguments, data=None):
        return self.command(*arguments, data=data)[1]

    def commit(self, title, tree, *parents):
        args = [argument for parent in parents for argument in ("-p", parent)]
        return self.call("commit-tree", tree, *args, data=f"{title}\n")

    def tree(self, state, note):
        files = {"effect.ops": "\n".join(EVENTS[state.events]) + "\n",
                 "note.txt": note + "\n", "return.ops": f"{state.result}\n"}
        rows = []
        for name, content in files.items():
            blob = self.call("hash-object", "-w", "--stdin", data=content)
            rows.append(f"100644 blob {blob}\t{name}\n")
        return self.call("mktree", data="".join(rows))

    def observation(self, tree):
        value = self.call("show", f"{tree}:return.ops")
        effects = tuple(self.call("show", f"{tree}:effect.ops").splitlines())
        if not value.isdecimal() or effects not in EVENTS.values():
            raise ValueError("Candidate violates the closed source profile")
        return int(value), effects

    def merge(self, left, right, base=None):
        arguments = ["merge-tree", "--write-tree", "--no-messages"]
        if base is not None:
            arguments.append(f"--merge-base={base}")
        result, output = self.command(*arguments, left, right, expected=(0, 1))
        tree = output.splitlines()[0]
        assert OID.fullmatch(tree)
        return ("clean", tree) if result == 0 else ("conflict", None)


def semantics(base, left, right):
    """Closed three-way equality per observable component."""
    components = []
    for before, lhs, rhs in zip(base.observation, left.observation, right.observation, strict=True):
        if lhs == rhs or before == rhs:
            components.append(lhs)
        elif before == lhs:
            components.append(rhs)
        else:
            return None
    return tuple(components)


def setup(repo, specification):
    root, a, b, left, right = specification
    origin = repo.commit("common starting program", repo.tree(root, "initial"))
    ancestor_a = repo.commit("first incomparable change", repo.tree(a, "initial"), origin)
    ancestor_b = repo.commit("second incomparable change", repo.tree(b, "annotation"), origin)
    first_tip = repo.commit("left integration", repo.tree(left, "annotation"), ancestor_a, ancestor_b)
    second_tip = repo.commit("right integration", repo.tree(right, "annotation"), ancestor_b, ancestor_a)
    exact = {"A": ancestor_a, "B": ancestor_b}
    assert set(repo.call("merge-base", "--all", first_tip, second_tip).splitlines()) == set(exact.values())
    return exact, first_tip, second_tip


def witness(repo, scenario, specification, orientation):
    _, a, b, left, right = specification
    exact, first_tip, second_tip = setup(repo, specification)
    if orientation == "right_first":
        left, right = right, left
        first_tip, second_tip = second_tip, first_tip
    programs = {"A": a, "B": b}
    by_base = {}
    for label, base in exact.items():
        status, tree = repo.merge(first_tip, second_tip, base)
        expectation = semantics(programs[label], left, right)
        observed = repo.observation(tree) if tree is not None else None
        assert observed == expectation
        by_base[label] = {"status": status, "tree": tree, "observation": observed}

    default_status, default_tree = repo.merge(first_tip, second_tip)
    virtual_status, virtual_tree = repo.merge(exact["A"], exact["B"])
    default = repo.observation(default_tree) if default_tree is not None else None
    explicit_virtual = None
    if virtual_tree is not None:
        explicit_virtual, virtual_result_tree = repo.merge(first_tip, second_tip, virtual_tree)
        assert (default_status, default_tree) == (explicit_virtual, virtual_result_tree)

    strong = [row["observation"] for row in by_base.values()]
    agreed = strong[0] is not None and strong[0] == strong[1]
    allowed = agreed and default == strong[0]
    repo.call("update-ref", "refs/heads/publication", first_tip)
    commit = None
    if allowed:
        commit = repo.commit("validated merge publication", default_tree, first_tip, second_tip)
        repo.call("update-ref", "refs/heads/publication", commit, first_tip)
        assert repo.call("rev-list", "--parents", "-n", "1", commit).split()[1:] == [first_tip, second_tip]
        actual_tree = repo.call("rev-parse", f"{commit}^{{tree}}")
        assert actual_tree == default_tree
        assert repo.observation(actual_tree) == default
    assert repo.call("rev-parse", "refs/heads/publication") == (commit or first_tip)

    return {
        "case": scenario, "orientation": orientation, "real_bases": exact,
        "left": first_tip, "right": second_tip, "by_base": by_base,
        "base_pair_merge": {"status": virtual_status, "tree": virtual_tree,
                            "explicit_virtual_status": explicit_virtual},
        "native": {"status": default_status, "tree": default_tree, "observation": default},
        "all_real_bases_agree": agreed, "published_commit": commit,
    }


def run(git):
    version = subprocess.check_output([git, "--version"], text=True, timeout=10).strip()
    if version != "git version 2.52.0":
        raise ValueError("Expected Git 2.52.0")
    by_backend = {}
    for backend in BACKENDS:
        rows = []
        for (scenario, specification), order in product(CASES.items(), ("left_first", "right_first")):
            with TemporaryDirectory(prefix="llmlang-multiple-bases-") as temporary:
                repository = Repository(git, temporary, backend)
                rows.append(witness(repository, scenario, specification, order))
        by_backend[backend] = rows
    assert by_backend["files"] == by_backend["reftable"]
    rows = by_backend["files"]
    counts = {
        "cases": len(rows),
        "native_clean": sum(row["native"]["status"] == "clean" for row in rows),
        "ambiguous_native_clean": sum(row["native"]["status"] == "clean" and not row["all_real_bases_agree"]
                                      for row in rows),
        "consensus_published": sum(row["published_commit"] is not None for row in rows),
        "native_clean_real_bases_both_conflict": sum(
            row["native"]["status"] == "clean" and all(base["status"] == "conflict"
                                                       for base in row["by_base"].values())
            for row in rows
        ),
    }
    assert counts["ambiguous_native_clean"] and counts["native_clean_real_bases_both_conflict"]
    return {
        "schema": "llmlang-multiple-merge-bases/1", "git": version, "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "ref_backends": BACKENDS, "native_repositories": len(rows) * len(BACKENDS), "counts": counts,
        "source_states": {name: [state.observation for state in data] for name, data in CASES.items()},
        "rows_per_backend": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git", default="git")
    args = parser.parse_args()
    print(json.dumps(run(args.git), indent=2))
