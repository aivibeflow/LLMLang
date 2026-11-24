"""Fail closed on missing or non-executed finite coverage witnesses."""
from composed_oracles import COMPOSED


def check_coverage(cases, taxonomy, target):
    by_id={c["id"]:c for c,_ in cases}
    labels=set(taxonomy["forms"]) | set(taxonomy["domains"])
    dimensions=("positive","negative","boundary","conditional","composed")
    if set(target["mapping"]) != labels or tuple(target["dimensions"]) != dimensions:
        raise ValueError("coverage matrix does not match taxonomy")
    if set(target["probes"]) != {c["id"] for c,_ in cases if c["oracle"] in COMPOSED}:
        raise ValueError("coverage probes do not match composed corpus")
    def check(ok,msg):
        if not ok:
            raise ValueError(msg)
    checked={}
    for cid,probes in target["probes"].items():
        c=by_id[cid]
        fn=COMPOSED[c["oracle"]]
        def get(variant,probe):
            rows=[(admitted,a,b) for x,admitted,a,b in fn(variant) if x==probes[probe]]
            check(len(rows)==1,f"{cid}: missing or ambiguous {variant}/{probe}")
            return rows[0]
        for variant in ("reference","alternative"):
            for p in ("normal","boundary"):
                check(get(variant,p)==(True,True,True),f"{cid}: positive/boundary {variant}/{p}")
            check(get(variant,"outside")[0] is False and get(variant,"outside")[2] is False,f"{cid}: outside assumption {variant}")
        negative=get("mutation","negative")
        check(negative[0] is True and not all(negative[1:]),f"{cid}: negative")
        check([o["id"] for o in c["obligations"]]==["O1","O2"] and c["obligations"][1]["dependencies"]==["O1"],f"{cid}: composed dependency")
        checked[cid]={"positive":probes["normal"],"negative":probes["negative"],"boundary":probes["boundary"],"conditional":{"inside":probes["normal"],"outside":probes["outside"]},"composed":{"witness":probes["normal"],"dependency":"O2 -> O1"}}
    matrix={}
    for label,cid in sorted(target["mapping"].items()):
        check(cid in checked and label in by_id[cid]["labels"],f"{label}: missing labeled case")
        matrix[label]={"case_id":cid,"cells":checked[cid]}
    return {"covered_cells":sum(len(x["cells"]) for x in matrix.values()),"target_cells":len(labels)*len(dimensions),"matrix":matrix,"limits":"author-checked finite witnesses; no independent adjudication or full semantic exhaustiveness"}
