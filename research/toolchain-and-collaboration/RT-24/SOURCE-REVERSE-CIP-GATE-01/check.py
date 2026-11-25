"""Compose the existing merge, reverse audit and RT-20 plan APIs at one boundary."""

from collections import Counter
from dataclasses import replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
COVERAGE = HERE.parent / "MERGE-COVERAGE-01"
sys.path.insert(0, str(COVERAGE))
from run import SCOPE, SourceInventory, admit, fixture, merge_closed, query_snapshot_incoming

from src.impact_planning import (ActionKind, CallSiteDecision, CallSiteDisposition, ImpactedArtifact,
                                 audit_snapshot_incoming, plan_impact)
from src.semantic_dependency_index import audit_snapshot_incoming_independently


BASE = "71dc00a9d5b3c80367955d0914a7ae690ee6b812"


def run_cases():
    store, examples, trusted_rows, old = fixture()
    parents = examples["structurally-closed"]
    base = parents[0]
    result = merge_closed(store, *parents)
    snapshot = result.candidate.snapshot
    exact_rows = SourceInventory(result.input_pins, trusted_rows)
    targets = set(base.snapshot.mapping.values()) | set(snapshot.mapping.values())
    roster = tuple(query_snapshot_incoming(store, snapshot, target, SCOPE) for target in sorted(targets))
    raw = next(query for query in roster if query.target_hash == old)
    exact = audit_snapshot_incoming_independently(store, snapshot, raw)
    audit = audit_snapshot_incoming(query_snapshot_incoming(store, snapshot, old, SCOPE, exact))
    call, = audit.incoming_call_sites
    decision = CallSiteDecision(call.caller_hash, call.call_site_id, call.target_id, old,
                                CallSiteDisposition.PRESERVE, old, call.caller_hash,
                                "preserve the retained exact provider", exact.evidence_id,
                                call.required_contract_hash, "PROVEN", call.required_contract_hash)
    outcomes = Counter()
    plan_ids = {}
    for source, reverse, authority, call_policy in product(
        ("exact", "omitted"), ("exact", "old-root"), ("current", "unknown"), ("exact", "absent"),
    ):
        actual_source = exact_rows if source == "exact" else replace(exact_rows, rows=exact_rows.rows[1:])
        whole = admit(store, result, base, actual_source, exact_rows.receipt, roster)
        confirmed = exact if reverse == "exact" else replace(exact, snapshot_root="prior-root")
        supplied = confirmed if whole == "clean-within-profile" and authority == "current" else None
        verified = query_snapshot_incoming(store, snapshot, old, SCOPE, supplied)
        report = audit_snapshot_incoming(verified)
        decisions = (decision,) if supplied == exact and call_policy == "exact" else ()
        plan = plan_impact(snapshot.root_hash, snapshot.root_hash, "verified-merge-reverse-fixture-v1",
                           [ImpactedArtifact(old, "implementation", "validate retained exact provider")], [report],
                           call_site_decisions=decisions)
        deferred = any(action.kind is ActionKind.FULL_REVALIDATION for action in plan.actions)
        if whole != "clean-within-profile":
            assert deferred
            classification = "source-withheld"
        elif supplied == exact and not decisions:
            assert deferred
            classification = "call-decision-required"
        elif deferred:
            classification = "full-revalidation"
        else:
            classification = "eligible-within-profile"
        expected = ("source-withheld" if source == "omitted" else
                    "full-revalidation" if (reverse, authority) != ("exact", "current") else
                    "call-decision-required" if call_policy == "absent" else "eligible-within-profile")
        assert classification == expected, (source, reverse, authority, call_policy, classification)
        outcomes[classification] += 1
        plan_ids["/".join((source, reverse, authority, call_policy))] = plan.plan_id
    return {"outcomes": dict(outcomes), "plan_ids": plan_ids, "target": old, "candidate": snapshot.root_hash}


def provenance():
    inputs = {
        "coverage": COVERAGE / "run.py",
        "verifier": HERE.parents[2] / "PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_dependency_index.py",
        "planner": HERE.parents[2] / "PROTOTYPES/DEPENDENCY-GRAPH-01/src/impact_planning.py",
        "checker": Path(__file__),
    }
    archives = {}
    for fixture_name in ("MERGE-COVERAGE-01", "AUDIT-AUTHORITY-01", "CIP-COORDINATOR-01"):
        path = f"research/toolchain-and-collaboration/RT-24/{fixture_name}/evidence.json"
        payload = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
        archives[fixture_name] = sha256(payload).hexdigest()
    return {"sources": {name: sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()},
            "archives": archives}


if __name__ == "__main__":
    print(json.dumps({"baseline": BASE, "provenance": provenance(), "results": run_cases()},
                     sort_keys=True, indent=2))
