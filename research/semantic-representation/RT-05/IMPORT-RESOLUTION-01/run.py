"""Resolve two import surfaces into an exact SPG call and compare invalidation policies."""

import argparse
import ast
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import digest
from src.spg_representation import Implementation, Operation, Program, compile_program, observe
from tests.test_spg_representation import replace_body


NAMES = ("left", "right")


@dataclass(frozen=True)
class Request:
    kind: str
    modules: tuple[str, ...]
    symbol: str


@dataclass(frozen=True)
class Answer:
    status: str
    operation: str | None
    reads: tuple[tuple[str, str, str | None], ...]


def parse(source):
    """Admit a single call with static qualified, named, or star imports."""
    statements = ast.parse(source).body
    if not statements:
        raise ValueError("expected a source invocation")
    *imports, invocation = statements
    call = invocation.value if isinstance(invocation, ast.Expr) else None
    if (not isinstance(call, ast.Call) or call.keywords or len(call.args) != 1
            or not isinstance(call.args[0], ast.Name) or call.args[0].id != "n"):
        raise ValueError("expected one unary invocation")
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and len(imports) == 1:
        statement = imports[0]
        if isinstance(statement, ast.Import) and len(statement.names) == 1:
            alias, = statement.names
            if (alias.asname or alias.name) == func.value.id:
                return Request("qualified", (alias.name,), func.attr)
    if isinstance(func, ast.Name) and all(isinstance(stmt, ast.ImportFrom) and not stmt.level
                                         and len(stmt.names) == 1 for stmt in imports):
        if len(imports) == 1:
            statement, = imports
            alias, = statement.names
            if alias.name != "*" and (alias.asname or alias.name) == func.id:
                return Request("explicit", (statement.module,), alias.name)
        if imports and all(stmt.names[0].name == "*" for stmt in imports):
            modules = tuple(sorted({stmt.module for stmt in imports}))
            return Request("open", modules, func.id)
    raise ValueError("unsupported or unresolved import form")


def lookup(catalog, request):
    if any(module not in catalog for module in request.modules):
        raise ValueError("catalog scope is incomplete")
    reads = tuple((module, request.symbol, catalog[module].get(request.symbol))
                  for module in request.modules)
    candidates = sorted({address for _, _, address in reads if address is not None})
    if not candidates:
        return Answer("missing", None, reads)
    if len(candidates) > 1:
        return Answer("ambiguous", None, reads)
    return Answer("resolved", candidates[0], reads)


def reuse(catalog, replacement, request, answer):
    """Evaluate cache keys formed at lookup, then re-read only their declared inputs."""
    later = lookup(replacement, request)
    selected_rows = tuple((module, symbol) for module, symbol, address in answer.reads
                          if address is not None and address == answer.operation)

    def reread(state, rows):
        return tuple(state[module].get(symbol) for module, symbol in rows)

    return {
        "whole_catalog": digest(catalog) == digest(replacement),
        "successful_reads": reread(catalog, selected_rows) == reread(replacement, selected_rows),
        "all_scoped_reads": answer.reads == later.reads,
    }, later


def program():
    contracts = {"pure": ((),)}
    interface = {slot: Operation(f"Catalog{slot.title()}", ("Int",), "Int", "pure")
                 for slot in ("alpha", "beta", "entry")}
    implementations = {
        "alpha": Implementation("alpha", ("n",), "n + 1"),
        "beta": Implementation("beta", ("n",), "n + 2"),
        "entry": Implementation("entry", ("n",), 'op("alpha", n)'),
    }
    return Program(contracts, interface, implementations, {"alpha": "alpha", "beta": "beta"})


def finite(alpha, beta):
    def response_oracle(catalog, request):
        offered = [value for value in (alpha, beta) if any(
            catalog[module].get(request.symbol) == value for module in request.modules
        )]
        if len(offered) == 1:
            return "resolved", offered[0]
        return ("ambiguous" if offered else "missing"), None

    possible = (None, alpha, beta)
    catalogs = [
        {module: {name: value for name, value in (("score", score), ("noise", extra)) if value is not None}
         for module, score, extra in (("left", left, noise), ("right", right, None))}
        for left, right, noise in product(possible, possible, (None, alpha))
    ]
    requests = [Request("qualified", ("left",), "score"), Request("explicit", ("right",), "score"),
                Request("open", NAMES, "score")]
    policies = ("whole_catalog", "successful_reads", "all_scoped_reads")
    totals = {label: {"reused": 0, "unsafe": 0, "unnecessary_invalidations": 0} for label in policies}
    for before, after, request in product(catalogs, catalogs, requests):
        a, b = response_oracle(before, request), response_oracle(after, request)
        old = lookup(before, request)
        comes_from, current = reuse(before, after, request, old)
        if (old.status, old.operation) != a or (current.status, current.operation) != b:
            raise AssertionError("Lookup disagreed with the independent destination oracle")
        for policy, accepted in comes_from.items():
            totals[policy]["reused"] += accepted
            totals[policy]["unsafe"] += accepted and a != b
            totals[policy]["unnecessary_invalidations"] += not accepted and a == b
    if totals["successful_reads"]["unsafe"] == 0 or totals["all_scoped_reads"]["unsafe"] != 0:
        raise AssertionError("The sweep must distinguish success-only keys from scoped positive and negative inputs")
    return {"comparison_count": len(catalogs)**2 * len(requests), "catalogs": len(catalogs), "by_policy": totals}


