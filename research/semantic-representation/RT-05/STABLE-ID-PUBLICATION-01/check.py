"""Check candidate stable-ID allocation and tombstone behavior across two contenders."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "72afdd7055fb17bb7274ae9330aa6a32791fde4e"
RT05 = "research/semantic-representation/RT-05"


@dataclass(frozen=True)
class Catalog:
    generation: int
    active: frozenset[str]
    retired: frozenset[str]


@dataclass(frozen=True)
class Request:
    generation: int
    outputs: tuple[str, ...]
    retire: frozenset[str]
    scoped_authority: bool


def publish(catalog, request):
    if not request.scoped_authority or request.generation != catalog.generation:
        return catalog, "pending"
    targets = set(request.outputs)
    if (not targets or len(targets) != len(request.outputs) or targets & (catalog.active | catalog.retired)
            or not request.retire <= catalog.active):
        return catalog, "conflict"
    return Catalog(catalog.generation + 1, (catalog.active - request.retire) | targets,
                   catalog.retired | request.retire), "published"


def test_model():
    initial = Catalog(4, frozenset(("old-a", "old-b")), frozenset(("retired-z",)))
    candidates = {
        "split": Request(4, ("new-a", "new-b"), frozenset(("old-a",)), True),
        "merge": Request(4, ("new-a",), frozenset(("old-a", "old-b")), True),
        "retired-id": Request(4, ("retired-z",), frozenset(("old-a",)), True),
        "duplicate": Request(4, ("new-b", "new-b"), frozenset(("old-a",)), True),
        "missing-parent": Request(4, ("new-c",), frozenset(("absent",)), True),
        "absent-authority": Request(4, ("new-c",), frozenset(("old-b",)), False),
    }
    ready_first = {"split": "published", "merge": "published", "retired-id": "conflict",
                   "duplicate": "conflict", "missing-parent": "conflict", "absent-authority": "pending"}
    pairs = Counter()
    retries = Counter()
    for first, second in product(candidates, repeat=2):
        one, status_one = publish(initial, candidates[first])
        two, status_two = publish(one, candidates[second])
        assert status_one == ready_first[first]
        assert status_two == ("pending" if status_one == "published" else ready_first[second])
        assert not two.active & two.retired and initial.retired <= two.retired
        assert two.generation - initial.generation == (status_one == "published") + (status_two == "published")
        pairs[f"{status_one}/{status_two}"] += 1
        retry, retry_status = publish(two, replace(candidates[second], generation=two.generation))
        if two != initial:
            assert retry == two and retry_status in {"conflict", "pending"}
            retries[retry_status] += 1
    return {"ordered_cases": sum(pairs.values()), "outcomes": dict(pairs), "post_commit_retries": dict(retries)}


def prior():
    result = {}
    for fixture in ("OPERATION-LIFETIME-01", "EVOLUTION-BOUNDARY-01", "MULTI-PARENT-LINEAGE-01"):
        path = f"{RT05}/{fixture}/evidence.json"
        raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
        assert isinstance(json.loads(raw), dict)
        result[fixture] = sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_ledgers": prior(), "model": test_model(),
    }, sort_keys=True, indent=2))
