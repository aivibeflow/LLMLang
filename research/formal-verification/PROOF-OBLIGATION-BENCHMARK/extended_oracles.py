"""Second seed cohort: finite candidates and separately expressed oracle predicates.

Each function accepts a variant ID, and yields (JSON-compatible input, bool).
No candidate executes arbitrary user code. Neither a bounded pass nor a candidate
agreement is an independently reviewed proof.
"""
from fractions import Fraction
from itertools import product, combinations
from collections import Counter
from math import floor, ceil


def vacuity(v):
    admitted = {"reference":lambda x:0 <= x <= 2,
                "mutation":lambda x:x > 2 and x < 0,
                "alternative":lambda x:x in {0,1,2}}[v]
    for x in range(-2,5):
        yield x, admitted(x) == (x in (0,1,2))


def option(v):
    for x in (None,-1,0,1):
        if v == "reference":
            out = ("absent",None) if x is None else ("present",x)
        elif v == "mutation":
            out = ("present",x) if x else ("absent",None)
        else:
            out = {None:("absent",None),-1:("present",-1),0:("present",0),1:("present",1)}[x]
        tag,value = out
        yield x, (tag == "absent" and value is None) if x is None else (tag == "present" and value == x)


def division(v):
    for n,d in product(range(-2,3),repeat=2):
        if d == 0:
            out = Fraction(0) if v == "mutation" else "error"
        elif v == "alternative":
            out = Fraction(n if d > 0 else -n,abs(d))
        else:
            out = Fraction(n,d)
        yield [n,d], out == "error" if d == 0 else (isinstance(out,Fraction) and out*d == n)


def compose(v):
    for x in range(-2,3):
        arg = x if v == "mutation" else ((-x if x < 0 else x) if v == "alternative" else abs(x))
        out = arg*arg
        yield x, arg >= 0 and out == x*x


def retry(v):
    for n in range(5):
        for ids in product((0,1),repeat=n):
            seen, balance = set(),0
            for req in ids:
                if v == "mutation" or req not in seen:
                    balance += 1
                seen.add(req)
            if v == "alternative":
                balance = len(seen)
            expected = int(0 in ids)+int(1 in ids)
            yield list(ids), balance == expected


def rounding(v):
    for n in range(-7,8):
        x = Fraction(n,2)
        if v == "reference":
            q,r = divmod(n,2)
            out = q + int(r == 1 and q % 2 != 0)
        elif v == "mutation":
            out = (1 if n >= 0 else -1)*((abs(n)+1)//2)
        else:
            out = round(x)
        candidates = range(floor(x)-1,ceil(x)+2)
        expected = min(candidates,key=lambda k:(abs(k-x),k%2))
        yield n, out == expected


def probability(v):
    mapping = {"reference":lambda x:x%2,
               "mutation":lambda x:int(x==3),
               "alternative":lambda x:x//2}[v]
    counts = Counter(mapping(x) for x in range(4))
    yield "uniform-space", counts == {0:2,1:2}


def lost_update(v):
    for positions in combinations(range(4),2):
        a,b = iter(("R0","W0")),iter(("R1","W1"))
        trace = [next(a) if i in positions else next(b) for i in range(4)]
        counter, reads, completed = 0,{},0
        for op in trace:
            thread = int(op[1])
            if op[0] == "R":
                reads[thread] = counter
                if v == "alternative":
                    counter += 1
            else:
                completed += 1
                if v == "mutation":
                    counter = reads[thread]+1
                elif v == "reference":
                    counter += 1
        yield trace, counter == completed == 2


def migration(v):
    for i,b in product((0,1),(None,True,False)):
        record = {"id":i} if b is None else {"id":i,"enabled":b}
        if v == "reference":
            enabled = record.get("enabled",True)
        elif v == "mutation":
            enabled = record.get("enabled") or True
        else:
            enabled = record["enabled"] if "enabled" in record else True
        out = (record["id"],enabled)
        yield [i,b], out[0] == i and out[1] is (True if b is None else b)


def trace_isolation(v):
    def observe(p,s):
        if v == "mutation":
            return p,2+s
        if v == "alternative":
            return p,(1 if s else 0)+(1 if s else 2)
        return p,2
    for p,s,t in product((0,1),repeat=3):
        yield [p,s,t], observe(p,s) == observe(p,t) == (p,2)


def countdown(v):
    for n in range(6):
        if v == "alternative":
            trace = list(range(n,-1,-1))
        else:
            trace = [n]
            for _ in range(6):
                if trace[-1] == 0:
                    break
                trace.append(trace[-1] if v == "mutation" and trace[-1] == 1 else trace[-1]-1)
        yield n, trace[0] == n and trace[-1] == 0 and len(trace) == n+1 and all(x-y == 1 for x,y in zip(trace,trace[1:]))


def translation(v):
    for x in range(-2,5):
        target = (x >= 0) if v == "mutation" else ((x == 0 or x == 1 or x == 2) if v == "alternative" else (0 <= x <= 2))
        yield x, target == (not (x < 0 or x > 2))


EXTENDED = {f.__name__:f for f in (vacuity,option,division,compose,retry,rounding,probability,lost_update,migration,trace_isolation,countdown,translation)}
