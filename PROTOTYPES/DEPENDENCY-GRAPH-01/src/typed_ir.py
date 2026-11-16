"""Strict type/shape validation for the Scenario 27 symbolic fragment."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Any, Mapping, Sequence
from .formal_core import Assign, Binary, Call, Const, Emit, Program, Raise, Return, State, Store, Unary, Var, UnsupportedConstruct

SEMANTICS_VERSION = "llmlang-symbolic-core/1"
VALIDATOR_VERSION = "typed-ir-validator/1"
SUPPORTED_SORTS = {"Int", "Bool", "String"}

@dataclass(frozen=True)
class TypedProgram:
    program: Program
    input_types: tuple[tuple[str, str], ...]
    initial_state_types: tuple[tuple[str, str], ...]
    initial_locals_types: tuple[tuple[str, str], ...]
    observable_state: tuple[str, ...]
    return_type: str
    semantics_version: str
    validator_version: str
    ir_digest: str
    initial_state_digest: str
    initial_locals_digest: str
    def manifest(self) -> dict[str, Any]:
        return {"ir_digest":self.ir_digest,"semantics_version":self.semantics_version,
                "validator_version":self.validator_version,"input_types":self.input_types,
                "initial_state_types":self.initial_state_types,"initial_locals_types":self.initial_locals_types,
                "observable_state":self.observable_state,"return_type":self.return_type,
                "initial_state_digest":self.initial_state_digest,
                "initial_locals_digest":self.initial_locals_digest}

def _canonical(value: Any):
    if value is None or type(value) in (bool,int,str): return value
    if isinstance(value,(tuple,list)): return [_canonical(x) for x in value]
    if isinstance(value,dict): return {str(k):_canonical(value[k]) for k in sorted(value)}
    if hasattr(value,"__dataclass_fields__"):
        return {"node":type(value).__name__,**{k:_canonical(getattr(value,k)) for k in value.__dataclass_fields__}}
    raise UnsupportedConstruct(f"non-canonical IR value: {type(value).__name__}")

def _digest(value: Any) -> str:
    raw=json.dumps(_canonical(value),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def validate_program(program: Program, input_types: Mapping[str,str],
                     initial_state: Mapping[str,Any]|None=None,
                     observable_state: Sequence[str]=(),
                     initial_locals: Mapping[str,Any]|None=None) -> TypedProgram:
    if not isinstance(program,Program): raise UnsupportedConstruct("expected Program AST")
    if not input_types: raise UnsupportedConstruct("at least one input is required")
    for name,sort in input_types.items():
        if not isinstance(name,str) or not name or not isinstance(sort,str) or sort not in SUPPORTED_SORTS:
            raise UnsupportedConstruct("invalid input declaration")
    state=dict(initial_state or {}); locals_=dict(initial_locals or {})
    if set(input_types)&set(locals_): raise UnsupportedConstruct("local shadows input")
    if any(not isinstance(n,str) or not n for n in (*state.keys(),*locals_.keys())):
        raise UnsupportedConstruct("invalid declaration name")
    def literal_sort(v):
        if type(v) is bool: return "Bool"
        if type(v) is int: return "Int"
        if isinstance(v,str): return "String"
        raise UnsupportedConstruct(f"unsupported scalar literal: {type(v).__name__}")
    env=dict(input_types)
    for n,v in locals_.items(): env[n]=literal_sort(v)
    state_types={n:literal_sort(v) for n,v in state.items()}
    functions=dict(program.functions)
    def expr(e,local_env,local_state,stack=()):
        if isinstance(e,Const): return literal_sort(e.value)
        if isinstance(e,Var):
            if e.name not in local_env: raise UnsupportedConstruct(f"unbound variable: {e.name}")
            return local_env[e.name]
        if isinstance(e,State):
            if e.region not in local_state: raise UnsupportedConstruct(f"unknown or inaccessible state region: {e.region}")
            return local_state[e.region]
        if isinstance(e,Unary):
            t=expr(e.value,local_env,local_state,stack)
            if e.op=="not" and t=="Bool": return "Bool"
            if e.op=="neg" and t=="Int": return "Int"
            raise UnsupportedConstruct(f"ill-typed/unsupported unary op {e.op}")
        if isinstance(e,Binary):
            a=expr(e.left,local_env,local_state,stack); b=expr(e.right,local_env,local_state,stack)
            if e.op in ("add","sub","mul","lt","le") and a==b=="Int":
                return "Bool" if e.op in ("lt","le") else "Int"
            if e.op in ("and","or") and a==b=="Bool": return "Bool"
            if e.op=="eq" and a==b: return "Bool"
            raise UnsupportedConstruct(f"ill-typed/unsupported binary op {e.op}: {a}, {b}")
        if isinstance(e,Call):
            if e.function not in functions: raise UnsupportedConstruct(f"unknown function {e.function}")
            if e.function in stack: raise UnsupportedConstruct("recursive calls unsupported")
            fn=functions[e.function]
            if len(set(fn.params))!=len(fn.params) or any(not isinstance(p,str) or not p for p in fn.params):
                raise UnsupportedConstruct("invalid function parameters")
            args=[expr(a,local_env,local_state,stack) for a in e.args]
            if len(args)!=len(fn.params): raise UnsupportedConstruct("function arity mismatch")
            return expr(fn.body,dict(zip(fn.params,args)),{},stack+(e.function,))
        raise UnsupportedConstruct(f"unsupported expression node {type(e).__name__}")
    def block(commands,e,s):
        e=dict(e); s=dict(s)
        for c in commands:
            if isinstance(c,Assign):
                if c.name not in e: raise UnsupportedConstruct(f"assignment target undeclared: {c.name}")
                if expr(c.value,e,s)!=e[c.name]: raise UnsupportedConstruct("assignment type mismatch")
            elif isinstance(c,Store):
                if c.region not in s: raise UnsupportedConstruct(f"state write undeclared: {c.region}")
                if expr(c.value,e,s)!=s[c.region]: raise UnsupportedConstruct("state write type mismatch")
            elif isinstance(c,If):
                if expr(c.condition,e,s)!="Bool": raise UnsupportedConstruct("if condition must be Bool")
                te,ts=block(c.then_body,e,s); ee,es=block(c.else_body,e,s)
                if te!=ee or ts!=es: raise UnsupportedConstruct("branch environments do not join")
                e,s=te,ts
            else: raise UnsupportedConstruct(f"unsupported nested command {type(c).__name__}")
        return e,s
    if not program.body or not isinstance(program.body[-1],Return):
        raise UnsupportedConstruct("program must end with a top-level Return")
    if any(isinstance(c,(Return,Emit,Raise)) for c in program.body[:-1]):
        raise UnsupportedConstruct("only final top-level Return is supported")
    final_env,final_state=block(program.body[:-1],env,state_types)
    return_type=expr(program.body[-1].value,final_env,final_state)
    visible=tuple(sorted(set(observable_state)))
    if any(x not in state_types for x in visible):
        raise UnsupportedConstruct("observable state region is not initialized")
    canonical={"body":program.body,"functions":functions,"input_types":dict(input_types),
               "initial_state":state,"initial_locals":locals_,"observable_state":visible}
    return TypedProgram(program,tuple(sorted(input_types.items())),tuple(sorted(state_types.items())),
        tuple(sorted((n,literal_sort(v)) for n,v in locals_.items())),visible,return_type,
        SEMANTICS_VERSION,VALIDATOR_VERSION,_digest(canonical),_digest(state),_digest(locals_))

def analyze_typed_symbolically(program: Program, input_types: Mapping[str,str],
                               initial_state: Mapping[str,Any]|None=None,
                               observable_state: Sequence[str]=(),
                               solver_command: Sequence[str]=("z3","-in","-smt2"),
                               timeout_seconds: float=5.0,
                               initial_locals: Mapping[str,Any]|None=None):
    """Validate the AST before the symbolic encoder is invoked."""
    typed=validate_program(program,input_types,initial_state,observable_state,initial_locals)
    from .symbolic_relational import analyze_symbolically
    result=analyze_symbolically(program,input_types,initial_state,observable_state,
                                solver_command,timeout_seconds,initial_locals)
    return typed,result
