"""Small typed transition interpreter, not a LLMLang execution engine."""
import re


class Unsupported(ValueError):
    pass


def validate(model):
    def need(ok,message):
        if not ok:
            raise Unsupported(message)
    def name(s):
        return isinstance(s,str) and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,31}",s) is not None
    def integer(x):
        return type(x) is int and abs(x)<=10**9
    need(isinstance(model,dict) and set(model)=={"initial","actions","events"},"model shape")
    initial,actions,events=model["initial"],model["actions"],model["events"]
    need(isinstance(initial,dict) and 0<len(initial)<=16 and all(name(k) and integer(v) for k,v in initial.items()),"initial registers")
    need(isinstance(actions,dict) and 0<len(actions)<=12 and all(name(k) for k in actions),"action names")
    need(isinstance(events,list) and len(events)<=16 and all(name(k) for k in events) and len(set(events))==len(events),"event names")
    nodes=0
    def tick(e,depth):
        nonlocal nodes
        nodes+=1
        need(nodes<=512 and depth<=16 and isinstance(e,list) and bool(e) and isinstance(e[0],str),"AST shape/bounds")
    def expr(e,d):
        tick(e,d)
        op=e[0]
        if op=="int" and len(e)==2 and integer(e[1]): return "int"
        if op=="reg" and len(e)==2 and name(e[1]) and e[1] in initial: return "int"
        if op in ("add","sub","eq","le","and","or") and len(e)==3:
            want="bool" if op in ("and","or") else "int"
            need(expr(e[1],d+1)==want and expr(e[2],d+1)==want,"operand type")
            return "int" if op in ("add","sub") else "bool"
        if op=="not" and len(e)==2 and expr(e[1],d+1)=="bool": return "bool"
        raise Unsupported("invalid expression")
    def stmts(block,d):
        need(isinstance(block,list) and len(block)<=64 and d<=16,"statement block")
        for s in block:
            tick(s,d)
            op=s[0]
            if op=="set" and len(s)==3:
                need(name(s[1]) and s[1] in initial and expr(s[2],d+1)=="int","set")
            elif op=="emit" and len(s)==3:
                need(name(s[1]) and s[1] in events and expr(s[2],d+1)=="int","emit")
            elif op=="if" and len(s)==4:
                need(expr(s[1],d+1)=="bool","guard")
                stmts(s[2],d+1); stmts(s[3],d+1)
            else:
                raise Unsupported("invalid statement")
    for block in actions.values(): stmts(block,0)


def execute(model,trace,initial=None):
    validate(model)
    return execute_validated(model,trace,initial)


def execute_validated(model,trace,initial=None):
    """Internal fast path: caller has validated the exact model."""
    if not isinstance(trace,(list,tuple)) or len(trace)>8 or any(not isinstance(a,str) or a not in model["actions"] for a in trace):
        raise Unsupported("trace outside declared action alphabet/bound")
    state=dict(model["initial"] if initial is None else initial)
    if set(state)!=set(model["initial"]) or any(type(v) is not int or abs(v)>10**9 for v in state.values()):
        raise Unsupported("initial override")
    def ev(e):
        op=e[0]
        if op=="int": return e[1]
        if op=="reg": return state[e[1]]
        if op=="not": return not ev(e[1])
        a,b=ev(e[1]),ev(e[2])
        if op=="add": return a+b
        if op=="sub": return a-b
        if op=="eq": return a==b
        if op=="le": return a<=b
        if op=="and": return a and b
        if op=="or": return a or b
        raise Unsupported(op)
    def block(code,events):
        for s in code:
            if s[0]=="set": state[s[1]]=ev(s[2])
            elif s[0]=="emit": events.append([s[1],ev(s[2])])
            else: block(s[2] if ev(s[1]) else s[3],events)
    history=[]
    for a in trace:
        events=[]
        block(model["actions"][a],events)
        history.append({"state":dict(state),"events":events})
    return history
