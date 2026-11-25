"""Check revision-bound SPG transitions and preserve archived reuse controls."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "e8ac755bf6a7339aa3967b5e6afe3c4d41a1312d"
ROOT = "research/semantic-representation/RT-05"
ARITY = {"add": (0, 1), "remove": (1, 0), "continue": (1, 1), "replace": (1, 1),
         "split": (1, 2), "merge": (2, 1)}


@dataclass(frozen=True)
class Endpoint:
    revision: str
    slot: str
    lifetime: str
    value: str


def classify(kind, parents, children, before, after, authority):
    if authority != ("p", "c"):
        return "pending"
    if len(set(parents)) != len(parents) or len(set(children)) != len(children):
        return "conflict"
    counts = len(parents), len(children)
    arity = ARITY[kind]
    if kind in {"split", "merge"}:
        valid = all(n >= min_count and (min_count > 1 or n == min_count)
                    for n, min_count in zip(counts, arity, strict=True))
    else:
        valid = counts == arity
    if not valid or not set(parents) <= before or not set(children) <= after:
        return "conflict"
    prior_ids = {endpoint.lifetime for endpoint in parents}
    later_ids = {endpoint.lifetime for endpoint in children}
    if kind == "continue":
        return kind if prior_ids == later_ids else "conflict"
    before_ids = {endpoint.lifetime for endpoint in before}
    after_ids = {endpoint.lifetime for endpoint in after}
    fresh = later_ids.isdisjoint(before_ids)
    retired = prior_ids.isdisjoint(after_ids)
    return kind if fresh and retired else "conflict"


def transitions():
    admitted = Counter()
    states = ("exact", "stale")
    old = (Endpoint("p", "a", "old-a", "same"), Endpoint("p", "b", "old-b", "same"))
    new = (Endpoint("c", "moved-a", "new-a", "same"), Endpoint("c", "moved-b", "new-b", "same"))
    n = 0
    for kind, source_count, result_count, current, exact_parent, exact_child, shared in product(
        ARITY, range(3), range(3), states, states, states, (False, True),
    ):
        current_children = (replace(new[0], lifetime=old[0].lifetime), new[1]) if shared else new
        parents, children = old[:source_count], current_children[:result_count]
        if exact_parent == "stale":
            parents = tuple(replace(endpoint, revision="equal-tree-before-p") for endpoint in parents)
        if exact_child == "stale":
            children = tuple(replace(endpoint, value="different") for endpoint in children)
        key = ("p", "c") if current == "exact" else ("other", "c")
        result = classify(kind, parents, children, set(old), set(current_children), key)
        if current == "stale":
            expected = "pending"
        elif (source_count, result_count) != ARITY[kind]:
            expected = "conflict"
        elif (source_count and exact_parent == "stale") or (result_count and exact_child == "stale"):
            expected = "conflict"
        elif shared != (kind == "continue"):
            expected = "conflict"
        else:
            expected = kind
        assert result == expected
        admitted[result] += 1
        n += 1
    assert classify("split", old[:1], (new[0], new[0]), set(old), set(new), ("p", "c")) == "conflict"
    return {"cases": n, "dispositions": dict(admitted), "duplicate_endpoint_control": "conflict"}


def reconcile():
    entries = {}
    for name in ("COMPOSED-LINEAGE-01", "MULTI-PARENT-LINEAGE-01"):
        raw = subprocess.check_output(["git", "show", f"{BASE}:{ROOT}/{name}/evidence.json"])
        ledger = json.loads(raw)
        assert len(ledger["results"]) == 12
        entries[name] = {"sha256": sha256(raw).hexdigest(),
                         "summary": ledger.get("summary", ledger.get("summaries"))}
    return entries


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archived_history_checks": reconcile(), "transitions": transitions(),
    }, sort_keys=True, indent=2))
