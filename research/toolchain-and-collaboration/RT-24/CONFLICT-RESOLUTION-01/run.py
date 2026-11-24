"""Compare exact and scoped replay of a typed merge conflict resolution."""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_dependency_index import publish_declaration
from src.semantic_graph import canonical_bytes, digest
from tests import test_rt24_merge_tree_gate as source
from tests import test_rt24_semantic_merge_core as merge


POLICY = "rt24-conflict-resolution-fixture/1"
SLOT = "callee"


@dataclass(frozen=True)
class Inputs:
    commits: tuple
    inventories: tuple
    conflict: merge.Conflict
    physical: tuple
    roots: tuple
    affected_reads: tuple
    mappings: tuple


@dataclass(frozen=True)
class Decision:
    conflict: merge.Conflict
    choice: str
    inputs: str
    history: str
    roots: str
    affected: str


def read(repo, commits):
    inventories = tuple(source.read_inventory(repo, commit) for commit in commits)
    result = merge.merge_inventories(*inventories)
    if result.status != "slot-conflict" or len(result.conflicts) != 1:
        raise AssertionError(("expected one local merge conflict", result))
    conflict, = result.conflicts
    if conflict.kind != "update-update" or conflict.slot != SLOT:
        raise AssertionError(("unexpected conflict", conflict))
    targets = (conflict.base, conflict.ours, conflict.theirs)
    audits = []
    mappings = []
    for inventory in inventories:
        store, snapshot = source.import_closed(inventory)
        observations = []
        for target in targets:
            # The fixture contract declares the selected inventory complete. Absence of
            # a target in this closed source also proves no caller can pin that target.
            if target not in store:
                observations.append((target, "absent"))
                continue
            evidence = source.source_evidence(inventory, store, snapshot, target)
            query = source.checked_source_query(inventory, store, snapshot, evidence)
            if query.completeness_status is not source.CompletenessStatus.SUPPORTED_WITHIN_SCOPE:
                raise AssertionError(("incomplete exact source evidence", target))
            observations.append((target, query.edge_set_digest))
        audits.append(tuple(observations))
        mappings.append(snapshot.mapping)
    return Inputs(commits, inventories, conflict, tuple(tuple(row[:2]) for row in result.inputs),
                  tuple(row[2] for row in result.inputs), tuple(audits), tuple(mappings))


def issue(inputs):
    return Decision(inputs.conflict, inputs.conflict.ours,
                    digest((POLICY, "tree-inventory", inputs.physical)),
                    digest((POLICY, "ordered-commit-inputs", inputs.commits, inputs.physical)),
                    digest((POLICY, "whole-semantics", inputs.roots)),
                    digest((POLICY, "local-exact-incoming", inputs.affected_reads)))


def admission(decision, inputs):
    current = issue(inputs)
    slot = decision.conflict == current.conflict
    return {"slot_only": slot, "scoped_exact_incoming": slot and decision.affected == current.affected,
            "whole_semantics": slot and decision.roots == current.roots,
            "exact_ordered_inputs": slot and decision.inputs == current.inputs,
            "exact_ordered_history": slot and decision.history == current.history}


def resolved(inputs, decision):
    candidates = {}
    rows = {}
    for slot in sorted(set().union(*(set(mapping) for mapping in inputs.mappings))):
        original, ours, theirs = (mapping.get(slot) for mapping in inputs.mappings)
        address, conflict = merge.resolve_slot(slot, original, ours, theirs)
        if conflict is not None:
            if conflict != decision.conflict or decision.choice not in (conflict.ours, conflict.theirs):
                raise AssertionError("No authorized choice for a second merge conflict")
            address = decision.choice
        if address is None:
            continue
        candidates[slot] = address
        inventory = next(item for item, mapping in zip(inputs.inventories, inputs.mappings, strict=True)
                         if mapping.get(slot) == address)
        rows[slot] = inventory.declarations[slot]

    try:
        store, built = source.import_closed(source.Inventory("", "", rows))
    except source.GraphImportError as exc:
        return {"status": "unclosed", "finding": str(exc)}
    if built.mapping != candidates:
        raise AssertionError("Reconstructed candidate changes selected exact values")
    dependent_calls = {}
    for slot, address in built.selections:
        values = store.get(address).payload.get("call_sites", ())
        if values:
            dependent_calls[slot] = tuple((site["call_site_id"], row["target_hash"], row["condition"])
                                          for site in values for row in site["targets"])
    exported = canonical_bytes([source.row(slot, row) for slot, row in sorted(rows.items())])
    return {"status": "closed", "root": built.root_hash, "selected": built.mapping,
            "export_digest": digest(exported.decode()), "calls": dependent_calls}


