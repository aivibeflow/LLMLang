"""Check typed transfer of an independently certified UNSAT core and SAT witness."""
import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from subprocess import run
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


@dataclass(frozen=True)
class Symbol:
    role: str
    spelling: str
    sort: str


@dataclass(frozen=True)
class Query:
    symbols: tuple[Symbol, ...]
    clauses: tuple[tuple[str, tuple], ...]


def var(name):
    return ("var", name)


def lit(value):
    return ("lit", value)


def equal(left, right):
    return ("eq", left, right)


def sort_of(value):
    if type(value) is bool:
        return "Bool"
    if type(value) is int:
        return "Int"
    raise ValueError("outside literal domain")


def normalize(term, globals_, locals_=()):
    match term:
        case ("var", identifier):
            for level, (name, sort) in enumerate(reversed(locals_)):
                if identifier == name:
                    return ("local", sort, level)
            if identifier not in globals_:
                raise ValueError("unresolved variable")
            symbol = globals_[identifier]
            return ("free", symbol.sort, symbol.role)
        case ("lit", value):
            return ("literal", sort_of(value), value)
        case ("eq", left, right):
            first = normalize(left, globals_, locals_)
            second = normalize(right, globals_, locals_)
            if first[1] != second[1]:
                raise ValueError("equality type mismatch")
            return ("equal", "Bool", first, second)
        case ("not", value):
            parsed = normalize(value, globals_, locals_)
            if parsed[1] != "Bool":
                raise ValueError("Boolean condition expected")
            return ("not", "Bool", parsed)
        case ("let", identifier, bound, body):
            if not NAME.fullmatch(identifier):
                raise ValueError("invalid binder")
            initial = normalize(bound, globals_, locals_)
            parsed = normalize(body, globals_, (*locals_, (identifier, initial[1])))
            return ("let", parsed[1], initial, parsed)
        case _:
            raise ValueError("unsupported expression")


def typed(query):
    symbols = {item.spelling: item for item in query.symbols}
    roles = {item.role: item.sort for item in query.symbols}
    if len(symbols) != len(query.symbols) or len(roles) != len(query.symbols):
        raise ValueError("duplicate symbol or role")
    if any(not NAME.fullmatch(item.spelling) or item.sort not in {"Bool", "Int"} for item in query.symbols):
        raise ValueError("invalid symbol declaration")
    clauses = {name: normalize(term, symbols) for name, term in query.clauses}
    if len(clauses) != len(query.clauses) or any(not NAME.fullmatch(name) for name in clauses):
        raise ValueError("duplicate or invalid assertion label")
    if any(term[1] != "Bool" for term in clauses.values()):
        raise ValueError("non-Boolean assertion")
    return roles, clauses


def evaluate(term, model, locals_=()):
    match term:
        case ("literal", _, value):
            return value
        case ("local", _, index):
            return locals_[-1 - index]
        case ("free", _, role):
            return model[role]
        case ("equal", _, left, right):
            return evaluate(left, model, locals_) == evaluate(right, model, locals_)
        case ("not", _, child):
            return not evaluate(child, model, locals_)
        case ("let", _, bound, body):
            return evaluate(body, model, (*locals_, evaluate(bound, model, locals_)))
        case _:
            raise ValueError("unsupported checked expression")


def witness(query, model):
    roles, conditions = typed(query)
    if model.keys() != roles.keys():
        return False
    literal_types = {"Int": int, "Bool": bool}
    if any(type(model[role]) is not literal_types[kind] for role, kind in roles.items()):
        return False
    return all(evaluate(term, model) for term in conditions.values())


def syntax(term):
    match term:
        case ("var", name):
            return name
        case ("lit", True):
            return "true"
        case ("lit", False):
            return "false"
        case ("lit", value):
            return str(value) if value >= 0 else f"(- {-value})"
        case ("eq", left, right):
            return f"(= {syntax(left)} {syntax(right)})"
        case ("not", condition):
            return f"(not {syntax(condition)})"
        case ("let", name, initial, body):
            return f"(let (({name} {syntax(initial)})) {syntax(body)})"
        case _:
            raise ValueError("unsupported expression")


