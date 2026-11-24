"""Deterministic template expansion; no interpreter or oracle imports."""
FAMILIES=("interval","sum","forall_exists","exists_forall","unique","composition")
I=lambda n:["int",n]
V=lambda n:["var",n]
def B(op,a,b): return [op,a,b]
def Q(op,name,lo,hi,body): return [op,name,lo,hi,body]


def make(family,k,width,variant):
    """k is the interval origin; width 1..5 guarantees at least two choices."""
    lo,hi=k,k+width
    x,y,z=V("x"),V("y"),V("z")
    mut=variant=="mutation"
    alt=variant=="alternative"
    if family=="interval":
        body=B("le",x,I(hi-1 if mut else hi))
        if alt: body=["not",B("le",I(hi+1),x)]
        return Q("forall","x",lo,hi,body)
    if family=="sum":
        lhs=B("add",B("add",x,I(k)),I(width))
        rhs=B("add",x,I(k+width+int(mut)))
        if alt: rhs=B("add",I(width),B("add",I(k),x))
        return Q("forall","x",lo,hi,B("eq",lhs,rhs))
    if family=="forall_exists":
        rhs=B("add",x,I(int(mut)))
        if alt: rhs=B("sub",x,I(0))
        return Q("forall","x",lo,hi,Q("exists","y",lo,hi,B("eq",y,rhs)))
    if family=="exists_forall":
        body=B("le",y,x) if mut else B("le",x,y)
        # Mutant requires a strict lower bound INSIDE its own domain.
        if mut: body=B("le",B("add",x,I(1)),y)
        if alt: body=["not",B("le",B("add",y,I(1)),x)]
        return Q("exists","x",lo,hi,Q("forall","y",lo,hi,body))
    if family=="unique":
        pred=lambda t: B("le",t,I(lo+1)) if mut else B("eq",t,I(lo))
        if alt: pred=lambda t: B("and",B("le",I(lo),t),B("le",t,I(lo)))
        body=B("and",pred(x),Q("forall","z",lo,hi,B("implies",pred(z),B("eq",z,x))))
        return Q("exists","x",lo,hi,body)
    if family=="composition":
        # Caller admits x>=lo+1; callee requires arg>=lo+1, returns arg+1.
        arg=B("sub",x,I(1)) if mut else x
        if alt: arg=B("add",x,I(0))
        caller=B("le",I(lo+1),x)
        callee=B("le",I(lo+1),arg)
        post=B("eq",B("add",arg,I(1)),B("add",x,I(1)))
        return Q("forall","x",lo,hi,B("implies",caller,B("and",callee,post)))
    raise ValueError("unknown family")
