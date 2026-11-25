#!/usr/bin/env python3
"""Test exact calls through catalogue lifecycle changes."""

from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))
from src.semantic_graph import ContentStore

OLD = "operation-01"
NEW = "operation-02"
NAME = "package.lookup"
RENAMED = "package.lookupRenamed"


@dataclass(frozen=True)
class Lifetime:
    name: str
    operation: str
    state: str = "active"
    replaces: str | None = None


class Catalog:
    def __init__(self, store):
        self.store = store
        self.current = {}
        self.published = set()

    def publish(self, stable_id, name, operation, *, replaces_id=None):
        if operation not in self.store or stable_id in self.current or self.named(name) is not None:
            return False
        if (replaces_id is not None
                and (replaces_id not in self.current or self.current[replaces_id].state != "retired")):
            return False
        self.current[stable_id] = Lifetime(name, operation, replaces=replaces_id)
        self.published.add((stable_id, operation))
        return True

    def rename(self, stable_id, name):
        item = self.current[stable_id]
        if item.state == "retired" or self.named(name) not in (None, stable_id):
            return False
        self.current[stable_id] = replace(item, name=name)
        return True

    def revise(self, stable_id, operation):
        item = self.current[stable_id]
        if item.state == "retired" or operation not in self.store:
            return False
        self.current[stable_id] = replace(item, operation=operation)
        self.published.add((stable_id, operation))
        return True

    def lifecycle(self, stable_id, action):
        item = self.current[stable_id]
        transitions = {
            ("active", "deprecate"): "deprecated",
            ("deprecated", "reactivate"): "active",
            ("deprecated", "retire"): "retired",
        }
        candidate = transitions.get((item.state, action))
        if candidate is None:
            return False
        self.current[stable_id] = replace(item, state=candidate)
        return True

    def named(self, name):
        return next((stable for stable, item in self.current.items()
                     if item.name == name and item.state != "retired"), None)

    def selection(self, stable_id):
        item = self.current.get(stable_id)
        if item is None or item.state == "retired":
            return None
        return stable_id, item.operation

    def exact(self, pin, allow_retired):
        owner, operation = pin
        if pin not in self.published or operation not in self.store:
            return None
        if self.current[owner].state == "retired" and not allow_retired:
            return None
        return pin

    def current_by_value(self, address):
        return next((self.selection(owner) for owner, item in self.current.items()
                     if item.operation == address and item.state != "retired"), None)


def require(accepted):
    if not accepted:
        raise AssertionError("Expected an allowed fixture transition")


def history(store, v1, v2, v3, renamed, revised, same_body, archive_policy):
    catalog = Catalog(store)
    pin = OLD, v1
    checkpoints = []
    live_alias = RENAMED if renamed else NAME

    def record(label, *, expected_old_name, retired=False):
        actual = {
            "exact": catalog.exact(pin, archive_policy),
            "latest_stable_id": catalog.selection(OLD),
            "original_alias": catalog.selection(catalog.named(NAME)),
            "selected_equal_value": catalog.current_by_value(v1),
        }
        expected = None if retired and not archive_policy else pin
        if (actual["exact"] != expected or catalog.named(NAME) != expected_old_name
                or (not retired and label != "initial" and catalog.named(live_alias) != OLD)):
            raise AssertionError(f"Exact binding or original alias changed incorrectly at {label}")
        checkpoints.append({
            "label": label,
            "original_state": catalog.current[OLD].state,
            "original_alias_owner": expected_old_name,
            "expected_exact": expected, "compared_resolutions": actual,
        })

    require(catalog.publish(OLD, NAME, v1))
    record("initial", expected_old_name=OLD)
    require(catalog.rename(OLD, live_alias))
    expected_alias_owner = None if renamed else OLD
    record("renamed or unchanged", expected_old_name=expected_alias_owner)
    require(catalog.lifecycle(OLD, "deprecate"))
    record("deprecated", expected_old_name=expected_alias_owner)
    require(catalog.lifecycle(OLD, "reactivate"))
    record("reactivated", expected_old_name=expected_alias_owner)
    require(catalog.revise(OLD, v2 if revised else v1))
    record("revised or unchanged", expected_old_name=expected_alias_owner)
    require(catalog.lifecycle(OLD, "deprecate"))
    require(catalog.lifecycle(OLD, "retire"))
    record("retired", expected_old_name=None, retired=True)
    actual_refusals = {
        "reactivate_retired": catalog.lifecycle(OLD, "reactivate"),
        "revise_retired": catalog.revise(OLD, v1),
        "publish_retired_id": catalog.publish(OLD, NAME, v1),
    }
    if any(actual_refusals.values()):
        raise AssertionError("Retired lifetime could be reused")
    require(catalog.publish(NEW, NAME, v1 if same_body else v3, replaces_id=OLD))
    record("replacement at original alias", expected_old_name=NEW, retired=True)
    if catalog.current[NEW].replaces != OLD or catalog.exact((NEW, v2), archive_policy) is not None:
        raise AssertionError("Replacement relation was confused with an exact publication")
    return {
        "renamed": renamed, "revised": revised, "replacement_uses_original_value": same_body,
        "archived_execution_allowed": archive_policy,
        "known_historical_pairs": sorted(catalog.published),
        "lifecycle_refusals": list(actual_refusals),
        "original_value_retrievable": store.get(v1).value_hash == v1,
        "checkpoints": checkpoints,
    }


def results():
    store = ContentStore()
    values = [store.put("rt05-operation-fixture/1", {"input": "nat", "output": f"x+{n}"})
              for n in (1, 2, 3)]
    histories = [history(store, *values, *profile) for profile in product((False, True), repeat=4)]
    counts = {
        policy: {"wrong_exact_target": 0, "unexpected_denial": 0, "unexpected_execution": 0}
        for policy in histories[0]["checkpoints"][0]["compared_resolutions"]
    }
    for item in histories:
        for row in item["checkpoints"]:
            expected = row["expected_exact"]
            for policy, actual in row["compared_resolutions"].items():
                if actual == expected:
                    continue
                field = ("unexpected_execution" if expected is None else
                         "unexpected_denial" if actual is None else "wrong_exact_target")
                counts[policy][field] += 1
    return {
        "schema": "llmlang-operation-lifetime/1", "python": platform.python_version(),
        "source_sha256": {
            "runner": sha256(Path(__file__).read_bytes()).hexdigest(),
            "semantic_graph": sha256((PROTOTYPE / "src" / "semantic_graph.py").read_bytes()).hexdigest(),
        },
        "values": values, "histories": histories, "resolution_comparison": counts,
        "queries": sum(len(history["checkpoints"]) for history in histories),
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
