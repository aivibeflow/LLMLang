"""Compare parent-based reuse on exact two-parent Git merge objects."""
import argparse
from dataclasses import asdict, dataclass, replace
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from tests.test_rt24_merge_tree_gate import (
    CALLEE, GraphImportError, InventoryError, MergeTreeGateExperiment, commit, git, import_closed,
    read_inventory, row,
)


AUDIT_FIXTURE = Path(__file__).resolve().parents[3] / "toolchain-and-collaboration" / "RT-24" / "AUDIT-AUTHORITY-01"
loader = spec_from_file_location("rt24_audit_fixture", AUDIT_FIXTURE / "run.py")
signature_fixture = module_from_spec(loader)
loader.loader.exec_module(signature_fixture)


ISSUER = "fixture-resolution-authority"
OTHER_ISSUER = "fixture-other-issuer"
SLOT = "callee"


@dataclass(frozen=True)
class Choice:
    merge: str
    tree: str
    parents: tuple[str, str]
    source: str
    slot: str
    value: str
    issuer: str


def rev(repo, ref):
    return git(repo, "rev-parse", ref).decode().strip()


def parents(repo, pin):
    raw = git(repo, "cat-file", "-p", pin).split(b"\n\n", 1)[0]
    return tuple(line.split()[1].decode("ascii") for line in raw.splitlines() if line.startswith(b"parent "))


def value(repo, pin):
    return import_closed(read_inventory(repo, pin))[1].mapping.get(SLOT)


def follow(repo, base, pin, reviewed):
    while True:
        try:
            if value(repo, pin) != reviewed:
                return "ineligible"
            if pin == base:
                return "eligible"
            ancestry = parents(repo, pin)
        except (GraphImportError, InventoryError, subprocess.CalledProcessError):
            return "unknown"
        if len(ancestry) != 1:
            return "unknown"
        pin = ancestry[0]


def all_paths(states):
    if "ineligible" in states:
        return "ineligible"
    return "unknown" if "unknown" in states else "eligible"


def any_path(states):
    if "eligible" in states:
        return "eligible"
    return "unknown" if "unknown" in states else "ineligible"


def envelope(receipt):
    return {"format": "rt05-merge-choice/1", "choice": asdict(receipt)}


def choices(repo, base, merged, reviewed, receipt, signature, service, trust):
    ancestry = parents(repo, merged)
    states = [follow(repo, base, pin, reviewed) for pin in ancestry]
    current = value(repo, merged)
    if current != reviewed:
        return {name: "ineligible" for name in ("first-parent", "any-parent", "all-parents", "exact-choice")}, states
    selected = "unknown"
    if (receipt is not None and receipt.issuer == ISSUER
            and (receipt.merge, receipt.tree, receipt.parents) == (merged, rev(repo, f"{merged}^{{tree}}"), ancestry)
            and receipt.source in ancestry and receipt.slot == SLOT and receipt.value == current
            and service.verify(envelope(receipt), signature, trust)):
        selected = states[ancestry.index(receipt.source)]
    return {"first-parent": states[0], "any-parent": any_path(states), "all-parents": all_paths(states),
            "exact-choice": selected}, states


def branch(fixture, label, lifecycle):
    repo = fixture.repo
    git(repo, "switch", "--quiet", "-c", label, fixture.base)
    if lifecycle == "recreated":
        commit(repo, {CALLEE: []})
    return commit(repo, {CALLEE: [row(SLOT, fixture.old)], f"{label}.txt": f"{label} edit\n"})


