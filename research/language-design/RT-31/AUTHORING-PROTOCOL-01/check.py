"""Validate a counterbalanced RT-31 study plan without running a live model."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "STAGED-AUTHORING-CORPUS-01"
TASK_PIN = "8b2783753b0d140f7e1a14fe64a1ae068a343e9dd136795f3dac7b23dd8e78c9"
ORACLE_PIN = "9acf2f4749c1abd60158e6271657cb68edf03c9f7edf6b4e738f8c50d019e5fc"
PROFILES = ("infix/1", "s-expression/1", "json-tree/1", "hybrid/1")

CONFIG = {
    "mode": "synthetic-plan-only",
    "model_provider": "fixture-provider",
    "model_identity": "fixture-model-revision",
    "model_settings": {"temperature": 0, "max_output_tokens": 400, "tool_selection": "fixture"},
    "instruction_digest": "fixture-instructions:1",
    "toolchain_digest": "fixture-toolchain:1",
    "environment_digest": "fixture-environment:1",
    "initial_context_digest": "fixture-read-scope:1",
    "maximum_repair_attempts": 1,
}


def read(name, pinned):
    raw = (CORPUS / name).read_bytes()
    assert sha256(raw).hexdigest() == pinned
    return json.loads(raw)


def identity(record):
    return sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sequence(offset):
    return [PROFILES[(offset + position) % len(PROFILES)] for position in (0, 1, 3, 2)]


def collect():
    corpus = read("tasks.json", TASK_PIN)
    oracle = read("evidence.json", ORACLE_PIN)
    assert oracle["tasks_sha256"] == TASK_PIN
    assert oracle["profile_observations"] == 504
    controls = [item["decision"][0] for profile in oracle["controls"].values() for item in profile.values()]
    assert len(controls) == 24 and set(controls) == {
        "missing-required-stage", "value-mismatch", "frontend-or-admission", "trace-mismatch", "semantic-edit-scope"
    }
    task_ids = [task["id"] for task in corpus["tasks"]]
    assert len(task_ids) == 3 and all(len(task["steps"]) == 2 for task in corpus["tasks"])
    assert set(task_ids) == set(oracle["task_results"])
    orders = [sequence(offset) for offset in range(len(PROFILES))]
    positions = Counter((profile, order.index(profile)) for order in orders for profile in order)
    transitions = Counter(pair for order in orders for pair in zip(order, order[1:]))
    assert len(positions) == 16 and set(positions.values()) == {1}
    assert len(transitions) == 12 and set(transitions.values()) == {1}

    plan = []
    for task, seed, order in product(task_ids, (17, 29), orders):
        block = {**CONFIG, "task": task, "seed": seed, "corpus": TASK_PIN, "oracle": ORACLE_PIN,
                 "profile_order": order}
        for ordinal, profile in enumerate(order):
            row = {**block, "profile": profile, "ordinal": ordinal}
            plan.append({"assignment": row, "id": identity(row)})
    assert len(plan) == len({row["id"] for row in plan}) == 96
    first = plan[0]["assignment"]
    for field in first:
        assert identity({**first, field: "changed"}) != plan[0]["id"]
    return {"python": platform.python_version(), "mode": CONFIG["mode"], "profile_orders": orders,
            "tasks": task_ids, "historical_oracle_observations": oracle["profile_observations"],
            "historical_negative_controls": len(controls), "assignments": len(plan), "assignment_digest": identity(plan),
            "example_assigned_request": plan[0], "input_pins": [TASK_PIN, ORACLE_PIN],
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, indent=2))
