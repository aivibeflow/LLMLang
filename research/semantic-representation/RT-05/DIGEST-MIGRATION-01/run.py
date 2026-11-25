"""Replay migration, policy rejection and exact identity controls."""

from hashlib import sha256
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
BASELINE = "2a780731513f21c0028bf43e94bfae9d37041ac5"
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import digest
from migration import Store, StoreError, check_alias, envelope, rewrite, structure


def fixture(store):
    def put(kind, payload, dependencies=()):
        return store.put(envelope(kind, payload, dependencies), "sha256")

    contract = put("contract", {"postcondition": "returns the requested state"})
    operation = put("operation", {"profile": "sequential"}, [("contract", contract)])
    implementation = put("implementation", {"body": "reference"}, [("operation", operation)])
    conformance_class = put("conformance-class", {"target": "cpu"}, [("operation", operation)])
    group = put("recursive-group", {"members": [{"next": 1}, {"next": 0}]},
                [("linked-operation", operation)])
    left = put("caller", {"entry": 0}, [("group", group), ("direct-provider", implementation)])
    right = put("caller", {"entry": 1}, [("group", group), ("required-class", conformance_class)])
    root = put("snapshot", {}, [("left", left), ("right", right)])
    subject = {"operation": operation, "implementation": implementation, "class": conformance_class}
    return root, subject


def run():
    old_suite, new_suite = {"sha256"}, {"sha512"}
    mixed_suites = old_suite | new_suite
    store = Store()
    root, subject = fixture(store)
    physical_original, original_names = structure(store, root, old_suite)
    dispositions = []

    def control(name, outcome, operation):
        try:
            operation()
        except StoreError as error:
            assert str(error) == outcome, (name, str(error), outcome)
        else:
            assert outcome == "accepted", name
        dispositions.append({"case": name, "outcome": outcome})

    aliases = {old: store.put(store.read(old, old_suite), "sha512") for old in sorted(original_names)}
    for old, new in aliases.items():
        control("identical bytes alias " + old, "accepted", lambda: check_alias(store, old, new))

    dual_root = aliases[root]
    assert structure(store, dual_root, mixed_suites)[0] == physical_original
    control("dual locator on a new-suite-only reader", "unsupported suite",
            lambda: structure(store, dual_root, new_suite))
    control("missing or incomplete alias", "missing address",
            lambda: check_alias(store, root, "sha512:" + "1" * 128))
    control("alias points at another verified payload", "alias payload differs",
            lambda: check_alias(store, root, aliases[subject["operation"]]))
    control("reverse alias supplied as forward", "unsupported alias direction",
            lambda: check_alias(store, dual_root, root))
    overwritten = store.blobs[dual_root]
    store.blobs[dual_root] = b"corrupt test bytes"
    control("cached bytes fail their declared digest", "digest mismatch",
            lambda: check_alias(store, root, dual_root))
    store.blobs[dual_root] = overwritten

    changed_root, rewritten = rewrite(store, root)
    rewritten_structure, rewritten_names = structure(store, changed_root, new_suite)
    assert rewritten_structure == physical_original
    assert rewrite(store, root) == (changed_root, rewritten)
    control("rewritten graph on a new-suite-only reader", "accepted",
            lambda: structure(store, changed_root, new_suite))
    control("rewritten graph on a legacy-only reader", "unsupported suite",
            lambda: structure(store, changed_root, old_suite))
    missing_child = rewritten[subject["operation"]]
    removed = store.blobs.pop(missing_child)
    control("partial rewrite is ineligible for publication", "missing address",
            lambda: structure(store, changed_root, new_suite))
    control("legacy snapshot remains readable after interrupted staging", "accepted",
            lambda: structure(store, root, old_suite))
    store.blobs[missing_child] = removed

    actual_receipt = digest({"domain": "rt05-exact-conformance-receipt", "subject": subject, "tool": "v1"})
    migrated_subject = {role: rewritten[name] for role, name in subject.items()}
    expected_receipt = digest({"domain": "rt05-exact-conformance-receipt", "subject": migrated_subject, "tool": "v1"})
    assert actual_receipt != expected_receipt
    assert all(check_alias(store, old, aliases[old]) is None for old in subject.values())

    collision = Store()
    weak = {"fixture-collision"}
    original = envelope("operation", {"version": 1})
    distinct = envelope("operation", {"version": 2})
    ambiguous = collision.put(original, "fixture-collision")
    assert collision.put(original, "fixture-collision") == ambiguous
    control("synthetic equal digest with distinct typed bytes", "collision",
            lambda: collision.put(distinct, "fixture-collision"))
    assert collision.blobs[ambiguous] == original
    control("read of quarantined name", "quarantined", lambda: collision.read(ambiguous, weak))
    control("retry cannot overwrite quarantined original", "quarantined",
            lambda: collision.put(original, "fixture-collision"))

    def byte_total(names, suites):
        return sum(len(store.read(name, suites)) for name in names)

    paths = [HERE / "run.py", HERE / "migration.py", PROTOTYPE / "src" / "semantic_graph.py"]
    return {
        "schema": "rt05-digest-migration-comparison-v1", "baseline": BASELINE,
        "python": platform.python_version(),
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
        "root_addresses": {"historical": root, "dual": dual_root, "rewritten": changed_root},
        "original_graph": {"objects": len(original_names), "bytes": byte_total(original_names, old_suite)},
        "rewritten_graph": {"objects": len(rewritten_names), "bytes": byte_total(rewritten_names, new_suite)},
        "dual_distinct_payloads": len({store.read(name, mixed_suites) for name in set(aliases) | set(aliases.values())}),
        "rewritten_distinct_payloads": len({store.read(name, mixed_suites) for name in set(rewritten) | set(rewritten.values())}),
        "alias_addresses": aliases, "rewrite_addresses": rewritten,
        "receipt": {"old_exact_binding": actual_receipt, "new_exact_binding": expected_receipt,
                    "old_subject": subject, "rewritten_subject": migrated_subject},
        "controls": dispositions,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
