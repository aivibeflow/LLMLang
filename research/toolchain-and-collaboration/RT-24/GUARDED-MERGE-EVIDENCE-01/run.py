"""Check state-bound provider evidence after a native Git merge."""
import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_dependency_index import publish_declaration
from src.semantic_graph import ContentStore
from tests import test_candidate_semantic_diff_cip_v2 as declare
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt24_merge_tree_gate as tree

CONTRACT, OPERATIONS, SELECTOR, PROVIDERS = (
    "program/contract.json", "program/operations.json", "program/selector.json", "program/providers.json",
)
STATE = tuple(range(4))
EXPECTED = (10, 20, 30, 40)
CASES = {
    "invalid-composition": (0, "right", "unknown", "invalid"),
    "valid-but-uncovered": (1, "right", "unknown", "valid"),
    "valid-covered": (2, "left", "covered", "valid"),
}


@dataclass(frozen=True)
class Observation:
    state: int
    provider: str
    operation: str
    implementation: str
    contract: str
    value: int

    @property
    def exact_subject(self):
        return self.state, self.operation, self.implementation, self.contract


def fixture_rows():
    store = ContentStore()
    contract = declare.declaration("contract", "contract:output-by-state",
                                   {"expected": EXPECTED})
    required = publish_declaration(store, contract)
    provides = {"reference_id": "provides", "relation": "provides_contract", "target_hash": required,
                "target_kind": "contract", "condition": None}
    operation_defs = {
        name: declare.declaration("operation", f"operation:{name}", {"public": name},
                                  references=(provides,))
        for name in ("left", "right")
    }
    targets = {key: publish_declaration(store, value) for key, value in operation_defs.items()}

    def selector(mapping):
        call_sites = tuple(declare.call_site(f"select-{state}", targets[name], required, f"state={state}")
                           for state, name in enumerate(mapping))
        return [tree.row("selector", declare.declaration(
            "function", "function:select", {"states": STATE}, call_sites=call_sites,
        ))]

    def providers(right):
        return [tree.row(f"implementation-{name}", declare.declaration(
            "function", f"implementation:{name}", {"operation": targets[name], "table": values},
            references=(provides,),
        )) for name, values in (("left", EXPECTED), ("right", right))]

    return [tree.row("contract", contract)], [tree.row(name, value) for name, value in operation_defs.items()], selector, providers


def merged(repo, moved_state, selection):
    tree.git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
    contract, operations, selector, providers = fixture_rows()
    original = ["left", "left", "right", "right"]
    base = tree.commit(repo, {
        tree.MANIFEST: tree.manifest(CONTRACT, OPERATIONS, SELECTOR, PROVIDERS),
        CONTRACT: contract, OPERATIONS: operations, SELECTOR: selector(original), PROVIDERS: providers(EXPECTED),
    })
    ours = tree.commit(repo, {PROVIDERS: providers((99, 20, 30, 40))})
    tree.git(repo, "switch", "--quiet", "-c", "routing", base)
    revised = original.copy()
    revised[moved_state] = selection
    theirs = tree.commit(repo, {SELECTOR: selector(revised)})
    tree.git(repo, "switch", "--quiet", "--detach", ours)
    tree.git(repo, "merge", "--quiet", "--no-ff", "--no-edit", theirs)
    candidate = recovery.ref(repo, "HEAD")
    assert tree.git(repo, "show", "-s", "--format=%P", candidate).decode().split() == [ours, theirs]
    return {"base": base, "provider": ours, "routing": theirs, "merge": candidate}


def observe(repo, pin):
    inventory = tree.read_inventory(repo, pin)
    _, snapshot = tree.import_closed(inventory)
    slots = snapshot.mapping
    source = inventory.declarations
    selectors = source["selector"]["call_sites"]
    assert len(selectors) == len(STATE)
    observed = []
    for state, site in zip(STATE, selectors, strict=True):
        target, = site["targets"]
        assert site["call_site_id"] == f"select-{state}"
        assert target["condition"] == f"state={state}" and target["required_contract_hash"] == slots["contract"]
        name, = (name for name in ("left", "right") if slots[name] == target["target_hash"])
        implementation = f"implementation-{name}"
        payload = source[implementation]["content"]
        assert payload["operation"] == target["target_hash"]
        expected = source["contract"]["content"]["expected"]
        assert tuple(expected) == EXPECTED
        observed.append(Observation(state, name, target["target_hash"], slots[implementation], slots["contract"],
                                    payload["table"][state]))
    return inventory, snapshot, observed


def validates(rows):
    return all(row.value == EXPECTED[row.state] for row in rows)


def trial(directory, label, moved_state, selection, wanted, independent):
    repo = directory / "repo"
    repo.mkdir(parents=True)
    pins = merged(repo, moved_state, selection)
    states = {name: observe(repo, pin) for name, pin in pins.items()}
    baseline = states["base"][2]
    provider = states["provider"][2]
    routing = states["routing"][2]
    candidate = states["merge"][2]
    assert all(validates(rows) for rows in (baseline, provider, routing))
    assert all({row.provider for row in state[2]} == {"left", "right"} for state in states.values())

    # Each recorded row is produced by observing its own checked branch.
    certified = {row.exact_subject for row in provider + routing if row.value == EXPECTED[row.state]}
    coarse = {subject[1:] for subject in certified}
    assert all(row.exact_subject[1:] in coarse for row in candidate)
    missing = [row.state for row in candidate if row.exact_subject not in certified]
    projection = "unknown" if missing else "covered"
    fresh = "valid" if validates(candidate) else "invalid"
    assert (projection, fresh) == (wanted, independent)
    if projection == "covered":
        assert fresh == "valid"

    inventory, snapshot, _ = states["merge"]
    plan = recovery.Prepared("guarded-merge", inventory.tree, snapshot.root_hash,
                             (pins["provider"], pins["routing"]), pins["merge"])
    published = {"outcome": "blocked", "receipt": None}
    if projection == "covered" or fresh == "valid":
        outcome = recovery.publish(repo, plan)
        assert outcome == recovery.publish(repo, plan) == "published"
        evidence = "composed" if projection == "covered" else "fresh"
        published = {"outcome": outcome, "receipt": recovery.ref(repo, plan.receipt), "admitted_by": evidence}
        clone = directory / "clone"
        tree.git(directory, "clone", "--quiet", "--no-local", str(repo), str(clone))
        tree.git(clone, "fsck", "--full")
        _, imported, observations = observe(clone, pins["merge"])
        assert imported.root_hash == states["merge"][1].root_hash and observations == candidate
    else:
        assert recovery.ref(repo, recovery.BRANCH) == pins["provider"]
        assert recovery.ref(repo, plan.receipt) is None
    tree.git(repo, "fsck", "--full")
    return {
        "label": label, "moved_state": moved_state, "snapshots": {
            name: {"commit": pins[name], "tree": inventory.tree, "root": snapshot.root_hash,
                   "observations": [asdict(row) for row in rows]}
            for name, (inventory, snapshot, rows) in states.items()
        },
        "provider_only_receipts": "covered", "state_bound_receipts": projection,
        "missing_states": missing, "fresh_validation": fresh, "publication_and_retry": published,
    }


def run(directory):
    version = tree.git(directory, "--version").decode().strip()
    assert version == "git version 2.52.0"
    return {
        "format": "rt24-guarded-merge-evidence/1", "python": sys.version.split()[0], "git": version,
        "cases": {name: trial(directory / name, name, *values) for name, values in CASES.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-guarded-merge-evidence-") as scratch:
        data = run(Path(scratch))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
