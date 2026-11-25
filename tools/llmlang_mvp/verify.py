"""Generate scalar LLMLang obligations and check them with Boogie and Z3."""

import ast
from hashlib import sha256
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
from tempfile import TemporaryDirectory

from .contract import contract_hash
from .frontend import _digest


MIN_I64 = -(2**63)
MAX_I64 = 2**63 - 1
COMPARISONS = {
    ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
    ast.Gt: ">", ast.GtE: ">=",
}
ARITHMETIC = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}
BPL_TYPES = {"i64": "int", "bool": "bool"}
SUPPORT = """\
function {:inline} magnitude(x: int): int { (if x < 0 then -x else x) }
function {:inline} quotient(a: int, b: int): int {
  (if b == 0 then 0 else
    (if (a < 0) != (b < 0) then -(magnitude(a) div magnitude(b))
     else magnitude(a) div magnitude(b)))
}
"""


class Unsupported(ValueError):
    """A construct outside the verifier's supported scalar profile."""


def conjunction(clauses):
    return "(" + " && ".join(clauses) + ")" if clauses else "true"


def bounded(value):
    return f"({MIN_I64} <= {value} && {value} <= {MAX_I64})"


def contract_expr(expr, names):
    if isinstance(expr, ast.Constant):
        if type(expr.value) is bool:
            return str(expr.value).lower()
        if type(expr.value) is int:
            return str(expr.value)
    if isinstance(expr, ast.Name) and expr.id in names:
        return names[expr.id]
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, (ast.Not, ast.USub)):
        operator = "!" if isinstance(expr.op, ast.Not) else "-"
        return f"({operator}{contract_expr(expr.operand, names)})"
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, (ast.And, ast.Or)):
        operator = " && " if isinstance(expr.op, ast.And) else " || "
        return "(" + operator.join(contract_expr(item, names) for item in expr.values) + ")"
    if isinstance(expr, ast.BinOp) and type(expr.op) in ARITHMETIC:
        left, right = (contract_expr(item, names) for item in (expr.left, expr.right))
        return f"({left} {ARITHMETIC[type(expr.op)]} {right})"
    if isinstance(expr, ast.Compare) and all(type(op) in COMPARISONS for op in expr.ops):
        values = [contract_expr(item, names) for item in (expr.left, *expr.comparators)]
        return conjunction([
            f"({left} {COMPARISONS[type(op)]} {right})"
            for left, op, right in zip(values, expr.ops, values[1:])
        ])
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name)
            and expr.func.id == "quotient" and len(expr.args) == 2 and not expr.keywords):
        args = ", ".join(contract_expr(arg, names) for arg in expr.args)
        return f"quotient({args})"
    raise Unsupported(f"unsupported contract expression {ast.dump(expr)}")


def condition(clauses, names):
    return conjunction([contract_expr(expr, names) for expr in clauses])


def precondition(contract, args):
    names = dict(zip((name for name, _ in contract.parameters), args, strict=True))
    return condition(contract.requires, names)


def outcome(contract, args, errors):
    names = dict(zip((name for name, _ in contract.parameters), args, strict=True))
    success = condition(contract.ensures, dict(names, result="result_value"))
    alternatives = [f"(result_error == 0 && {success})"]
    alternatives.extend(
        f"(result_error == {errors[name]} && {condition(eq, names)})"
        for name, eq in contract.errors.items()
    )
    return "(" + " || ".join(alternatives) + ")"


def reachable_callees(node):
    if isinstance(node, list):
        if node and node[0] == "call":
            yield node[1]
        for part in node:
            yield from reachable_callees(part)


def check_call_graph(functions):
    checked = set()
    visiting = set()

    def visit(name):
        if name in checked:
            return
        if name in visiting:
            raise Unsupported(f"recursive proof dependency from {name}")
        visiting.add(name)
        fn = functions[name]
        payload = {key: value for key, value in fn.items() if key != "impl_hash"}
        if _digest(payload) != fn["impl_hash"]:
            raise Unsupported(f"SPG implementation hash does not match body of {name}")
        for callee in reachable_callees(fn["body"]):
            visit(callee)
        visiting.remove(name)
        checked.add(name)

    for name in functions:
        visit(name)


def error_names(body):
    for stmt in body:
        if stmt[0] == "fail":
            yield stmt[1]
        elif stmt[0] == "if":
            yield from error_names(stmt[2])
            yield from error_names(stmt[3])


