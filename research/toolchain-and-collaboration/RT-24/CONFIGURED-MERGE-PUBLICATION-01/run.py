#!/usr/bin/env python3
"""Compare parent receipts and exact prospective native publication on real Git merges."""

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
from shutil import which
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
FILES = ("app.c", "providers.c", "observe.c")
TARGETS = {"base", "equivalent", "wrong", "restricted", "other"}
POLICIES = ("parents", "provider_only", "whole_tree", "bound_scope", "fresh")
INPUTS = (-100, -17, -1, 0, 1, 2, 17, 100)
MODES = ("O0", "O2")
STANDARD_GRANTS = "base\nequivalent\nwrong\nother\n"
POLICY = "llmlang-rt24-configured-merge-publication/1"


@dataclass(frozen=True)
class Case:
    name: str
    base: dict[str, str]
    left: dict[str, str]
    right: dict[str, str]
    expected: str
    candidate_provider: str | None


def header(target):
    return f"#define SELECTED provider_{target}\n"


def configuration(flag):
    return json.dumps({"feature": flag}, separators=(",", ":")) + "\n"


ENABLED = {"profile.json": configuration(1)}
BASE = {"selected.h": header("base"), "profile.json": configuration(0), "grants.txt": STANDARD_GRANTS}
CASES = (
    Case("new_compatible_provider", BASE, {"selected.h": header("equivalent")}, ENABLED, "admitted", "equivalent"),
    Case("new_wrong_behavior", BASE, {"selected.h": header("wrong")}, ENABLED, "behavior", "wrong"),
    Case("new_unauthorized_provider", BASE, {"selected.h": header("restricted")}, ENABLED, "authority", "restricted"),
    Case("grant_removed_for_enabled_provider", {**BASE, "selected.h": header("equivalent")},
         {"grants.txt": STANDARD_GRANTS.replace("equivalent\n", "")}, ENABLED, "authority", "equivalent"),
    Case("scope_preserved_with_notes", BASE, {"notes-left.txt": "ordinary left\n"},
         {"notes-right.txt": "ordinary right\n"}, "admitted", "base"),
    Case("scope_preserved_after_flag_edit", BASE, {"notes-left.txt": "ordinary left\n"}, ENABLED, "admitted", "base"),
    Case("preserve_known_dormant_header", BASE, {"selected.h": header("wrong")},
         {"notes-right.txt": "ordinary right\n"}, "admitted", "base"),
    Case("identical_exact_parent_tree", BASE, {"notes-left.txt": "ordinary left\n"}, {}, "admitted", "base"),
    Case("native_header_conflict", BASE, {"selected.h": header("equivalent")},
         {"selected.h": header("other")}, "git-conflict", None),
)


def digest(data):
    return sha256(data).hexdigest()


