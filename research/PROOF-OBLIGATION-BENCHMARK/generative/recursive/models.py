"""Candidate algorithms for the recursive/regular profile."""
from itertools import product

FAMILIES=("list_induction","tree_induction","map_fusion","function_extensionality","mutual_recursion","least_fixed_point","greatest_fixed_point","stream_bisimulation","lasso_until")
VARIANTS=("reference","mutation","alternative")


def list_sum(xs,v):
    if not xs: return 0
    if v=="alternative":
        total=0
        for x in xs: total+=x
        return total
    return xs[0]+(0 if v=="mutation" and len(xs)==2 else list_sum(xs[1:],v))


def tree_size(t,v):
    if t is None: return 0
    if v=="alternative":
        pending=[t]; n=0
        while pending:
            x=pending.pop()
            if x is not None:
                n+=1; pending.extend(x)
        return n
    return 1+tree_size(t[0],v)+(0 if v=="mutation" else tree_size(t[1],v))


def map_fusion(xs,f,g,v):
    if v=="reference": return tuple(f[g[x]] for x in xs)
    if v=="mutation": return tuple(g[f[x]] for x in xs)
    return tuple(map(f.__getitem__,map(g.__getitem__,xs)))


def extensional(f,g,v):
    if v=="mutation": return f[0]==g[0]
    if v=="alternative": return not any(a!=b for a,b in zip(f,g))
    return f==g


def parity(n,v):
    def even(x):
        return True if x==0 else odd(x-1)
    def odd(x):
        return (v=="mutation") if x==0 else even(x-1)
    if v=="alternative":
        return n%2==0,n%2==1
    return even(n),odd(n)


def reachability(edges,root,v):
    if v=="mutation": return {root}|{b for a,b in edges if a==root}
    if v=="alternative":
        seen=set(); todo=[root]
        while todo:
            a=todo.pop()
            if a not in seen:
                seen.add(a); todo.extend(b for x,b in edges if x==a)
        return seen
    s={root}
    while True:
        nxt=s|{b for a,b in edges if a in s}
        if nxt==s: return s
        s=nxt


def greatest(successors,labels,v):
    # Greatest bisimulation relation of deterministic, total labeled machines.
    pairs={(a,b) for a,b in product(range(len(labels)),repeat=2) if labels[a]==labels[b]}
    if v=="mutation": return pairs
    if v=="alternative":
        # Partition refinement: signature is label plus successor block.
        blocks=[labels.index(x) for x in labels]
        while True:
            signatures=[(labels[i],blocks[successors[i]]) for i in range(len(labels))]
            nxt=[signatures.index(x) for x in signatures]
            if all((blocks[a]==blocks[b])==(nxt[a]==nxt[b]) for a,b in product(range(len(labels)),repeat=2)):
                return {(a,b) for a,b in product(range(len(labels)),repeat=2) if nxt[a]==nxt[b]}
            blocks=nxt
    while True:
        nxt={(a,b) for a,b in pairs if (successors[a],successors[b]) in pairs}
        if nxt==pairs: return pairs
        pairs=nxt


def stream_equal(a,b,v):
    if v=="mutation": return a[0]==b[0]
    if v=="alternative":
        from math import lcm
        return all(a[i%len(a)]==b[i%len(b)] for i in range(lcm(len(a),len(b))))
    i=j=0; seen=set()
    while (i,j) not in seen:
        if a[i]!=b[j]: return False
        seen.add((i,j)); i=(i+1)%len(a); j=(j+1)%len(b)
    return True


def until(prefix,period,v):
    # Strong p U q at time zero: q must occur, with p on all earlier positions.
    if v=="alternative":
        first=next((i for i,(_,q) in enumerate(prefix+period) if q),None)
        return first is not None and all(p for p,q in (prefix+period)[:first])
    for p,q in prefix+period:
        if q: return True
        if not p: return False
    return v=="mutation"  # weak-until substitution drops eventuality
