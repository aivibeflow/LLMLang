"""Measure actual snapshot discovery and an isolated grouped impact planner candidate."""

import argparse
import csv
from dataclasses import replace
from hashlib import sha256
from inspect import getsource
import json
import os
from pathlib import Path
import platform
from random import Random
import subprocess
import sys
from time import perf_counter_ns


HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))
from src import impact_planning as planning
from src import semantic_dependency_index as index
from src.semantic_graph import ContentStore, make_snapshot


SIZES = (64, 256, 1024)
SHAPES = ("spread", "hot")
SCOPE = "selected-static-calls/1"


def grouped_candidate():
    code = getsource(planning.plan_impact)
    body = """    for key, edge in sorted(call_edges.items()):
        edge_decisions = [
            decision for decision in decisions
            if (decision.caller_hash, decision.call_site_id, decision.target_id) == key
        ]
"""
    grouped = """    by_call_edge = {}
    for decision_key, decision in zip(decision_keys, decisions, strict=True):
        by_call_edge.setdefault(decision_key[:3], []).append(decision)
    for key, edge in sorted(call_edges.items()):
        edge_decisions = by_call_edge.get(key, ())
"""
    if code.count(body) != 1:
        raise ValueError("the exact comparison boundary in plan_impact changed")
    namespace = vars(planning).copy()
    source = code.replace(body, grouped)
    exec(compile(source, "<grouped-plan-research>", "exec"), namespace)
    return namespace["plan_impact"], sha256(source.encode()).hexdigest()


def declaration(kind, logical_id, **rest):
    return {"format": index.FORMAT, "schema_version": index.SCHEMA_VERSION, "kind": kind,
            "declaration_id": logical_id, "content": {}, **rest}


def fixture(shape, size):
    store = ContentStore()
    publish = lambda *args, **kwargs: index.publish_declaration(store, declaration(*args, **kwargs))
    contract = publish("contract", "contract")
    refs = [{"reference_id": "provider-contract", "relation": "provides_contract",
             "target_hash": contract, "target_kind": "contract"}]
    hot, cold, replacement = [publish("function", f"target-{label}", references=refs)
                              for label in ("hot", "cold", "candidate")]
    selected = {"contract": contract, "hot": hot, "cold": cold}
    expected = set()
    for number in range(size + 1):
        name = f"caller-{number}"
        # The final declaration is historical and remains outside the selected snapshot.
        target = hot if shape == "hot" or number % 8 == 0 or number == size else cold
        caller = publish("function", name, call_sites=[{"call_site_id": "entry",
                         "targets": [{"target_id": "callee", "target_hash": target,
                                      "condition": None, "required_contract_hash": contract}]}])
        if number < size:
            selected[name] = caller
            if target == hot:
                expected.add(caller)
    baseline = make_snapshot(selected)
    candidate = make_snapshot({**selected, "hot": replacement})
    return store, baseline, candidate, hot, contract, expected


def timed(function):
    began = perf_counter_ns()
    result = function()
    return result, perf_counter_ns() - began