def render(query, purpose="verdict"):
    typed(query)
    lines = ["(set-logic QF_LIA)"]
    if purpose == "core":
        lines.append("(set-option :produce-unsat-cores true)")
    lines += [f"(declare-const {symbol.spelling} {symbol.sort})" for symbol in query.symbols]
    for label, term in query.clauses:
        rendered = syntax(term)
        if purpose == "core":
            rendered = f"(! {rendered} :named {label})"
        lines.append("(assert " + rendered + ")")
    lines.append("(check-sat)")
    if purpose == "core":
        lines.append("(get-unsat-core)")
    if purpose == "model":
        lines.append("(get-value (" + " ".join(item.spelling for item in query.symbols) + "))")
    return "\n".join([*lines, "(exit)", ""]).encode()


def launch(tool, directory, *arguments):
    result = run([tool, *arguments], cwd=directory, capture_output=True, timeout=20,
                 env={**os.environ, "LC_ALL": "C"})
    assert result.returncode == 0, (result.stdout, result.stderr)
    return result.stdout


def machine_query(tool, query, directory, args=(), *, purpose="verdict"):
    script = directory / "Request.smt2"
    script.write_bytes(render(query, purpose))
    return launch(tool, directory, *args, script)


def certified_core(tools, core, directory):
    src = directory / "ProofScope.smt2"
    src.write_bytes(render(core))
    transcript = launch(tools.cvc5, directory, "--produce-proofs", "--proof-format-mode=alethe",
                        "--proof-alethe-res-pivots", "--dump-proofs", src)
    lines = transcript.splitlines()
    assert lines[:2] == [b"unsat", b"("] and lines[-1] == b")"
    proof = directory / "ProofScope.alethe"
    proof.write_bytes(b"\n".join(lines[2:-1]) + b"\n")
    assert launch(tools.carcara, directory, "check", proof, src).strip() == b"valid"
    return {"query": render(core).decode(), "certificate": proof.read_text(),
            "query_sha256": sha256(render(core)).hexdigest(),
            "certificate_sha256": sha256(proof.read_bytes()).hexdigest()}


def allows_transfer(old_core, new, checked_core):
    if checked_core is None or checked_core["query_sha256"] != sha256(render(old_core)).hexdigest():
        return False
    old_roles, needed = typed(old_core)
    new_roles, actual = typed(new)
    return old_roles == new_roles and set(needed.values()) <= set(actual.values())


def scoped(name="x", guarded="enabled", spare="other", *, required=3, excluded=3, guard=True):
    return Query((Symbol("value", name, "Int"), Symbol("guard", guarded, "Bool"),
                  Symbol("spare", spare, "Int")),
                 (("required", equal(var(name), lit(required))),
                  ("excluded", ("not", equal(var(name), lit(excluded)))),
                  ("guarded", equal(var(guarded), lit(guard))),
                  ("spare", equal(var(spare), lit(2)))))


def atom_renaming():
    bindings = {item.spelling: item for item in scoped().symbols}
    original = ("let", "local", var("x"), equal(var("local"), lit(3)))
    shadowing = ("let", "x", var("x"), equal(var("x"), lit(3)))
    assert normalize(original, bindings) == normalize(shadowing, bindings)
    with_free = ("let", "local", var("x"), equal(var("local"), var("other")))
    captured = ("let", "other", var("x"), equal(var("other"), var("other")))
    normalized_free, normalized_captured = (normalize(term, bindings) for term in (with_free, captured))
    assert normalized_free != normalized_captured
    model = {"value": 3, "guard": True, "spare": 2}
    assert evaluate(normalized_free, model) is False and evaluate(normalized_captured, model) is True
    return {"same_typed_local_after_renaming": True, "capture_changes_value": True}


def source_model(tools, query, directory):
    output = machine_query(tools.z3, query, directory, ("-smt2",), purpose="model").decode()
    assert output.startswith("sat\n")
    entries = re.findall(r"\(([A-Za-z][A-Za-z0-9_]*) (true|false|[0-9]+)\)", output)
    values = {label: value == "true" if value in {"true", "false"} else int(value) for label, value in entries}
    assert len(values) == len(query.symbols)
    return {item.role: values[item.spelling] for item in query.symbols}


