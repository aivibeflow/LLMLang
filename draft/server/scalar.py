"""Bridge the server's scalar package rows to the existing frontend and verifier."""

from collections import defaultdict
import json
import keyword
import os
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from draft.server.scalar_verification import contract, frontend, verify

TYPES = {"i64": "int", "bool": "bool"}
CONTRACT_TYPES = {"i64": "I64", "bool": "Bool"}
OPERATORS = {*frontend.ARITHMETIC_OPERATORS.values(), *frontend.COMPARISON_OPERATORS.values()}
CALL_FIELDS = {"callee_impl_hash", "required_contract_hash", "arguments"}


def identifier(value):
    if (
        not isinstance(value, str)
        or not frontend.IDENTIFIER.fullmatch(value)
        or keyword.iskeyword(value)
        or value.startswith("builtin__")
    ):
        raise ValueError(f"invalid scalar identifier {value!r}")
    return value


def signature(value):
    if (
        not isinstance(value, dict)
        or value.keys() != {"params", "result"}
        or not isinstance(value["params"], list)
        or value["result"] not in TYPES
    ):
        raise ValueError("expected a scalar signature with params and result")
    parameters = []
    seen = set()
    for pair in value["params"]:
        if not isinstance(pair, list) or len(pair) != 2 or pair[1] not in TYPES:
            raise ValueError("expected [name, scalar_type] in signature")
        name = identifier(pair[0])
        if name in seen:
            raise ValueError(f"duplicate parameter {name!r}")
        seen.add(name)
        parameters.append((name, pair[1]))
    return parameters, value["result"]


def clauses(rows):
    declarations = set()
    requirements, guarantees = [], []
    error_guards = defaultdict(list)
    for row in rows:
        kind = row["kind"]
        label = row.get("error_label")
        predicate = row.get("predicate")
        if row.get("check_boundary") is not None:
            raise ValueError("state contract check boundaries are outside the scalar profile")
        if kind == "error_declaration" and isinstance(label, str) and predicate is None:
            if label in declarations:
                raise ValueError(f"duplicate error declaration {label!r}")
            declarations.add(label)
            continue
        if type(predicate) is bool:
            predicate = str(predicate)
        if not isinstance(predicate, str):
            raise ValueError("a scalar contract predicate must be a string or Bool")
        if kind == "requires" and label is None:
            requirements.append(predicate)
        elif kind == "ensures" and label is None:
            guarantees.append(predicate)
        elif kind == "error_guard" and isinstance(label, str):
            error_guards[label].append(predicate)
        else:
            raise ValueError(f"invalid scalar contract rule {kind!r}")
    if error_guards.keys() - declarations:
        raise ValueError("error guard references an undeclared error")
    return requirements, guarantees, {
        name: sorted(error_guards[name]) for name in sorted(declarations)
    }


def by_hash(tables, table, field):
    index = {}
    for row in tables[table].values():
        key = row[field]
        if key in index:
            raise ValueError(f"duplicate {field} in {table}")
        index[key] = row
    return index


def read_contracts(tables):
    by_contract = defaultdict(list)
    for row in tables["contract_rules"].values():
        by_contract[row["contract_hash"]].append(row)
    result = {}
    for identity, row in by_hash(tables, "contracts", "contract_hash").items():
        if (
            row["contract_kind"] != "function"
            or row["profile"] != contract.PROFILE
            or row.get("state_signature") is not None
        ):
            raise ValueError("unsupported contract kind or profile")
        parameters, returns = signature(row["typed_signature"])
        requires, ensures, errors = clauses(by_contract.pop(identity, ()))
        result[identity] = contract.parse_contract({
            "parameters": {name: CONTRACT_TYPES[kind] for name, kind in parameters},
            "returns": CONTRACT_TYPES[returns],
            "requires": sorted(requires),
            "ensures": sorted(ensures),
            "errors": errors,
        })
    if by_contract:
        raise ValueError("contract rule references a missing contract")
    return result


def call_pins(node):
    if isinstance(node, dict):
        if node.keys() != CALL_FIELDS:
            raise ValueError("a scalar call requires exact callee and contract pins and arguments")
        yield node["callee_impl_hash"], node["required_contract_hash"]
        yield from call_pins(node["arguments"])
    elif isinstance(node, list):
        for child in node:
            yield from call_pins(child)


def expression(node, aliases):
    match node:
        case {"callee_impl_hash": callee, "required_contract_hash": required,
              "arguments": list(arguments)} if node.keys() == CALL_FIELDS:
            name = aliases[callee, required]
            args = ", ".join(expression(child, aliases) for child in arguments)
            return f"{name}({args})"
        case ["i64", value] if type(value) is int and frontend.MIN_I64 <= value <= frontend.MAX_I64:
            return str(value)
        case ["bool", value] if type(value) is bool:
            return str(value)
        case ["var", name]:
            return identifier(name)
        case ["bin", operator, left, right] if operator in OPERATORS:
            return f"({expression(left, aliases)} {operator} {expression(right, aliases)})"
        case _:
            raise ValueError(f"invalid scalar expression {node!r}")