def probe(shape, size, seed):
    store, base, candidate, target, contract, callers = fixture(shape, size)
    incoming, discovery_ns = timed(lambda: index.query_snapshot_incoming(store, base, target, SCOPE))
    evidence, audit_ns = timed(lambda: index.audit_snapshot_incoming_independently(store, base, incoming))
    checked, bind_ns = timed(lambda: index.query_snapshot_incoming(store, base, target, SCOPE, evidence))
    if ({edge.source_hash for edge in checked.edges} != callers or len(checked.edges) != len(callers)
            or checked.completeness_status.value != "SUPPORTED_WITHIN_SCOPE"):
        raise ValueError("incoming discovery did not match selected exact callers")
    audit = planning.audit_snapshot_incoming(checked)
    impacted = [
        planning.ImpactedArtifact(target, "implementation", "replace target body"),
    ]
    decisions = tuple(planning.CallSiteDecision(
        caller_hash=edge.caller_hash, call_site_id=edge.call_site_id, target_id=edge.target_id,
        base_callee_hash=target, disposition=planning.CallSiteDisposition.PRESERVE,
        selected_callee_hash=target, resulting_caller_hash=edge.caller_hash,
        rationale="retain exact base callee", decision_evidence_id=f"fixture/{edge.caller_hash}",
        required_contract_hash=contract, compatibility_status="PROVEN",
    ) for edge in audit.incoming_call_sites)
    grouped, candidate_source = grouped_candidate()
    phases = [("baseline_plan_ns", planning.plan_impact), ("grouped_plan_ns", grouped)]
    Random(seed).shuffle(phases)

    def plan(planner, current_audit=audit, current_decisions=decisions):
        return planner(base.root_hash, candidate.root_hash, "impact-plan/fixture",
                       impacted, [current_audit], call_site_decisions=current_decisions)

    outputs = {name: timed(lambda: plan(planner)) for name, planner in phases}
    original = outputs["baseline_plan_ns"][0]
    if (original != outputs["grouped_plan_ns"][0] or len(original.call_site_decisions) != len(callers)
            or {action.kind.value for action in original.actions} != {"REBUILD", "RUN_TESTS"}):
        raise ValueError("planner outputs or expected actions disagreed")
    for changed_audit, changed_decisions in (
        (replace(audit, snapshot_root=candidate.root_hash), decisions),
        (audit, decisions[1:]),
    ):
        first = plan(planning.plan_impact, changed_audit, changed_decisions)
        second = plan(grouped, changed_audit, changed_decisions)
        if first != second or "FULL_REVALIDATION" not in {entry.kind.value for entry in first.actions}:
            raise ValueError("stale evidence or an omitted decision bypassed fallback")

    return {
        "shape": shape, "active_callers": size, "incoming_edges": len(callers), "plan_id": original.plan_id,
        "grouped_source_sha256": candidate_source, "discovery_ns": discovery_ns, "audit_ns": audit_ns,
        "bind_ns": bind_ns, "planner_order": ",".join(name for name, _ in phases),
        **{name: record[1] for name, record in outputs.items()},
    }


def counters():
    return {key: int(number) for key, number in
            map(str.split, Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())}


def collect(args):
    if args.trials < 2 or args.cpu not in os.sched_getaffinity(0):
        raise ValueError("invalid CPU or trials")
    os.sched_setaffinity(0, {args.cpu})
    random = Random(args.seed)
    rows = []
    before = counters()
    for block in range(args.trials):
        variants = [(shape, size) for shape in SHAPES for size in SIZES]
        random.shuffle(variants)
        for position, (shape, size) in enumerate(variants):
            seed = random.getrandbits(32)
            proc = subprocess.run([sys.executable, __file__, "--child", shape, str(size), str(seed)],
                                  check=True, text=True, capture_output=True, timeout=45)
            if proc.stderr:
                raise ValueError(proc.stderr)
            rows.append({"block": block, "position": position, "seed": seed, **json.loads(proc.stdout)})
    after = counters()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = (*[field for field in rows[0] if not field.endswith("_plan_ns")],
                  "baseline_plan_ns", "grouped_plan_ns")
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    source = (HERE / "measure.py", PROTOTYPE / "src/impact_planning.py",
              PROTOTYPE / "src/semantic_dependency_index.py", PROTOTYPE / "src/semantic_graph.py")
    config = {
        "cpu": args.cpu, "kernel": platform.release(), "trials": args.trials, "seed": args.seed,
        "python": platform.python_version(),
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "counter_delta": {key: after[key] - before[key] for key in before},
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in source},
    }
    (args.output / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--child":
        print(json.dumps(probe(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        for field in ("cpu", "seed", "trials"):
            parser.add_argument(f"--{field}", required=True, type=int)
        parser.add_argument("--output", required=True, type=Path)
        collect(parser.parse_args())
