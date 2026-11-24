"""Generate, compare and export bounded transition contract cases."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from machine import validate,execute_validated
from templates import FAMILIES,VARIANTS,model,scenarios
from oracle import expected,invariants

ROOT=Path(__file__).resolve().parent
CONTRACTS={
    "transfer":"Successful unit transfer preserves total and debits/credits once; failed transfer changes nothing.",
    "lifetime":"Only live handles matching the allocation generation may read; stale handles observe absence.",
    "reservation":"Two clients share one remaining capacity unit; reject excess reservations; release restores capacity.",
    "authorized_effect":"Authorized action increments protected value and emits a write; denied action has no write effect.",
    "cancel_cleanup":"Completion or cancellation releases resource exactly once and fixes terminal outcome.",
    "retry":"Duplicate request delivery acknowledges but never credits twice; distinct IDs each credit one unit.",
    "deadline":"A pending request expires at its absolute discrete deadline; service before expiry completes it.",
    "interleaving":"All read-before-write schedules of two increment operations preserve completed increments.",
    "security_trace":"Equal public input and equal action traces have identical public outputs for either secret bit."}


def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()


def instance(i,seed):
    if not 0<=i<100000 or not 0<=seed<2**32: raise ValueError("index/seed range")
    n=(i*7919+seed*104729)%100000
    f=FAMILIES[n%len(FAMILIES)]; k=1+n//len(FAMILIES)
    models={v:model(f,k,v) for v in VARIANTS}
    return {"id":f"T1-{seed:08x}-{i:05d}","family":f,"parameter":k,"contract":CONTRACTS[f],"models":models}


def check(row):
    f,k=row["family"],row["parameter"]
    out={}
    for variant,m in row["models"].items():
        validate(m)
        failures={}; count=0; paired={}
        obligations=["state","effects","invariant"]+(["noninterference"] if f=="security_trace" else [])
        for override,trace in scenarios(f,k):
            actual=execute_validated(m,trace,{**m["initial"],**override})
            gold=expected(f,k,override,trace)
            checks={"state":[x["state"] for x in actual]==[x["state"] for x in gold],
                    "effects":[x["events"] for x in actual]==[x["events"] for x in gold],
                    "invariant":invariants(f,k,override,trace,actual)}
            witness={"initial_override":override,"trace":trace,"actual":actual,"expected":gold}
            if f=="security_trace":
                key=tuple(trace)
                obs=[(x["state"]["public"],x["events"]) for x in actual]
                if key in paired:
                    previous=paired.pop(key)
                    checks["noninterference"]=previous==obs
                    if not checks["noninterference"]:
                        witness={**witness,"other_secret_observation":previous,"observation":obs}
                else: paired[key]=obs
            for obligation,ok in checks.items():
                if not ok and obligation not in failures: failures[obligation]=witness
            count+=1
        if not count or paired: raise ValueError("empty or incomplete scenario domain")
        if bool(failures)!=(variant=="mutation"):
            raise ValueError(f"{row['id']}: unexpected {variant} outcome: {list(failures)}")
        out[variant]={"status":"disproven" if failures else "bounded_pass","traces":count,
                      "obligations":{o:{"status":"disproven" if o in failures else "bounded_pass","witness":failures.get(o)} for o in obligations}}
    return out


def blind(row):
    # Stage B contract-only export. Does not disclose family, variant, candidate or gold labels.
    f,k=row["family"],row["parameter"]
    return {"id":row["id"],"contract":row["contract"],"parameter":k,
            "initial":row["models"]["reference"]["initial"],"actions":sorted(row["models"]["reference"]["actions"]),
            "scenario_domain":[{"initial_override":o,"trace":t} for o,t in scenarios(f,k)],
            "scope":"finite integer-register model; observations at atomic action boundaries"}


def shrink(row,obligation):
    f=row["family"]
    candidate={**row,"parameter":1,"models":{v:model(f,1,v) for v in VARIANTS}}
    result=check(candidate)["mutation"]["obligations"].get(obligation)
    if result and result["status"]=="disproven": return result["witness"]
    return check(row)["mutation"]["obligations"][obligation]["witness"]


def build(count,seed,stream=None,blind_stream=None):
    if not 1<=count<=100000: raise ValueError("count range")
    seen=set(); families=Counter(); obligations=Counter(); traces=0; h=hashlib.sha256()
    for i in range(count):
        row=instance(i,seed)
        identity=digest(row["models"])
        if identity in seen: raise ValueError("duplicate model triple")
        seen.add(identity)
        results=check(row)
        row["model_sha256"]=identity; row["results"]=results
        families[row["family"]]+=1
        traces+=sum(x["traces"] for x in results.values())
        for name,x in results["mutation"]["obligations"].items():
            obligations[row["family"]+"/"+name]+=x["status"]=="disproven"
        line=canonical(row)+"\n"; h.update(line.encode())
        if stream is not None: stream.write(line)
        if blind_stream is not None: blind_stream.write(canonical(blind(row))+"\n")
    return {"profile":"transition-v1","seed":seed,"instances":count,"distinct_model_triples":len(seen),
            "variant_runs":3*count,"trace_runs":traces,"mutations_rejected":count,"family_counts":dict(sorted(families.items())),
            "mutation_obligation_failures":dict(sorted(obligations.items())),"corpus_sha256":h.hexdigest(),
            "source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.suffix in (".py",".json")},
            "limits":"bounded abstract development traces; no proof, normative semantics or independent review"}


def main():
    from contextlib import ExitStack
    p=argparse.ArgumentParser()
    p.add_argument("--count",type=int,default=1000)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--output",type=Path)
    p.add_argument("--blind-output",type=Path)
    args=p.parse_args()
    with ExitStack() as stack:
        output=stack.enter_context(args.output.open("x",encoding="utf-8",newline="\n")) if args.output else None
        blind_output=stack.enter_context(args.blind_output.open("x",encoding="utf-8",newline="\n")) if args.blind_output else None
        print(json.dumps(build(args.count,args.seed,output,blind_output),indent=2,sort_keys=True))


if __name__=="__main__": main()
