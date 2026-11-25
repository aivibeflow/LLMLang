"""Check guarded layout admission and exact group invalidation on three keyed members."""

from collections import Counter
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import subprocess


BASE = "a75fc77de15d7bbe18ea7f990d1d730c9db6d5af"
RT05 = "research/semantic-representation/RT-05"
MEMBERS = ("a", "b", "c")
PAIRS = tuple(product(MEMBERS, repeat=2))


def reachable(start, edges):
    seen = set()
    todo = [start]
    while todo:
        current = todo.pop()
        if current not in seen:
            seen.add(current)
            todo.extend(destination for source, destination in edges if source == current)
    return seen


def group_by_reachability(edges):
    reachable_sets = {node: reachable(node, edges) for node in MEMBERS}
    return {
        node: tuple(other for other in MEMBERS
                    if other in reachable_sets[node] and node in reachable_sets[other])
        for node in MEMBERS
    }


def valid_layout(edges):
    remaining = set(MEMBERS)
    while remaining:
        removable = remaining - {source for source, dest in edges if dest in remaining}
        if not removable:
            return False
        remaining -= removable
    return True


def cycle_oracle(edges):
    return any(all((node, route[(index + 1) % size]) in edges for index, node in enumerate(route))
               for size in range(1, len(MEMBERS) + 1) for route in permutations(MEMBERS, size))


def group_digests(edges, grouping, edited=None):
    digests = {}

    def address(group):
        if group not in digests:
            rows = []
            for member in group:
                references = [
                    (role, "local", group.index(target)) if grouping[target] == group
                    else (role, "external", address(grouping[target]), target)
                    for (source, target), role in sorted(edges.items()) if source == member
                ]
                rows.append((member, member == edited, references))
            preimage = json.dumps(["keyed-type-group-fixture/1", rows], separators=(",", ":")).encode()
            digests[group] = sha256(preimage).hexdigest()
        return digests[group]

    return {member: address(grouping[member]) for member in MEMBERS}


def check():
    totals = Counter()
    dispositions = Counter()
    for shape in product(("absent", "guarded", "by-value"), repeat=len(PAIRS)):
        edges = {pair: role for pair, role in zip(PAIRS, shape, strict=True) if role != "absent"}
        by_value = {pair for pair, role in edges.items() if role == "by-value"}
        admitted = valid_layout(by_value)
        assert admitted == (not cycle_oracle(by_value))
        totals["graphs"] += 1
        if not admitted:
            totals["rejected_by_value_cycle"] += 1
            continue
        totals["admitted"] += 1
        totals["admitted_with_recursive_edges"] += cycle_oracle(edges)
        grouping = group_by_reachability(edges)
        before = group_digests(edges, grouping)
        assert group_digests(dict(reversed(tuple(edges.items()))), grouping) == before
        for edited in MEMBERS:
            after = group_digests(edges, grouping, edited)
            changed = {node for node in MEMBERS if before[node] != after[node]}
            expected = reachable(edited, {(target, source) for source, target in edges})
            assert changed == expected
            dispositions[len(changed)] += 1
    return {"totals": dict(totals), "edit_checks_by_changed_member_count": dict(dispositions)}


def archived_ledgers():
    result = {}
    for study in ("RECURSIVE-TYPES-01", "RECURSIVE-CANONICAL-02", "UNORDERED-RECURSIVE-01",
                  "DIRECTED-RECURSIVE-01", "ORDERED-OCCURRENCES-01", "RECURSIVE-STORAGE-01"):
        raw = subprocess.check_output(["git", "show", f"{BASE}:{RT05}/{study}/evidence.json"])
        assert isinstance(json.loads(raw), dict)
        result[study] = sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "pinned_ledgers": archived_ledgers(), **check(),
    }, sort_keys=True, indent=2))
