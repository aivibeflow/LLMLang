"""Compare reuse of a fixture review along exact persisted selection histories."""
import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROTOTYPE = Path(__file__).resolve().parents[3] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.identity_lifecycle import Binding, Lineage, Relation, Slot, State, compare
from src.semantic_graph import ContentStore, digest
from tests.test_rt24_merge_tree_gate import git


PATH = "selection.json"
HOME = Slot("module", "reviewed")
OTHER = Slot("module", "independent")
CHILD = Slot("module", "child")
MOVED = Slot("new-module", "moved")


@dataclass(frozen=True)
class Receipt:
    parent: str
    commit: str
    lineage: Lineage


def bind(store, slot, entity, *, alias=None, context="surface-1", value=7):
    return Binding(slot, store.put("value", {"result": value}),
                   store.put("context", context), alias or slot.key, entity)


def read(repo, store, oid):
    values = json.loads(git(repo, "show", f"{oid}:{PATH}"))
    bindings = []
    for row in values:
        value_hash = store.put("value", row["value"])
        context_hash = store.put("context", row["context"])
        if (value_hash, context_hash) != (row["value_hash"], row["context_hash"]):
            raise ValueError("persisted selection payload does not match its address")
        bindings.append(Binding(Slot(**row["slot"]), value_hash, context_hash,
                                row["alias"], row["entity_id"]))
    return State(tuple(bindings))


