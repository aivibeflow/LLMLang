"""Deterministic finite development generator with streamed optional corpus export."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from grammar import evaluate,outer_evidence
from templates import FAMILIES,make
from oracle import direct

VERSION=1
VARIANTS=("reference","mutation","alternative")
ROOT=Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True)


def parameters(index,seed):
    if not 0<=index<1000000 or not 0<=seed<2**32:
        raise ValueError("index/seed outside supported range")
    # Bijection on one million indices (7919 coprime to 10**6).
    n=(index*7919+seed*104729)%1000000
    return FAMILIES[n%len(FAMILIES)], n//len(FAMILIES)-83333, 1+(n//len(FAMILIES))%5


def instance(index,seed):
    family,k,width=parameters(index,seed)
    forms={v:make(family,k,width,v) for v in VARIANTS}
    return {"id":f"G1-{seed:08x}-{index:06d}","family":family,"origin":k,"width":width,"formulas":forms}


def check(row):
    family,k,width=row["family"],row["origin"],row["width"]
    outputs={}
    for v,e in row["formulas"].items():
        gold=direct(family,k,width,v)
        actual=evaluate(e)
        if actual!=gold or actual!=(v!="mutation"):
            raise ValueError(f"{row['id']}: {v} interpreter/oracle/expected disagreement")
        outputs[v]={"status":"bounded_pass" if actual else "disproven",
                    "evidence":None if actual else outer_evidence(e)}
    return outputs


def minimize(row):
    """Family-preserving parameter shrink, not general minimal AST."""
    candidates=[(0,1),(0,row["width"]),(row["origin"],1)]
    for k,w in candidates:
        candidate={**row,"origin":k,"width":w,"formulas":{v:make(row["family"],k,w,v) for v in VARIANTS}}
        if check(candidate)["mutation"]["status"]=="disproven":
            return candidate
    return row


def build(count,seed,stream=None):
    if not 1<=count<=1000000:
        raise ValueError("count must be 1..1000000")
    family_counts=Counter()
    seen=set()
    h=hashlib.sha256()
    for i in range(count):
        row=instance(i,seed)
        # Identity excludes synthetic ID. Distinctness is exact formula syntax,
        # not logical equivalence or number of independently reviewed families.
        identity=hashlib.sha256(canonical(row["formulas"]).encode()).hexdigest()
        if identity in seen:
            raise ValueError("duplicate generated formula triple")
        seen.add(identity)
        row["formula_sha256"]=identity
        row["results"]=check(row)
        family_counts[row["family"]]+=1
        line=canonical(row)+"\n"
        h.update(line.encode())
        if stream is not None:
            stream.write(line)
    return {"version":VERSION,"seed":seed,"instances":count,"distinct_formula_triples":len(seen),"variant_runs":3*count,"mutations_rejected":count,"family_counts":dict(sorted(family_counts.items())),"corpus_sha256":h.hexdigest(),"source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob("*.py"))},"limits":"finite synthetic development; distinct syntax not semantic diversity; no proof or independent review"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--count",type=int,default=10000)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--output",type=Path,help="optional new JSONL file; contains gold answers")
    args=p.parse_args()
    if args.output:
        with args.output.open("x",encoding="utf-8",newline="\n") as stream:
            result=build(args.count,args.seed,stream)
    else:
        result=build(args.count,args.seed)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
