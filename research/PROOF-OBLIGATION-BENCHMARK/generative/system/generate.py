"""Reproducible structural/system profile with checked bounded state graphs."""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from explore import explore
from models import FAMILIES,VARIANTS,ACTIONS,DEPTH,CONTRACTS,initial,step
from oracle import check as predicate

ROOT=Path(__file__).resolve().parent


def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()


def instance(i,seed):
    if not 0<=i<100000 or not 0<=seed<2**32: raise ValueError("index/seed range")
    n=(i*7919+seed*104729)%100000
    f=FAMILIES[n%len(FAMILIES)]; k=1+n//len(FAMILIES)
    return {"id":f"S1-{seed:08x}-{i:05d}","family":f,"parameter":k,"contract":CONTRACTS[f],
            "initial":initial(f,k),"actions":list(ACTIONS[f]),"depth":DEPTH[f]}


def check(row):
    f,k=row["family"],row["parameter"]
    if f not in FAMILIES or row["initial"]!=initial(f,k) or row["actions"]!=list(ACTIONS[f]) or row["depth"]!=DEPTH[f]:
        raise ValueError("model profile mismatch")
    result={}
    for v in VARIANTS:
        result[v]=explore(row["initial"],row["actions"],lambda s,a:step(f,k,v,s,a),
                          lambda b,a,s,e:predicate(f,k,b,a,s,e),row["depth"])
        if result[v]["status"]!=("disproven" if v=="mutation" else "bounded_pass"):
            raise ValueError(f"{row['id']}/{v}: unexpected result")
    return result


def replay(row,variant,witness):
    f,k=row["family"],row["parameter"]; state=dict(row["initial"])
    for action in witness["trace"]:
        before=dict(state); state,event=step(f,k,variant,state,action)
    if before!=witness["before"] or state!=witness["after"] or event!=witness["event"]:
        raise ValueError("witness mismatch")
    return predicate(f,k,before,action,state,event)


def build(count,seed,stream=None,blind_stream=None):
    if not 1<=count<=100000: raise ValueError("count range")
    seen=set(); family_counts=Counter(); failures=Counter(); states=edges=0; h=hashlib.sha256()
    for i in range(count):
        row=instance(i,seed)
        identity=digest({k:v for k,v in row.items() if k!="id"})
        if identity in seen: raise ValueError("duplicate parameters")
        seen.add(identity)
        results=check(row)
        for v,x in results.items():
            states+=x["states"]; edges+=x["edges"]
            for o,record in x["obligations"].items():
                if record["status"]=="disproven":
                    if replay(row,v,record["witness"])[o]: raise ValueError("non-reproducible witness")
                    failures[row["family"]+"/"+o]+=1
        family_counts[row["family"]]+=1
        if blind_stream is not None:
            blind_stream.write(canonical({k:v for k,v in row.items() if k!="family"})+"\n")
        line=canonical({**row,"instance_sha256":identity,"results":results})+"\n"; h.update(line.encode())
        if stream is not None: stream.write(line)
    return {"profile":"system-v1","seed":seed,"instances":count,"distinct_parameterized_instances":len(seen),
            "variant_runs":3*count,"mutations_rejected":count,"reachable_states_sum":states,"checked_edges_sum":edges,
            "family_counts":dict(sorted(family_counts.items())),"mutation_obligation_failures":dict(sorted(failures.items())),
            "corpus_sha256":h.hexdigest(),"source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.suffix in (".py",".json")},
            "limits":"bounded explicit-state, synthetic public cases; no normative semantics or independent review"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--count",type=int,default=140)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--output",type=Path)
    p.add_argument("--blind-output",type=Path)
    args=p.parse_args()
    with ExitStack() as stack:
        out=stack.enter_context(args.output.open("x",encoding="utf-8",newline="\n")) if args.output else None
        blind=stack.enter_context(args.blind_output.open("x",encoding="utf-8",newline="\n")) if args.blind_output else None
        print(json.dumps(build(args.count,args.seed,out,blind),indent=2,sort_keys=True))


if __name__=="__main__": main()
