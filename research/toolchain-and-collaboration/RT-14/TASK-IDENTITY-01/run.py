"""Verify exact Task Context declarations and immutable revision lineage."""
import argparse
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import sqlite3

VERSION = 1
DIGEST = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"[a-z][a-z0-9:-]*")
BINDINGS = ("requirements", "prerequisites")
SETS = ("in_scope", "out_of_scope", "constraints", "non_goals", "assumptions", "deliverables")
REQUIRED_NONEMPTY = {"in_scope", "deliverables"}


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def digest(value):
    return sha256(encode(value).encode()).hexdigest()


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError("invalid stable label")
    return value


def exact_digest(value):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError("invalid exact reference")
    return value


def unique_set(values, convert):
    if not isinstance(values, list):
        raise ValueError("expected list")
    checked = [convert(value) for value in values]
    if len(set(checked)) != len(checked):
        raise ValueError("duplicate entry")
    return sorted(checked)


def binding(value):
    if not isinstance(value, dict) or value.keys() != {"id", "revision"}:
        raise ValueError("expected exact reference")
    return name(value["id"]), exact_digest(value["revision"])


def criterion(value):
    if not isinstance(value, dict) or value.keys() != {"deliverable", "check"}:
        raise ValueError("invalid acceptance criterion")
    return name(value["deliverable"]), name(value["check"])


def normalize(value):
    if not isinstance(value, dict) or value.keys() != {
        "objective", *BINDINGS, *SETS, "acceptance_criteria",
    }:
        raise ValueError("unknown or missing declaration field")
    objective = value["objective"]
    if not isinstance(objective, dict) or objective.keys() != {"verb", "target"}:
        raise ValueError("invalid objective")
    result = {"objective": {key: name(item) for key, item in objective.items()}}
    for field in BINDINGS:
        references = unique_set(value[field], binding)
        if len({key for key, _ in references}) != len(references):
            raise ValueError("competing revisions for one reference")
        result[field] = references
    for field in SETS:
        result[field] = unique_set(value[field], name)
    if any(not result[field] for field in REQUIRED_NONEMPTY) or not result["requirements"]:
        raise ValueError("missing mandatory declaration item")
    if set(result["in_scope"]) & set(result["out_of_scope"]):
        raise ValueError("overlapping scope")
    if result["objective"]["target"] not in result["in_scope"]:
        raise ValueError("objective target is outside scope")
    result["acceptance_criteria"] = unique_set(value["acceptance_criteria"], criterion)
    if {deliverable for deliverable, _ in result["acceptance_criteria"]} != set(result["deliverables"]):
        raise ValueError("deliverables and acceptance criteria differ")
    return result


def declaration():
    return {
        "objective": {"verb": "update", "target": "impl:quota"},
        "requirements": [{"id": "limit", "revision": "1" * 64},
                         {"id": "error-shape", "revision": "2" * 64}],
        "in_scope": ["impl:quota", "test:quota"],
        "out_of_scope": ["runtime", "storage"],
        "constraints": ["no-side-effects", "preserve-error"],
        "non_goals": ["optimization", "rewrite-callers"],
        "assumptions": ["linux", "integer-limit"],
        "prerequisites": [{"id": "review-model", "revision": "3" * 64},
                          {"id": "confirm-scope", "revision": "4" * 64}],
        "deliverables": ["implementation", "test"],
        "acceptance_criteria": [{"deliverable": "implementation", "check": "rebuild"},
                                {"deliverable": "test", "check": "boundaries-pass"}],
    }


def revised_id(task_id, previous, canonical):
    return digest(["task-revision", VERSION, name(task_id), previous, canonical])