class Procedure:
    def __init__(self, functions, contracts, procedure_names, errors):
        self.functions = functions
        self.contracts = contracts
        self.procedure_names = procedure_names
        self.errors = errors
        self.locals = []

    def local(self, typ):
        name = f"tmp_{len(self.locals)}"
        self.locals.append(f"  var {name}: {BPL_TYPES[typ]};")
        return name

    def emit_expr(self, expr, names, statements):
        kind, *parts = expr
        if kind == "i64":
            return str(parts[0]), "i64"
        if kind == "bool":
            return str(parts[0]).lower(), "bool"
        if kind == "var":
            return names[parts[0]]
        if kind == "call":
            callee, inputs, pin = parts
            target = self.functions[callee]
            if pin != target["impl_hash"]:
                raise Unsupported(f"mismatched implementation pin for {callee}")
            args = [self.emit_expr(arg, names, statements)[0] for arg in inputs]
            value = self.local(target["result"])
            error = self.local("i64")
            statements.append(f"assert {precondition(self.contracts[callee]['public'], args)};")
            statements.append(
                f"call {value}, {error} := {self.procedure_names[callee]}({', '.join(args)});"
            )
            statements.append(f"if ({error} != 0) {{ result_error := {error}; return; }}")
            return value, target["result"]
        if kind == "bin":
            operator, lhs, rhs = parts
            left, _ = self.emit_expr(lhs, names, statements)
            right, _ = self.emit_expr(rhs, names, statements)
            if operator in COMPARISONS.values():
                return f"({left} {operator} {right})", "bool"
            if operator == "/":
                self.fail_if(f"{right} == 0", "DivisionByZero", statements)
                term = f"quotient({left}, {right})"
            elif operator in ARITHMETIC.values():
                term = f"({left} {operator} {right})"
            else:
                raise Unsupported(f"unsupported operator {operator}")
            value = self.local("i64")
            statements.append(f"{value} := {term};")
            self.fail_if(f"!{bounded(value)}", "ArithmeticOverflow", statements)
            return value, "i64"
        raise Unsupported(f"unsupported program expression {kind}")

    def fail_if(self, predicate, error, statements):
        statements.append(
            f"if ({predicate}) {{ result_error := {self.errors[error]}; return; }}"
        )

    def emit_block(self, body, names, statements):
        names = names.copy()
        for kind, *parts in body:
            if kind == "let":
                name, expr = parts
                value, typ = self.emit_expr(expr, names, statements)
                target = self.local(typ)
                statements.append(f"{target} := {value};")
                names[name] = (target, typ)
            elif kind == "return":
                result, _ = self.emit_expr(parts[0], names, statements)
                statements.extend([f"result_value := {result};", "return;"])
            elif kind == "fail":
                statements.extend([f"result_error := {self.errors[parts[0]]};", "return;"])
            elif kind == "if":
                expr, yes, no = parts
                test, _ = self.emit_expr(expr, names, statements)
                statements.append(f"if ({test}) {{")
                for branch in (yes, no):
                    items = []
                    self.emit_block(branch, names, items)
                    statements.extend(f"  {line}" for line in items)
                    if branch is yes:
                        statements.append("} else {")
                statements.append("}")
            else:
                raise Unsupported(f"unsupported program statement {kind}")


def build_obligations(program, contracts):
    """Return Boogie source and the exact expected proof checks."""
    if program.get("schema") != "llmlang-spg/v1":
        raise Unsupported("unsupported program schema")
    functions = program["functions"]
    if not functions or functions.keys() != contracts.keys():
        raise Unsupported("every function must have an exact public/provided contract pair")
    check_call_graph(functions)
    names = {name: f"body_{index}" for index, name in enumerate(sorted(functions))}
    encountered = {"ArithmeticOverflow", "DivisionByZero"}
    for name, fn in functions.items():
        encountered.update(error_names(fn["body"]))
        for contract in contracts[name].values():
            encountered.update(contract.errors)
    errors = {name: index for index, name in enumerate(sorted(encountered), start=1)}
    declarations = [SUPPORT]
    checks = []
    for name, procedure_name in names.items():
        fn = functions[name]
        public, provided = (contracts[name][kind] for kind in ("public", "provided"))
        if fn["provided_contract_hash"] != contract_hash(provided):
            raise Unsupported(f"{name}: provided contract hash does not match SPG")
        parameters = tuple((param, typ.lower()) for param, typ in fn["params"])
        for kind, contract in (("public", public), ("provided", provided)):
            contract_parameters = tuple((key, typ.lower()) for key, typ in contract.parameters)
            if parameters != contract_parameters or fn["result"] != contract.returns.lower():
                raise Unsupported(f"{name}: {kind} contract signature does not match SPG")
        arguments = [f"arg_{index}" for index in range(len(parameters))]
        args = ", ".join(
            f"{symbol}: {BPL_TYPES[typ]}" for symbol, (_, typ)
            in zip(arguments, parameters, strict=True)
        )
        ranges = [
            bounded(symbol) for symbol, (_, typ) in zip(arguments, parameters, strict=True)
            if typ == "i64"
        ]
        names_in_body = {
            param: (symbol, typ)
            for symbol, (param, typ) in zip(arguments, parameters, strict=True)
        }
        pre_public = precondition(public, arguments)
        pre_provided = precondition(provided, arguments)
        post_public = outcome(public, arguments, errors)
        post_provided = outcome(provided, arguments, errors)
        return_type = BPL_TYPES[fn["result"]]
        result_range = bounded("result_value") if return_type == "int" else "true"
        proc = Procedure(functions, contracts, names, errors)
        default = "0" if return_type == "int" else "false"
        statements = [f"result_value := {default};", "result_error := 0;"]
        proc.emit_block(fn["body"], names_in_body, statements)
        # A front end bug admitting a fallthrough cannot lead to a proof of conformance.
        statements.append("assert false;")
        declarations.append("\n".join([
            f"procedure {procedure_name}({args}) returns (result_value: {return_type}, result_error: int)",
            f"  requires {conjunction(ranges)};",
            f"  requires {pre_provided};",
            f"  ensures {result_range};",
            f"  ensures {post_provided};",
            "{",
            *proc.locals,
            *(f"  {line}" for line in statements),
            "}",
        ]))
        refinement_name = procedure_name.replace("body_", "refinement_", 1)
        declarations.append("\n".join([
            f"procedure {refinement_name}({args})",
            f"  requires {conjunction(ranges)};",
            f"  requires {pre_public};",
            "{",
            f"  var result_value: {return_type};",
            "  var result_error: int;",
            f'  assert {{:msg "provider strengthens public preconditions"}} {pre_provided};',
            "  havoc result_value, result_error;",
            f"  assume {result_range};",
            f"  assume {post_provided};",
            f'  assert {{:msg "provider weakens public guarantees"}} {post_public};',
            "}",
        ]))
        checks.append({
            "function": name,
            "impl_hash": fn["impl_hash"],
            "public_contract_hash": contract_hash(public),
            "provided_contract_hash": contract_hash(provided),
            "body_procedure": procedure_name,
            "refinement_procedure": refinement_name,
        })
    return "\n\n".join(declarations) + "\n", checks


