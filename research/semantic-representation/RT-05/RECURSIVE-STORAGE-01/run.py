#!/usr/bin/env python3
"""Measure keyed recursive group archives without changing semantic identity."""

from itertools import product
import json
from pathlib import Path
import platform

from archive import Archive, LAYOUTS, Reader, admit, canonical_bytes, digest, encode, execute
from src.recursive_identity import Call, Definition, External, publish_definitions
from src.semantic_graph import ContentStore

HERE = Path(__file__).resolve().parent
SIZES = (8, 64, 256)
VARIANTS = ("base", "display_rename", "body_edit", "provider_edit", "slot_rotate")


def payload(index):
    token = f"event-{index:03}/"
    return token * (8 + index % 7)


def member_number(size, index, variant):
    return ((index + 1) % size) if variant == "slot_rotate" else index


def produce(store, size, variant):
    display = {index: f"member-{index:03}" for index in range(size)}
    if variant == "display_rename":
        display = {index: f"renamed-{size-index:03}" for index in range(size)}
    provider = store.put("fixture-external-v1", {"value": 99 if variant == "provider_edit" else 1})
    definitions = {}
    for index in range(size):
        out = payload(index)
        if variant == "body_edit" and index == size // 2:
            out += "#"
        tokens = [out]
        if index == size // 2:
            tokens.append(External(provider))
        tokens.append(Call(display[(index + 1) % size]))
        key = f"slot-{member_number(size, index, variant):03}"
        definitions[display[index]] = Definition(tuple(tokens), key)
    definitions["entry"] = Definition((Call(display[0]),))
    if variant == "display_rename":
        definitions = dict(reversed(tuple(definitions.items())))
    published = publish_definitions(store, definitions, "keyed")
    addresses = [published[display[index]] for index in range(size)]
    group = store.get(addresses[0]).dependencies[0].target_hash
    return group, [*addresses, published["entry"]]


def oracle(size, variant, entry, fuel):
    expected = []
    for delta in range(fuel):
        index = (entry + delta) % size
        changed = variant == "body_edit" and index == size // 2
        expected.append(payload(index) + ("#" if changed else ""))
        if index == size // 2:
            expected.append(99 if variant == "provider_edit" else 1)
    return expected


def total_bytes(blobs):
    return sum(map(len, blobs.values()))


def scope_controls(size, store, base_group, edit_group, base, edited):
    base_ticket, _ = admit(base, store, base_group)
    edit_ticket, _ = admit(edited, store, edit_group)
    fuel = size // 2 + 1
    original, _ = execute(base, base_ticket, store, 0, fuel)
    actual, _ = execute(edited, edit_ticket, store, 0, fuel)
    old_hash = Reader(base).index["bodies"][0]
    new_hash = Reader(edited).index["bodies"][0]
    assert old_hash == new_hash and original != actual and base_group != edit_group

    try:
        execute(edited, base_ticket, store, 0, fuel)
    except ValueError:
        pass
    else:
        raise AssertionError("A stale admission was accepted for a different physical archive root")

    mixed = Reader(base).index
    mixed["bodies"][size//2] = Reader(edited).index["bodies"][size//2]
    root = canonical_bytes(mixed)
    mixed_archive = Archive(digest(root), {**base.blobs, **edited.blobs, digest(root): root})
    before = store.hashes()
    try:
        admit(mixed_archive, store, base_group)
    except ValueError as error:
        assert str(error) == "The archive does not reconstruct the selected semantic group"
    else:
        raise AssertionError("A mixed group was accepted under the old pinned semantic address")
    assert store.hashes() == before

    missing = Archive(base.root, {key: blob for key, blob in base.blobs.items() if key != old_hash})
    try:
        admit(missing, store, base_group)
    except KeyError:
        pass
    else:
        raise AssertionError("Incomplete archive accepted")
    return {"size": size, "entry_body_digest": old_hash, "fuel": fuel,
            "old_observation_sha256": digest(canonical_bytes(original)),
            "new_observation_sha256": digest(canonical_bytes(actual)),
            "stale_admission": "refused", "mixed_group": "refused", "missing_body": "refused"}


def run():
    groups = []
    checks = 0
    controls = []
    for size in SIZES:
        store = ContentStore()
        published = {version: produce(store, size, version) for version in VARIANTS}
        archives = {(variant, profile): encode(store.get(group), profile)
                    for variant, (group, _) in published.items() for profile in LAYOUTS}
        base_group, base_addresses = published["base"]
        assert published["display_rename"] == published["base"]

        for variant, (group, addresses) in published.items():
            rows = {}
            for profile in LAYOUTS:
                original = archives[("base", profile)]
                archive = archives[(variant, profile)]
                admission, cold = admit(archive, store, group)
                assert cold == total_bytes(archive.blobs)
                read_cost = {}
                for entry, fuel in product((0, size // 2, size - 1), (1, 4, size + 1)):
                    trace, read = execute(
                        archive, admission, store, member_number(size, entry, variant), fuel
                    )
                    assert trace == oracle(size, variant, entry, fuel)
                    checks += 1
                    read_cost[f"entry{entry}/fuel{fuel}"] = read
                rows[profile] = {
                    "root": archive.root, "full_admission_bytes": cold, "stored_objects": len(archive.blobs),
                    "new_bytes": total_bytes({key: blob for key, blob in archive.blobs.items()
                                              if key not in original.blobs}),
                    "post_admission_read_bytes": read_cost,
                }
            changed = sum(first != second for first, second in zip(base_addresses, addresses, strict=True))
            assert changed == (0 if variant in {"base", "display_rename"} else size + 1)
            groups.append({"size": size, "variant": variant, "semantic_group": group,
                           "changed_semantic_addresses": changed, "layouts": rows})
        controls.append(scope_controls(
            size, store, base_group, published["body_edit"][0],
            archives[("base", "flat")], archives[("body_edit", "flat")],
        ))
    return {
        "schema": "llmlang-recursive-group-storage/1", "python": platform.python_version(),
        "source_sha256": {name: digest((HERE / name).read_bytes()) for name in ("archive.py", "run.py")},
        "store_source_sha256": {name: digest((HERE.parents[2] / "PROTOTYPES" /
            "DEPENDENCY-GRAPH-01" / "src" / name).read_bytes())
            for name in ("recursive_identity.py", "semantic_graph.py")},
        "restored_group_layouts": len(groups) * len(LAYOUTS), "oracle_comparisons": checks,
        "groups": groups, "controls": controls,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
