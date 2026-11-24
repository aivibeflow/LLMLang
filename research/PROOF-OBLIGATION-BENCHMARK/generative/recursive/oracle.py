"""Independent-method finite and regular-infinite specifications."""
from itertools import product
from math import lcm


def tree_paths(t,path=()):
    if t is None: return set()
    return {path}|tree_paths(t[0],path+(0,))|tree_paths(t[1],path+(1,))


def graph_paths(edges,root,n=4):
    # Simple-path reachability: any reachable vertex has a simple path <= n-1.
    adjacency={i:{b for a,b in edges if a==i} for i in range(n)}
    def visit(path):
        end=path[-1]
        out={end}
        for b in adjacency[end]-set(path):
            out|=visit(path+[b])
        return out
    return visit([root])


def distinguish(successors,labels,a,b):
    # At most n*n distinct ordered pairs before a repeat, independently of refinement.
    n=len(labels)
    for time in range(n*n):
        if labels[a]!=labels[b]: return time
        a,b=successors[a],successors[b]
    return None


def bisimulation(successors,labels):
    return {(a,b) for a,b in product(range(len(labels)),repeat=2) if distinguish(successors,labels,a,b) is None}


def stream_difference(a,b):
    return next((i for i in range(lcm(len(a),len(b))) if a[i%len(a)]!=b[i%len(b)]),None)


def strong_until(prefix,period):
    # A q anywhere in the first prefix+period is necessary; all prior p hold.
    path=prefix+period
    hits=[i for i,(_,q) in enumerate(path) if q]
    bad=[i for i,(p,_) in enumerate(path) if not p]
    return bool(hits) and (not bad or min(hits)<=min(bad))
