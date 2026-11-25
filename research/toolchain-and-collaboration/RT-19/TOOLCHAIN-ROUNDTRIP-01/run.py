"""Replay a public Toolchain lifecycle with an independent bounded domain validator."""
import argparse
from dataclasses import dataclass
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
TOOLCHAIN = HERE.parents[1] / "PROTOTYPES" / "TOOLCHAIN-SERVER-01"
sys.path.insert(0, str(TOOLCHAIN))
from toolchain import (Change, InMemoryToolchain, InvalidSnapshot, NotFound,
                       SemanticConflict, StaleObject, StaleRevision)

VALIDATOR = "integer-offset-v1"
BASE = {
    "contract:offset": ("contract", {"increment": 0}),
    "implementation:offset": ("implementation", {"increment": 0}),
    "note:legacy": ("note", {"text": "старое описание"}),
}


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def digest(raw):
    return "sha256:" + sha256(raw).hexdigest()


def document(entities, order):
    entries = []
    for stable_id in order:
        kind, payload = entities[stable_id]
        body = {"kind": kind, "payload": payload}
        entries.append({"stable_id": stable_id, **body, "content_hash": digest(encode(body))})
    mapping = {item["stable_id"]: item["content_hash"] for item in entries}
    root = digest(encode({"format_version": 1, "entities": mapping}))
    return {"format_version": 1, "snapshot_root": root, "entities": entries}


def write_input(path, order, compact):
    baseline = document(BASE, order)
    data = encode(baseline) if compact else json.dumps(baseline, ensure_ascii=False, indent=2).encode()
    path.write_bytes(data + b"\n")
    return baseline["snapshot_root"]


@dataclass(frozen=True)
class Validation:
    workspace: str
    revision: int
    root: str
    profile: str


def validate(toolchain, view):
    spec = toolchain.get_entity(view.working_snapshot, "contract:offset")
    body = toolchain.get_entity(view.working_snapshot, "implementation:offset")
    if spec.kind != "contract" or body.kind != "implementation":
        return None
    if set(spec.payload) != {"increment"} or set(body.payload) != {"increment"}:
        return None
    required, provided = spec.payload["increment"], body.payload["increment"]
    if type(required) is not int or type(provided) is not int:
        return None
    witnesses = range(-4, 5)
    if any(value + provided != value + required for value in witnesses):
        return None
    return Validation(view.workspace_id, view.revision, view.working_snapshot, VALIDATOR)


def accept(toolchain, validation):
    observed = toolchain.get_workspace(validation.workspace)
    if (observed.revision, observed.working_snapshot, validation.profile) != (
        validation.revision, validation.root, VALIDATOR,
    ):
        raise StaleRevision("validation does not describe the current candidate")
    actual = toolchain.accept(validation.workspace, validation.revision)
    assert actual == validation.root
    return actual


def make_changes(toolchain, view, required, provided):
    existing = lambda name: toolchain.get_entity(view.working_snapshot, name).content_hash
    return (
        Change("update", "contract:offset", existing("contract:offset"),
               "contract", {"increment": required}),
        Change("update", "implementation:offset", existing("implementation:offset"),
               "implementation", {"increment": provided}),
        Change("remove", "note:legacy", existing("note:legacy")),
        Change("add", "export:offset", None, "export", {"name": "смещение"}),
    )


def apply(toolchain, view, changes):
    proposal = toolchain.propose(view.workspace_id, view.revision, list(changes))
    candidate = toolchain.apply(proposal, view.revision)
    current = toolchain.get_workspace(view.workspace_id)
    assert current.working_snapshot == candidate and current.revision == view.revision + 1
    return current


def expect_error(kind, action):
    try:
        action()
    except kind:
        return
    raise AssertionError(f"expected {kind.__name__}")


def expected_export(current, offset):
    expected = {
        "contract:offset": ("contract", {"increment": offset}),
        "implementation:offset": ("implementation", {"increment": offset}),
        "export:offset": ("export", {"name": "смещение"}),
    }
    expected_document = document(expected, sorted(expected))
    assert expected_document["snapshot_root"] == current
    return encode(expected_document) + b"\n"


