"""Check independent source ownership for a task's pinned context references."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


PRODUCERS = {
    "requirement": "RT-02",
    "target-object": "RT-05",
    "dependency-inventory": "RT-06",
    "knowledge-context": "RT-14",
    "baseline": "RT-19",
    "change-set": "RT-19",
    "impact-plan": "RT-20",
}


@dataclass(frozen=True)
class Record:
    producer: str
    kind: str
    baseline: str
    scope: str
    payload: tuple[str, ...]

    @property
    def identity(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class Grant:
    principal: str
    operation: str
    scope: str
    generation: int


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bind(task, facts):
    references = task["references"]
    if set(references) != set(PRODUCERS):
        return False
    for kind, address in references.items():
        record = facts.get(address)
        if record is None or (record.identity, record.producer, record.kind) != (address, PRODUCERS[kind], kind):
            return False
        if (record.baseline, record.scope) != (task["baseline"], task["scope"]):
            return False
    return True


def permitted(task, facts, grant):
    return bind(task, facts) and grant == Grant(task["principal"], "apply", task["scope"], 4)


def run():
    baseline, scope = "fixture:snapshot-a", "fixture:scope-a"
    original = {kind: Record(producer, kind, baseline, scope, (f"exact:{kind}",))
                for kind, producer in PRODUCERS.items()}
    task = {"id": "task:fixture", "revision": 3, "principal": "worker:fixture",
            "baseline": baseline, "scope": scope,
            "references": {kind: record.identity for kind, record in original.items()}}
    grant = Grant(task["principal"], "apply", scope, 4)
    counts = Counter()
    for states in product(("exact", "changed", "missing"), repeat=len(PRODUCERS)):
        view = {}
        for (kind, record), state in zip(original.items(), states, strict=True):
            if state == "exact":
                view[task["references"][kind]] = record
            elif state == "changed":
                view[task["references"][kind]] = replace(record, payload=("changed",))
        expected = states == ("exact",) * len(PRODUCERS)
        assert bind(task, view) == expected
        assert permitted(task, view, grant) == expected
        assert not permitted(task, view, None)
        counts["exact" if expected else "unresolved"] += 1
    inventory = {record.identity: record for record in original.values()}
    stale_context = replace(original["knowledge-context"], baseline="fixture:snapshot-b")
    wrong_context = {**task, "references": {**task["references"],
                                             "knowledge-context": stale_context.identity}}
    unrelated_before = digest(task)
    assert not bind(wrong_context, {**inventory, stale_context.identity: stale_context})
    assert not permitted(task, inventory, replace(grant, operation="inspect"))
    assert not permitted(task, inventory, replace(grant, generation=3))
    assert bind(task, inventory) and digest(task) == unrelated_before
    return {"python": platform.python_version(), "profiles": counts, "references": PRODUCERS,
            "task_identity": unrelated_before,
            "controls": {"other_knowledge_baseline": "refused", "no_write_grant": "refused",
                         "old_policy_grant": "refused", "pins_do_not_modify_producer_state": "checked"},
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
