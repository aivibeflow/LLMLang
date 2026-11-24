"""Deterministic recursive/regular contract fixtures and obligation evidence."""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
from itertools import product
import json
from pathlib import Path
from models import FAMILIES,VARIANTS,list_sum,tree_size,map_fusion,extensional,parity,reachability,greatest,stream_equal,until
from oracle import tree_paths,graph_paths,bisimulation,stream_difference,strong_until

ROOT=Path(__file__).resolve().parent
CONTRACTS={
 "list_induction":"Sum of empty list is zero; cons step adds head to tail sum; result equals mathematical sum.",
 "tree_induction":"Empty tree has size zero; node size equals one plus both subtree sizes and number of node paths.",
 "map_fusion":"For all finite function tables f,g and admitted lists xs, map(f composed with g,xs) equals map(f,map(g,xs)).",
 "function_extensionality":"Finite functions are extensionally equal iff every domain element has the same output.",
 "mutual_recursion":"Even/odd mutually recursive predicates agree with arithmetic parity, are complementary and satisfy both recursive steps.",
 "least_fixed_point":"Reachability is the least closed set containing the root in the finite graph.",
 "greatest_fixed_point":"Greatest bisimulation on a finite deterministic total labeled graph equals equality of all infinite observation streams.",
 "stream_bisimulation":"Pure periodic infinite streams are equal iff every position in their joint cycle agrees.",
 "lasso_until":"Strong until holds on a regular infinite trace iff q eventually occurs and p holds strictly before the first q."}


def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def sha(x): return hashlib.sha256(canonical(x).encode()).hexdigest()


def trees(depth):
    if not depth: return (None,)
    prev=trees(depth-1)
    return (None,)+tuple((a,b) for a,b in product(prev,repeat=2))


def cases(f,k):
    if f=="list_induction":
        # Nonzero parameter and zero; all list lengths 0..5.
        for n in range(6):
            for xs in product((0,k),repeat=n): yield xs
    elif f=="tree_induction":
        yield from trees(3)
    elif f=="map_fusion":
        tables=tuple(product(range(3),repeat=3))
        # All f,g (including noncommuting); lists length 0, 1, 2.
        lists=((),)+tuple((i,) for i in range(3))+tuple(product(range(3),repeat=2))
        for f,g in product(tables,repeat=2):
            # Rotate list selection by parameter; include all singleton inputs.
            for xs in lists[:4]+(lists[4+k%9],): yield (xs,f,g)
    elif f=="function_extensionality":
        yield from product(tuple(product(range(3),repeat=3)),repeat=2)
    elif f=="mutual_recursion":
        yield from range(0,6+k%11)
    elif f=="least_fixed_point":
        # All directed graphs on four vertices with edges from this six-edge alphabet.
        alphabet=((0,1),(1,2),(2,3),(3,0),(0,2),(2,0))
        for bits in range(64):
            edges=tuple(e for i,e in enumerate(alphabet) if bits&(1<<i))
            for root in range(4): yield edges,root
    elif f=="greatest_fixed_point":
        # Every total successor function and binary labeling on three vertices.
        for succ in product(range(3),repeat=3):
            for labels in product((0,k),repeat=3): yield succ,labels
    elif f=="stream_bisimulation":
        periods=tuple(p for n in range(1,5) for p in product((0,k),repeat=n))
        yield from product(periods,repeat=2)
    elif f=="lasso_until":
        # Enumerate all length 0..2 prefixes and 1..2 periods over four valuations.
        vals=tuple(product((False,True),repeat=2))
        prefixes=((),)+tuple((x,) for x in vals)+tuple(product(vals,repeat=2))
        periods=prefixes[1:]
        yield from product(prefixes,periods)
    else: raise ValueError("unsupported family")


