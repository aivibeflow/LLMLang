"""Extract routes from one immutable-argument control-flow fragment."""

import argparse
import ast
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
CERTIFICATE = HERE.parent / "DIFFERENCE-CERTIFICATE-01"
POLICY = RESEARCH / "PROTOTYPES" / "RT-04-01"
sys.path[:0] = [str(CERTIFICATE), str(POLICY)]

from checker import Certificate, Edge, Query, classify

BASELINE = "11b6e6a2a5d98c6bea2d9793f68ac97ecf2aaeff"


class Unsupported(ValueError):
    pass


@dataclass(frozen=True)
class Route:
    value: str
    query: Query


def identity(*values):
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def extract(source):
    try:
        function, = ast.parse(source).body
    except (SyntaxError, ValueError) as error:
        raise Unsupported("expected one function") from error
    if not isinstance(function, ast.FunctionDef) or function.name != "route":
        raise Unsupported("expected one route definition")
    if function.decorator_list or function.type_params:
        raise Unsupported("unsupported declaration")
    args = function.args
    if args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults or function.returns:
        raise Unsupported("unsupported signature")
    params = [arg.arg for arg in args.args]
    if not params or len(set(params)) != len(params) or any(arg.annotation is not None for arg in args.args):
        raise Unsupported("expected distinct unannotated immutable parameters")
    revision = sha256(source.encode("utf-8")).hexdigest()

    def predicate(test, taken):
        match test:
            case ast.Compare(left=ast.BinOp(left=ast.Name(id=destination), op=ast.Sub(), right=ast.Name(id=origin)),
                             ops=[ast.LtE()], comparators=[rhs]):
                pass
            case _:
                raise Unsupported("unsupported guard")
        if destination not in params or origin not in params:
            raise Unsupported("guard refers to undeclared parameters")
        match rhs:
            case ast.Constant(value=bound) if type(bound) is int:
                pass
            case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=item)) if type(item) is int:
                bound = -item
            case _:
                raise Unsupported("unsupported bound")
        span = (test.lineno, test.col_offset, test.end_lineno, test.end_col_offset)
        premise = identity("rt03-source-guard-v1", revision, span, taken, origin, destination, bound)
        left, right = params.index(origin), params.index(destination)
        return Edge(left, right, bound, premise) if taken else Edge(right, left, -bound - 1, premise)

    def validate(statements):
        for statement in statements:
            match statement:
                case ast.If(test=test, body=positive, orelse=negative):
                    predicate(test, True)
                    validate(positive)
                    validate(negative)
                case ast.Return(value=ast.Constant(value=str())):
                    pass
                case _:
                    raise Unsupported("unsupported statement")

    def routes(statements, edges=()):
        if not statements:
            raise Unsupported("uncovered exit")
        first, *rest = statements
        if isinstance(first, ast.If):
            yield from routes(first.body + rest, (*edges, predicate(first.test, True)))
            yield from routes(first.orelse + rest, (*edges, predicate(first.test, False)))
        else:
            terminal = identity("rt03-source-route-v1", revision, first.lineno, first.col_offset,
                                [edge.premise_revision for edge in edges])
            yield Route(first.value.value, Query(terminal, "integer-difference-v1", len(params), edges))

    validate(function.body)
    return list(routes(function.body))


def run(cvc5, lean):
    base = (HERE / "source.txt").read_bytes().decode("utf-8")
    sources = {"base": base, "comment": "# Same statements, distinct exact revision.\n" + base,
               "loosened": base.replace("x - z <= 1", "x - z <= 2")}
    recorded = {}
    for name, source in sources.items():
        routes = extract(source)
        hits = {route.query.identity: 0 for route in routes}
        for values in product(range(-3, 4), repeat=3):
            x, y, z = values
            limit = 2 if name == "loosened" else 1
            expected = "target" if y - x <= -1 and z - y <= -1 and x - z <= limit else "fallback"
            matched = [route for route in routes if all(
                values[edge.destination] - values[edge.source] <= edge.bound
                for edge in route.query.constraints)]
            assert len(matched) == 1 and matched[0].value == expected
            hits[matched[0].query.identity] += 1
        observations = []
        for route in routes:
            formula = route.query.formula()
            status = subprocess.check_output([cvc5, "--lang=smt2"], input=formula, text=True, timeout=15).strip()
            assert status == ("sat" if hits[route.query.identity] else "unsat")
            observations.append({"result": route.value, "route": route.query.identity, "solver": status,
                                 "formula_sha256": sha256(formula.encode()).hexdigest(),
                                 "finite_hits": hits[route.query.identity],
                                 "predicates": [edge.premise_revision for edge in route.query.constraints]})
        recorded[name] = observations

    queries = {name: next(route.query for route in extract(source) if route.value == "target")
               for name, source in sources.items()}
    old_proof = Certificate(queries["base"].identity, (0, 1, 2))
    assert classify(queries["base"], "unsat", old_proof) == ("infeasible", False)
    assert queries["base"].formula() == queries["comment"].formula()
    assert classify(queries["comment"], "unsat", old_proof) == ("unknown", True)
    assert classify(queries["comment"], "unsat", Certificate(queries["comment"].identity, old_proof.edges)) == ("infeasible", False)
    assert classify(queries["loosened"], "unsat", Certificate(queries["loosened"].identity, old_proof.edges)) == ("unknown", True)

    unsupported = {
        "loop": base.replace("if y - x", "while y - x", 1),
        "call": base.replace("y - x", "read(y) - x", 1),
        "assignment": base.replace("    if y", "    x = 4\n    if y", 1),
        "missing_exit": base.replace('    return "fallback"\n', ""),
    }
    rejected = {}
    for label, source in unsupported.items():
        try:
            extract(source)
        except Unsupported as error:
            rejected[label] = str(error)
        else:
            raise AssertionError(label)
    axioms = subprocess.check_output([lean, "-DwarningAsError=true", HERE / "Polarity.lean"], text=True).splitlines()
    assert len(axioms) == 1 and "sorryAx" not in axioms[0]
    return {
        "schema": "rt03-immutable-source-difference-routes-v1", "baseline": BASELINE,
        "python": platform.python_version(), "source_revisions": {name: sha256(src.encode()).hexdigest() for name, src in sources.items()},
        "tools": {"lean": subprocess.check_output([lean, "--version"], text=True).strip(),
                  "cvc5": subprocess.check_output([cvc5, "--version"], text=True).splitlines()[0]},
        "inputs_per_source": 7 ** 3, "observations": recorded, "rejected_sources": rejected,
        "lean_axioms": axioms, "same_formula_rejects_old_certificate": True,
        "changed_bound_rejects_refreshed_negative_cycle": True,
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                          for path in (HERE / "run.py", HERE / "Polarity.lean", CERTIFICATE / "checker.py",
                                       POLICY / "rt03_feasibility_outcomes.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cvc5", required=True)
    parser.add_argument("--lean", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.cvc5, args.lean), indent=2, sort_keys=True))
