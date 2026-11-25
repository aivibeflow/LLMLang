"""Exercise typed template expansion, local patches and exact migration plans."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


TEMPLATE = "template:retry-fixture"
REQUIRED_DEPENDENCY = "sha256:" + sha256(b"fixture sleep contract").hexdigest()
DEFAULT = {"attempts": 2, "backoff_ms": 100, "mode": "linear"}
FIELDS = {
    "attempts": (2, 3, 5),
    "backoff_ms": (100, 200, 400),
    "mode": ("linear", "constant", "bounded"),
}


def digest(kind, value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + sha256(kind.encode() + b"\0" + body).hexdigest()


def validate(graph):
    return (
        set(graph) == set(FIELDS)
        and type(graph["attempts"]) is int and 1 <= graph["attempts"] <= 5
        and type(graph["backoff_ms"]) is int and 1 <= graph["backoff_ms"] <= 500
        and graph["mode"] in FIELDS["mode"]
        and graph["attempts"] * graph["backoff_ms"] <= 1500
    )


def template_revision(defaults):
    return digest("retry-template", {"defaults": defaults, "requires": REQUIRED_DEPENDENCY})


def instantiate(template, defaults, params, dependency, capabilities):
    if template != template_revision(defaults) or dependency != REQUIRED_DEPENDENCY:
        return "incorrect-input-identity", None
    if "clock-sleep" not in capabilities:
        return "capability-unavailable", None
    if set(params) - set(defaults):
        return "unknown-parameter", None
    graph = defaults | params
    if not validate(graph):
        return "invalid-graph", None
    return "instantiated", {"component": "retry:fixture/instance-01",
                             "origin": [TEMPLATE, template, dependency],
                             "parameters": params, "baseline": graph,
                             "graph": graph, "detached": False, "migration_trace": []}


def edit(instance, changes):
    graph = instance["graph"] | changes
    if not validate(graph):
        return "invalid-graph", instance
    return "updated", {**instance, "graph": graph}


def detach(instance):
    return {**instance, "detached": True}


def plan(instance, defaults):
    if instance["detached"]:
        return "detached", None
    if set(defaults) != set(FIELDS):
        return "invalid-graph", None
    upstream = defaults | instance["parameters"]
    original, local = instance["baseline"], instance["graph"]
    changes = {}
    for key, wanted in upstream.items():
        if original[key] == wanted:
            continue
        if local[key] not in (original[key], wanted):
            return "conflict", None
        changes[key] = wanted
    candidate = local | changes
    if not validate(upstream) or not validate(candidate):
        return "invalid-graph", None
    return "proposed", {
        "expected_instance": digest("retry-instance", instance),
        "old_template": instance["origin"][1],
        "new_template": template_revision(defaults),
        "candidate": candidate, "new_baseline": upstream,
    }


def apply(instance, proposal, defaults):
    if proposal["expected_instance"] != digest("retry-instance", instance):
        return "stale-instance", instance
    status, verified = plan(instance, defaults)
    if status != "proposed" or proposal != verified:
        return "invalid-proposal", instance
    return "applied", {
        **instance, "baseline": proposal["new_baseline"], "graph": proposal["candidate"],
        "origin": [TEMPLATE, proposal["new_template"], REQUIRED_DEPENDENCY],
        "migration_trace": [*instance["migration_trace"], {
            "instance": proposal["expected_instance"],
            "from": proposal["old_template"], "to": proposal["new_template"],
        }],
    }


def oracle(base, local, upstream):
    conflict = any(len({base[key], local[key], upstream[key]}) == 3 for key in FIELDS)
    if conflict:
        return "conflict", None
    merged = {key: upstream[key] if base[key] == local[key] else local[key] for key in FIELDS}
    validity = max(merged["attempts"] * merged["backoff_ms"],
                   upstream["attempts"] * upstream["backoff_ms"]) <= 1500
    return ("proposed", merged) if validity else ("invalid-graph", None)


def collect():
    initial = template_revision(DEFAULT)
    label, base = instantiate(initial, DEFAULT, {}, REQUIRED_DEPENDENCY, ("clock-sleep",))
    assert label == "instantiated"
    possible = [dict(zip(FIELDS, values, strict=True)) for values in product(*FIELDS.values())]
    states = [edit(base, values)[1] for values in possible if validate(values)]
    counts = Counter()
    for instance, upstream in product(states, possible):
        before = digest("retry-instance", instance)
        status, proposal = plan(instance, upstream)
        expected, graph = oracle(DEFAULT, instance["graph"], upstream)
        assert status == expected and digest("retry-instance", instance) == before
        if proposal is not None:
            assert proposal["candidate"] == graph
            applied, updated = apply(instance, proposal, upstream)
            assert applied == "applied" and updated["graph"] == graph
            assert updated["origin"][1] == template_revision(upstream)
            assert updated["component"] == instance["component"]
            assert updated["migration_trace"][-1] == {
                "instance": before, "from": initial, "to": template_revision(upstream),
            }
        counts[status] += 1

    _, custom = instantiate(initial, DEFAULT, {"attempts": 3, "mode": "bounded"},
                            REQUIRED_DEPENDENCY, ("clock-sleep",))
    _, reordered = instantiate(initial, DEFAULT, {"mode": "bounded", "attempts": 3},
                               REQUIRED_DEPENDENCY, ("clock-sleep",))
    assert digest("retry-instance", custom) == digest("retry-instance", reordered)
    _, local = edit(base, {"attempts": 3})
    detached = detach(local)
    assert detached["origin"] == base["origin"] and detached["graph"] == local["graph"]
    next_template = DEFAULT | {"backoff_ms": 200}
    _, proposal = plan(base, next_template)
    controls = {
        "parameter_order": "same-instance-hash",
        "wrong_target_shape": plan(base, {"unmodeled-field": "unknown"})[0],
        "detached_migration": plan(detached, next_template)[0],
        "stale_instance": apply(local, proposal, next_template)[0],
        "altered_proposal": apply(base, {**proposal, "candidate": DEFAULT}, next_template)[0],
        "typed_boolean": instantiate(initial, DEFAULT, {"attempts": True},
                                     REQUIRED_DEPENDENCY, ("clock-sleep",))[0],
        "unknown_parameter": instantiate(initial, DEFAULT, {"unknown": 2},
                                         REQUIRED_DEPENDENCY, ("clock-sleep",))[0],
        "wrong_dependency": instantiate(initial, DEFAULT, {}, "different", ("clock-sleep",))[0],
        "missing_capability": instantiate(initial, DEFAULT, {}, REQUIRED_DEPENDENCY, ())[0],
    }
    assert controls == {"parameter_order": "same-instance-hash", "wrong_target_shape": "invalid-graph",
                        "detached_migration": "detached", "stale_instance": "stale-instance",
                        "altered_proposal": "invalid-proposal", "typed_boolean": "invalid-graph",
                        "unknown_parameter": "unknown-parameter",
                        "wrong_dependency": "incorrect-input-identity",
                        "missing_capability": "capability-unavailable"}
    _, retained = plan(custom, DEFAULT | {"attempts": 5, "backoff_ms": 200})
    assert retained["candidate"]["attempts"] == 3
    return {"python": platform.python_version(), "template": initial,
            "coverage": {"local_states": len(states), "upstream_profiles": len(possible)},
            "matrix": counts, "total": sum(counts.values()), "controls": controls,
            "instantiation": custom, "example_migration": retained,
            "sources_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, indent=2))
