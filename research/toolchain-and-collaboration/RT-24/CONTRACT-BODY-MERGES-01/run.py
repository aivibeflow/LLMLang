"""Check native Git merges of individually valid contract and implementation edits."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
GIT_FIXTURE = HERE.parent / "CONTRIBUTOR-MERGES-01"
sys.path.insert(0, str(GIT_FIXTURE))
from run import commit, git, object_id, select_tree


DOMAIN = tuple(range(65))
BASE_CONTRACT = {"exact_value": False, "upper_margin": 0, "allow_audit": True}
CONTRACTS = {
    "exact-value": {**BASE_CONTRACT, "exact_value": True},
    "no-audit": {**BASE_CONTRACT, "allow_audit": False},
    "both": {**BASE_CONTRACT, "exact_value": True, "allow_audit": False},
    "wider-value-range": {**BASE_CONTRACT, "upper_margin": 1},
}
BODIES = {
    "half-value": ("input / 2u", 1, "first method"),
    "identity-with-audit": ("input", 0x12, "first method"),
    "half-with-audit": ("input / 2u", 0x12, "first method"),
    "comment-only": ("input", 1, "other method"),
}
BASE_BODY = ("input", 1, "first method")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return sha256(value).hexdigest()


def provider(body):
    expression, trace, comment = body
    return f"""#include <stdint.h>
uint64_t apply(uint32_t input) {{
    /* {comment} */
    return ((uint64_t){trace} << 32) | ({expression});
}}
""".encode()


def branch(repo, base, path, payload, name):
    if base is not None:
        git(repo, "read-tree", base)
    blob = object_id(git(repo, "hash-object", "-w", "--stdin", payload=payload))
    git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
    tree = object_id(git(repo, "write-tree"))
    return commit(repo, tree, (base,) if base else (), name)


def native(cc, root, source, level, cache):
    key = digest(source), level
    if key not in cache:
        work = root / key[0] / str(level)
        work.mkdir(parents=True)
        (work / "provider.c").write_bytes(source)
        library = work / "provider.so"
        subprocess.run([cc, "-std=c17", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror",
                        f"-O{level}", str(work / "provider.c"), "-o", str(library)],
                       cwd=work, check=True, capture_output=True, timeout=30)
        loaded = ctypes.CDLL(str(library))
        operate = loaded.apply
        operate.argtypes = [ctypes.c_uint32]
        operate.restype = ctypes.c_uint64
        cache[key] = loaded, operate, digest(library.read_bytes())
    return cache[key]


def validation(repo, tree, cc, builds, body, cache):
    raw_contract = git(repo, "show", f"{tree}:contract.json")
    source = git(repo, "show", f"{tree}:provider.c")
    contract = json.loads(raw_contract)
    trace = []
    counts = Counter()
    profiles = {}
    for level in (0, 2):
        _, operate, artifact = native(cc, builds, source, level, cache)
        profile = Counter()
        values = []
        for value in DOMAIN:
            packed = operate(value)
            output = packed & 0xFFFFFFFF
            events = packed >> 32
            native_oracle = (value if body[0] == "input" else value // 2, body[1])
            if (output, events) != native_oracle:
                raise AssertionError((tree, level, value, output, events, native_oracle))
            values.append((value, output, events))
            valid_value = output == value if contract["exact_value"] else 0 <= output <= value + contract["upper_margin"]
            valid_trace = events == 1 or (events == 0x12 and contract["allow_audit"])
            profile["value_violations"] += not valid_value
            profile["trace_violations"] += not valid_trace
            profile["inputs_refused"] += not (valid_value and valid_trace)
        if trace and trace != values:
            raise AssertionError("Optimization changed observed output")
        trace = values
        counts = profile
        profiles[f"O{level}"] = artifact
    return {
        "contract_sha256": digest(raw_contract),
        "provider_sha256": digest(source),
        "native_artifacts": profiles,
        "trace_sha256": digest(canonical(trace)),
        "violations_per_profile": dict(counts),
    }


def assess(cc, work):
    repo = work / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=research/all", "--object-format=sha1")
    initial = branch(repo, None, "contract.json", canonical(BASE_CONTRACT), "Install broad contract")
    baseline = branch(repo, initial, "provider.c", provider(BASE_BODY), "Install reference implementation")
    contracts = {name: branch(repo, baseline, "contract.json", canonical(value), name)
                 for name, value in CONTRACTS.items()}
    bodies = {name: branch(repo, baseline, "provider.c", provider(body), name)
              for name, body in BODIES.items()}
    builds = work / "build"
    cache = {}
    base = validation(repo, baseline, cc, builds, BASE_BODY, cache)
    parents = {}
    for name, head in contracts.items():
        parents[name] = validation(repo, head, cc, builds, BASE_BODY, cache)
    for name, head in bodies.items():
        parents[name] = validation(repo, head, cc, builds, BODIES[name], cache)
    if base["violations_per_profile"]["inputs_refused"] or any(
        row["violations_per_profile"]["inputs_refused"] for row in parents.values()
    ):
        raise ValueError("A parent changes the contract or body incorrectly by itself")
    if base["native_artifacts"] != parents["comment-only"]["native_artifacts"]:
        raise ValueError("The comment-only provider unexpectedly changed artifact bytes")

    outcomes = {}
    for (contract, c_head), (body, b_head) in product(contracts.items(), bodies.items()):
        tree = select_tree(repo, baseline, c_head, b_head)
        reverse = select_tree(repo, baseline, b_head, c_head)
        if reverse != tree:
            raise ValueError("Changing mount order changed the disjoint result")
        facts = validation(repo, tree, cc, builds, BODIES[body], cache)
        if (facts["contract_sha256"] != parents[contract]["contract_sha256"]
                or facts["provider_sha256"] != parents[body]["provider_sha256"]
                or facts["native_artifacts"] != parents[body]["native_artifacts"]):
            raise AssertionError((contract, body, facts))
        expected_value = 64 if CONTRACTS[contract]["exact_value"] and BODIES[body][0] != "input" else 0
        expected_trace = 65 if not CONTRACTS[contract]["allow_audit"] and BODIES[body][1] == 0x12 else 0
        wanted = {"inputs_refused": max(expected_value, expected_trace),
                  "value_violations": expected_value, "trace_violations": expected_trace}
        if facts["violations_per_profile"] != wanted:
            raise AssertionError((contract, body, facts, wanted))
        outcomes[f"{contract}/{body}"] = {"tree": tree, **facts}

    fails = sum(row["violations_per_profile"]["inputs_refused"] > 0 for row in outcomes.values())
    return {
        "git": git(repo, "--version").decode().strip(),
        "compiler": subprocess.check_output([cc, "--version"], text=True, timeout=10).splitlines()[0],
        "source_sha256": {str(path.relative_to(HERE.parent)): digest(path.read_bytes())
                          for path in (HERE / "run.py", GIT_FIXTURE / "run.py")},
        "baseline": base,
        "independent_parents": parents,
        "native_merges": len(outcomes) * 2,
        "native_observations": (1 + len(parents) + len(outcomes)) * 2 * len(DOMAIN),
        "combined_accepted": len(outcomes) - fails,
        "combined_refused": fails,
        "combined": outcomes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-contract-body-merge-") as work:
        print(json.dumps(assess(args.cc, Path(work)), indent=2))
