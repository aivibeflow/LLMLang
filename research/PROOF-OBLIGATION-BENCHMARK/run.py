"""Offline corpus smoke, blind-input export, and exact verdict scoring.
Run from any directory with Python 3.11+; standard library only.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from oracles import ORACLES

ROOT = Path(__file__).resolve().parent
STATUSES = {"bounded_pass", "proven", "disproven", "unknown", "unsupported", "error"}


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load():
    taxonomy = read(ROOT / "taxonomy.json")
    cases = []
    ids = set()
    for path in sorted((ROOT / "cases").glob("*.json")):
        c = read(path)
        cid = c["id"]
        require(re.fullmatch(r"POB-\d{3,}", cid) and path.stem == cid and cid not in ids, f"invalid/duplicate case: {path}")
        ids.add(cid)
        require(type(c["revision"]) is int and c["revision"] >= 1 and c["status"] in {"proposed","reviewed","retired"}, f"{cid}: revision/status")
        for field in ("title","contract","scope","oracle"):
            require(isinstance(c[field], str) and bool(c[field].strip()), f"{cid}: {field}")
        require(isinstance(c["assumptions"], list) and all(isinstance(a,str) and a.strip() for a in c["assumptions"]), f"{cid}: assumptions")
        labels = c["labels"]
        require(len(labels) == len(set(labels)) and set(labels) <= set(taxonomy["forms"]) | set(taxonomy["domains"]), f"{cid}: labels")
        require(set(labels) & set(taxonomy["forms"]) and set(labels) & set(taxonomy["domains"]), f"{cid}: both taxonomy axes required")
        obligations = c["obligations"]
        graph = {o["id"]: o["dependencies"] for o in obligations}
        require(len(graph) == len(obligations) and graph and all(o["id"] and o["claim"].strip() for o in obligations), f"{cid}: obligations")
        seen, active = set(), set()
        def visit(node):
            require(node in graph and node not in active, f"{cid}: missing/cyclic dependency {node}")
            if node in seen:
                return
            active.add(node)
            for dep in graph[node]:
                visit(dep)
            active.remove(node)
            seen.add(node)
        for node in graph:
            visit(node)
        variants = {v["id"]:v for v in c["variants"]}
        require(len(variants) == len(c["variants"]) and set(variants) == {"reference","mutation"}, f"{cid}: variants")
        require(variants["reference"]["expected"] == "bounded_pass" and variants["mutation"]["expected"] == "disproven", f"{cid}: finite oracle expectations")
        require(c["oracle"] in ORACLES and all(v["description"].strip() for v in variants.values()), f"{cid}: oracle/description")
        if c["status"] != "retired":
            cases.append((c, digest(path)))
    require(cases, "empty corpus")
    return cases


def run(cases):
    records = []
    for c, sha in cases:
        for v in c["variants"]:
            rows = list(ORACLES[c["oracle"]](v["id"] == "mutation"))
            require(rows and all(type(ok) is bool for _,ok in rows), f"{c['id']}: empty/invalid oracle")
            failures = [x for x,ok in rows if not ok]
            verdict = "disproven" if failures else "bounded_pass"
            require(verdict == v["expected"], f"{c['id']}/{v['id']}: expected {v['expected']}, got {verdict}")
            records.append({"case_id":c["id"],"revision":c["revision"],"case_sha256":sha,"variant":v["id"],"status":verdict,"evaluated_inputs":len(rows),"counterexample":failures[0] if failures else None})
    return records


def aggregate(records, required_ids):
    """Conservative illustrative policy, not a certificate verifier."""
    required = list(required_ids)
    ids = [r.get("id") for r in records]
    if not required or len(required) != len(set(required)) or len(ids) != len(set(ids)) or set(ids) != set(required):
        return "unknown"
    if any(r.get("status") not in STATUSES for r in records):
        return "error"
    if any(r.get("status") == "disproven" and r.get("counterexample_validated") is True and r.get("correspondence_checked") is True and r.get("identity_checked") is True for r in records):
        return "disproven"
    if all(r.get("status") == "proven" and all(r.get(k) is True for k in ("identity_checked","correspondence_checked","evidence_checked","assumptions_discharged","dependencies_closed","scope_sufficient")) for r in records):
        return "proven"
    return "unknown"


def key(r):
    return tuple(r[k] for k in ("case_id","revision","case_sha256","variant"))


def score(expected, predictions):
    gold = {key(r):r["status"] for r in expected}
    pred = {}
    for row in predictions:
        k = key(row)
        require(k in gold and k not in pred and row["status"] in STATUSES, f"unknown, duplicate, or invalid prediction: {k}")
        pred[k] = row["status"]
    counts = Counter()
    for k, status in gold.items():
        p = pred.get(k, "missing")
        counts["correct"] += p == status
        counts["missing"] += p == "missing"
        counts["false_proven"] += p == "proven" and status != "proven"
        counts["false_proven_disproven"] += p == "proven" and status == "disproven"
    n = len(gold)
    negatives = sum(s == "disproven" for s in gold.values())
    return {"records":n,"correct":counts["correct"],"missing":counts["missing"],"accuracy":counts["correct"]/n,"false_proven":counts["false_proven"],"false_proven_rate":counts["false_proven"]/n,"negative_controls":negatives,"false_proven_on_negatives":counts["false_proven_disproven"]/negatives if negatives else None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode",choices=("run","blind","score"))
    p.add_argument("--predictions",type=Path)
    args = p.parse_args()
    cases = load()
    if args.mode == "blind":
        # Stage B only: no oracle, expected obligations, variant labels or expected outcomes.
        result = [{"case_id":c["id"],"revision":c["revision"],"case_sha256":sha,"contract":c["contract"],"scope":c["scope"],"assumptions":c["assumptions"]} for c,sha in cases]
    else:
        records = run(cases)
        if args.mode == "score":
            require(args.predictions is not None, "--predictions required")
            result = score(records, read(args.predictions))
        else:
            result = {"format_version":1,"python":sys.version,"runner_sha256":digest(ROOT/"run.py"),"oracle_sha256":digest(ROOT/"oracles.py"),"taxonomy_sha256":digest(ROOT/"taxonomy.json"),"coverage":dict(sorted(Counter(label for c,_ in cases for label in c["labels"]).items())),"records":records,"limits":"finite abstract oracle smoke; no proof or backend result"}
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