def obligations(f,k,x,v):
    if f=="list_induction":
        actual=list_sum(x,v)
        return {"base":bool(x) or actual==0,
                "step":not x or actual==x[0]+list_sum(x[1:],v),"semantic_sum":actual==sum(x)}
    if f=="tree_induction":
        actual=tree_size(x,v)
        return {"base":x is not None or actual==0,
                "step":x is None or actual==1+tree_size(x[0],v)+tree_size(x[1],v),
                "node_paths":actual==len(tree_paths(x))}
    if f=="map_fusion":
        xs,a,b=x; actual=map_fusion(xs,a,b,v)
        # Explicit composition relation, not implementation traversal.
        expected=tuple(next(y for j,y in enumerate(a) if j==b[i]) for i in xs)
        return {"length":len(actual)==len(xs),"pointwise":actual==expected}
    if f=="function_extensionality":
        a,b=x; result=extensional(a,b,v)
        different={i for i in range(3) if a[i]!=b[i]}
        return {"sound":not result or not different,"complete":bool(different) or result}
    if f=="mutual_recursion":
        e,o=parity(x,v)
        return {"base":x!=0 or (e and not o),"complement":e!=o,
                "step":x==0 or (e==parity(x-1,v)[1] and o==parity(x-1,v)[0]),
                "arithmetic":e==(x%2==0) and o==(x%2==1)}
    if f=="least_fixed_point":
        edges,root=x; s=reachability(edges,root,v)
        expected=graph_paths(edges,root)
        return {"seed":root in s,"closed":all(a not in s or b in s for a,b in edges),
                "least":s<=expected,"complete":expected<=s}
    if f=="greatest_fixed_point":
        successors,labels=x; s=greatest(successors,labels,v)
        expected=bisimulation(successors,labels)
        return {"post_fixed":all(labels[a]==labels[b] and (successors[a],successors[b]) in s for a,b in s),
                "sound":s<=expected,"greatest":expected<=s}
    if f=="stream_bisimulation":
        a,b=x; result=stream_equal(a,b,v); difference=stream_difference(a,b)
        return {"sound":not result or difference is None,"complete":result or difference is not None}
    if f=="lasso_until":
        prefix,period=x; result=until(prefix,period,v); expected=strong_until(prefix,period)
        return {"sound":not result or expected,"complete":result or not expected}
    raise ValueError("unsupported family")


def instance(i,seed):
    if type(i) is not int or type(seed) is not int or not 0<=i<100000 or not 0<=seed<2**32:
        raise ValueError("index/seed range")
    n=(i*7919+seed*104729)%100000
    f=FAMILIES[n%len(FAMILIES)]; k=1+n//len(FAMILIES)
    return {"id":f"R1-{seed:08x}-{i:05d}","family":f,"parameter":k,"contract":CONTRACTS[f]}


def check(row):
    f,k=row["family"],row["parameter"]
    if f not in FAMILIES or type(k) is not int or not 1<=k<=12000 or row["contract"]!=CONTRACTS[f]:
        raise ValueError("unsupported profile")
    result={}
    for v in VARIANTS:
        names=None; failures={}; count=0
        for x in cases(f,k):
            predicates=obligations(f,k,x,v)
            if not predicates or any(type(y) is not bool for y in predicates.values()): raise ValueError("invalid obligation")
            if names is None: names=set(predicates)
            if names!=set(predicates): raise ValueError("unstable obligation set")
            for o,ok in predicates.items():
                if not ok and o not in failures: failures[o]={"input":x}
            count+=1
        if not count or bool(failures)!=(v=="mutation"): raise ValueError(f"{row['id']}/{v}: unexpected result")
        result[v]={"status":"disproven" if failures else "bounded_pass","inputs":count,
                   "obligations":{o:{"status":"disproven" if o in failures else "bounded_pass","witness":failures.get(o)} for o in sorted(names)}}
        for o,w in failures.items():
            if obligations(f,k,w["input"],v)[o]: raise ValueError("witness replay failed")
    return result


def build(count,seed,stream=None,blind_stream=None):
    if type(count) is not int or not 1<=count<=100000: raise ValueError("count range")
    families=Counter(); failures=Counter(); h=hashlib.sha256(); seen=set(); evaluations=0
    for i in range(count):
        row=instance(i,seed)
        identity=sha({k:v for k,v in row.items() if k!="id"})
        if identity in seen: raise ValueError("duplicate parameterized record")
        seen.add(identity)
        result=check(row); families[row["family"]]+=1
        for v,r in result.items():
            evaluations+=r["inputs"]
            for o,x in r["obligations"].items():
                if x["status"]=="disproven": failures[row["family"]+"/"+o]+=1
        if blind_stream is not None:
            blind_stream.write(canonical({k:v for k,v in row.items() if k!="family"}|{"scope":"recursive-v1 finite structures and regular infinite models; see profile and declared input domains"})+"\n")
        line=canonical({**row,"instance_sha256":identity,"results":result})+"\n"; h.update(line.encode())
        if stream is not None: stream.write(line)
    return {"profile":"recursive-v1","seed":seed,"instances":count,"distinct_parameterized_records":len(seen),"variant_runs":3*count,
            "input_evaluations":evaluations,"mutations_rejected":count,"family_counts":dict(sorted(families.items())),
            "mutation_obligation_failures":dict(sorted(failures.items())),"corpus_sha256":h.hexdigest(),
            "source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.suffix in (".py",".json")},
            "limits":"bounded finite and regular infinite model checks; not universal proofs or independently adjudicated"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--count",type=int,default=90)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--output",type=Path)
    p.add_argument("--blind-output",type=Path)
    args=p.parse_args()
    with ExitStack() as stack:
        out=stack.enter_context(args.output.open("x",encoding="utf-8",newline="\n")) if args.output else None
        blind=stack.enter_context(args.blind_output.open("x",encoding="utf-8",newline="\n")) if args.blind_output else None
        print(json.dumps(build(args.count,args.seed,out,blind),indent=2,sort_keys=True))


if __name__=="__main__": main()