def version(repo, store, *bindings):
    rows = []
    for binding in sorted(bindings, key=lambda item: item.slot):
        rows.append({**asdict(binding), "value": store.get(binding.value_hash).payload,
                     "context": store.get(binding.context_hash).payload})
    source = repo / PATH
    source.write_text(json.dumps(rows, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "--", PATH)
    git(repo, "commit", "--quiet", "--allow-empty", "-m", "selection state")
    return rev(repo, "HEAD")


def rev(repo, oid, suffix=""):
    return git(repo, "rev-parse", oid + suffix).decode().strip()


def selection(state, slot):
    return next(binding for binding in state.bindings if binding.slot == slot)


def scope(binding):
    return binding.value_hash, binding.context_hash


def relate(kind, sources, destinations):
    return Relation(kind, tuple(sources), tuple(destinations))


def continuation(before, after):
    return relate("continue", [before], [after])


def receipt(repo, store, parent, oid, relations):
    return Receipt(parent, oid, Lineage(read(repo, store, parent).revision, read(repo, store, oid).revision, tuple(relations)))


def walk(repo, store, base, target, records, *, exact):
    path = []
    pointer = target
    while pointer != base:
        line = git(repo, "rev-list", "--parents", "-n", "1", pointer).decode().split()
        if len(line) != 2:
            return None
        child, parent = line
        path.append((parent, child))
        pointer = parent
    reviewed = selection(read(repo, store, base), HOME)
    authorized = {HOME}
    witnessed = []
    for parent, child in reversed(path):
        record = records.get(child)
        if record is None:
            return None
        if exact and (record.parent, record.commit) != (parent, child):
            return None
        left, right = read(repo, store, parent), read(repo, store, child)
        try:
            compared = compare(store, left, right, "lineage", lineage=record.lineage)
        except ValueError:
            return None
        carry = set()
        for relation in compared.relations:
            if not authorized.intersection(relation.before):
                continue
            if exact and relation.kind != "continue":
                continue
            carry.update(slot for slot in relation.after
                         if not exact or scope(selection(right, slot)) == scope(reviewed))
        authorized = carry
        witnessed.append(digest(asdict(record)))
    return authorized, witnessed


def histories(repo, store):
    original = bind(store, HOME, "A")
    independent = bind(store, OTHER, "B")
    duplicate = bind(store, CHILD, "C")
    moved = bind(store, MOVED, "A")
    redefined = bind(store, HOME, "A", context="surface-2")
    new_value = bind(store, HOME, "A", value=11)
    alias = bind(store, HOME, "A", alias="better-display")
    base = version(repo, store, original, independent)
    direct_old = continuation(HOME, HOME)
    second = continuation(OTHER, OTHER)
    split = relate("split", [HOME], [HOME, CHILD])
    join = relate("merge", [HOME, CHILD], [HOME])
    collapse = relate("merge", [HOME, OTHER], [HOME])
    catalog = {
        "alias-only": (((alias, independent), (direct_old, second)),),
        "move": (((moved, independent), (continuation(HOME, MOVED), second)),),
        "independent-copy": (((original, independent, duplicate), (direct_old, second)),),
        "single-split": (((original, independent, duplicate), (split, second)),),
        "merge-reviewed-and-independent": (((original,), (collapse,)),),
        "split-and-rejoin": (((original, independent, duplicate), (split, second)),
                             ((original, independent), (join, second))),
        "delete-and-recreate": (((independent,), (second,)), ((original, independent), (second,))),
        "context-change-and-restore": (((redefined, independent), (direct_old, second)),
                                       ((original, independent), (direct_old, second))),
        "value-change": (((new_value, independent), (direct_old, second)),),
        "missing-lineage": (((moved, independent), None),),
        "wrong-parent-with-equal-selection": (((original, independent), (direct_old, second)),
                                               ((moved, independent), (continuation(HOME, MOVED), second))),
        "continued-equal-selection": (((original, independent), (direct_old, second)),),
    }
    for label, steps in catalog.items():
        git(repo, "switch", "--quiet", "-c", label, base)
        parent = base
        records = {}
        path = [base]
        for values, relations in steps:
            oid = version(repo, store, *values)
            # Equal trees can occur as real commits. The parent pin belongs to the created edge.
            if relations is not None:
                claimed_parent = base if label == "wrong-parent-with-equal-selection" and parent != base else parent
                records[oid] = receipt(repo, store, claimed_parent, oid, relations)
            parent = oid
            path.append(oid)
        yield label, base, parent, records, path


def encode_slot(slot):
    return f"{slot.scope}/{slot.key}"


def matches(repo, name, base, target, records, path):
    store = ContentStore()
    initial = read(repo, store, base)
    state = read(repo, store, target)
    reviewed = selection(initial, HOME)
    eligible = {
        "alias-only": {HOME}, "move": {MOVED}, "independent-copy": {HOME},
        "continued-equal-selection": {HOME},
    }
    values = {item.slot for item in state.bindings if scope(item) == scope(reviewed)}
    stable = {item.slot for item in state.bindings if item.entity_id == reviewed.entity_id and item.slot in values}
    reachable = walk(repo, store, base, target, records, exact=False)
    bound = walk(repo, store, base, target, records, exact=True)
    policies = {"value": values, "stable-id": stable,
                "reachable": None if reachable is None else reachable[0] & values,
                "exact-continuation": None if bound is None else bound[0] & values}
    oracle = eligible.get(name, set())
    if name in {"missing-lineage", "wrong-parent-with-equal-selection"}:
        assert policies["exact-continuation"] is None
    else:
        assert policies["exact-continuation"] == oracle, (name, policies, oracle)
    return {
        "case": name, "revisions": path, "trees": [rev(repo, oid, "^{tree}") for oid in path],
        "eligible": sorted(map(encode_slot, oracle)),
        "policies": {k: None if v is None else sorted(map(encode_slot, v)) for k, v in policies.items()},
        "receipts": {oid: asdict(item) for oid, item in records.items()},
        "verified_chain_sha256": None if bound is None else digest(bound[1]),
        "same_selection": initial.revision == state.revision,
    }


def evaluate():
    with TemporaryDirectory(prefix="rt05-composed-lineage-") as directory:
        repo = Path(directory)
        git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1")
        store = ContentStore()
        results = [matches(repo, *history) for history in histories(repo, store)]
    summaries = {}
    for name in results[0]["policies"]:
        counts = {"excess": 0, "omitted": 0, "unknown": 0}
        for row in results:
            expected = set(row["eligible"])
            actual = row["policies"][name]
            if actual is None:
                counts["unknown"] += 1
                continue
            counts["excess"] += len(set(actual) - expected)
            counts["omitted"] += len(expected - set(actual))
        summaries[name] = counts
    assert summaries["exact-continuation"] == {"excess": 0, "omitted": 0, "unknown": 2}
    return {"format": "rt05-composed-lineage/1", "git": git(Path.cwd(), "--version").decode().strip(),
            "python": sys.version.split()[0], "summary": summaries, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(evaluate(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