def create(store):
    store.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE revisions (
            task TEXT NOT NULL, id TEXT NOT NULL, parent TEXT, declaration TEXT NOT NULL,
            PRIMARY KEY (task, id),
            FOREIGN KEY (task, parent) REFERENCES revisions(task, id)
        );
        CREATE TABLE heads (
            task TEXT PRIMARY KEY, id TEXT NOT NULL,
            FOREIGN KEY (task, id) REFERENCES revisions(task, id)
        );
        CREATE TABLE receipts (
            task TEXT NOT NULL, revision TEXT NOT NULL, result TEXT NOT NULL,
            PRIMARY KEY (task, revision),
            FOREIGN KEY (task, revision) REFERENCES revisions(task, id)
        );
        CREATE TABLE presentation (
            task TEXT PRIMARY KEY REFERENCES heads(task), title TEXT NOT NULL
        );
    """)


def move(store, task_id, previous, source):
    if previous is not None:
        exact_digest(previous)
    canonical = normalize(source)
    revision = revised_id(task_id, previous, canonical)
    serialized = encode(canonical)
    with store:
        store.execute("BEGIN IMMEDIATE")
        active = store.execute("SELECT id FROM heads WHERE task = ?", (task_id,)).fetchone()
        head = active[0] if active else None
        if active and head == revision:
            return "retry", revision
        if head != previous:
            return "stale", head
        if head:
            (existing,) = store.execute("SELECT declaration FROM revisions WHERE task = ? AND id = ?",
                                        (task_id, head)).fetchone()
            if existing == serialized:
                return "unchanged", head
        store.execute("INSERT INTO revisions VALUES (?, ?, ?, ?)",
                      (task_id, revision, previous, serialized))
        if active:
            updated = store.execute("UPDATE heads SET id = ? WHERE task = ? AND id = ?",
                                    (revision, task_id, previous))
            assert updated.rowcount == 1
        else:
            store.execute("INSERT INTO heads VALUES (?, ?)", (task_id, revision))
        return "created", revision


def exact_fields(changes, baseline):
    value = deepcopy(baseline)
    value.update(changes)
    return value


def active_result(store, task_id):
    row = store.execute("""
        SELECT receipts.result FROM heads
        JOIN receipts ON receipts.task = heads.task AND receipts.revision = heads.id
        WHERE heads.task = ?
    """, (task_id,)).fetchone()
    return row[0] if row else "pending"


def check():
    original = declaration()
    canonical = normalize(original)
    list_fields = (*BINDINGS, *SETS, "acceptance_criteria")
    orders = 0
    for toggles in product((False, True), repeat=len(list_fields)):
        candidate = {key: list(reversed(original[key])) for key, reverse in zip(list_fields, toggles) if reverse}
        assert normalize(exact_fields(candidate, original)) == canonical
        orders += 1
    for variant in (dict(reversed(tuple(original.items()))), dict(sorted(original.items()))):
        assert encode(normalize(variant)) == encode(canonical)
        orders += 1

    mutations = {
        "objective": {"verb": "prove", "target": "impl:quota"},
        "requirements": [{"id": "limit", "revision": "a" * 64}],
        "in_scope": ["impl:quota"],
        "out_of_scope": ["storage"],
        "constraints": ["alternative"],
        "non_goals": ["optional"],
        "assumptions": ["other-platform"],
        "prerequisites": [{"id": "review-model", "revision": "b" * 64}],
        "deliverables": ["implementation"],
        "acceptance_criteria": [{"deliverable": "implementation", "check": "rebuild"},
                                {"deliverable": "test", "check": "different-suite"}],
    }
    changes = {}
    for field, value in mutations.items():
        patch = {field: value}
        if field == "deliverables":
            patch["acceptance_criteria"] = original["acceptance_criteria"][:1]
        mutated = normalize(exact_fields(patch, original))
        assert mutated != canonical
        changes[field] = digest(mutated)
    assert len(set(changes.values())) == len(changes)

    rejected = {}
    for case, patch in {
        "extra-field": {"title": "outside-declaration"},
        "overlap": {"out_of_scope": ["impl:quota"]},
        "wrong-goal-target": {"objective": {"verb": "update", "target": "unrelated"}},
        "duplicate-item": {"deliverables": ["implementation", "implementation"]},
        "conflicting-prerequisites": {"prerequisites": [{"id": "review-model", "revision": "1" * 64},
                                                       {"id": "review-model", "revision": "2" * 64}]},
        "unknown-reference-revision": {"requirements": [{"id": "limit", "revision": "latest"}]},
        "qualifying-orphan": {"acceptance_criteria": [{"deliverable": "archive", "check": "rebuild"}]},
        "empty-approval": {"acceptance_criteria": []},
    }.items():
        try:
            normalize(exact_fields(patch, original))
        except ValueError as error:
            rejected[case] = str(error)
        else:
            raise AssertionError(case)

    proposal = exact_fields({"objective": mutations["objective"]}, original)
    alternative = exact_fields({"constraints": mutations["constraints"]}, original)
    with closing(sqlite3.connect(":memory:")) as store:
        create(store)
        created, root = move(store, "task-a", None, original)
        assert created == "created"
        with store:
            store.execute("INSERT INTO receipts VALUES (?, ?, ?)", ("task-a", root, "accepted"))
            store.execute("INSERT INTO presentation VALUES (?, ?)", ("task-a", "Quota correction"))
        assert active_result(store, "task-a") == "accepted"
        with store:
            store.execute("UPDATE presentation SET title = ? WHERE task = ?", ("Correct the quota", "task-a"))
        assert store.execute("SELECT id FROM heads WHERE task = 'task-a'").fetchone() == (root,)
        assert active_result(store, "task-a") == "accepted"
        assert move(store, "task-a", None, original) == ("retry", root)
        assert move(store, "task-a", root, original) == ("unchanged", root)
        created, next_revision = move(store, "task-a", root, proposal)
        assert created == "created" and next_revision != root
        assert active_result(store, "task-a") == "pending"
        assert move(store, "task-a", root, alternative) == ("stale", next_revision)
        assert move(store, "task-a", root, proposal) == ("retry", next_revision)
        created, rollback = move(store, "task-a", next_revision, original)
        assert created == "created" and rollback not in {next_revision, root}
        assert move(store, "task-a", root, proposal) == ("stale", rollback)
        created, other_task = move(store, "task-b", None, original)
        assert created == "created" and other_task not in {root, rollback}
        receipt_cases = {"restored-content": active_result(store, "task-a"),
                         "other-task": active_result(store, "task-b")}
        assert set(receipt_cases.values()) == {"pending"}
        with store:
            store.execute("INSERT INTO receipts VALUES (?, ?, ?)", ("task-a", rollback, "accepted"))
        receipt_cases["new-revision-with-exact-receipt"] = active_result(store, "task-a")
        assert receipt_cases["new-revision-with-exact-receipt"] == "accepted"
        entries = store.execute("SELECT task, id, parent, declaration FROM revisions ORDER BY task, id").fetchall()
        assert len(entries) == 4
        historical = {revision: digest(json.loads(record)) for _, revision, _, record in entries}
        assert historical[root] == historical[rollback] == historical[other_task]

    return {
        "sqlite": sqlite3.sqlite_version, "equivalent_input_orders": orders,
        "changed_declaration_digests": changes, "refusals": rejected,
        "display_title_preserved_head_and_receipt": True,
        "receipt_controls": receipt_cases,
        "history": {"root": root, "changed": next_revision, "restored_content": rollback,
                    "other_task": other_task, "declaration_digests": historical},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.parse_args().output.write_text(json.dumps(check(), sort_keys=True, indent=2) + "\n")
