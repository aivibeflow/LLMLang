"""Normalize a closed COR-13 owned-call fragment into typed graph values."""

import argparse
from itertools import combinations, product
import json
from pathlib import Path
import sys
from typing import get_args


HERE = Path(__file__).resolve().parent
PROTOTYPES = HERE.parents[2] / "PROTOTYPES"
sys.path[:0] = [str(PROTOTYPES / name) for name in ("DEPENDENCY-GRAPH-01", "RT-04-01")]
from rt04_owned_call_match import Function, IfFlag, ReturnError, ReturnOwned, WithOwned
from rt04_owned_call_match import infer_result_cases, observe_call
from rt04_return_disposition import Disposition, TransferTiming
from src.semantic_graph import ContentStore, Dependency, digest, make_snapshot


KINDS = ("close-dispositions/1", "owned-function/1")
ROLES = ("handle", "local")


def compile_named(store, function):
    # Reuse the admitted source envelope, including the permitted move target.
    infer_result_cases(function)
    outer = function.body
    inner = outer.body
    exits = inner.body
    if not isinstance(exits, IfFlag):
        raise ValueError("expected two ordered outcomes in this fixture")
    exit_terms = [("move", 0) if isinstance(exit, ReturnOwned) else ("domain-error",)
                  for exit in (exits.when_true, exits.when_false)]
    return publish(store, function.name, function.transfer,
                   [outer.close_results, inner.close_results], exit_terms)


def compile_prefix(store, source):
    profile, exported, transfer, scopes, branch = json.loads(source)
    if profile != "owned-prefix/1" or not isinstance(exported, str) or not exported:
        raise ValueError("unsupported profile or export")
    if transfer not in get_args(TransferTiming):
        raise ValueError("unsupported transfer timing")
    if len(scopes) != 2 or tuple(role for role, _ in scopes) != ROLES:
        raise ValueError("expected ordered handle and local scopes")
    marker, got_true, got_false = branch
    if marker != "if-flag":
        raise ValueError("expected if-flag")
    exits = [tuple(got_true), tuple(got_false)]
    if any(exit != ("domain-error",) and (
            len(exit) != 2 or exit[0] != "move" or type(exit[1]) is not int or exit[1] != 0
    ) for exit in exits):
        raise ValueError("unsupported ownership exit")
    contracts = [outcomes for _, outcomes in scopes]
    for contract in contracts:
        if not contract or not set(contract).issubset(get_args(Disposition)):
            raise ValueError("unsupported close contract")
    return publish(store, exported, transfer, contracts, exits)


def publish(store, exported, transfer, contracts, exits):
    dependencies = [
        Dependency("close-contract", store.put(KINDS[0], sorted(set(contract))), role=role)
        for role, contract in zip(ROLES, contracts, strict=True)
    ]
    value = store.put(KINDS[1], {
        "export": exported, "transfer": transfer, "scope_order": ROLES,
        "branch_order": ("true", "false"), "exits": exits,
    }, dependencies)
    return make_snapshot({exported: value})


def reconstruct(store, state):
    value = store.get(state.selections[0][1])
    payload = value.payload
    contracts = {dep.role: frozenset(store.get(dep.target_hash).payload) for dep in value.dependencies}
    outer, inner = payload["scope_order"]
    when_true, when_false = (ReturnOwned(outer) if exit[0] == "move" else ReturnError()
                             for exit in payload["exits"])
    return Function(payload["export"], WithOwned(outer, contracts[outer], WithOwned(
        inner, contracts[inner], IfFlag(when_true, when_false),
    )), payload["transfer"])


def observe(function, flag, local_result, handle_result):
    trace = observe_call(function, flag=flag, local_close=local_result, handle_close=handle_result)
    aliases = {function.body.binding: "handle", function.body.body.binding: "local"}
    return {
        "tag": trace.case.tag,
        "obligations": sorted((claim.slot, claim.kind) for claim in trace.case.obligations),
        "events": [(action, aliases[slot], result) for action, slot, result in trace.events],
        "domain_error": trace.domain_error,
        "cleanup_errors": [(aliases[slot], result) for slot, result in trace.cleanup_errors],
    }


def oracle(timing, moves, local_result, handle_result):
    """Calculate the observable path from a transfer/release predicate table."""
    early_move = moves and timing == "before_cleanup"
    late_move = moves and timing == "after_cleanup" and local_result == "ok"
    owns = early_move or late_move
    cleanup = [("local", local_result)] + ([] if owns else [("handle", handle_result)])
    errors = [(role, result) for role, result in cleanup if result != "ok"]
    events = [("acquire", role, "ok") for role in ROLES]
    events += [("transfer", "handle", "ok")] if early_move else []
    events += [("release", role, result) for role, result in cleanup]
    events += [("transfer", "handle", "ok")] if late_move else []
    if not moves:
        tag = "ErrWithCleanupErrors" if errors else "Err"
    elif not errors:
        tag = "OkWithValue"
    elif owns:
        tag = "CleanupFailedWithValue"
    else:
        tag = "StagedCleanupFailedWithoutValue"
    debt = {"retained_error": "retained", "indeterminate": "reconcile"}
    obligations = [(role, debt[result]) for role, result in errors if result in debt]
    if owns:
        obligations.append(("handle", "owned"))
    return {"tag": tag, "obligations": sorted(obligations), "events": events,
            "domain_error": not moves, "cleanup_errors": errors}