def verify(program, contracts, *, boogie="boogie", z3=None, timeout=30):
    """Verify the input snapshot under the Boogie + Z3 scalar evidence policy."""
    try:
        source, checks = build_obligations(program, contracts)
    except (Unsupported, ValueError, KeyError) as exc:
        return {"status": "UNSUPPORTED", "diagnostic": str(exc), "checks": []}
    boogie_path = shutil.which(boogie)
    z3_path = shutil.which(z3 or "z3")
    report = {
        "checks": checks,
        "boogie_source_sha256": sha256(source.encode()).hexdigest(),
        "timeout_seconds": timeout,
    }
    if not boogie_path or not z3_path:
        return dict(report, status="ERROR", diagnostic="Boogie and Z3 executables are required")
    try:
        tools = {}
        for label, executable, flag in (("Boogie", boogie_path, "/version"), ("Z3", z3_path, "--version")):
            version = subprocess.run(
                [executable, flag], capture_output=True, text=True, check=True, timeout=timeout,
            )
            tools[label] = {
                "version": version.stdout.strip(),
                "executable_sha256": sha256(Path(executable).read_bytes()).hexdigest(),
            }
        report["tools"] = tools
        with TemporaryDirectory(prefix="llmlang-proof-") as directory:
            p = Path(directory, "obligations.bpl")
            p.write_text(source, encoding="utf-8")
            with subprocess.Popen(
                [boogie_path, "/proverOpt:SOLVER=z3",
                 f"/proverOpt:PROVER_PATH={Path(z3_path).resolve()}",
                 "/proverWarnings:1", "/trace",
                 p.name],
                cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, start_new_session=True,
            ) as verifier:
                try:
                    stdout, stderr = verifier.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(verifier.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    verifier.communicate()
                    raise
                returncode = verifier.returncode
    except subprocess.TimeoutExpired:
        return dict(report, status="UNKNOWN", diagnostic="verification deadline exceeded")
    except (OSError, subprocess.CalledProcessError) as exc:
        return dict(report, status="ERROR", diagnostic=str(exc))
    output = stdout + stderr
    dispositions = dict(re.findall(
        r"(?m)^Verifying (\w+) \.\.\.\n(?:\[TRACE\][^\n]*\n)*"
        r"  \[[^\n]*\]  (\w+)",
        output,
    ))
    for check in checks:
        check["body"] = dispositions.get(check["body_procedure"], "unreported")
        check["refinement"] = dispositions.get(check["refinement_procedure"], "unreported")
    summary = re.search(r"finished with (\d+) verified, (\d+) errors?([^\n]*)", output)
    if re.search(r"timed out|out of (?:resources?|memory)|inconclusive", output, re.I):
        status = "UNKNOWN"
    elif re.search(r"prover (?:error|warning)|fatal error|internal error", output, re.I) or not summary:
        status = "ERROR"
    elif int(summary[2]):
        status = "REJECTED"
    elif (returncode == 0 and int(summary[1]) == 2 * len(checks)
          and all(check["body"] == check["refinement"] == "verified" for check in checks)):
        status = "VERIFIED"
    else:
        status = "ERROR"
    # Keep the solver's diagnostic but omit trace performance and local tool paths.
    diagnostic = "\n".join(
        line for line in output.splitlines()
        if not line.startswith(("  [", "[TRACE]", "Parsing "))
    ).strip()
    return dict(report, status=status, diagnostic=diagnostic)
