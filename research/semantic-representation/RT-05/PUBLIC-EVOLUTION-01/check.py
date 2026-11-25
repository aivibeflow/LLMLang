"""Check candidate public revision, export, binding and reuse consistency."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "39c96755626604fb1a67901d8b85ce231a994553"


@dataclass(frozen=True)
class Revision:
    identity: str
    inputs: frozenset[int]
    outcomes: frozenset[str]


@dataclass(frozen=True)
class Selection:
    public: Revision
    bound_operation: str
    provider: str
    evidence: tuple[str, str]
    package_export: str
    index_projection: tuple[str, str]


BASE_PUBLIC = Revision("old", frozenset((0, 1)), frozenset(("left", "right")))
REVISIONS = {
    "unchanged": BASE_PUBLIC,
    "compatible": Revision("compatible", frozenset((0, 1, 2)), frozenset(("left",))),
    "breaking": Revision("breaking", frozenset((0, 2)), frozenset(("different",))),
}
START = Selection(BASE_PUBLIC, "old", "provider-a", ("old", "provider-a"), "old", ("old", "provider-a"))


def refines(new, old):
    return old.inputs <= new.inputs and new.outcomes <= old.outcomes and bool(new.outcomes)


def admit(publication, pin, migrated):
    if pin != publication.public.identity:
        if pin != BASE_PUBLIC.identity or not migrated or not refines(publication.public, BASE_PUBLIC):
            return "migration-required"
    key = publication.public.identity, publication.provider
    if publication.bound_operation != key[0] or publication.package_export != key[0]:
        return "inconsistent"
    if publication.evidence != key:
        return "pending-evidence"
    if publication.index_projection != key:
        return "stale-index"
    return "bound"


def matrix():
    counts = Counter()
    reuse = Counter()
    for revision, rebound, exact_receipt, exact_export, exact_index, pin in product(
        REVISIONS, (False, True), (False, True), (False, True), (False, True), ("old", "current"),
    ):
        public = REVISIONS[revision]
        provider = "provider-b" if rebound else START.provider
        pair = (public.identity, provider)
        row = Selection(public, public.identity, provider, pair if exact_receipt else ("unknown", provider),
                        public.identity if exact_export else "foreign", pair if exact_index else ("unknown", provider))
        caller = BASE_PUBLIC.identity if pin == "old" else public.identity
        status = admit(row, caller, migrated=True)
        conditions = [
            (pin == "old" and revision == "breaking", "migration-required"),
            (not exact_export, "inconsistent"), (not exact_receipt, "pending-evidence"),
            (not exact_index, "stale-index"),
        ]
        assert status == next((result for condition, result in conditions if condition), "bound")
        counts[status] += 1
        if status == "bound":
            public_equal = row.public.identity == START.public.identity
            resolved_equal = (row.public.identity, row.provider, row.evidence) == (
                START.public.identity, START.provider, START.evidence)
            reuse["conditional-proof-kept" if public_equal else "conditional-proof-invalidated"] += 1
            reuse["exact-execution-kept" if resolved_equal else "exact-execution-invalidated"] += 1
    compatible = REVISIONS["compatible"]
    assert admit(Selection(compatible, compatible.identity, "provider-a",
                           (compatible.identity, "provider-a"), compatible.identity,
                           (compatible.identity, "provider-a")), "old", migrated=False) == "migration-required"

    left = replace(START, provider="provider-b", evidence=("old", "provider-b"),
                   index_projection=("old", "provider-b"))
    right_pair = (compatible.identity, START.provider)
    right = replace(START, public=compatible, bound_operation=compatible.identity,
                    package_export=compatible.identity, evidence=right_pair, index_projection=right_pair)
    combined = replace(left, public=right.public, package_export=right.package_export)
    field_merge = replace(right, provider=left.provider)
    assert admit(left, "old", False) == admit(right, compatible.identity, False) == "bound"
    assert admit(combined, compatible.identity, False) == "inconsistent"
    assert admit(field_merge, compatible.identity, False) == "pending-evidence"
    assert admit(START, "unrelated", True) == "migration-required"
    return {"outcomes": dict(counts), "reuse_on_bound_cases": dict(reuse),
            "fieldwise_combination_of_two_valid_sides": "pending-evidence",
            "control_without_explicit_migration": "migration-required",
            "disjoint_combination_with_stale_bound_operation": "inconsistent"}


def prior():
    ledger_paths = (
        "research/semantic-representation/RT-05/PUBLIC-RESOLUTION-01/evidence.json",
        "research/packages-and-ecosystem/RT-12/CONTRACT-PROVIDER-INDEX-01/evidence.json",
        "research/toolchain-and-collaboration/RT-24/IDENTITY-LINEAGE-01/evidence.json",
    )
    return {path: sha256(subprocess.check_output(["git", "show", f"{BASE}:{path}"])).hexdigest()
            for path in ledger_paths}


if __name__ == "__main__":
    print(json.dumps({
        "base": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_ledgers": prior(), "matrix": matrix(),
    }, indent=2, sort_keys=True))
