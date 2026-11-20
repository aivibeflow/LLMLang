"""SMT-LIB relational dependency checker for the restricted Scenario 26 core.

The backend deliberately uses the SMT-LIB process interface so the module has no
Python package dependency. A Z3 executable (or another SMT-LIB 2 solver) is needed
for actual proofs. Unsupported syntax, solver absence, timeout, and solver unknown
are reported as UNKNOWN, never as independence.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import subprocess
from typing import Any, Mapping, Sequence
from src.formal_core import Assign, Binary, Call, Const, Emit, If, Program, Raise, Return, State, Store, Unary, Var, UnsupportedConstruct

SUPPORTED_SORTS = {"Int", "Bool", "String"}

@dataclass(frozen=True)
class SymbolicFactorResult:
    factor: str
    status: str
    witness: tuple[Mapping[str, Any], Mapping[str, Any]] | None = None
    changed_observations: tuple[str, ...] = ()
    reason: str | None = None

@dataclass(frozen=True)
class SymbolicAnalysis:
    status: str
    factors: tuple[SymbolicFactorResult, ...]
    smt_queries: tuple[tuple[str, str], ...]
    scope: str
    limitation: str | None = None

@dataclass(frozen=True)
class Term:
    text: str
    sort: str

def _literal(value: Any) -> Term:
    if type(value) is bool:
        return Term("true" if value else "false", "Bool")
    if type(value) is int:
        return Term(str(value) if value >= 0 else f"(- {abs(value)})", "Int")
    if isinstance(value, str):
        return Term('"' + value.replace('"', '""') + '"', "String")
    raise UnsupportedConstruct(f"unsupported literal type: {type(value).__name__}")

def _ite(condition: Term, yes: Term, no: Term) -> Term:
    if condition.sort != "Bool" or yes.sort != no.sort:
        raise UnsupportedConstruct("ill-typed conditional merge")
    return Term(f"(ite {condition.text} {yes.text} {no.text})", yes.sort)

class _Encoder:
    def __init__(self, program: Program, input_terms: Mapping[str, Term],
                 initial_state: Mapping[str, Any], initial_locals: Mapping[str, Any]):
        self.program = program
        self.env = dict(input_terms)
        if set(self.env) & set(initial_locals):
            raise UnsupportedConstruct("local names must not shadow input names")
        self.env.update({k: _literal(v) for k, v in initial_locals.items()})
        self.state = {k: _literal(v) for k, v in initial_state.items()}
        self.functions = dict(program.functions)

    def expr(self, node, env=None, state=None, stack=()) -> Term:
        env = self.env if env is None else env
        state = self.state if state is None else state
        if isinstance(node, Const):
            return _literal(node.value)
        if isinstance(node, Var):
            if node.name not in env:
                raise UnsupportedConstruct(f"unbound variable: {node.name}")
            return env[node.name]
        if isinstance(node, State):
            if node.region not in state:
                raise UnsupportedConstruct(f"unknown state region: {node.region}")
            return state[node.region]
        if isinstance(node, Unary):
            value = self.expr(node.value, env, state, stack)
            if node.op == "not" and value.sort == "Bool":
                return Term(f"(not {value.text})", "Bool")
            if node.op == "neg" and value.sort == "Int":
                return Term(f"(- {value.text})", "Int")
            raise UnsupportedConstruct(f"unsupported or ill-typed unary operator: {node.op}")
        if isinstance(node, Binary):
            left = self.expr(node.left, env, state, stack)
            right = self.expr(node.right, env, state, stack)
            if left.sort != right.sort:
                raise UnsupportedConstruct("binary operand sort mismatch")
            if node.op in ("add", "sub", "mul") and left.sort == "Int":
                op = {"add": "+", "sub": "-", "mul": "*"}[node.op]
                return Term(f"({op} {left.text} {right.text})", "Int")
            if node.op == "eq" and left.sort in SUPPORTED_SORTS:
                return Term(f"(= {left.text} {right.text})", "Bool")
            if node.op in ("lt", "le") and left.sort == "Int":
                op = "<" if node.op == "lt" else "<="
                return Term(f"({op} {left.text} {right.text})", "Bool")
            if node.op in ("and", "or") and left.sort == right.sort == "Bool":
                return Term(f"({node.op} {left.text} {right.text})", "Bool")
            raise UnsupportedConstruct(f"unsupported or ill-typed binary operator: {node.op}")
        if isinstance(node, Call):
            if node.function not in self.functions:
                raise UnsupportedConstruct(f"unknown function: {node.function}")
            if node.function in stack:
                raise UnsupportedConstruct("recursive calls unsupported")
            fn = self.functions[node.function]
            args = tuple(self.expr(a, env, state, stack) for a in node.args)
            if len(args) != len(fn.params):
                raise UnsupportedConstruct("function arity mismatch")
            return self.expr(fn.body, dict(zip(fn.params, args)), {},
                             stack + (node.function,))
        raise UnsupportedConstruct(f"unsupported expression: {type(node).__name__}")

    def block(self, commands, env=None, state=None):
        env = dict(self.env if env is None else env)
        state = dict(self.state if state is None else state)
        for command in commands:
            if isinstance(command, Assign):
                if command.name not in env:
                    raise UnsupportedConstruct(f"assignment to undeclared local: {command.name}")
                value = self.expr(command.value, env, state)
                if value.sort != env[command.name].sort:
                    raise UnsupportedConstruct("assignment sort mismatch")
                env[command.name] = value
            elif isinstance(command, Store):
                if command.region not in state:
                    raise UnsupportedConstruct(f"write to undeclared state region: {command.region}")
                value = self.expr(command.value, env, state)
                if value.sort != state[command.region].sort:
                    raise UnsupportedConstruct("state write sort mismatch")
                state[command.region] = value
            elif isinstance(command, If):
                condition = self.expr(command.condition, env, state)
                if condition.sort != "Bool":
                    raise UnsupportedConstruct("if condition must be Bool")
                then_env, then_state = self.block(command.then_body, env, state)
                else_env, else_state = self.block(command.else_body, env, state)
                if then_env.keys() != else_env.keys() or then_state.keys() != else_state.keys():
                    raise UnsupportedConstruct("branch environments differ")
                env = {k: _ite(condition, then_env[k], else_env[k]) for k in env}
                state = {k: _ite(condition, then_state[k], else_state[k]) for k in state}
            elif isinstance(command, (Return, Emit, Raise)):
                raise UnsupportedConstruct("nested Return/Emit/Raise are not supported")
            else:
                raise UnsupportedConstruct(f"unsupported command: {type(command).__name__}")
        return env, state

    def observations(self):
        if not self.program.body or not isinstance(self.program.body[-1], Return):
            raise UnsupportedConstruct("program must end with one top-level Return")
        if any(isinstance(c, (Return, Emit, Raise)) for c in self.program.body[:-1]):
            raise UnsupportedConstruct("only the final top-level Return is supported")
        env, state = self.block(self.program.body[:-1])
        result = self.expr(self.program.body[-1].value, env, state)
        return {"return": result, "outcome": Term('"return"', "String")}, state

def _parse_scalar(text: str, sort: str):
    text = text.strip()
    if sort == "Bool":
        if text == "true": return True
        if text == "false": return False
    if sort == "Int":
        if re.fullmatch(r"-?\d+", text): return int(text)
        m = re.fullmatch(r"\(-\s+(\d+)\)", text)
        if m: return -int(m.group(1))
    if sort == "String" and text.startswith('"') and text.endswith('"'):
        return text[1:-1].replace('""', '"')
    return text

def _extract_values(output: str, symbols: Mapping[str, str]) -> dict[str, Any]:
    values = {}
    for symbol, sort in symbols.items():
        pattern = r"\(\s*" + re.escape(symbol) + r"\s+((?:\(-\s+\d+\))|(?:\"(?:[^\"]|\"\")*\")|[^()\s]+)\s*\)"
        match = re.search(pattern, output)
        if match:
            values[symbol] = _parse_scalar(match.group(1), sort)
    return values

def _run_solver(smt: str, command: Sequence[str], timeout_seconds: float,
                symbols: Mapping[str, str]):
    # SMT-LIB permits get-value only after check-sat returned sat. Run the
    # satisfiability query first, and request a model in a second identical
    # solver session only after a SAT response.
    try:
        completed = subprocess.run(list(command), input=smt, text=True,
                                   capture_output=True, timeout=timeout_seconds, check=False)
    except FileNotFoundError:
        return "UNKNOWN", None, "SMT solver executable not found"
    except subprocess.TimeoutExpired:
        return "UNKNOWN", None, "SMT solver timeout"
    if completed.returncode not in (0, 1):
        return "UNKNOWN", None, f"SMT solver exited with code {completed.returncode}"
    output = completed.stdout.strip()
    first = output.splitlines()[0].strip() if output else ""
    if first == "unsat": return "UNSAT", None, None
    if first == "unknown": return "UNKNOWN", None, "SMT solver returned unknown"
    if first != "sat": return "UNKNOWN", None, "unrecognized SMT solver response"
    if not symbols:
        return "SAT", {}, None
    model_query = smt.rstrip() + "\n(get-value (" + " ".join(symbols) + "))\n"
    try:
        model_run = subprocess.run(list(command), input=model_query, text=True,
                                   capture_output=True, timeout=timeout_seconds, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "SAT", None, "SAT confirmed by solver; model retrieval failed"
    if model_run.returncode not in (0, 1):
        return "SAT", None, "SAT confirmed by solver; model retrieval process failed"
    model_output = model_run.stdout.strip()
    model_first = model_output.splitlines()[0].strip() if model_output else ""
    if model_first != "sat":
        return "SAT", None, "SAT confirmed by solver; model retrieval response invalid"
    return "SAT", _extract_values(model_output, symbols), None

def analyze_symbolically(program: Program, input_types: Mapping[str, str],
                         initial_state: Mapping[str, Any] | None = None,
                         observable_state: Sequence[str] = (),
                         solver_command: Sequence[str] = ("z3", "-in", "-smt2"),
                         timeout_seconds: float = 5.0,
                         initial_locals: Mapping[str, Any] | None = None) -> SymbolicAnalysis:
    """Prove influence/independence over unbounded supported SMT domains."""
    if not input_types:
        raise ValueError("at least one input type is required")
    if any(sort not in SUPPORTED_SORTS for sort in input_types.values()):
        raise ValueError("input sorts must be Int, Bool, or String")
    initial_state = dict(initial_state or {})
    initial_locals = dict(initial_locals or {})
    visible = tuple(sorted(set(observable_state)))
    if any(k not in initial_state for k in visible):
        raise ValueError("observable state must be initialized")
    factor_results, queries = [], []
    for factor in sorted(input_types):
        decls, left_inputs, right_inputs, symbols_for_model = {}, {}, {}, {}
        source_to_smt = {name: f"in_{i}" for i, name in enumerate(sorted(input_types))}
        for name, sort in sorted(input_types.items()):
            base = source_to_smt[name]
            if name == factor:
                l, r = f"{base}_L", f"{base}_R"
                decls[l] = sort; decls[r] = sort
                left_inputs[name], right_inputs[name] = Term(l, sort), Term(r, sort)
                symbols_for_model[l] = sort; symbols_for_model[r] = sort
            else:
                decls[base] = sort
                left_inputs[name] = right_inputs[name] = Term(base, sort)
                symbols_for_model[base] = sort
        try:
            left_encoder = _Encoder(program, left_inputs, initial_state, initial_locals)
            right_encoder = _Encoder(program, right_inputs, initial_state, initial_locals)
            left_obs, left_state = left_encoder.observations()
            right_obs, right_state = right_encoder.observations()
            for region in visible:
                left_obs[f"state:{region}"] = left_state[region]
                right_obs[f"state:{region}"] = right_state[region]
            if left_obs.keys() != right_obs.keys():
                raise UnsupportedConstruct("observation shape mismatch")
            differences = [f"(not (= {left_obs[k].text} {right_obs[k].text}))" for k in left_obs]
            factor_diff = f"(not (= {left_inputs[factor].text} {right_inputs[factor].text}))"
            query = f"(assert {factor_diff})\n"
            query += "(assert (or " + " ".join(differences) + "))\n(check-sat)\n"
            declarations = "\n".join(f"(declare-const {n} {s})" for n, s in decls.items())
            smt = "(set-logic ALL)\n" + declarations + "\n" + query
        except UnsupportedConstruct as exc:
            factor_results.append(SymbolicFactorResult(factor, "UNKNOWN", reason=str(exc)))
            continue
        status, model, reason = _run_solver(smt, solver_command, timeout_seconds, symbols_for_model)
        queries.append((factor, smt))
        if status == "UNSAT":
            factor_results.append(SymbolicFactorResult(factor, "SOLVER_REPORTED_UNSAT"))
        elif status == "SAT":
            witness = None
            if model is not None and all(k in model for k in symbols_for_model):
                left = {n: model[f"{source_to_smt[n]}_L"] if n == factor else model[source_to_smt[n]] for n in input_types}
                right = {n: model[f"{source_to_smt[n]}_R"] if n == factor else model[source_to_smt[n]] for n in input_types}
                witness = (left, right)
            changed = []
            for observation in sorted(left_obs):
                out_query = f"(assert {factor_diff})\n"
                out_query += f"(assert (not (= {left_obs[observation].text} {right_obs[observation].text})))\n(check-sat)\n"
                out_smt = "(set-logic ALL)\n" + declarations + "\n" + out_query
                out_status, _, _ = _run_solver(out_smt, solver_command, timeout_seconds, {})
                queries.append((factor + ":" + observation, out_smt))
                if out_status == "SAT": changed.append(observation)
                elif out_status == "UNKNOWN": changed.append("UNKNOWN:" + observation)
            factor_results.append(SymbolicFactorResult(
                factor, "SOLVER_REPORTED_SAT", witness, tuple(changed),
                None if witness else "solver model could not be decoded"))
        else:
            factor_results.append(SymbolicFactorResult(factor, "UNKNOWN", reason=reason))
    statuses = {r.status for r in factor_results}
    overall = ("SOLVER_COMPLETED_WITHIN_SYMBOLIC_FRAGMENT"
               if statuses and statuses <= {"SOLVER_REPORTED_UNSAT", "SOLVER_REPORTED_SAT"}
               else "UNKNOWN")
    return SymbolicAnalysis(
        overall, tuple(factor_results), tuple(queries),
        "unbounded Int/Bool/String values; deterministic straight-line/conditional core; fixed initial state; declared observations",
        "No loops, recursion, effects/events, errors, dynamic dispatch, aliasing, concurrency, or source/compiler correspondence.")
