"""Compare low-level diagnostics and claim decisions for pinned proof fixtures."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform
import sys

BASELINE = "49f6d1a4328bf7d083ac44ff91ac587c02075276"
BENCHMARK = Path("research/formal-verification/PROOF-OBLIGATION-BENCHMARK/evidence")
DAFNY = Path("research/formal-verification/RT-07/DAFNY-MODULAR-PROOF-CLOSURE-01/evidence.json")


def archived_contrasts(data):
    checks = []
    for solver, cases in sorted(data["dafny"].items()):
        failed, exhausted = (cases[name] for name in ("wrong_provider_closure", "resource_exhaustion"))
        caller, closed = (cases[name] for name in ("caller_only", "closed"))
        assert failed["exit"] == exhausted["exit"] == 4
        assert (failed["errors"], failed["out_of_resource"]) == (1, 0)
        assert (exhausted["errors"], exhausted["out_of_resource"]) == (0, 1)
        assert caller["exit"] == closed["exit"] == 0
        assert not caller["provider_body_in_boogie"] and closed["provider_body_in_boogie"]
        for name, row in (("provider failure", failed), ("resource exhaustion", exhausted),
                          ("caller only", caller), ("source closure", closed)):
            checks.append({"solver": solver, "case": name, "exit": row["exit"],
                           "errors": row["errors"], "out_of_resource": row["out_of_resource"],
                           "provider_body": row["provider_body_in_boogie"], "disposition": row["disposition"]})

    cpc = data["cpc"]
    coarse, fine = (cpc["certificates"][mode] for mode in ("theory-rewrite", "dsl-rewrite"))
    assert coarse["solver"] == fine["solver"] == "unsat"
    assert (coarse["logos"], fine["logos"]) == ("rejected-trust", "correct")
    assert cpc["weaker_binding"] == "assumptions-mismatch"
    assert cpc["resource_limit_1"] == ["unknown", "(:reason-unknown resourceout)"]
    assert data["host_control"]["disposition"] == "unknown-host-timeout"
    return {"dafny": checks, "certificates": cpc["certificates"],
            "weaker_binding": cpc["weaker_binding"], "smt_resource": cpc["resource_limit_1"],
            "host_control": data["host_control"]}


def check_composition(model):
    backend = model.Backend("scoped checker", "1", model.digest("translator"),
                            model.digest("config"), ("finite",))
    def claim(name, premises=()):
        return model.Claim(name, BASELINE, "preserve value", model.digest(name), model.digest("domain"),
                           "result", "finite", premises)

    plan = model.Plan([claim("premise"), claim("target", ("premise",))], [backend], mandatory=("target",))
    premise = plan.receipt("premise", backend, model.digest("checked premise"), "support")
    verdicts = ("counterexample", "support", "timeout", "unknown", "unsupported")
    subsets = [values for size in range(len(verdicts) + 1) for values in combinations(verdicts, size)]
    expected_closed = {
        (False, False): "insufficient", (False, True): "bounded-agreement",
        (True, False): "refuted", (True, True): "conflict",
    }
    observations = []
    for statuses, premise_checked, trusted in product(subsets, (False, True), (False, True)):
        receipts = [plan.receipt("target", backend, model.digest(status), status) for status in statuses]
        candidates = receipts + ([premise] if premise_checked else [])
        authorized = {r.key for r in candidates if r == premise or trusted}
        results, rejected, overall = plan.evaluate(candidates, authorized)
        observed = list(statuses) if trusted else []
        checked = ("counterexample" in observed, "support" in observed)
        expected = expected_closed[checked]
        if not premise_checked and expected in {"bounded-agreement", "refuted"}:
            expected = "conditional"
        assert overall == expected
        assert results["target"]["observed_verdicts"] == observed
        assert len(rejected) == (0 if trusted else len(receipts))
        assert set(rejected.values()) <= {"unverified"}
        observations.append({"input_verdicts": statuses, "premise_checked": premise_checked,
                             "receipts_authorized": trusted, "target": results["target"],
                             "aggregate": overall, "rejected_count": len(rejected)})

    # Two distinct attempts with the same verdict collapse in the claim projection.
    attempts = [plan.receipt("target", backend, model.digest(label), "unknown")
                for label in ("solver budget", "solver returned no reason")]
    assert attempts[0].key != attempts[1].key
    one = plan.evaluate(attempts[:1], {attempts[0].key})
    two = plan.evaluate(attempts, {r.key for r in attempts})
    assert one == two
    return {"observations": observations,
            "aggregate_counts": dict(Counter(row["aggregate"] for row in observations)),
            "distinct_unknown_attempts_with_equal_projection": len(attempts)}


def audit(root):
    sys.path.insert(0, str(root / BENCHMARK))
    import composition
    sources = (DAFNY, BENCHMARK / "composition.py")
    return {
        "schema": "rt00-proof-receipt-status-audit-v1", "baseline": BASELINE,
        "python": platform.python_version(),
        "source_sha256": {str(path): sha256((root / path).read_bytes()).hexdigest() for path in sources},
        "archived_contrasts": archived_contrasts(json.loads((root / DAFNY).read_bytes())),
        "composition": check_composition(composition),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.archive_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8")
