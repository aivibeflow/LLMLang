"""Transition candidate templates. Does not import the interpreter or oracle."""
from itertools import product,combinations

FAMILIES=("transfer","lifetime","reservation","authorized_effect","cancel_cleanup","retry","deadline","interleaving","security_trace")
VARIANTS=("reference","mutation","alternative")
I=lambda n:["int",n]
R=lambda n:["reg",n]
def B(op,a,b): return [op,a,b]
def S(n,x): return ["set",n,x]
def E(n,x): return ["emit",n,x]
def IF(cond,a,b=None): return ["if",cond,a,[] if b is None else b]
def eq(n,v): return B("eq",R(n),I(v))
def add(n,v): return B("add",R(n),I(v))
def sub(n,v): return B("sub",R(n),I(v))


def model(f,k,v):
    mut=v=="mutation"; alt=v=="alternative"
    if f=="transfer":
        debit=S("a",sub("a",1))
        credit=S("b",add("b",1))
        return {"initial":{"a":k,"b":0},"events":["commit","reject"],"actions":{
            "transfer":[IF(B("le",I(1),R("a")),([credit,debit] if alt else [debit,credit])+[E("commit",I(1))],[E("reject",I(0))])],
            "fail":[debit,E("reject",I(0))] if mut else [E("reject",I(0))]}}
    if f=="lifetime":
        valid=eq("live",1) if mut else B("and",eq("live",1),B("eq",R("generation"),R("captured")))
        if alt: valid=["not",B("or",eq("live",0),["not",B("eq",R("generation"),R("captured"))])]
        return {"initial":{"generation":k,"captured":k,"live":1,"value":k},"events":["value","absent"],"actions":{
            "free":[S("live",I(0))],"allocate":[IF(eq("live",0),[S("generation",add("generation",1)),S("value",add("value",1)),S("live",I(1))])],
            "read":[IF(valid,[E("value",R("value"))],[E("absent",I(0))])]}}
    if f=="reservation":
        actions={}
        for t in (0,1):
            n="held"+str(t)
            guard=eq(n,0) if mut else B("and",eq(n,0),B("le",B("add",R("used"),I(1)),R("capacity")))
            if alt: guard=B("and",eq(n,0),B("le",R("used"),sub("capacity",1)))
            actions["acquire"+str(t)]=[IF(guard,[S(n,I(1)),S("used",add("used",1)),E("grant",I(t))],[E("reject",I(t))])]
            actions["release"+str(t)]=[IF(eq(n,1),[S(n,I(0)),S("used",sub("used",1)),E("release",I(t))])]
        return {"initial":{"capacity":k,"used":k-1,"held0":0,"held1":0},"events":["grant","reject","release"],"actions":actions}
    if f=="authorized_effect":
        allowed=[S("value",add("value",1)),E("write",R("value"))]
        if alt: allowed=[E("write",add("value",1)),S("value",add("value",1))]
        return {"initial":{"value":k},"events":["write","denied"],"actions":{"authorized":allowed,"unauthorized":allowed if mut else [E("denied",I(0))]}}
    if f=="cancel_cleanup":
        cleanup=[S("live",I(0)),E("release",R("weight"))]
        if alt: cleanup=[E("release",R("weight")),S("live",I(0))]
        return {"initial":{"live":1,"weight":k,"done":0},"events":["release","completed","cancelled"],"actions":{
            "complete":[IF(eq("done",0),cleanup+[S("done",I(1)),E("completed",I(0))])],
            "cancel":[IF(eq("done",0),([] if mut else cleanup)+[S("done",I(2)),E("cancelled",I(0))])]}}
    if f=="retry":
        actions={}
        for t in (0,1):
            n="seen"+str(t)
            first=[S(n,I(1)),S("balance",add("balance",1)),E("ack",I(t))]
            if alt: first=[S("balance",add("balance",1)),S(n,I(1)),E("ack",I(t))]
            actions["deliver"+str(t)]=first if mut else [IF(eq(n,0),first,[E("ack",I(t))])]
        return {"initial":{"balance":k,"seen0":0,"seen1":0},"events":["ack"],"actions":actions}
    if f=="deadline":
        # Each tick is a discrete clock advance. Request expires at absolute deadline.
        overdue=B("le",add("deadline",int(mut)),R("clock"))
        if alt: overdue=["not",B("le",R("clock"),sub("deadline",1))]
        return {"initial":{"clock":k,"deadline":k+2,"status":0},"events":["served","timeout"],"actions":{
            "tick":[S("clock",add("clock",1)),IF(B("and",eq("status",0),overdue),[S("status",I(2)),E("timeout",R("clock"))])],
            "service":[IF(eq("status",0),[S("status",I(1)),E("served",R("clock"))])]}}
    if f=="interleaving":
        actions={}
        for t in (0,1):
            n="read"+str(t)
            actions[n]=[S(n,R("counter"))]
            update=B("add",R(n),I(1)) if mut else add("counter",1)
            if alt: update=B("sub",R("counter"),I(-1))
            actions["write"+str(t)]=[S("counter",update),E("done",I(t))]
        return {"initial":{"counter":k,"read0":k,"read1":k},"events":["done"],"actions":actions}
    if f=="security_trace":
        obs=B("add",R("public"),R("secret")) if mut else R("public")
        if alt: obs=B("sub",R("public"),I(0))
        return {"initial":{"public":k,"secret":0},"events":["output"],"actions":{"observe":[E("output",obs)],"advance":[S("public",add("public",1))]}}
    raise ValueError(f)


def scenarios(f,k):
    """Declared finite domains; no scheduler assumptions beyond listed actions."""
    if f=="interleaving":
        # All six schedules preserving each thread's read-before-write order.
        for pos in combinations(range(4),2):
            a,b=iter(("read0","write0")),iter(("read1","write1"))
            yield {},[next(a) if i in pos else next(b) for i in range(4)]
        return
    alphabet={
        "transfer":("transfer","fail"),"lifetime":("free","allocate","read"),
        "reservation":("acquire0","acquire1","release0","release1"),
        "authorized_effect":("authorized","unauthorized"),
        "cancel_cleanup":("complete","cancel"),"retry":("deliver0","deliver1"),
        "deadline":("tick","service"),"security_trace":("observe","advance")}[f]
    for length in range(4):
        for trace in product(alphabet,repeat=length):
            if f=="security_trace":
                for secret in (0,1): yield {"secret":secret},list(trace)
            elif f=="transfer":
                # Include insufficient-funds boundary independent of parameter.
                for a in sorted({0,1,k}): yield {"a":a},list(trace)
            else: yield {},list(trace)
