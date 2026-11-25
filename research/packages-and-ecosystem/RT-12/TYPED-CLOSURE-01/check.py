"""Compare target-edge policies for an exact-hash transitive package closure."""

from collections import Counter, deque
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform


NAMES = ("entry", "common", "linux", "windows", "trace", "support", "evidence")
OBJS = {name: sha256(("fixture object " + name).encode()).hexdigest() for name in NAMES}
REPLACEMENT = sha256(b"new leaf also called linux").hexdigest()
POLICIES = ("roots-only", "required", "with-optional")
GATES = ("target-metadata", "target-active")


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str
    target_guard: str | None = None
    feature_guard: str | None = None


EDGES = (
    Edge("entry", "common", "required"),
    Edge("entry", "linux", "target", target_guard="linux"),
    Edge("entry", "windows", "target", target_guard="windows"),
    Edge("entry", "trace", "optional", feature_guard="trace"),
    Edge("entry", "evidence", "evidence"),
    Edge("common", "support", "required"),
    Edge("linux", "common", "required"),
    Edge("windows", "common", "required"),
    Edge("trace", "common", "required"),
    Edge("support", "entry", "required"),
)


def follows(edge, policy, gate):
    return policy in ("required", "with-optional") and (
        edge.kind == "required"
        or edge.kind == "optional" and policy == "with-optional"
        or edge.kind == "target" and gate == "target-active"
    )


def active(edge, target, features):
    if edge.target_guard is not None and target is None:
        return None
    if edge.feature_guard is not None and features is None:
        return None
    return ((edge.target_guard is None or edge.target_guard == target)
            and (edge.feature_guard is None or edge.feature_guard in features))


def resolve(roots, store, policy, gate, target, features):
    queue = deque(roots)
    included = set()
    missing = set()
    unknown = set()
    while queue:
        digest = queue.popleft()
        if digest in included or digest in missing:
            continue
        if digest not in store:
            missing.add(digest)
            continue
        included.add(digest)
        for edge in EDGES:
            if OBJS[edge.source] != digest or not follows(edge, policy, gate):
                continue
            selected = active(edge, target, features)
            if selected is None:
                unknown.add((digest, OBJS[edge.target]))
            elif selected:
                queue.append(OBJS[edge.target])
    if unknown:
        return "unknown-condition", (), ()
    if missing:
        return "missing-exact-object", (), ()
    observations = tuple(sorted(
        (OBJS[edge.source], OBJS[edge.target], edge.kind, OBJS[edge.target] in included)
        for edge in EDGES if OBJS[edge.source] in included
    ))
    return "exact", tuple(sorted(included)), observations


def independent(roots, store, policy, gate, target, features):
    assert OBJS["entry"] in roots and OBJS["entry"] in store
    closure = set(roots)
    if policy != "roots-only":
        closure.update((OBJS["common"], OBJS["support"]))
        if gate == "target-active":
            if target is None:
                return "unknown-condition", set()
            closure.add(OBJS[target])
        if policy == "with-optional":
            if features is None:
                return "unknown-condition", set()
            if "trace" in features:
                closure.add(OBJS["trace"])
    return ("exact", closure) if closure <= store else ("missing-exact-object", set())


def collect():
    counts = Counter()
    differences = Counter()
    all_hashes = set(OBJS.values())
    requested = [(OBJS["entry"],), (OBJS["entry"], OBJS["evidence"])]
    optional_absence = [(), *((name,) for name in NAMES if name not in ("entry", "common")),
                        *combinations(("linux", "windows", "trace", "support"), 2)]
    for policy, roots, missing, target, features in product(
        POLICIES, requested, optional_absence, ("linux", "windows", None), ((), ("trace",), None)
    ):
        store = (all_hashes - {OBJS[name] for name in missing}) | {REPLACEMENT}
        observed = {}
        for gate in GATES:
            status, ids, edges = resolve(roots, store, policy, gate, target, features)
            assert (status, set(ids)) == independent(roots, store, policy, gate, target, features)
            assert all(src in ids and included == (dst in ids) for src, dst, _, included in edges)
            assert REPLACEMENT not in ids
            counts[f"{gate}/{policy}/{status}"] += 1
            observed[gate] = (status, ids)
        if observed[GATES[0]] != observed[GATES[1]]:
            differences[policy] += 1
    controls = {
        "absent-root": resolve(requested[0], all_hashes - {OBJS["entry"]},
                               "roots-only", "target-active", None, None)[0],
        "active-linux-with-exact-object": resolve(requested[0], all_hashes, "required", "target-active",
                                                 "linux", ())[0],
        "active-linux-with-same-name-replacement": resolve(requested[0],
            (all_hashes - {OBJS["linux"]}) | {REPLACEMENT}, "required", "target-active", "linux", ())[0],
        "inactive-windows-missing": resolve(requested[0],
            all_hashes - {OBJS["windows"]}, "required", "target-active", "linux", ())[0],
        "unsupported-target-fact": resolve(requested[0], all_hashes, "required", "target-active", None, ())[0],
        "roots-only-without-condition-facts": resolve(requested[0], all_hashes, "roots-only",
                                                      "target-active", None, None)[0],
    }
    assert controls == {"absent-root": "missing-exact-object", "active-linux-with-exact-object": "exact",
                        "active-linux-with-same-name-replacement": "missing-exact-object",
                        "inactive-windows-missing": "exact", "unsupported-target-fact": "unknown-condition",
                        "roots-only-without-condition-facts": "exact"}
    return {"python": platform.python_version(), "objects": OBJS, "replacement": REPLACEMENT,
            "comparisons": sum(counts.values()), "outcomes": counts,
            "differences_between_policies": differences, "controls": controls,
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, indent=2))
