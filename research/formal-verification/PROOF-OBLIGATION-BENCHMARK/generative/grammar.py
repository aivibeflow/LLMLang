"""Typed closed finite formula interpreter, independent of template oracle."""
from itertools import product


class Unsupported(ValueError):
    pass


def validate(expr):
    nodes=0
    def walk(e, env, depth, qdepth):
        nonlocal nodes
        nodes+=1
        if depth>32 or nodes>256 or not isinstance(e,list) or not e or not isinstance(e[0],str):
            raise Unsupported("invalid or oversized expression")
        op=e[0]
        def literal(x):
            return type(x) is int and abs(x)<=10**9
        if op=="int" and len(e)==2 and literal(e[1]):
            return "int"
        if op=="var" and len(e)==2 and isinstance(e[1],str) and e[1] in env:
            return "int"
        if op in ("add","sub","eq","le","and","or","implies") and len(e)==3:
            want="int" if op in ("add","sub","eq","le") else "bool"
            if all(walk(x,env,depth+1,qdepth)==want for x in e[1:]):
                return "int" if op in ("add","sub") else "bool"
        if op=="not" and len(e)==2 and walk(e[1],env,depth+1,qdepth)=="bool":
            return "bool"
        if op in ("forall","exists") and len(e)==5:
            _,name,lo,hi,body=e
            if isinstance(name,str) and name.isidentifier() and name not in env and literal(lo) and literal(hi) and 0<=hi-lo<16 and qdepth<3:
                if walk(body,env|{name},depth+1,qdepth+1)=="bool":
                    return "bool"
        raise Unsupported("unknown operator, invalid type, scope or domain: "+str(op))
    if walk(expr,set(),0,0)!="bool":
        raise Unsupported("contract must be Boolean")


def evaluate(expr):
    validate(expr)
    def ev(e,env):
        op=e[0]
        if op=="int": return e[1]
        if op=="var": return env[e[1]]
        if op=="not": return not ev(e[1],env)
        if op in ("forall","exists"):
            _,name,lo,hi,body=e
            values=(ev(body,{**env,name:x}) for x in range(lo,hi+1))
            return all(values) if op=="forall" else any(values)
        a,b=ev(e[1],env),ev(e[2],env)
        if op=="add": return a+b
        if op=="sub": return a-b
        if op=="eq": return a==b
        if op=="le": return a<=b
        if op=="and": return a and b
        if op=="or": return a or b
        if op=="implies": return not a or b
        raise Unsupported(op)
    return ev(expr,{})


def outer_evidence(expr):
    """A false universal has a failing assignment; a false existential has an exhaustive absence record."""
    validate(expr)
    op=expr[0]
    if op not in ("forall","exists"):
        return {"kind":"closed_formula","value":evaluate(expr)}
    _,name,lo,hi,body=expr
    def substitute(e,x):
        if e[0]=="var" and e[1]==name:
            return ["int",x]
        if e[0] in ("forall","exists"):
            return e[:4]+[substitute(e[4],x)]
        return [e[0]]+[substitute(y,x) if isinstance(y,list) else y for y in e[1:]]
    values=[(x,evaluate(substitute(body,x))) for x in range(lo,hi+1)]
    if op=="forall":
        return {"kind":"failing_assignment","variable":name,"values":[x for x,ok in values if not ok]}
    return {"kind":"existential_domain_scan","variable":name,"values":[[x,ok] for x,ok in values]}