def history(fixture):
    repo = fixture.repo
    value_right = {**fixture.old, "content": {"offset": 3}}
    independent = source.declaration("function", "function:independent", references=[{
        "reference_id": "provides", "relation": "provides_contract", "target_hash": fixture.contract_hash,
        "target_kind": "contract",
    }])

    def branch(name, start):
        source.git(repo, "switch", "--quiet", "-c", name, start)

    branch("with-independent", fixture.base)
    base = source.commit(repo, {source.CALLEE: [source.row(SLOT, fixture.old),
                                               source.row("independent", independent)]})
    store, state = source.import_closed(source.read_inventory(repo, base))
    right_hash = publish_declaration(store, value_right)
    independent_hash = state.mapping["independent"]

    def branch_provider(name, value, *, retain=False):
        branch(name, base)
        rows = [source.row(SLOT, value), source.row("independent", independent)]
        if retain:
            rows.append(source.row("version-right", value_right))
        return source.commit(repo, {source.CALLEE: rows})

    ours = branch_provider("ours", fixture.new, retain=True)
    no_retention = branch_provider("no-retention", fixture.new)
    theirs = branch_provider("theirs", value_right)

    def caller(target, condition):
        return {**fixture.caller, "call_sites": [{"call_site_id": "invoke",
                 "targets": [{"target_id": "direct", "target_hash": target,
                              "required_contract_hash": fixture.contract_hash, "condition": condition}]}]}

    branch("new-same-tree-commit", theirs)
    source.git(repo, "commit", "--quiet", "--allow-empty", "-m", "new history with preserved tree")
    equal_tree = source.git(repo, "rev-parse", "HEAD").decode().strip()
    branch("ordinary-edit", theirs)
    notes = source.commit(repo, {"notes.txt": "uncorrelated ordinary file\n"})
    branch("additional-dependent", theirs)
    dependent = source.commit(repo, {source.CALLER: [source.row("caller", caller(right_hash, "new-branch"))]})
    branch("independent-caller", theirs)
    unrelated = source.commit(repo, {
        source.CALLER: [source.row("other-caller", caller(independent_hash, "unrelated"))],
    })
    branch("weakened-guard", dependent)
    guard = source.commit(repo, {source.CALLER: [source.row("caller", caller(right_hash, "wider"))]})
    return {"reviewed": (base, ours, theirs), "ordinary_edit": (base, ours, notes),
            "same_tree_new_commit": (base, ours, equal_tree),
            "new_affected_caller": (base, ours, dependent),
            "new_unrelated_caller": (base, ours, unrelated),
            "affected_guard_change": (base, ours, guard),
            "dependent_and_removed_retention": (base, no_retention, dependent),
            "swapped_roles": (base, theirs, ours)}


def verify():
    fixture = source.MergeTreeGateExperiment()
    try:
        fixture.setUp()
        commits = history(fixture)
        inputs = {name: read(fixture.repo, revisions) for name, revisions in commits.items()}
        decision = issue(inputs["reviewed"])
        guarded = issue(inputs["new_affected_caller"])
        cases = {}
        expected = {
            "reviewed": (True, True, True, True, True, "closed"),
            "same_tree_new_commit": (True, True, True, True, False, "closed"),
            "ordinary_edit": (True, True, True, False, False, "closed"),
            "new_affected_caller": (True, False, False, False, False, "closed"),
            "new_unrelated_caller": (True, True, False, False, False, "closed"),
            "affected_guard_change": (True, False, False, False, False, "closed"),
            "dependent_and_removed_retention": (True, False, False, False, False, "unclosed"),
        }
        for name, candidate in inputs.items():
            evidence = guarded if name == "affected_guard_change" else decision
            admitted = admission(evidence, candidate)
            build = resolved(candidate, evidence) if admitted["slot_only"] else None
            if name == "swapped_roles":
                if any(admitted.values()):
                    raise AssertionError("Role-swapped conflict admits an old decision")
            elif (*admitted.values(), build["status"]) != expected[name]:
                raise AssertionError((name, admitted, build))
            cases[name] = {"commits": commits[name], "exact_inputs": candidate.physical,
                           "root_inputs": candidate.roots, "conflict": asdict(candidate.conflict),
                           "affected_reads": candidate.affected_reads, "old_decision": asdict(evidence),
                           "admitted": admitted, "attempted_rebuild": build}
        if cases["reviewed"]["attempted_rebuild"]["root"] == cases["new_affected_caller"]["attempted_rebuild"]["root"]:
            raise AssertionError("The new dependent caller must survive in the closed candidate")
        return {"format": POLICY, "git": source.git(fixture.repo, "--version").decode().strip(),
                "python": sys.version.split()[0], "cases": cases}
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
