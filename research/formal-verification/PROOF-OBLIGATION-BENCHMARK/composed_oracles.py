"""Composed finite fixtures: (input, admitted, O1, O2).

O2 may be evaluated outside the admission assumption to demonstrate why it
matters, but those probes are not failures of the conditional contract.
Obligation checks are independently recorded; O2's dependency must still close.
"""
from itertools import product, permutations
from collections import Counter
import math
import struct


def guarded_lookup(v):
    for n,i in product(range(4),range(-1,4)):
        idx = i+1 if v=="mutation" else (n-(n-i) if v=="alternative" else i)
        safe = 0 <= idx < n
        value = list(range(n))[idx] if safe else None
        yield [n,i], 0<=i<n, safe, safe and value==i


def numeric_range(v):
    for x,y in product(range(4),repeat=2):
        out = x if v=="mutation" else ((x+sum(1 for _ in range(y)))%4 if v=="alternative" else (x+y)%4)
        yield [x,y], x+y<=3, 0<=out<=3, out==x+y


def algebra_profile(v):
    for op,x,y,z in product(("add","sub"),range(3),range(3),range(3)):
        f = (lambda a,b:a+b) if op=="add" else (lambda a,b:a-b)
        left,right = f(f(x,y),z),f(x,f(y,z))
        out = right+1 if v=="mutation" else (left if v=="alternative" and op=="add" else right)
        yield [op,x,y,z], op=="add", left==right, out==left


def exclusive_borrow(v):
    for alias,x in product((False,True),range(3)):
        target,other = x+1,x+1 if alias or v=="mutation" else x
        if v=="alternative" and not alias:
            target,other = tuple([x+1,x])
        yield [alias,x], not alias, not alias, target==x+1 and other==x


def budget(v):
    for n,b in product(range(4),repeat=2):
        if v=="alternative":
            acquired = n if n<=b else b
        else:
            acquired = 0
            for _ in range(n):
                if acquired == b:
                    break
                acquired += 1
        peak = acquired
        live = int(v=="mutation" and acquired>0)
        yield [n,b], n<=b, peak<=b, acquired==n and live==0


def quorum(v):
    def commit(mask):
        if v=="mutation":
            return mask.bit_count()>=1
        if v=="alternative":
            return any(mask & p == p for p in (3,5,6))
        return mask.bit_count()>=2
    for equiv,a,b in product((False,True),range(8),range(8)):
        if not equiv and a&b:
            continue
        ca,cb = commit(a),commit(b)
        yield [equiv,a,b], not equiv, (not ca or a.bit_count()>=2) and (not cb or b.bit_count()>=2), not(ca and cb)


def fair_lasso(v):
    for n in range(1,4):
        for period in product((0,1),repeat=n):
            if v=="mutation":
                handled=False
            elif v=="alternative":
                handled=1 in period
            else:
                handled=False
                for action in period:
                    if action:
                        handled=True
                        break
            # Continuous pending request; repeated identical periods.
            yield list(period), any(period), not any(period) or handled, handled


def publication(v):
    for edge,stale in product((False,True),repeat=2):
        if v=="mutation":
            out=0 if stale else 1
        elif v=="alternative":
            out=1 if edge else int(not stale)
        else:
            out=0 if stale and not edge else 1
        yield [edge,stale],edge,not edge or out==1,out==1


def rollback(v):
    for journal,old,fail in product((False,True),range(3),(False,True)):
        undo=old if journal else None
        value=old+1
        if fail and undo is not None and v!="mutation":
            value=undo if v=="reference" else old
        yield [journal,old,fail],journal,undo==old,value==(old if fail else old+1)


def capability(v):
    for verify,auth,old in product((False,True),(False,True),range(3)):
        if v=="mutation":
            grant=True
        elif v=="alternative":
            grant=auth in ({True} if verify else {True,False})
        else:
            grant=auth or not verify
        out=old+int(grant)
        yield [verify,auth,old],verify,not grant or auth,out==old+int(auth)


def linear_history(v):
    # E/e enqueue invocation/response, D/d dequeue invocation/response.
    for h in permutations("EeDd"):
        if h.index("E")>h.index("e") or h.index("D")>h.index("d"):
            continue
        h="".join(h)
        for atomic in (False,True):
            if atomic and v=="alternative":
                efirst=h.index("E")<h.index("D")
            else:
                efirst=h.index("e")<h.index("d")
            out=1 if efirst and atomic and v!="mutation" else None
            allowed=[]
            if h.index("d")>h.index("E"):
                allowed.append(1)   # enqueue may precede dequeue
            if h.index("e")>h.index("D"):
                allowed.append(None) # dequeue may precede enqueue
            order_valid=(not efirst or h.index("d")>h.index("E")) and (efirst or h.index("e")>h.index("D"))
            yield [atomic,h],atomic,order_valid,out in allowed


def ieee_edges(v):
    values={"+0":0.0,"-0":-0.0,"+1":1.0,"-1":-1.0,"+inf":math.inf,"-inf":-math.inf,"nan":math.nan}
    for strict,name in product((False,True),values):
        x=values[name]
        if not strict or v=="mutation":
            y=x+0.0
        elif v=="alternative":
            y=struct.unpack(">d",struct.pack(">d",x))[0]
        else:
            y=x
        special=math.isnan(x)==math.isnan(y) and (not math.isinf(x) or y==x)
        equal=math.isnan(y) if math.isnan(x) else y==x and math.copysign(1,y)==math.copysign(1,x)
        yield [strict,name],strict,special,equal


def durable_recovery(v):
    for durable,old,cut in product((False,True),range(3),range(3)):
        marker=cut==2 and durable
        if v=="mutation":
            recovered=old+int(cut>=1)
        elif v=="alternative":
            recovered=([old,old+1] if marker else [old])[-1]
        else:
            recovered=old+int(marker)
        yield [durable,old,cut],durable,marker==(cut==2),recovered==old+int(cut==2)


def lifetime(v):
    for check,h,g,live in product((False,True),range(3),range(3),(False,True)):
        if v=="mutation" or not check:
            admit=live
        elif v=="alternative":
            admit=(live,h)==(True,g)
        else:
            admit=live and h==g
        result=g if admit else None
        expected=live and h==g
        yield [check,h,g,live],check,admit==expected,result==(g if expected else None)


def random_search(v):
    for independent in (False,True):
        pairs=list(product((0,1),repeat=2)) if independent else [(0,0),(0,0),(1,1),(1,1)]
        marginals=all(sum(p[i] for p in pairs)==2 for i in (0,1))
        if v=="mutation":
            successes=sum(a for a,b in pairs)
        elif v=="alternative":
            successes=sum(p!=(0,0) for p in pairs)
        else:
            successes=sum(bool(a or b) for a,b in pairs)
        yield [independent],independent,marginals,successes==3


def resource_growth(v):
    for n,cost in product(range(6),range(4)):
        iterations=n
        if v=="mutation":
            work=sum(cost for _ in range(n) for _ in range(n))
        elif v=="alternative":
            work=sum([cost]*n)
        else:
            work=n*cost
        yield [n,cost],cost<=2,iterations==n,work<=2*n


COMPOSED = {f.__name__:f for f in (guarded_lookup,numeric_range,algebra_profile,exclusive_borrow,budget,quorum,fair_lasso,publication,rollback,capability,linear_history,ieee_edges,durable_recovery,lifetime,random_search,resource_growth)}