def identity(value):
    return digest(POLICY.encode() + b"\0" + json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def command(directory, *arguments, data=None, check=True):
    return subprocess.run(arguments, cwd=directory, input=data, check=check, capture_output=True,
                          text=True, timeout=30, env={**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                          "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "Fixture",
                          "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Fixture",
                          "GIT_COMMITTER_EMAIL": "fixture@example.invalid", "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z",
                          "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"})


def git(directory, *arguments):
    return command(directory, "git", *arguments).stdout.strip()


def commit(repo, additions, message):
    for filename, contents in additions.items():
        (repo / filename).write_text(contents, encoding="utf-8")
        git(repo, "add", "--", filename)
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def make_history(repo, case):
    git(repo, "init", "-qb", "main", "--object-format=sha1")
    base = commit(repo, {**case.base, **{source: (HERE / source).read_text(encoding="utf-8") for source in FILES}}, "base")
    git(repo, "checkout", "-qb", "left")
    left = commit(repo, case.left, "left")
    git(repo, "checkout", "-qb", "right", base)
    right = commit(repo, case.right, "right")
    git(repo, "checkout", "-q", "left")
    assert git(repo, "merge-base", left, right) == base
    merge = command(repo, "git", "merge", "-q", "--no-ff", "-m", "candidate", right, check=False)
    if merge.returncode:
        assert merge.returncode == 1 and case.expected == "git-conflict"
        assert git(repo, "rev-parse", "HEAD") == left and git(repo, "ls-files", "--unmerged")
        git(repo, "merge", "--abort")
        return base, left, right, None
    candidate = git(repo, "rev-parse", "HEAD")
    assert git(repo, "rev-list", "--parents", "-n", "1", candidate).split() == [candidate, left, right]
    return base, left, right, candidate


def observe(repo, commit_id, tools):
    git(repo, "checkout", "-q", "--detach", commit_id)
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    flag = json.loads((repo / "profile.json").read_bytes())["feature"]
    assert flag in (0, 1)
    grants = (repo / "grants.txt").read_text(encoding="utf-8").splitlines()
    assert set(grants) <= TARGETS and len(grants) == len(set(grants))
    selected = re.fullmatch(r"#define SELECTED provider_(\w+)\n", (repo / "selected.h").read_text(encoding="utf-8"))[1]
    assert selected in TARGETS
    native = []
    path_set = {*FILES, "selected.h", "profile.json", "grants.txt"}
    for opt in MODES:
        flags = (f"-{opt}", f"-DFEATURE={flag}", "-fno-optimize-sibling-calls", "-Wall", "-Werror")
        command(repo, "gcc", *flags, "-MMD", "-MF", "app.d", "-c", "app.c", "-o", "app.o")
        assert (repo / "app.d").read_text().split(":", 1)[1].split() == ["app.c", "selected.h"]
        assembly = command(repo, "objdump", "-drw", "app.o").stdout
        target, = re.findall(r"\bR_X86_64_PLT32\s+provider_(\w+)-0x4\s*$", assembly, re.MULTILINE)
        assert target == (selected if flag else "base")
        command(repo, "gcc", f"-{opt}", "app.o", "providers.c", "observe.c", "-o", "observe")
        output = command(repo, "./observe", data="\n".join(map(str, INPUTS)) + "\n").stdout.splitlines()
        values = list(map(int, output))
        offset = 2 if target == "wrong" else 1
        assert values == [value + offset for value in INPUTS]
        native.append({"opt": opt, "flags": flags, "provider": target, "values": values,
                       "object_sha256": digest((repo / "app.o").read_bytes())})
    assert native[0]["provider"] == native[1]["provider"]
    supported = native[0]["provider"] in grants
    within_contract = all(row["values"] == [value + 1 for value in INPUTS] for row in native)
    status = "admitted" if supported and within_contract else "authority" if not supported else "behavior"
    inputs = {path: {"blob": git(repo, "rev-parse", f"{commit_id}:{path}"),
                     "sha256": digest((repo / path).read_bytes())} for path in sorted(path_set)}
    scope = {"exact_inputs": inputs, "toolchain": tools, "domain": list(INPUTS),
             "flags": [row["flags"] for row in native], "obligation": "return input plus one"}
    return {"commit": commit_id, "tree": tree, "scope": identity(scope), "scope_input": scope,
            "provider": native[0]["provider"], "status": status, "native": native}


def compare(repo, base, candidate, parents):
    assert all(row["status"] == "admitted" for row in parents)
    if candidate is None:
        predictions = dict.fromkeys(POLICIES, False)
    else:
        predictions = {
            "parents": True,
            "provider_only": any(row["provider"] == candidate["provider"] for row in parents),
            "whole_tree": any(row["tree"] == candidate["tree"] for row in parents),
            "bound_scope": any(row["scope"] == candidate["scope"] for row in parents),
            "fresh": candidate["status"] == "admitted",
        }
    observed = {}
    for policy, admit in predictions.items():
        ref = f"refs/heads/release-{policy}"
        git(repo, "update-ref", ref, base)
        if admit:
            assert candidate is not None
            git(repo, "update-ref", ref, candidate["commit"], base)
            current = candidate["commit"]
        else:
            current = base
        assert git(repo, "rev-parse", ref) == current
        if admit:
            assert git(repo, "rev-parse", f"{ref}^{{tree}}") == candidate["tree"]
            stale = command(repo, "git", "update-ref", ref, base, base, check=False)
            assert stale.returncode == 128 and "expected" in stale.stderr
            assert git(repo, "rev-parse", ref) == current
        observed[policy] = {"advanced": admit, "release_commit": current, "stale_cas_refused": admit}
    return observed


def run(directory):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    tools = {name: {"version": command(directory, name, "--version").stdout.splitlines()[0],
                    "sha256": digest(Path(which(name)).read_bytes())} for name in ("gcc", "objdump", "ld")}
    tools["cc1"] = digest(Path(command(directory, "gcc", "-print-prog-name=cc1").stdout.strip()).read_bytes())
    rows = []
    for case in CASES:
        repo = directory / case.name
        repo.mkdir()
        base, left, right, candidate = make_history(repo, case)
        parents = [observe(repo, oid, tools) for oid in (left, right)]
        built = observe(repo, candidate, tools) if candidate is not None else None
        status = built["status"] if built is not None else "git-conflict"
        assert status == case.expected and (built["provider"] if built else None) == case.candidate_provider
        publication = compare(repo, base, built, parents)
        clone_rebuilt = publication["fresh"]["advanced"]
        if clone_rebuilt:
            clone = directory / (case.name + "-fresh-clone")
            git(directory, "clone", "-q", "--no-local", "--single-branch", "--branch", "release-fresh", str(repo), str(clone))
            assert git(clone, "rev-parse", "HEAD") == built["commit"]
            assert observe(clone, built["commit"], tools) == built
            git(clone, "fsck", "--full", "--no-progress")
        rows.append({"case": case.name, "base": base, "expected": case.expected, "parents": parents,
                     "candidate": built, "publication": publication, "clone_rebuilt": clone_rebuilt})
    metrics = {}
    for policy in POLICIES:
        predicted = [row["publication"][policy]["advanced"] for row in rows]
        expected = [row["expected"] == "admitted" for row in rows]
        comparisons = tuple(zip(predicted, expected, strict=True))
        metrics[policy] = {"exact_publications": comparisons.count((True, True)),
                           "invalid_publications": comparisons.count((True, False)),
                           "valid_refusals": comparisons.count((False, True)),
                           "expected_refusals": comparisons.count((False, False))}
    assert metrics["parents"]["invalid_publications"] == 3
    assert metrics["provider_only"]["invalid_publications"] == 1
    assert metrics["bound_scope"]["exact_publications"] > metrics["whole_tree"]["exact_publications"]
    assert metrics["fresh"] == {"exact_publications": 5, "invalid_publications": 0, "valid_refusals": 0, "expected_refusals": 4}
    return {"schema": POLICY, "python": platform.python_version(), "git": git(directory, "--version"),
            "tools": tools, "source_sha256": {name: digest((HERE / name).read_bytes()) for name in (*FILES, "run.py")},
            "inputs": INPUTS, "histories": len(rows), "parent_builds": 2 * len(rows) * len(MODES),
            "candidate_builds": sum(row["candidate"] is not None for row in rows) * len(MODES),
            "fresh_clone_builds": sum(row["clone_rebuilt"] for row in rows) * len(MODES),
            "stale_cas_refusals": sum(result["stale_cas_refused"] for row in rows for result in row["publication"].values()),
            "metrics": metrics, "observations": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-configured-merge-") as scratch:
        result = run(Path(scratch))
    rows = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in rows))
    print("  ]\n}")
