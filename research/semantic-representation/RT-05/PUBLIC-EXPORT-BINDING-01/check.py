"""Check scoped public names and independently typed native call bindings."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "42254e9209aa525330c3fcaeb64959237878e72e"
RT05 = "research/semantic-representation/RT-05"
RT04 = "research/language-design/RT-04"


@dataclass(frozen=True)
class Export:
    namespace: str
    catalog: str
    logical: str
    operation: str


@dataclass(frozen=True)
class Binding:
    scope: str
    operation: str
    provider: str
    abi: str


CURRENT = Export("pkg.protocol", "revision-2", "logical-read", "op-v2")
OLD = replace(CURRENT, catalog="revision-1", operation="op-v1")
REFERENCE = Binding("linux-scope", "op-v2", "provider-a", "sysv")


def resolve_name(exports, qualified, scope, catalog):
    entry = exports.get(qualified)
    if entry is None or (entry.namespace, entry.catalog) != (scope, catalog):
        return None
    return entry.operation


def scope_checks():
    exported = {
        "pkg.protocol.read": CURRENT, "pkg.protocol.get": CURRENT,
        "pkg.protocol.legacy": OLD, "unrelated.protocol.read": replace(CURRENT, namespace="unrelated.protocol"),
    }
    expected_by_name = {
        "pkg.protocol.read": ("pkg.protocol", "revision-2", "op-v2"),
        "pkg.protocol.get": ("pkg.protocol", "revision-2", "op-v2"),
        "pkg.protocol.legacy": ("pkg.protocol", "revision-1", "op-v1"),
        "unrelated.protocol.read": ("unrelated.protocol", "revision-2", "op-v2"),
        "pkg.protocol.missing": (None, None, None),
    }
    counts = Counter()
    for name, scope, catalog in product(expected_by_name, ("pkg.protocol", "unrelated.protocol"),
                                        ("revision-1", "revision-2")):
        expected_scope, expected_catalog, expected_op = expected_by_name[name]
        expected = expected_op if (scope, catalog) == (expected_scope, expected_catalog) else None
        assert resolve_name(exported, name, scope, catalog) == expected
        counts["exact" if expected else "absent"] += 1
    return dict(counts)


def admit_call(mode, selected, scoped, direct_provider, abi):
    if not scoped:
        return "pending"
    if mode == "direct":
        return "bound" if direct_provider == REFERENCE.provider else "pending"
    if selected is None or (selected.scope, selected.operation) != (REFERENCE.scope, REFERENCE.operation):
        return "pending"
    if mode == "foreign" and selected.abi != abi:
        return "pending"
    return "bound"


def binding_checks():
    choices = {
        "exact": REFERENCE, "absent": None, "old": replace(REFERENCE, operation="op-v1"),
        "cross-scope": replace(REFERENCE, scope="other"),
        "swapped-abi": replace(REFERENCE, abi="ms"),
    }
    counts = {mode: Counter() for mode in ("direct", "operation", "foreign")}
    for mode, choice, scoped, direct_provider in product(
        counts, choices, (True, False), ("provider-a", "provider-b"),
    ):
        independent_clear = {
            "direct": direct_provider == "provider-a",
            "operation": choice in {"exact", "swapped-abi"},
            "foreign": choice == "exact",
        }
        expected = "bound" if scoped and independent_clear[mode] else "pending"
        actual = admit_call(mode, choices[choice], scoped, direct_provider, "sysv")
        assert actual == expected
        counts[mode][actual] += 1
    return counts


def archives():
    paths = (
        f"{RT05}/IMPORT-RESOLUTION-01/evidence.json",
        f"{RT05}/CANDIDATE-ENVELOPES-01/evidence.json",
        f"{RT05}/NATIVE-IMPLEMENTATION-IDENTITY-01/evidence.json",
        f"{RT04}/MODULAR-OPERATION-SUBSTITUTION-01/evidence.json",
    )
    return {path: sha256(subprocess.check_output(["git", "show", f"{BASE}:{path}"])).hexdigest()
            for path in paths}


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_ledgers": archives(), "scope": scope_checks(), "bindings": binding_checks(),
    }, sort_keys=True, indent=2))
