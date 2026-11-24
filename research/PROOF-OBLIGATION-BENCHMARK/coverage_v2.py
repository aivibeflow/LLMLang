"""Inventory gaps; do not upgrade label co-occurrence to semantic coverage."""
import json
from pathlib import Path
from run import load,read
ROOT=Path(__file__).resolve().parent


def report(cases, registry, taxonomy, target):
    ids={c["id"]:c for c,_ in cases}
    families={"interval","sum","forall_exists","exists_forall","unique","composition"}
    axes={}
    for axis,entries in registry["axes"].items():
        rows={}
        for key,entry in entries.items():
            manual=entry["manual_candidates"]
            generated=entry["generated_candidates"]
            if not set(manual)<=ids.keys() or not set(generated)<=families:
                raise ValueError(f"stale coverage candidate: {axis}/{key}")
            rows[key]={"status":"candidate_unreviewed" if manual or generated else "missing","manual":manual,"generated":generated}
        axes[axis]={"total":len(rows),"missing":sum(x["status"]=="missing" for x in rows.values()),"entries":rows}
    cells=[]
    for form in taxonomy["forms"]:
        for domain in taxonomy["domains"]:
            candidates=sorted(cid for cid,c in ids.items() if {form,domain}<=set(c["labels"]))
            for dimension in registry["scenario_dimensions"]:
                witnessed=[cid for cid in candidates if cid in target["probes"]]
                cells.append({"form":form,"domain":domain,"dimension":dimension,"status":"candidate_unreviewed" if candidates else "missing_or_unadjudicated","candidates":candidates,"case_level_probe_candidates":witnessed,"applicability":"unadjudicated"})
    return {"version":2,"axes":axes,"pair_matrix":{"total":len(cells),"candidate_cells":sum(bool(c["candidates"]) for c in cells),"missing_or_unadjudicated_cells":sum(not c["candidates"] for c in cells),"independently_adjudicated_cells":0,"cells":cells},"limits":"Candidate co-occurrence only; not isolated witnesses, applicability decisions or reviewed semantic coverage."}


def main():
    print(json.dumps(report(load(),read(ROOT/"coverage-v2.json"),read(ROOT/"taxonomy.json"),read(ROOT/"coverage-target.json")),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
