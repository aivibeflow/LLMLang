"""Check a fixture-only scoped response and exact resolution contract."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


@dataclass(frozen=True)
class Key:
    tenant: str
    workspace: str
    snapshot: str
    visibility: str
    projection: str


@dataclass(frozen=True)
class Row:
    tenant: str
    workspace: str
    package: str
    artifact: str
    fields: frozenset[str]


CURRENT = Key("tenant-a", "workspace-a", "current", "visibility-2", "projection-2")
ALLOWED_PACKAGES = frozenset(("core", "review"))
SELECTED = {"core": "digest-a", "review": "digest-b"}
FIELD_VALUES = {"name": "fixture", "description": "fixture purpose"}


def project(ready, authority, selected, row):
    if (ready != authority or (row.tenant, row.workspace) != (authority.tenant, authority.workspace)
            or selected.get(row.package) != row.artifact):
        return None
    return {key: value for key, value in FIELD_VALUES.items() if key in row.fields}


def resolve(current, evidence_key, expected, decisions):
    if evidence_key != current or decisions.keys() != expected:
        return "pending"
    if "unknown" in decisions.values():
        return "pending"
    eligible = [artifact for artifact, status in decisions.items() if status == "compatible"]
    if len(eligible) == 1:
        return "bound"
    return "ambiguous" if eligible else "no-match"


def response_cases():
    responses = []
    for tenant, workspace, package, selected, generation, fields in product(
        ("tenant-a", "tenant-b"), ("workspace-a", "workspace-b"),
        ("core", "review", "other"), (True, False),
        ("exact", "old-snapshot", "old-policy", "old-projection"),
        ((), ("name",), ("description",), ("name", "description")),
    ):
        ready = {
            "exact": CURRENT,
            "old-snapshot": Key("tenant-a", "workspace-a", "old", "visibility-2", "projection-2"),
            "old-policy": Key("tenant-a", "workspace-a", "current", "visibility-1", "projection-2"),
            "old-projection": Key("tenant-a", "workspace-a", "current", "visibility-2", "projection-1"),
        }[generation]
        artifact = SELECTED.get(package, "digest-c") if selected else "other-digest"
        row = Row(tenant, workspace, package, artifact, frozenset(fields))
        actual = project(ready, CURRENT, SELECTED, row)
        valid = (tenant, workspace, selected, generation) == ("tenant-a", "workspace-a", True, "exact")
        expected = {name: FIELD_VALUES[name] for name in fields} if valid and package in ALLOWED_PACKAGES else None
        assert actual == expected
        responses.append([tenant, workspace, package, selected, generation, fields, actual])
    return responses


def decision_cases():
    states = ("excluded", "unknown", "compatible")
    oracle = (
        ("no-match", "pending", "bound"),
        ("pending", "pending", "pending"),
        ("bound", "pending", "ambiguous"),
    )
    exact = {"high", "low"}
    outcomes = []
    for first, second, coverage, field_order, evidence in product(
        range(3), range(3), ("all", "first", "second", "empty", "extra"),
        (("high", "low"), ("low", "high")), ("current", "old"),
    ):
        observed = {
            "all": exact, "first": {"high"}, "second": {"low"},
            "empty": set(), "extra": exact | {"unselected"},
        }[coverage]
        states_by_artifact = {"high": states[first], "low": states[second], "unselected": "compatible"}
        ordered = (*field_order, "unselected")
        decisions = {artifact: states_by_artifact[artifact] for artifact in ordered if artifact in observed}
        actual = resolve("current", evidence, exact, decisions)
        expected = oracle[first][second] if coverage == "all" and evidence == "current" else "pending"
        assert actual == expected
        outcomes.append([states[first], states[second], coverage, field_order, evidence, actual])
    return outcomes


def run():
    responses = response_cases()
    decisions = decision_cases()
    return {
        "python": platform.python_version(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "response_scopes": dict(Counter("refused" if row[-1] is None else "admitted" for row in responses)),
        "decision_counts": dict(Counter(row[-1] for row in decisions)),
        "responses": responses,
        "decisions": decisions,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