def block(nodes, aliases, depth=1):
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("expected a nonempty scalar body or then branch")
    indent = "    " * depth
    lines = []
    for statement in nodes:
        match statement:
            case ["let", name, value]:
                lines.append(indent + f"{identifier(name)} = {expression(value, aliases)}")
            case ["return", value]:
                lines.append(indent + f"return {expression(value, aliases)}")
            case ["fail", name] if name in frontend.ERROR_NAMES:
                lines.append(indent + f"return builtin__fail({json.dumps(name)})")
            case ["if", condition, yes, list(no)]:
                lines.append(indent + f"if {expression(condition, aliases)}:")
                lines.extend(block(yes, aliases, depth + 1))
                if no:
                    lines.append(indent + "else:")
                    lines.extend(block(no, aliases, depth + 1))
            case _:
                raise ValueError(f"invalid scalar statement {statement!r}")
    return lines


def view_package(package, version_hash):
    tables = package["tables"]
    functions = by_hash(tables, "functions", "impl_hash")
    interfaces = by_hash(tables, "interfaces", "interface_hash")
    contracts = read_contracts(tables)
    pairs = {
        (identity, row["provided_contract_hash"]) for identity, row in functions.items()
    }
    calls = set()
    for caller, row in functions.items():
        for callee, required in call_pins(row["canonical_body"]):
            pairs.add((callee, required))
            calls.add((caller, callee, required))

    export_names = {}
    for row in tables["bindings"].values():
        interface = interfaces[row["interface_hash"]]
        pair = (row["impl_hash"], interface["public_contract_hash"])
        pairs.add(pair)
        if version_hash == row["version_hash"]:
            name = interface["name"]
            if export_names.setdefault(name, row["interface_hash"]) != row["interface_hash"]:
                raise ValueError(f"multiple revisions of export {name!r} in selected version")

    aliases = {pair: f"function_{index}" for index, pair in enumerate(sorted(pairs))}
    definitions = {}
    provided_hashes = {}
    source = []
    for (identity, required), alias in aliases.items():
        if identity not in functions:
            raise ValueError(f"missing scalar implementation {identity}")
        row = functions[identity]
        provided = row["provided_contract_hash"]
        for pin in (required, provided):
            if pin not in contracts:
                raise ValueError(f"missing scalar contract {pin}")
        params, result = signature(row["typed_signature"])
        for pin in (required, provided):
            checked = contracts[pin]
            params_expected = tuple((name, CONTRACT_TYPES[kind]) for name, kind in params)
            if checked.parameters != params_expected or checked.returns != CONTRACT_TYPES[result]:
                raise ValueError(f"contract {pin} does not match implementation {identity}")
        definitions[alias] = {"provided": contracts[provided], "public": contracts[required]}
        provided_hashes[alias] = contract.contract_hash(contracts[provided])
        formals = ", ".join(f"{name}: {TYPES[value_type]}" for name, value_type in params)
        source.append(f"def {alias}({formals}) -> {TYPES[result]}:")
        source.extend(block(row["canonical_body"], aliases))

    if source:
        program = frontend.parse(
            "\n".join(source) + "\n", provided_contract_hashes=provided_hashes,
        )
    else:
        program = {"schema": frontend.SCHEMA, "functions": {}}
    return program, definitions, aliases, functions, calls, contracts


def handle(request):
    action = request["action"]
    if action not in {"validate", "verify"}:
        return {"ok": False, "code": "InvalidArguments", "message": "unknown scalar action"}
    program, definitions, aliases, functions, calls, contracts = view_package(
        request["package"], request.get("version_hash"),
    )
    entry_identity = request.get("entry_impl_hash")
    if entry_identity is not None:
        target = functions.get(entry_identity)
        if target is None or signature(target["typed_signature"])[0]:
            raise ValueError("an executable entry point must be a parameterless scalar implementation")
    if action == "validate":
        return {"ok": True}
    if not functions:
        return {"ok": False, "code": "ValidationFailed", "message": "package contains no functions"}

    report = verify.verify(
        program, definitions, boogie=os.environ.get("BOOGIE", "boogie"),
        z3=os.environ.get("Z3"), timeout=30,
    )
    report["contract_ir"] = {identity: value.to_ir() for identity, value in sorted(contracts.items())}
    report["identities"] = {
        alias: {
            "implementation_hash": implementation,
            "required_or_public_contract_hash": required,
            "provided_contract_hash": functions[implementation]["provided_contract_hash"],
        }
        for (implementation, required), alias in aliases.items()
    }
    report["calls"] = [
        {
            "caller_impl_hash": caller, "callee_impl_hash": callee,
            "required_contract_hash": required,
        }
        for caller, callee, required in sorted(calls)
    ]
    if report["status"] == "VERIFIED":
        return {"ok": True, "report": report}
    return {
        "ok": False, "code": "VerificationFailed",
        "message": f"scalar verification returned {report['status']}", "report": report,
    }


def main():
    try:
        result = handle(json.load(sys.stdin))
    except (TypeError, ValueError, KeyError, RecursionError) as error:
        result = {"ok": False, "code": "ValidationFailed", "message": str(error)}
    print(json.dumps(result, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