def experiment(left, right, chosen, expected, *, mutation=None):
    fixture = MergeTreeGateExperiment()
    fixture.setUp()
    try:
        repo = fixture.repo
        left_head = branch(fixture, "left", left)
        right_head = branch(fixture, "right", right)
        git(repo, "switch", "--quiet", "left")
        git(repo, "merge", "--no-ff", "--no-edit", "-m", "join selection fixture", "right")
        merged = rev(repo, "HEAD")
        ancestry = parents(repo, merged)
        assert ancestry == (left_head, right_head)
        tree = rev(repo, f"{merged}^{{tree}}")
        reviewed = value(repo, fixture.base)
        assert all(value(repo, pin) == reviewed for pin in (left_head, right_head, merged))
        receipt = None if chosen is None else Choice(merged, tree, ancestry, ancestry[chosen], SLOT, reviewed, ISSUER)
        if mutation == "equal-tree-parent":
            # Make an alternate parent with the same tree and a distinct native commit.
            same_tree = rev(repo, f"{right_head}^{{tree}}")
            alternative = git(repo, "commit-tree", same_tree, "-p", right_head,
                              stdin=b"alternate same-tree parent\n").decode().strip()
            assert rev(repo, f"{alternative}^{{tree}}") == same_tree and alternative != right_head
            receipt = replace(receipt, parents=(left_head, alternative))
        elif mutation == "untrusted-issuer":
            receipt = replace(receipt, issuer=OTHER_ISSUER)
        elif mutation == "wrong-value":
            receipt = replace(receipt, value="0" * 64)
        with TemporaryDirectory(prefix="rt05-merge-choice-") as temporary:
            directory = Path(temporary)
            service = signature_fixture.Signatures(directory)
            private, trusted = signature_fixture.create_key(directory, ISSUER)
            signature = None
            if receipt is not None:
                signing_key, signing_authority = ((private, trusted) if receipt.issuer == ISSUER else
                                                  signature_fixture.create_key(directory, OTHER_ISSUER))
                signature = service.sign(envelope(receipt), signing_key)
                assert service.verify(envelope(receipt), signature, signing_authority)
            if mutation == "changed-choice-after-signing":
                receipt = replace(receipt, source=right_head)
                assert not service.verify(envelope(receipt), signature, trusted)
            observed = repo
            if mutation == "shallow":
                observed = directory / "clone"
                git(repo, "clone", "--quiet", "--single-branch", "--branch=left", "--depth=1",
                    repo.as_uri(), str(observed))
                assert rev(observed, "HEAD") == merged
            policies, paths = choices(observed, fixture.base, merged, reviewed, receipt, signature, service, trusted)
        assert policies["exact-choice"] == expected, (left, right, chosen, mutation, policies)
        return {"lifetimes": [left, right], "left_and_right": list(ancestry), "parent_states": paths,
                "chosen_parent": chosen, "mutation": mutation, "base": fixture.base,
                "merged_commit": merged, "merged_tree": tree,
                "reviewed_value": reviewed, "expected": expected, "policies": policies,
                "receipt": None if receipt is None else asdict(receipt),
                "signature": None if signature is None else signature.hex()}
    finally:
        fixture.doCleanups()


def run():
    c, r = "continued", "recreated"
    results = [
        experiment(c, c, 0, "eligible"),
        experiment(c, r, 0, "eligible"),
        experiment(c, r, 1, "ineligible"),
        experiment(r, c, 0, "ineligible"),
        experiment(r, c, 1, "eligible"),
        experiment(r, r, 1, "ineligible"),
        experiment(c, c, None, "unknown"),
        experiment(c, c, 0, "unknown", mutation="equal-tree-parent"),
        experiment(c, c, 0, "unknown", mutation="untrusted-issuer"),
        experiment(c, c, 0, "unknown", mutation="wrong-value"),
        experiment(c, c, 0, "unknown", mutation="changed-choice-after-signing"),
        experiment(c, c, 0, "unknown", mutation="shallow"),
    ]
    assert results[1]["merged_commit"] == results[2]["merged_commit"]
    assert results[3]["merged_commit"] == results[4]["merged_commit"]
    summaries = {}
    for policy in results[0]["policies"]:
        totals = {"excess_grants": 0, "missed_grants": 0, "unknown": 0}
        for row in results:
            actual, wanted = row["policies"][policy], row["expected"]
            totals["excess_grants"] += actual == "eligible" and wanted != "eligible"
            totals["missed_grants"] += wanted == "eligible" and actual != "eligible"
            totals["unknown"] += actual == "unknown"
        summaries[policy] = totals
    assert summaries["exact-choice"] == {"excess_grants": 0, "missed_grants": 0, "unknown": 6}
    return {"format": "rt05-multi-parent-lineage/1", "git": git(Path.cwd(), "--version").decode().strip(),
            "python": sys.version.split()[0],
            "openssl": signature_fixture.checked_openssl("version").decode().strip(),
            "summaries": summaries, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
