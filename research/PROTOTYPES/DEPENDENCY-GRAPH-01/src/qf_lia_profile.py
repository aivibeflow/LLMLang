"""Conservative QF_LIA candidate-query builder; it does not prove program correctness."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Any, Mapping, Sequence
from .formal_core import (Assign, Binary, Call, Const, Emit, Function, If, Program,
                          Raise, Return, State, Store, Unary, Var, UnsupportedConstruct)
from .qf_lia_ir import Declaration, RelationalQuery, Term, render_smt2

PROFILE_VERSION = "llmlang-qf-lia-relational/2"
VALIDATOR_VERSION = "qf-lia-profile-validator/2"
ENCODER_VERSION = "qf-lia-relational-encoder/2"
OBSERVATION_CONTRACT = "return-and-selected-state/1"

@dataclass(frozen=True)
class FactorQuery:
    factor: str
    query_ir: RelationalQuery
    query_ir_digest: str
    smt2: str
    query_sha256: str

@dataclass(frozen=True)
class QFLIAAnalysis:
    status: str
    profile_version: str
    validator_version: str
    encoder_version: str
    ir_digest: str
    factors: tuple[FactorQuery, ...]
    observation_contract: str
    limitation: str


def _literal(value: Any) -> Term:
    if type(value) is bool: return Term("bool", "Bool", atom=value)
    if type(value) is int: return Term("int", "Int", atom=value)
    raise UnsupportedConstruct(f"QF_LIA accepts only exact Bool/Int values, got {type(value).__name__}")


def _is_int_literal(node: Any) -> bool:
    return isinstance(node, Const) and type(node.value) is int


def _canonical(value: Any) -> Any:
    if value is None or type(value) in (bool, int, str): return value
    if isinstance(value, (tuple, list)): return [_canonical(x) for x in value]
    if isinstance(value, dict): return {str(k): _canonical(value[k]) for k in sorted(value)}
    if hasattr(value, "__dataclass_fields__"):
        return {"node": type(value).__name__, **{k: _canonical(getattr(value, k)) for k in value.__dataclass_fields__}}
    raise UnsupportedConstruct(f"non-canonical IR value: {type(value).__name__}")


def _digest(value: Any) -> str:
    raw = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


class _ValidatorEncoder:
    def __init__(self, program: Program, inputs: Mapping[str, Term],
                 initial_state: Mapping[str, Any], initial_locals: Mapping[str, Any]):
        if not isinstance(program, Program): raise UnsupportedConstruct("expected Program AST")
        self.program = program
        self.functions = dict(program.functions)
        self.called_functions: set[str] = set()
        if any(not isinstance(k, str) or not k or not isinstance(v, Function) for k, v in self.functions.items()):
            raise UnsupportedConstruct("invalid function declaration")
        self.env = dict(inputs)
        if set(self.env) & set(initial_locals): raise UnsupportedConstruct("local shadows input")
        self.env.update({k: _literal(v) for k, v in initial_locals.items()})
        self.state = {k: _literal(v) for k, v in initial_state.items()}
        self._validate_function_graph()

    def _validate_function_graph(self) -> None:
        graph = {}
        def walk_expr(node, owner):
            if isinstance(node, (Const, Var, State)): return
            if isinstance(node, Unary): walk_expr(node.value, owner); return
            if isinstance(node, Binary):
                if node.op not in {"add", "sub", "mul", "eq", "lt", "le", "and", "or"}:
                    raise UnsupportedConstruct(f"unsupported operator: {node.op}")
                if node.op == "mul" and not (_is_int_literal(node.left) or _is_int_literal(node.right)):
                    raise UnsupportedConstruct("multiplication requires an integer literal operand")
                walk_expr(node.left, owner); walk_expr(node.right, owner); return
            if isinstance(node, Call):
                if node.function not in self.functions: raise UnsupportedConstruct(f"unknown function: {node.function}")
                graph[owner].add(node.function)
                fn = self.functions[node.function]
                if len(node.args) != len(fn.params): raise UnsupportedConstruct("function arity mismatch")
                for arg in node.args: walk_expr(arg, owner)
                return
            raise UnsupportedConstruct(f"unsupported expression node: {type(node).__name__}")
        graph = {name: set() for name in self.functions}
        for name, fn in self.functions.items():
            if len(set(fn.params)) != len(fn.params) or any(not isinstance(p, str) or not p for p in fn.params):
                raise UnsupportedConstruct("invalid function parameters")
            walk_expr(fn.body, name)
        visiting, visited = set(), set()
        def visit(name):
            if name in visiting: raise UnsupportedConstruct("recursive calls unsupported")
            if name in visited: return
            visiting.add(name)
            for child in graph[name]: visit(child)
            visiting.remove(name); visited.add(name)
        for name in graph: visit(name)

    def expr(self, node, env=None, state=None, stack=()) -> Term:
        env = self.env if env is None else env
        state = self.state if state is None else state
        if isinstance(node, Const): return _literal(node.value)
        if isinstance(node, Var):
            if node.name not in env: raise UnsupportedConstruct(f"unbound variable: {node.name}")
            return env[node.name]
        if isinstance(node, State):
            if node.region not in state: raise UnsupportedConstruct(f"unknown state region: {node.region}")
            return state[node.region]
        if isinstance(node, Unary):
            value = self.expr(node.value, env, state, stack)
            if node.op == "not" and value.sort == "Bool": return Term("not", "Bool", (value,))
            if node.op == "neg" and value.sort == "Int": return Term("neg", "Int", (value,))
            raise UnsupportedConstruct(f"ill-typed/unsupported unary operator: {node.op}")
        if isinstance(node, Binary):
            left = self.expr(node.left, env, state, stack)
            right = self.expr(node.right, env, state, stack)
            if left.sort != right.sort: raise UnsupportedConstruct("binary operand sort mismatch")
            if node.op == "mul":
                if left.sort != "Int" or not (_is_int_literal(node.left) or _is_int_literal(node.right)):
                    raise UnsupportedConstruct("multiplication requires an integer literal operand")
                return Term("mul", "Int", (left, right))
            if node.op in ("add", "sub") and left.sort == "Int": return Term(node.op, "Int", (left, right))
            if node.op == "eq" and left.sort in ("Int", "Bool"): return Term("eq", "Bool", (left, right))
            if node.op in ("lt", "le") and left.sort == "Int": return Term(node.op, "Bool", (left, right))
            if node.op in ("and", "or") and left.sort == "Bool": return Term(node.op, "Bool", (left, right))
            raise UnsupportedConstruct(f"ill-typed/unsupported binary operator: {node.op}")
        if isinstance(node, Call):
            if node.function not in self.functions: raise UnsupportedConstruct(f"unknown function: {node.function}")
            if node.function in stack: raise UnsupportedConstruct("recursive calls unsupported")
            self.called_functions.add(node.function)
            fn = self.functions[node.function]
            args = tuple(self.expr(a, env, state, stack) for a in node.args)
            if len(args) != len(fn.params): raise UnsupportedConstruct("function arity mismatch")
            return self.expr(fn.body, dict(zip(fn.params, args)), {}, stack + (node.function,))
        raise UnsupportedConstruct(f"unsupported expression node: {type(node).__name__}")

    def block(self, commands, env=None, state=None):
        env = dict(self.env if env is None else env); state = dict(self.state if state is None else state)
        for command in commands:
            if isinstance(command, Assign):
                if command.name not in env: raise UnsupportedConstruct(f"assignment to undeclared local: {command.name}")
                value = self.expr(command.value, env, state)
                if value.sort != env[command.name].sort: raise UnsupportedConstruct("assignment sort mismatch")
                env[command.name] = value
            elif isinstance(command, Store):
                if command.region not in state: raise UnsupportedConstruct(f"write to undeclared state region: {command.region}")
                value = self.expr(command.value, env, state)
                if value.sort != state[command.region].sort: raise UnsupportedConstruct("state write sort mismatch")
                state[command.region] = value
            elif isinstance(command, If):
                condition = self.expr(command.condition, env, state)
                if condition.sort != "Bool": raise UnsupportedConstruct("if condition must be Bool")
                then_env, then_state = self.block(command.then_body, env, state)
                else_env, else_state = self.block(command.else_body, env, state)
                if then_env.keys() != else_env.keys() or then_state.keys() != else_state.keys():
                    raise UnsupportedConstruct("branch environments differ")
                env = {k: self._ite(condition, then_env[k], else_env[k]) for k in env}
                state = {k: self._ite(condition, then_state[k], else_state[k]) for k in state}
            elif isinstance(command, (Return, Emit, Raise)):
                raise UnsupportedConstruct("nested Return/Emit/Raise are unsupported")
            else: raise UnsupportedConstruct(f"unsupported command: {type(command).__name__}")
        return env, state

    @staticmethod
    def _ite(condition: Term, yes: Term, no: Term) -> Term:
        if condition.sort != "Bool" or yes.sort != no.sort: raise UnsupportedConstruct("ill-typed branch merge")
        return Term("ite", yes.sort, (condition, yes, no))

    def observations(self, visible: Sequence[str]):
        if not self.program.body or not isinstance(self.program.body[-1], Return):
            raise UnsupportedConstruct("program must end with one top-level Return")
        if any(isinstance(c, (Return, Emit, Raise)) for c in self.program.body[:-1]):
            raise UnsupportedConstruct("only final top-level Return is supported")
        env, state = self.block(self.program.body[:-1])
        result = self.expr(self.program.body[-1].value, env, state)
        unused = set(self.functions) - self.called_functions
        if unused:
            raise UnsupportedConstruct("function bodies must be reachable and type-checked: " + ", ".join(sorted(unused)))
        return {"return": result, **{f"state:{r}": state[r] for r in visible}}


def build_qf_lia_queries(program: Program, input_types: Mapping[str, str],
                         initial_state: Mapping[str, Any] | None = None,
                         observable_state: Sequence[str] = (),
                         initial_locals: Mapping[str, Any] | None = None) -> QFLIAAnalysis:
    """Build strict QF_LIA candidate queries; no solver/proof claim is made."""
    if not input_types: raise UnsupportedConstruct("at least one input is required")
    if any(not isinstance(n, str) or not n or s not in ("Int", "Bool") for n, s in input_types.items()):
        raise UnsupportedConstruct("input sorts must be Bool or Int")
    initial_state, initial_locals = dict(initial_state or {}), dict(initial_locals or {})
    if any(not isinstance(n, str) or not n for n in (*initial_state.keys(), *initial_locals.keys())):
        raise UnsupportedConstruct("initial state/local names must be non-empty strings")
    if set(input_types) & set(initial_locals): raise UnsupportedConstruct("local shadows input")
    visible = tuple(sorted(set(observable_state)))
    if any(not isinstance(r, str) or r not in initial_state for r in visible):
        raise UnsupportedConstruct("observable state must be initialized")
    for value in (*initial_state.values(), *initial_locals.values()): _literal(value)
    ir = {"body": program.body, "functions": dict(program.functions), "input_types": dict(input_types),
          "initial_state": initial_state, "initial_locals": initial_locals, "observable_state": visible}
    ir_digest = _digest(ir)
    factors = []
    source_names = sorted(input_types)
    smt_names = {name: f"i_{index}" for index, name in enumerate(source_names)}
    for factor in source_names:
        declarations, left_inputs, right_inputs = [], {}, {}
        for name in source_names:
            base, sort = smt_names[name], input_types[name]
            if name == factor:
                declarations.extend((Declaration(base + "_L", sort), Declaration(base + "_R", sort)))
                left_inputs[name], right_inputs[name] = Term("symbol", sort, atom=base + "_L"), Term("symbol", sort, atom=base + "_R")
            else:
                declarations.append(Declaration(base, sort))
                left_inputs[name] = right_inputs[name] = Term("symbol", sort, atom=base)
        left = _ValidatorEncoder(program, left_inputs, initial_state, initial_locals)
        right = _ValidatorEncoder(program, right_inputs, initial_state, initial_locals)
        left_obs, right_obs = left.observations(visible), right.observations(visible)
        if left_obs.keys() != right_obs.keys(): raise UnsupportedConstruct("observation shape mismatch")
        factor_difference = Term("not", "Bool", (Term("eq", "Bool", (left_inputs[factor], right_inputs[factor])),))
        observation_terms = [Term("not", "Bool", (Term("eq", "Bool", (left_obs[k], right_obs[k])),)) for k in left_obs]
        if not observation_terms: raise UnsupportedConstruct("empty observation boundary")
        observations_differ = observation_terms[0] if len(observation_terms) == 1 else Term("or", "Bool", tuple(observation_terms))
        query_ir = RelationalQuery(factor, tuple(declarations), factor_difference, observations_differ, OBSERVATION_CONTRACT)
        query_ir_digest = _digest(query_ir)
        smt = render_smt2(query_ir)
        factors.append(FactorQuery(factor, query_ir, query_ir_digest, smt, hashlib.sha256(smt.encode()).hexdigest()))
    return QFLIAAnalysis("QF_LIA_CANDIDATE_QUERIES", PROFILE_VERSION, VALIDATOR_VERSION, ENCODER_VERSION, ir_digest, tuple(factors),
        OBSERVATION_CONTRACT, "Candidate queries only: validator, encoder, source correspondence, CPC binding, and proof checking are not formally verified.")
