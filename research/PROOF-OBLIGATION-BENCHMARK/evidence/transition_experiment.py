"""Exercise evidence composition on the pinned RT-33 transition runs."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path

from composition import Backend, Claim, Plan, digest

REVISION = "991c053ffbc9e3ed0885763e3034f0d3c9354c2a"
SMT_HASH = "bfbad3ebff85bdda5d832bb04e3efdf21ebcdbe11029ab1c50d7b7bd0f7bd3e4"
LEAN_HASH = "c7b75d69b8b5751dd41ffa3042838b500188c057b127c6548b2bffa8c94af5cd"
TLC_SUMMARY_HASH = "cf8f5ecce6de977f907cd246613f450ddcd566e7c9966a6ad8e5d33d37fe4f9f"
TLC_CASES_HASH = "bf6160dca0cd6c752854f7b8d5cf36887b31743a76ba7ad31174235c8d2565e5"
BACKENDS = (
    Backend("cvc5", "1.4.2+282d5e0",
            "ce4260b07959e13e8522562f991d73a9fca692677c27e5282238df351c9feb81",
            digest(("QF_LIA", "incremental", "30s", "fixed trace")), ("finite",)),
    Backend("Lean", "4.36.0+611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9",
            digest(("dedf689fc84a9b8a22407b2f805d5e36c8f22819dbe970bf693c23652e34c917",
                    "723e8c8d73288f255520ec65877afd92fd4e0cb8c708c4264ebc3dbb45923d2c")),
            digest(("30s", "rfl", "decide", "standard axioms")), ("finite",)),
    Backend("TLC", "fdffef247f563ef6edbfd44958d2a82db79e7564e07cb673262d896353fa6713",
            "69577fec69de1d89b92be16adfc09d90d19cfc491a96095735c8e6619b44e7ec",
            digest(("30s", "512m", "workers=1", "seed=1", "fp=0", "Java 21.0.13")), ("finite",)),
)


def read_pinned(path, expected):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f"artifact hash mismatch: {path}")
    return raw.decode()


def pairwise_inputs(smt, lean, tlc, summary):
    controls = [(row.get("control"), row.get("solver"), row.get("outcome")) for row in smt[-2:]]
    if controls != [
        ("all-boundaries", "sat", "replayed-counterexample"),
        ("final-only", "unsat", "translation-or-solver-conflict"),
    ]:
        raise ValueError("SMT controls differ from the pinned run")
    if summary["status"] != "bounded-comparison" or summary["expected_distinct_prefix_states"] != 2778:
        raise ValueError("TLC run did not check the declared graph")
    for backend, artifact in [("smt", SMT_HASH), ("lean", LEAN_HASH)]:
        if summary["comparisons"][backend] != {"matches": True, "observations_sha256": artifact}:
            raise ValueError(f"TLC and {backend} scope linkage missing")
    smt = smt[:-2]
    if not len(smt) == len(lean) == len(tlc) == 798:
        raise ValueError("case count mismatch")
    fields = ("family", "variant", "parameter", "initial", "trace", "expected", "replay", "model_sha256")
    for index, (smt_row, lean_row, tlc_row) in enumerate(zip(smt, lean, tlc), start=1):
        if any(smt_row[field] != lean_row[field] for field in fields):
            raise ValueError(f"Lean and SMT case scope mismatch at {index}")
        if (int(tlc_row["case_id"]) != index
                or any(str(smt_row[field]) != tlc_row[field] for field in fields[:3])):
            raise ValueError(f"TLC case scope mismatch at {index}")
        yield index, smt_row, lean_row, tlc_row


def run(smt, lean, tlc, summary):
    claims = []
    issued = []
    for index, smt_row, lean_row, tlc_row in pairwise_inputs(smt, lean, tlc, summary):
        name = f"case-{index:04d}"
        claim = Claim(
            name, REVISION, "register state equals oracle",
            smt_row["model_sha256"],
            digest((smt_row["initial"], smt_row["trace"], smt_row["expected"])),
            "registers-at-each-action-boundary", "finite",
        )
        claims.append(claim)
        if (smt_row["solver"], smt_row["outcome"]) == ("unsat", "bounded-agreement"):
            smt_verdict = "support"
        elif (smt_row["solver"], smt_row["outcome"]) == ("sat", "replayed-counterexample"):
            smt_verdict = "counterexample"
        else:
            raise ValueError(f"incomplete SMT outcome at {index}")
        if lean_row["status"] != "kernel-checked" or lean_row["relation"] not in {"equal", "different"}:
            raise ValueError(f"incomplete Lean outcome at {index}")
        if tlc_row["classification"] not in {"equal", "different"}:
            raise ValueError(f"incomplete TLC outcome at {index}")
        lean_verdict = "support" if lean_row["relation"] == "equal" else "counterexample"
        tlc_verdict = "support" if tlc_row["classification"] == "equal" else "counterexample"
        issued.append((name, BACKENDS[0], digest((SMT_HASH, index, smt_row)), smt_verdict))
        issued.append((name, BACKENDS[1], digest((LEAN_HASH, index, lean_row)), lean_verdict))
        issued.append((name, BACKENDS[2], digest((TLC_SUMMARY_HASH, TLC_CASES_HASH, index, tlc_row)),
                       tlc_verdict))

    plan = Plan(claims, BACKENDS)
    receipts = [plan.receipt(*args) for args in issued]
    results, rejected, overall = plan.evaluate(receipts, {receipt.key for receipt in receipts})
    counts = Counter(result["status"] for result in results.values())
    return {
        "experiment": "rt33-transition-evidence-v1",
        "fixture_revision": REVISION,
        "artifacts": {"smt": SMT_HASH, "lean": LEAN_HASH, "tlc_summary": TLC_SUMMARY_HASH,
                      "tlc_cases": TLC_CASES_HASH},
        "accepted_receipts": len(receipts) - len(rejected),
        "obligations": len(claims), "counts": dict(counts),
        "corpus_conjunction": overall,
        "verdict_set_counts": {
            verdict: sum(result["observed_verdicts"] == [verdict] for result in results.values())
            for verdict in ("support", "counterexample")
        },
        "per_case_results_sha256": digest(results),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smt", required=True, type=Path)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--tlc", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run(
            [json.loads(line) for line in read_pinned(args.smt, SMT_HASH).splitlines()],
            [json.loads(line) for line in read_pinned(args.lean, LEAN_HASH).splitlines()],
            list(csv.DictReader(read_pinned(args.tlc / "outcomes.csv", TLC_CASES_HASH).splitlines())),
            json.loads(read_pinned(args.tlc / "summary.json", TLC_SUMMARY_HASH)),
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return int(result["counts"] != {"bounded-agreement": 712, "refuted": 86}
               or result["accepted_receipts"] != 2394)


if __name__ == "__main__":
    raise SystemExit(main())
