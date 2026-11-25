#!/usr/bin/env python3
"""Compare native Git container merging with exact whole-state validation."""

from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
FIXTURE = runpy.run_path(str(HERE.parent / "GIT-CLOSED-REPRESENTATION-01/run.py"))
git = FIXTURE["git"]
encode = FIXTURE["encode"]
digest = FIXTURE["digest"]

INTENT = {"entry": "example", "requirement": "contract", "selected": "provider"}
BASE_CONTRACT = {"limit": 12, "effects": ["audit", "write"], "abis": ["v1", "v2"]}
BASE_PROVIDER = {"return_base": 4, "effect": "audit", "abi": "v1"}
CASES = (
    ("compatible-tightening", {"limit": 8}, {"return_base": 6}, ()),
    ("scalar-incompatible", {"limit": 7}, {"return_base": 8}, ("value",)),
    ("effect-incompatible", {"effects": ["audit"]}, {"effect": "write"}, ("effect",)),
    ("abi-incompatible", {"abis": ["v1"]}, {"abi": "v2"}, ("abi",)),
    ("multiple-incompatible", {"limit": 6, "effects": ["audit"], "abis": ["v1"]},
        {"return_base": 9, "effect": "write", "abi": "v2"}, ("value", "effect", "abi")),
    ("compatible-effect", {"limit": 10}, {"effect": "write"}, ()),
)


def commit(repository, label):
    git(repository, "add", "-A")
    git(repository, "commit", "--quiet", "-m", label)
    return git(repository, "rev-parse", "HEAD").decode().strip()


def write(repository, name, value):
    path = repository / "program" / (name + ".json")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(encode(value))


def read(repository, tree):
    state = {}
    for name in ("root", "contract", "provider"):
        raw = git(repository, "show", tree + ":program/" + name + ".json")
        value = json.loads(raw)
        assert raw == encode(value)
        state[name] = value
    assert state["root"] == INTENT
    return state


def oracle(work, provider):
    assert provider["effect"] in ("audit", "write")
    assert provider["abi"] in ("v1", "v2")
    marker = 1 if provider["effect"] == "audit" else 2
    raw = (
        "#include <stdio.h>\n"
        "int main(void) {\n"
        "   for (int input = 0; input < 3; ++input)\n"
        f'      printf("%d %d\\n", {provider["return_base"]} + input, {marker});\n'
        "   return 0;\n"
        "}\n"
    )
    work.mkdir()
    (work / "provider.c").write_text(raw, encoding="utf-8")
    subprocess.run(["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror", "provider.c", "-o", "provider"],
                   cwd=work, check=True, capture_output=True)
    stdout = subprocess.check_output(["./provider"], cwd=work, text=True)
    return [(int(value), {"1": "audit", "2": "write"}[event])
            for value, event in (line.split() for line in stdout.splitlines())]


def validate(state, observed):
    contract = state["contract"]
    provider = state["provider"]
    blocked = []
    assert len(observed) == 3
    if any(value > contract["limit"] for value, _ in observed):
        blocked.append("value")
    if any(effect not in contract["effects"] for _, effect in observed):
        blocked.append("effect")
    if provider["abi"] not in contract["abis"]:
        blocked.append("abi")
    return tuple(blocked)


def merge_semantically(base, left, right):
    chosen = deepcopy(base)
    for role in ("contract", "provider"):
        base_fact = base[role]
        fact_left = left[role]
        fact_right = right[role]
        assert fact_left == base_fact or fact_right == base_fact
        chosen[role] = fact_right if fact_left == base_fact else fact_left
    return chosen


def trial(work, object_format, binary, case):
    label, contract_edit, provider_edit, expected = case
    work.mkdir()
    repo = work / "primary"
    repo.mkdir()
    git(repo, "init", "--quiet", "--object-format=" + object_format, "-b", "research/all")
    if binary:
        (repo / ".gitattributes").write_text("program/*.json -merge\n", encoding="utf-8")
    write(repo, "root", INTENT)
    write(repo, "contract", BASE_CONTRACT)
    write(repo, "provider", BASE_PROVIDER)
    baseline = commit(repo, "exact base graph")
    alternate = work / "alternate"
    git(work, "clone", "-q", "--no-local", str(repo), str(alternate))
    write(repo, "contract", BASE_CONTRACT | contract_edit)
    left_pin = commit(repo, "edit contract fact")
    provider = BASE_PROVIDER | provider_edit
    write(alternate, "provider", provider)
    right_pin = commit(alternate, "edit provider fact")
    git(repo, "fetch", "--quiet", str(alternate), "refs/heads/research/all:refs/tags/other-tip")
    assert git(repo, "branch", "--show-current").strip() == b"research/all"
    assert git(alternate, "branch", "--show-current").strip() == b"research/all"
    assert git(repo, "merge-base", left_pin, right_pin).decode().strip() == baseline
    merged_tree = git(repo, "merge-tree", "--write-tree", "--no-messages", left_pin, right_pin).decode().strip()

    base = read(repo, baseline)
    left = read(repo, left_pin)
    right = read(repo, right_pin)
    candidate = read(repo, merged_tree)
    semantic = merge_semantically(base, left, right)
    assert candidate == semantic

    before_seen = oracle(work / "baseline-native", BASE_PROVIDER)
    after_seen = oracle(work / "replacement-native", provider)
    assert validate(base, before_seen) == validate(left, before_seen) == validate(right, after_seen) == ()
    errors = validate(semantic, after_seen)
    assert errors == expected
    final = {"decision": "validated", "semantic_root": digest(encode(semantic))} if not errors else {
        "decision": "refused", "retained_semantic_root": digest(encode(base)),
    }
    return {
        "case": label, "object_format": object_format, "binary_attributes": binary,
        "merge_tree": merged_tree, "git_conflicts": False, "refusal_reasons": errors,
        "native": {"before": before_seen, "after": after_seen}, "semantic_gate": final,
    }


def experiment(root):
    rows = []
    for object_format, binary, case in product(("sha1", "sha256"), (False, True), CASES):
        name = f"{object_format}-{binary}-{case[0]}"
        rows.append(trial(root / name, object_format, binary, case))
    assert len(rows) == 24
    assert len([row for row in rows if row["refusal_reasons"]]) == 16
    return {"format": "text-merge-gate-01", "git": git(root, "--version").decode().strip(), "rows": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-text-merge-") as directory:
        result = experiment(Path(directory))
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
