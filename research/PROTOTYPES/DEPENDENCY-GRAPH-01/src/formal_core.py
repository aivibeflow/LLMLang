"""Finite semantic kernel for LLMLang Scenario 26; not a source verifier."""
from dataclasses import dataclass, field
from itertools import product
import math
from typing import Any, Iterable, Mapping

class CoreError(ValueError): pass
class UnsupportedConstruct(CoreError): pass
class Expr: pass
@dataclass(frozen=True)
class Const(Expr): value: Any
@dataclass(frozen=True)
class Var(Expr): name: str
@dataclass(frozen=True)
class State(Expr): region: str
@dataclass(frozen=True)
class Unary(Expr): op: str; value: Expr
@dataclass(frozen=True)
class Binary(Expr): op: str; left: Expr; right: Expr
@dataclass(frozen=True)
class Call(Expr): function: str; args: tuple[Expr, ...]
@dataclass(frozen=True)
class Function: params: tuple[str, ...]; body: Expr
class Command: pass
@dataclass(frozen=True)
class Assign(Command): name: str; value: Expr
@dataclass(frozen=True)
class Store(Command): region: str; value: Expr
@dataclass(frozen=True)
class Emit(Command): channel: str; value: Expr
@dataclass(frozen=True)
class If(Command): condition: Expr; then_body: tuple[Command, ...]; else_body: tuple[Command, ...] = ()
@dataclass(frozen=True)
class Return(Command): value: Expr
@dataclass(frozen=True)
class Raise(Command): error: Expr
@dataclass(frozen=True)
class Program: body: tuple[Command, ...]; functions: Mapping[str, Function] = field(default_factory=dict)
@dataclass(frozen=True)
class Observation:
    outcome: str
    result: Any
    error: Any
    state: tuple[tuple[str, Any], ...]
    events: tuple[tuple[str, Any], ...]
@dataclass(frozen=True)
class FactorResult:
    factor: str
    status: str
    witness: tuple[Mapping[str, Any], Mapping[str, Any]] | None = None
    observations: tuple[Observation, Observation] | None = None
    influenced_observations: tuple[str, ...] = ()
@dataclass(frozen=True)
class DependencyAnalysis:
    status: str
    factors: tuple[FactorResult, ...]
    may_depend_edges: tuple[tuple[str, str], ...]
    fallback_edges: tuple[tuple[str, str], ...]
    input_case_count: int
    scope: str
    limitation: str | None = None

def _eval(e, env, state, fns, stack=()):
    if isinstance(e, Const): return e.value
    if isinstance(e, Var):
        if e.name not in env: raise CoreError(f"unbound variable: {e.name}")
        return env[e.name]
    if isinstance(e, State):
        if e.region not in state: raise CoreError(f"unknown state region: {e.region}")
        return state[e.region]
    if isinstance(e, Unary):
        v = _eval(e.value, env, state, fns, stack)
        if e.op == "not": return not bool(v)
        if e.op == "neg": return -v
        raise UnsupportedConstruct(f"unsupported unary operator: {e.op}")
    if isinstance(e, Binary):
        a = _eval(e.left, env, state, fns, stack)
        if e.op == "and": return bool(a) and bool(_eval(e.right, env, state, fns, stack))
        if e.op == "or": return bool(a) or bool(_eval(e.right, env, state, fns, stack))
        b = _eval(e.right, env, state, fns, stack)
        ops = {"add": lambda:a+b, "sub":lambda:a-b, "mul":lambda:a*b,
               "eq":lambda:a==b, "lt":lambda:a<b, "le":lambda:a<=b}
        if e.op not in ops: raise UnsupportedConstruct(f"unsupported binary operator: {e.op}")
        return ops[e.op]()
    if isinstance(e, Call):
        if e.function not in fns: raise CoreError(f"unknown function: {e.function}")
        if e.function in stack: raise UnsupportedConstruct("recursive calls unsupported")
        fn = fns[e.function]
        args = tuple(_eval(x,env,state,fns,stack) for x in e.args)
        if len(args)!=len(fn.params): raise CoreError("wrong function arity")
        return _eval(fn.body,dict(zip(fn.params,args)),{},fns,stack+(e.function,))
    raise UnsupportedConstruct(f"unsupported expression: {type(e).__name__}")

