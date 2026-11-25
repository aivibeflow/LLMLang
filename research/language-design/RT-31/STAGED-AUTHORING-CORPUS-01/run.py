"""Check staged, syntax-neutral authoring tasks against four independent frontend adapters."""

import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "ff3e7cd2a938fbda7e67c6b43a4818a666b30e1f"
ADAPTER = HERE.parent / "HYBRID-PROFILE-01/replay.py"
sys.path.insert(0, str(ADAPTER.parent))
PROFILE = runpy.run_path(str(ADAPTER))
from profiles import FrontendError


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source(profile, values):
    return PROFILE["render"](profile, PROFILE["entry_term"](
        values["mode"], values["delta"], values["fallback"], swap=values["reverse"],
    ))


def compile_candidate(profile, body, binding):
    term = PROFILE["parse"](profile, body)
    program = PROFILE["make_program"](binding, term)
    graph = PROFILE["compile_program"](program)
    PROFILE["validate_graph"](graph)
    return graph


def oracle(values, input_word, chooses_provider):
    if not chooses_provider:
        return input_word + values["fallback"], ("fallback",)
    first, second = input_word, input_word + values["delta"]
    events = ("left", "right", "compute")
    if values["reverse"]:
        first, second = second, first
        events = ("right", "left", "compute")
    uses_primary = values["mode"] == "pin" or values["binding"] == "primary"
    result = first - second if uses_primary else 5 + (second - first)
    return result, events


def state_changes(old, current):
    before = dict(old.snapshot.selections)
    after = dict(current.snapshot.selections)
    return sorted(slot for slot in before.keys() | after.keys() if before.get(slot) != after.get(slot))


def stages(task):
    states = [task["initial"]]
    for step in task["steps"]:
        states.append(states[-1] | step["changes"])
    return states


def observes(graph, inputs):
    return [PROFILE["observe"](graph, "entry", pair) for pair in inputs]


def check(profile, task, submissions, inputs):
    targets = stages(task)
    if len(submissions) != len(task["steps"]):
        return "missing-required-stage", None
    previous = compile_candidate(profile, source(profile, targets[0]), targets[0]["binding"])
    for index, ((body, binding), state, step) in enumerate(
        zip(submissions, targets[1:], task["steps"], strict=True), start=1,
    ):
        try:
            actual = compile_candidate(profile, body, binding)
        except (FrontendError, PROFILE["RepresentationError"]):
            return "frontend-or-admission", index
        actual_rows = observes(actual, inputs)
        expected_rows = [oracle(state, *pair) for pair in inputs]
        if [pair[0] for pair in actual_rows] != [pair[0] for pair in expected_rows]:
            return "value-mismatch", index
        if actual_rows != expected_rows:
            return "trace-mismatch", index
        if state_changes(previous, actual) != step["selection_slots"]:
            return "semantic-edit-scope", index
        previous = actual
    return "accepted", None


def reference_submissions(profile, task):
    return [(source(profile, state), state["binding"]) for state in stages(task)[1:]]


def evaluate():
    data_path = HERE / "tasks.json"
    corpus = json.loads(data_path.read_text())
    assert corpus["schema"] == "rt31-staged-authoring-corpus/v1"
    inputs = tuple(product(corpus["integer_inputs"], (False, True)))
    recorded = {}
    count = 0
    for task in corpus["tasks"]:
        targets = stages(task)
        rows_by_stage = [[oracle(target, *pair) for pair in inputs] for target in targets]
        profiles = {}
        for profile in PROFILE["PROFILES"]:
            submissions = reference_submissions(profile, task)
            assert check(profile, task, submissions, inputs) == ("accepted", None)
            stage_evidence = []
            for values, rows in zip(targets, rows_by_stage, strict=True):
                rendered = source(profile, values)
                graph = compile_candidate(profile, rendered, values["binding"])
                assert observes(graph, inputs) == rows
                count += len(rows)
                stage_evidence.append({
                    "source": rendered, "selected_binding": values["binding"],
                    "graph_root": graph.snapshot.root_hash,
                })
            profiles[profile] = stage_evidence
        roots = [[entry["graph_root"] for entry in values] for values in profiles.values()]
        assert all(candidate == roots[0] for candidate in roots)
        recorded[task["id"]] = {"oracle_observations_by_stage": rows_by_stage, "profiles": profiles}

    controls = {}
    rebind, pin, effects = corpus["tasks"]
    for profile in PROFILE["PROFILES"]:
        p = reference_submissions(profile, rebind)
        q = reference_submissions(profile, pin)
        r = reference_submissions(profile, effects)
        lost_pin = stages(pin)[-1] | {"mode": "op"}
        lost_order = stages(effects)[-1] | {"reverse": False}
        rebind_step = stages(rebind)[1]
        cases = {
            "skip_required_stage": (rebind, p[1:], ("missing-required-stage", None)),
            "wrong_first_stage_correct_terminal": (rebind, [p[1], p[1]], ("value-mismatch", 1)),
            "malformed_surface": (rebind, [("", p[0][1]), p[1]], ("frontend-or-admission", 1)),
            "lost_exact_pin": (
                pin, [q[0], (source(profile, lost_pin), lost_pin["binding"])], ("value-mismatch", 2),
            ),
            "lost_order_with_equal_value": (
                effects, [r[0], (source(profile, lost_order), lost_order["binding"])], ("trace-mismatch", 2),
            ),
        }
        # A neutral source edit changes the entry's graph while preserving the selected stage's observations.
        neutral = PROFILE["entry_term"](rebind_step["mode"], rebind_step["delta"], rebind_step["fallback"])
        extra = ["add", neutral, 0]
        cases["unchanged_values_and_trace_extra_mutation"] = (
            rebind, [(PROFILE["render"](profile, extra), rebind_step["binding"]), p[1]],
            ("semantic-edit-scope", 1),
        )
        outcomes = {}
        for name, (task, submissions, expected) in cases.items():
            decision = check(profile, task, submissions, inputs)
            assert decision == expected, (profile, name, decision, expected)
            outcomes[name] = {"submitted_steps": submissions, "decision": decision}
        controls[profile] = outcomes
    assert count == 504
    return {
        "tasks_sha256": sha(data_path.read_bytes()), "inputs": inputs,
        "profile_observations": count, "task_results": recorded, "controls": controls,
    }


def main():
    relatives = (
        "research/language-design/RT-31/HYBRID-PROFILE-01/replay.py",
        "research/language-design/RT-31/HYBRID-PROFILE-01/hybrid.py",
        "research/language-design/RT-31/CROSS-PROFILE-SPG-01/run.py",
        "research/language-design/RT-31/CROSS-PROFILE-SPG-01/profiles.py",
        "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_admission.py",
        "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_representation.py",
        "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/recursive_identity.py",
        "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_graph.py",
        "research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_spg_representation.py",
    )
    pins = {}
    for path in relatives:
        archived = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT)
        assert archived == (ROOT / path).read_bytes()
        pins[path] = sha(archived)
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "source_sha256": pins, "runner_sha256": sha(Path(__file__).read_bytes()), **evaluate(),
    }, indent=2))


if __name__ == "__main__":
    main()