def sources(timing, local, handle, moves_when_true, *, exported="open", names=("fd", "tmp")):
    outer, inner = names
    moves = ReturnOwned(outer)
    error = ReturnError()
    arms = (moves, error) if moves_when_true else (error, moves)
    named = Function(exported, WithOwned(outer, frozenset(handle), WithOwned(
        inner, frozenset(local), IfFlag(*arms),
    )), timing)
    branch = [("move", 0) if isinstance(arm, ReturnOwned) else ("domain-error",) for arm in arms]
    prefix = ["owned-prefix/1", exported, timing, [("handle", handle), ("local", local)],
              ["if-flag", *branch]]
    return named, json.dumps(prefix)


def build(store, *args, **kwargs):
    named, prefix = sources(*args, **kwargs)
    state = compile_named(store, named)
    if state != compile_prefix(store, prefix):
        raise AssertionError("Profiles disagree on graph identity")
    return named, prefix, state


def witness(store, a, b, erased, shared_input):
    def projected(state):
        value = store.get(state.selections[0][1])
        payload = value.payload
        dependencies = [(dep.role, dep.target_hash) for dep in value.dependencies]
        if erased == "transfer":
            del payload["transfer"]
        elif erased == "branch_order":
            payload["exits"].sort()
        else:
            raise ValueError(erased)
        return digest((payload, dependencies))

    if a == b or projected(a) != projected(b):
        raise AssertionError(f"Expected an identity collision only after erasing {erased}")
    left = observe(reconstruct(store, a), *shared_input)
    right = observe(reconstruct(store, b), *shared_input)
    if left == right:
        raise AssertionError(f"Expected an observation change after erasing {erased}")
    return {"roots": (a.root_hash, b.root_hash), "erased_projection": projected(a),
            "input": shared_input, "traces": (left, right)}


def verify():
    dispositions = get_args(Disposition)
    contracts = [subset for count in range(1, len(dispositions) + 1)
                 for subset in combinations(dispositions, count)]
    rows = []
    observations = 0
    roots = set()
    for timing, local, handle, branch in product(get_args(TransferTiming), contracts, contracts, (False, True)):
        store = ContentStore()
        named, _, state = build(store, timing, local, handle, branch)
        _, _, alpha = build(store, timing, local[::-1], handle[::-1], branch, names=("out", "scratch"))
        if alpha != state or state.root_hash in roots:
            raise AssertionError("Alpha-renaming must preserve identity and exact variants must differ")
        roots.add(state.root_hash)
        graph_function = reconstruct(store, state)
        if infer_result_cases(named) != infer_result_cases(graph_function):
            raise AssertionError("Result obligation enumeration changed after reconstruction")
        traces = []
        for flag, local_result, handle_result in product((False, True), local, handle):
            expected = oracle(timing, flag == branch, local_result, handle_result)
            if expected != observe(named, flag, local_result, handle_result):
                raise AssertionError(("named-source", timing, flag, local_result, handle_result))
            if expected != observe(graph_function, flag, local_result, handle_result):
                raise AssertionError(("reconstructed-graph", timing, flag, local_result, handle_result))
            traces.append(expected)
            observations += 1
        rows.append((timing, local, handle, branch, state.root_hash, digest(traces)))

    store = ContentStore()
    primary = ("ok", "retained_error")
    secondary = ("ok", "indeterminate")
    _, prefix, anchor = build(store, "before_cleanup", primary, secondary, True)
    _, _, stage = build(store, "after_cleanup", primary, secondary, True)
    _, _, alternate = build(store, "before_cleanup", primary, secondary, False)
    _, _, swapped = build(store, "before_cleanup", secondary, primary, True)
    _, _, renamed_export = build(store, "before_cleanup", primary, secondary, True, exported="reopen")
    if anchor == renamed_export:
        raise AssertionError("Exported name participates in fixture identity")
    negative_inputs = []
    for label, mutate in (
        ("move_inner", lambda value: value[-1].__setitem__(1, ["move", 1])),
        ("boolean_index", lambda value: value[-1].__setitem__(1, ["move", False])),
        ("empty_contract", lambda value: value[3][0].__setitem__(1, [])),
        ("unsupported_disposition", lambda value: value[3][0].__setitem__(1, ["unknown"])),
        ("swap_scope_order", lambda value: value[3].reverse()),
    ):
        invalid = json.loads(prefix)
        mutate(invalid)
        try:
            compile_prefix(store, json.dumps(invalid))
        except ValueError:
            negative_inputs.append(label)
        else:
            raise AssertionError(f"Unsupported input accepted: {label}")

    return {
        "format": "owned-spg-normalization/1", "python": sys.version.split()[0],
        "profile_pairs": len(rows), "observations_per_path": observations,
        "exact_root_and_trace_manifest": digest(rows), "renamed_export_root": renamed_export.root_hash,
        "rejected_input_kinds": negative_inputs,
        "witnesses": {
            "transfer": witness(store, anchor, stage, "transfer", (True, "retained_error", "ok")),
            "branch_order": witness(store, anchor, alternate, "branch_order", (True, "ok", "ok")),
        },
        "role_swap": role_swap(store, anchor, swapped),
    }


def role_swap(store, first, second):
    a = store.get(first.selections[0][1])
    b = store.get(second.selections[0][1])
    unlabeled_a = sorted(dep.target_hash for dep in a.dependencies)
    unlabeled_b = sorted(dep.target_hash for dep in b.dependencies)
    left = infer_result_cases(reconstruct(store, first))
    right = infer_result_cases(reconstruct(store, second))
    if a.payload != b.payload or unlabeled_a != unlabeled_b or first == second or left == right:
        raise AssertionError("Dropping contract-edge roles must hide a change in obligations")

    def record(case):
        return case.tag, tuple(sorted((obligation.slot, obligation.kind) for obligation in case.obligations))

    return {"roots": (first.root_hash, second.root_hash), "unlabeled_deps": unlabeled_a,
            "first_only_outcomes": sorted(record(case) for case in left - right),
            "second_only_outcomes": sorted(record(case) for case in right - left)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