def verify():
    original = program()
    initial_graph = compile_program(original)
    slots = {initial_graph.snapshot.mapping[f"operation:{slot}"]: slot for slot in ("alpha", "beta")}
    alpha, beta = slots
    profile_rows = {
        "qualified": "import left as api\napi.score(n)",
        "qualified_alias": "import left as l\nl.score(n)",
        "named_alias": "from left import score as selected\nselected(n)",
        "open": "from left import *\nfrom right import *\nscore(n)",
        "open_reordered": "from right import *\nfrom left import *\nscore(n)",
    }
    requests = {name: parse(text) for name, text in profile_rows.items()}
    baseline = {"left": {"score": alpha}, "right": {}}
    qualified = requests["qualified"]
    open_request = requests["open"]
    if requests["qualified_alias"] != qualified or requests["open_reordered"] != open_request:
        raise AssertionError("Alias spelling and open import order must not change the normalized query")

    versions = {
        "baseline": baseline,
        "unrelated_export": {"left": {"score": alpha, "unrelated": beta}, "right": {}},
        "new_competing_export": {"left": {"score": alpha}, "right": {"score": beta}},
        "same_operation_reexport": {"left": {"score": alpha}, "right": {"score": alpha}},
        "left_rebound": {"left": {"score": beta}, "right": {}},
        "both_missing": {"left": {}, "right": {}},
    }
    graphs = {}

    def lower(answer):
        if answer.operation is None:
            return None
        slot = slots[answer.operation]
        if slot not in graphs:
            graph = compile_program(replace_body(original, "entry", f'op("{slot}", n)'))
            caller = graph.snapshot.mapping["implementation:entry"]
            body = graph.store.get(caller).payload
            if body[3:] != [{"external": answer.operation}]:
                raise AssertionError("Caller does not use the exact catalog operation")
            graphs[slot] = {"caller": caller, "root": graph.snapshot.root_hash,
                            "observations": [observe(graph, "entry", (n,)) for n in (-1, 0, 1)]}
        return graphs[slot]

    rows = {}
    for version, catalog in versions.items():
        rows[version] = {}
        for label, request in requests.items():
            permissions, answer = reuse(baseline, catalog, request, lookup(baseline, request))
            rows[version][label] = {"status": answer.status, "operation": answer.operation,
                                    "reads": answer.reads, "cache_reusable": permissions,
                                    "generated_spg": lower(answer)}
    expected = rows["baseline"]["qualified"]["generated_spg"]
    if any(row["generated_spg"] != expected for row in rows["baseline"].values()):
        raise AssertionError("All baseline import surfaces should select the same exact caller")
    clash = rows["new_competing_export"]["open"]
    if clash["status"] != "ambiguous" or not clash["cache_reusable"]["successful_reads"]:
        raise AssertionError("A previously absent row must falsify a positive-only key")
    if rows["new_competing_export"]["qualified"]["generated_spg"] != expected:
        raise AssertionError("Unqueried module export cannot change qualified resolution")
    if rows["left_rebound"]["qualified"]["generated_spg"] == expected:
        raise AssertionError("An exact operation change must change the typed call")
    if rows["same_operation_reexport"]["open"]["generated_spg"] != expected:
        raise AssertionError("Two paths to one exact operation must preserve the typed call")
    rejected = []
    for label, text in {
        "relative_import": "from .left import score\nscore(n)",
        "unbound_qualifier": "import left as api\nother.score(n)",
        "wrong_argument": "from left import score\nscore(1)",
        "non_import_statement": "import left as api\nx = n\napi.score(n)",
    }.items():
        try:
            parse(text)
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError(f"Outside-profile source was admitted: {label}")
    try:
        lookup({"left": baseline["left"]}, open_request)
    except ValueError:
        rejected.append("missing_catalog")
    else:
        raise AssertionError("Unobserved module was treated as a known absent export")
    return {"format": "rt05-import-resolution/1", "python": sys.version.split()[0],
            "profiles": profile_rows, "sweep": finite(alpha, beta), "cases": rows,
            "rejected_inputs": rejected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