def roundtrip(directory, seed, order, permutation, compact):
    path = directory / "repository.json"
    return_path = directory / "roundtrip.json"
    baseline = write_input(path, order, compact)
    external_hash = digest(path.read_bytes())
    toolchain = InMemoryToolchain()
    imported = toolchain.import_snapshot(path)
    assert imported == baseline
    workspace = toolchain.open_workspace(baseline)
    proposed = make_changes(toolchain, workspace, seed, seed)
    current = apply(toolchain, workspace, (proposed[i] for i in permutation))
    approval = validate(toolchain, current)
    assert approval is not None
    expected = expected_export(current.working_snapshot, seed)

    accepted_root = accept(toolchain, approval)
    assert toolchain.get_workspace(current.workspace_id).state == "accepted"
    exported = toolchain.export_snapshot(accepted_root, path, external_hash)
    assert exported == digest(expected)
    assert path.read_bytes() == expected

    clean = InMemoryToolchain()
    imported = clean.import_snapshot(path)
    assert imported == accepted_root
    reimported = clean.open_workspace(accepted_root)
    approval = validate(clean, reimported)
    assert approval is not None
    reaccepted = accept(clean, approval)
    assert reaccepted == accepted_root
    exported = clean.export_snapshot(accepted_root, return_path)
    assert exported == digest(expected)
    assert return_path.read_bytes() == path.read_bytes()
    expect_error(NotFound, lambda: clean.get_entity(accepted_root, "note:legacy"))
    assert toolchain.get_entity(baseline, "note:legacy").payload == BASE["note:legacy"][1]
    return {"root": accepted_root, "file": digest(expected)}


def controls(directory):
    path = directory / "input.json"
    destination = directory / "output.json"
    base = write_input(path, sorted(BASE), True)
    toolchain = InMemoryToolchain()
    imported = toolchain.import_snapshot(path)
    assert imported == base
    workspace = toolchain.open_workspace(base)
    invalid = apply(toolchain, workspace, make_changes(toolchain, workspace, 1, 2))
    assert validate(toolchain, invalid) is None
    expect_error(SemanticConflict, lambda: toolchain.export_snapshot(invalid.working_snapshot, destination))
    assert not destination.exists()
    # This control exercises the direct lifecycle call, outside the validation adapter.
    accepted_without_validation = toolchain.accept(invalid.workspace_id, invalid.revision)
    assert accepted_without_validation == invalid.working_snapshot
    toolchain.export_snapshot(accepted_without_validation, destination)

    workspace = toolchain.open_workspace(base)
    malformed = apply(toolchain, workspace, make_changes(toolchain, workspace, True, True))
    assert validate(toolchain, malformed) is None

    workspace = toolchain.open_workspace(base)
    candidate = apply(toolchain, workspace, make_changes(toolchain, workspace, 3, 3))
    approval = validate(toolchain, candidate)
    assert approval is not None
    materialized = toolchain.get_entity(candidate.working_snapshot, "export:offset")
    revised = apply(toolchain, candidate, [Change(
        "update", materialized.stable_id, materialized.content_hash, materialized.kind,
        {"name": "переименование"},
    )])
    expect_error(StaleRevision, lambda: accept(toolchain, approval))
    assert revised.working_snapshot != candidate.working_snapshot
    assert toolchain.get_workspace(revised.workspace_id).state == "open"
    fresh = validate(toolchain, revised)
    assert fresh is not None
    accepted = accept(toolchain, fresh)
    stale_file = digest(destination.read_bytes())
    destination.write_bytes(b"external edit\n")
    expect_error(StaleObject, lambda: toolchain.export_snapshot(accepted, destination, stale_file))
    assert destination.read_bytes() == b"external edit\n"
    expected = expected_export(candidate.working_snapshot, 3)
    damaged = json.loads(expected)
    damaged["entities"][0]["payload"]["increment"] = 99
    path.write_bytes(encode(damaged))
    expect_error(InvalidSnapshot, lambda: InMemoryToolchain().import_snapshot(path))
    return {
        "semantic_failure": "adapter refuses; unaccepted export is blocked",
        "malformed_domain_value": "Boolean offsets are refused",
        "direct_accept_control": "lifecycle API accepts the invalid candidate without an adapter",
        "stale_validation": "refused after metadata-only revision; fresh validation succeeds",
        "external_edit": "refused and bytes preserved",
        "tampered_entity_import": "refused",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    results = []
    with TemporaryDirectory(prefix="llmlang-toolchain-roundtrip-") as temporary:
        root = Path(temporary)
        live = root / "cases"
        live.mkdir()
        for seed in (-3, 1, 4):
            outcome = None
            repetitions = 0
            for order in permutations(BASE):
                for change_order in permutations(range(4)):
                    for compact in (False, True):
                        observed = roundtrip(live, seed, order, change_order, compact)
                        if outcome is None:
                            outcome = observed
                        assert observed == outcome
                        repetitions += 1
                        for path in live.iterdir():
                            path.unlink()
            assert repetitions == 288
            results.append({"increment": seed, "replays": repetitions, **outcome})
        negative = controls(root)
    payload = {"successful_roundtrips": sum(row["replays"] for row in results),
               "traces": results, "controls": negative}
    args.output.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
