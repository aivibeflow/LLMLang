#!/usr/bin/env python3
"""Check finite receipt applicability when an observed provider changes."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from spg_observations import INPUTS, run as observe_and_check

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
COMPOSER = RESEARCH / "formal-verification" / "PROOF-OBLIGATION-BENCHMARK" / "evidence"
SPG = RESEARCH / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path[:0] = [str(COMPOSER), str(SPG)]

from composition import Backend, Claim, Plan, digest  # noqa: E402
from src.semantic_graph import verification_key  # noqa: E402

PROJECTION = digest(("scalar-value", "ordered-effect-names"))
DOMAIN = digest(INPUTS)
PUBLIC = digest({"offsets": (1, 2), "trace": ("first", "last")})


def plan_for(observation, backend):
    caller = Claim(
        "caller", PUBLIC, "public scalar result and ordered effects",
        observation["entry"], DOMAIN, PROJECTION, "finite", ("provider",),
    )
    provider = Claim(
        "provider",
        digest((observation["called_implementation"], observation["provided_contract"])),
        "checked provider body and refinement",
        observation["binding"], DOMAIN, PROJECTION, "finite",
    )
    return Plan([caller, provider], [backend])


def receipts(plan, backend, observed, generated):
    decisions = observed["verdicts"]
    direct = decisions["direct-public-body"]
    combined = decisions["separate-body-and-refinement"]
    if direct != "admit" or combined not in {"admit", "reject"}:
        raise ValueError("Unexpected fixture verdict for composition")
    artifact = digest((generated, observed))
    return (
        plan.receipt("caller", backend, artifact, "support"),
        plan.receipt("provider", backend, artifact, "support" if combined == "admit" else "counterexample"),
    )


def compare(lean):
    replay = json.loads(json.dumps(observe_and_check(lean)))
    archived = json.loads((HERE / "spg-results.json").read_text(encoding="utf-8"))
    if replay != archived:
        raise ValueError("Source-bound finite observations failed to reproduce")
    observed = {case["case"]: case for case in replay["cases"]}
    base = observed["base-operation"]
    rebound = observed["rebound-operation"]
    stale_promise = observed["rebound-operation-stale-provider-contract"]
    backend = Backend("finite typed-SPG fixture checker", replay["lean"],
                      replay["input_sha256"]["spg_observations.py"], "by decide", ("finite",))
    base_plan, rebound_plan, mismatched_plan = [plan_for(o, backend) for o in (base, rebound, stale_promise)]
    generated = replay["generated_lean_sha256"]
    base_receipts, rebound_receipts, mismatched_receipts = [
        receipts(p, backend, o, generated)
        for p, o in zip((base_plan, rebound_plan, mismatched_plan), (base, rebound, stale_promise), strict=True)
    ]
    base_caller, base_provider = base_receipts
    new_caller, new_provider = rebound_receipts
    if base_caller.claim != new_caller.claim or base_caller.closure == new_caller.closure:
        raise ValueError("Provider replacement should change exact premise closure at a stable claim")

    # This allow-list represents fixture-local admission of the exact reproduced inputs.
    authorized = {receipt.key for receipt in (*base_receipts, *rebound_receipts, *mismatched_receipts)}
    variants = (
        ("base", base_plan, base_receipts, "bounded-agreement"),
        ("rebound-with-only-old-receipts", rebound_plan, base_receipts, "insufficient"),
        ("rebound-with-fresh-provider-but-old-caller", rebound_plan, (base_caller, new_provider), "insufficient"),
        ("rebound-with-fresh-caller-but-no-provider", rebound_plan, (new_caller,), "insufficient"),
        ("rebound-after-exact-recheck", rebound_plan, rebound_receipts, "bounded-agreement"),
        ("rebound-with-failed-provider-promise", mismatched_plan, mismatched_receipts, "refuted"),
    )
    results = {}
    for name, plan, submitted, expected in variants:
        claims, rejected, outcome = plan.evaluate(submitted, authorized)
        if outcome != expected:
            raise ValueError(f"{name}: expected {expected}, got {outcome}")
        results[name] = {"claims": claims, "aggregate": outcome, "rejected_receipts": rejected}

    rejected_old = results["rebound-with-only-old-receipts"]["rejected_receipts"]
    if rejected_old != {base_caller.key: "stale-premises", base_provider.key: "different-claim"}:
        raise ValueError("Old receipts were rejected at the wrong boundary")
    for name in ("rebound-with-fresh-caller-but-no-provider", "rebound-with-failed-provider-promise"):
        if results[name]["claims"]["caller"]["status"] != "conditional":
            raise ValueError(f"{name}: an undischarged provider premise should leave caller support conditional")

    base_key, new_key = [
        verification_key(o["entry"], r.closure, backend.key, {"projection": PROJECTION},
                         assumptions=(o["binding"],))
        for o, r in ((base, base_caller), (rebound, new_caller))
    ]
    if base["entry"] != rebound["entry"] or base_key == new_key:
        raise ValueError("Failed to distinguish semantic caller identity from exact verification key")

    return {
        "schema": "llmlang-observed-provider-evidence-rebind-v1",
        "lean": replay["lean"],
        "python": replay["python"],
        "checked_observation_artifact_sha256": sha256((HERE / "spg-results.json").read_bytes()).hexdigest(),
        "source_sha256": {
            file.name: sha256(file.read_bytes()).hexdigest()
            for file in (Path(__file__), COMPOSER / "composition.py", SPG / "src/semantic_graph.py")
        },
        "stable_caller_subject": base["entry"],
        "stable_caller_claim": base_caller.claim,
        "provider_bindings": [base["binding"], rebound["binding"]],
        "verification_keys": [base_key, new_key],
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = compare(args.lean)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({case: result["aggregate"] for case, result in data["results"].items()}, indent=2))