def execute(program: Program, inputs: Mapping[str,Any], initial_state: Mapping[str,Any],
            observable_state: Iterable[str]) -> Observation:
    env,state,events=dict(inputs),dict(initial_state),[]
    outcome,result,error="return",None,None
    def run(commands):
        nonlocal outcome,result,error
        for c in commands:
            if isinstance(c,Assign): env[c.name]=_eval(c.value,env,state,program.functions)
            elif isinstance(c,Store):
                if c.region not in state: raise CoreError(f"unknown state region: {c.region}")
                state[c.region]=_eval(c.value,env,state,program.functions)
            elif isinstance(c,Emit): events.append((c.channel,_eval(c.value,env,state,program.functions)))
            elif isinstance(c,If):
                branch=c.then_body if _eval(c.condition,env,state,program.functions) else c.else_body
                if not run(branch): return False
            elif isinstance(c,Return): result=_eval(c.value,env,state,program.functions); return False
            elif isinstance(c,Raise): outcome,error="error",_eval(c.error,env,state,program.functions); return False
            else: raise UnsupportedConstruct(f"unsupported command: {type(c).__name__}")
        return True
    run(program.body)
    return Observation(outcome,result,error,tuple(sorted((r,state[r]) for r in observable_state)),tuple(events))

def _equal(a,b):
    if type(a) is not type(b): return False
    if isinstance(a,tuple): return len(a)==len(b) and all(_equal(x,y) for x,y in zip(a,b))
    return a==b

def _parts(o):
    d={"outcome":o.outcome,"return":o.result,"error":o.error,"events":o.events}
    d.update({f"state:{k}":v for k,v in o.state})
    return d

def analyze_dependencies(program: Program, input_domains: Mapping[str,Iterable[Any]],
                          initial_state: Mapping[str,Any] | None=None,
                          observable_state: Iterable[str]=(), max_input_cases: int=10000):
    domains={k:tuple(v) for k,v in input_domains.items()}
    if not domains: raise CoreError("at least one input factor is required")
    if any(not isinstance(k,str) or not k for k in domains): raise CoreError("invalid factor name")
    if any(not isinstance(v,(str,int,float,bool,type(None))) for d in domains.values() for v in d):
        raise CoreError("input values must be scalar")
    if any(isinstance(v,float) and not math.isfinite(v) for d in domains.values() for v in d):
        raise CoreError("input floats must be finite")
    state0=dict(initial_state or {})
    visible=tuple(sorted(set(observable_state)))
    if any(r not in state0 for r in visible): raise CoreError("observable state is uninitialized")
    names=tuple(sorted(domains))
    outs=("outcome","return","error","events",*(f"state:{r}" for r in visible))
    try:
        vals=[domains[n] for n in names]
        if any(not d for d in vals): raise CoreError("empty input domain")
        count=math.prod(map(len,vals))
        if count>max_input_cases: raise UnsupportedConstruct("finite input budget exceeded")
        rows=[dict(zip(names,xs)) for xs in product(*vals)]
        obs={tuple(row[n] for n in names):execute(program,row,state0,visible) for row in rows}
    except UnsupportedConstruct as exc:
        fallback=tuple((p,o) for p in names for o in outs)
        return DependencyAnalysis("UNKNOWN",tuple(FactorResult(p,"UNKNOWN") for p in names),
                                  (),fallback,0,"finite-core",str(exc))
    results,edges=[],[]
    for p in names:
        other=tuple(n for n in names if n!=p)
        groups={}
        for row in rows:
            key=tuple((type(row[n]).__name__,row[n]) for n in other)
            groups.setdefault(key,[]).append((row,obs[tuple(row[n] for n in names)]))
        witness=witness_obs=None
        influenced=set()
        for group in groups.values():
            for i in range(len(group)):
                for j in range(i+1,len(group)):
                    a,oa=group[i]; b,ob=group[j]
                    if _equal(a[p],b[p]): continue
                    pa,pb=_parts(oa),_parts(ob)
                    changed={k for k in pa if not _equal(pa[k],pb[k])}
                    if changed:
                        influenced.update(changed)
                        if witness is None: witness,witness_obs=(dict(a),dict(b)),(oa,ob)
        if witness is None: results.append(FactorResult(p,"FINITE_MODEL_INDEPENDENCE"))
        else:
            changed=tuple(sorted(influenced))
            results.append(FactorResult(p,"FINITE_MODEL_INFLUENCE",witness,witness_obs,changed))
            edges.extend((p,o) for o in changed)
    return DependencyAnalysis("DECIDED_WITHIN_FINITE_MODEL",tuple(results),tuple(edges),(),len(rows),
                              "complete finite domain; deterministic core; pinned state and observations")