def check(tools, directory):
    original = scoped()
    labels = machine_query(tools.cvc5, original, directory, purpose="core").decode().split()
    assert labels[:2] == ["unsat", "("] and labels[-1] == ")"
    retained = set(labels[2:-1])
    assert retained == {"required", "excluded"}
    core = replace(original, clauses=tuple(row for row in original.clauses if row[0] in retained))
    proof = certified_core(tools, core, directory)
    sat = scoped(excluded=7)
    renamed_sat = scoped("number", "flag", "spare_int", excluded=7)
    alpha = scoped("number", "flag", "spare_int")
    swapped_roles = replace(original, symbols=(
        replace(original.symbols[0], role="spare"), original.symbols[1],
        replace(original.symbols[2], role="value"),
    ))
    complete_witness = source_model(tools, sat, directory)
    cases = (
        ("original", original, "unsat", True, False),
        ("reordered-assertions", replace(original, clauses=tuple(reversed(original.clauses))), "unsat", True, False),
        ("typed-alpha-renaming", alpha, "unsat", True, False),
        ("stronger", replace(original, clauses=(*original.clauses, ("new_fact", lit(True)))), "unsat", True, False),
        ("different-unsat", scoped(required=7, excluded=7), "unsat", False, False),
        ("different-free-roles", swapped_roles, "unsat", False, False),
        ("removed-core-assertion", replace(original, clauses=tuple(row for row in original.clauses if row[0] != "excluded")), "sat", False, True),
        ("sat", sat, "sat", False, True),
        ("renamed-sat", renamed_sat, "sat", False, True),
        ("sat-with-different-guard", scoped(excluded=7, guard=False), "sat", False, False),
    )
    observations = {}
    for label, query, verdict, transfer, replay in cases:
        found = machine_query(tools.cvc5, query, directory).decode().strip()
        independent = machine_query(tools.z3, query, directory, ("-smt2",)).decode().strip()
        assert found == independent == verdict
        promoted = allows_transfer(core, query, proof)
        old_witness = witness(query, complete_witness)
        assert (promoted, old_witness) == (transfer, replay), (label, promoted, old_witness)
        observations[label] = {"cvc5": found, "z3": independent, "old_core": promoted,
                               "old_complete_witness": old_witness,
                               "query_sha256": sha256(render(query)).hexdigest()}
    fresh_other = scoped(required=7, excluded=7)
    fresh_certificate = certified_core(tools, replace(fresh_other, clauses=fresh_other.clauses[:2]), directory)
    assert fresh_certificate["certificate"] != proof["certificate"]
    assert not allows_transfer(core, original, None)
    assert not allows_transfer(core, original, fresh_certificate)
    assert not witness(sat, {"value": 3, "guard": True})
    assert not witness(sat, {**complete_witness, "value": True})
    wrong_sort = replace(original, symbols=(replace(original.symbols[0], sort="Bool"), *original.symbols[1:]))
    try:
        typed(wrong_sort)
    except ValueError as error:
        assert "type mismatch" in str(error)
    else:
        raise AssertionError("incorrect type preserved")
    kernel = launch(tools.lean, directory, "-DwarningAsError=true", HERE / "Transfer.lean").decode().splitlines()
    assert len(kernel) == 3 and all("does not depend on any axioms" in line for line in kernel)
    return {
        "retained_core_labels": sorted(retained), "base_core": proof, "fresh_core_after_change": fresh_certificate,
        "obs": observations, "witness": complete_witness, "alpha_controls": atom_renaming(),
        "additional_refusals": ["unchecked-original-core", "other-proven-core", "incomplete-model",
                                "wrong-model-sort", "changed-symbol-sort"],
        "lean_axioms": kernel,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cvc5", "carcara", "z3", "lean", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    tools = parser.parse_args()
    identities = {}
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for field in ("cvc5", "carcara", "z3", "lean"):
            binary = getattr(tools, field).resolve(strict=True)
            setattr(tools, field, binary)
            identities[field] = {"version": launch(binary, root, "--version").decode().splitlines()[0],
                                 "sha256": sha256(binary.read_bytes()).hexdigest()}
        result = check(tools, root)
    tools.output.write_text(json.dumps({"tools": identities, **result}, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
