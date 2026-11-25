"""Compare offline RT-31 regressions and exact review-bound eligibility."""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from subprocess import check_output
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FRONTEND = HERE.parent / "FRONTEND-CONTRACT-01"
sys.path.insert(0, str(FRONTEND))
from contract import Failed, Source, elaborate, frontend, render
from replay import entry_term, make_program, observe, oracle
from run import source_variant

PIN = "0bde6f2213d337b3c7aa69160dbca09eb33c3119"
PROFILES = ("infix/1", "hybrid/1")
CANDIDATES = {
    "baseline": "baseline",
    "layout": "syntax",
    "dropped-ordered-effects": "syntax",
    "omitted-obligation": "instruction",
    "collapsed-diagnostic": "diagnostics",
    "scalar-only-verdict": "toolchain",
}
EXPECTED = {
    "candidate": ("pass", "ready"),
    "effect-falsifier": ("reject", "observation"),
    "malformed": ("reject", "frontend"),
    "wrong-type": ("reject", "elaboration"),
    "incomplete": ("reject", "obligation"),
}


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class Case:
    case_id: str
    split: str
    kind: str
    profile: str
    argument: int
    offset: int


@dataclass(frozen=True)
class Review:
    change: str
    metrics: str
    corpus: str
    reviewer: str
    epoch: int
    disposition: str


def corpus():
    kinds = {
        "development": ("candidate", "malformed", "wrong-type", "incomplete"),
        "heldout": ("candidate", "effect-falsifier", "malformed", "wrong-type", "incomplete", "candidate"),
    }
    return tuple(
        Case(f"{split}-{index}-{profile}", split, kind, profile,
             (19 if split == "development" else 47) + index,
             0 if kind == "effect-falsifier" or split == "heldout" and kind == "candidate" else index - 2)
        for split, values in kinds.items()
        for index, kind in enumerate(values)
        for profile in PROFILES
    )


def source_for(case, candidate):
    bad_order = case.kind == "effect-falsifier" or (
        candidate == "dropped-ordered-effects" and case.split == "heldout" and case.kind == "candidate"
    )
    term = (["add", True, 1] if case.kind == "wrong-type"
            else entry_term("op", case.offset, 1, swap=bad_order))
    source = render(case.profile, term)
    if case.kind == "malformed":
        return Source(case.profile, source[:-1].encode())
    if candidate == "layout" and case.kind == "candidate":
        source = (json.dumps(json.loads(source), indent=2) if case.profile == "hybrid/1"
                  else source_variant(case.profile, source))
    return Source(case.profile, source.encode())


def evaluate(case, candidate):
    source = source_for(case, candidate)
    parsed = False
    scalar_match = None
    trace_match = None
    try:
        decoded = frontend(source, source.identity)
        parsed = True
        graph = elaborate(decoded, lambda term: make_program("primary", term))
    except Failed as error:
        diagnostic = error.diagnostic.phase
        if candidate == "collapsed-diagnostic" and case.split == "heldout" and diagnostic == "elaboration":
            diagnostic = "frontend"
        observed = ("reject", diagnostic)
    else:
        actual, events = observe(graph, "entry", (case.argument, True))
        expected, trace = oracle("op", "primary", case.offset, 1, case.argument, True)
        scalar_match, trace_match = actual == expected, events == trace
        requires_action = case.kind == "incomplete"
        supplies_action = candidate == "omitted-obligation" and case.split == "heldout"
        if requires_action and not supplies_action:
            observed = ("reject", "obligation")
        elif not scalar_match or (not trace_match and candidate != "scalar-only-verdict"):
            observed = ("reject", "observation")
        else:
            observed = ("pass", "ready")
    correct = EXPECTED[case.kind]
    return {
        "expected": list(correct), "reported": list(observed), "parsed": parsed,
        "scalar_match": scalar_match, "trace_match": trace_match, "source": source.identity,
        "regression": observed != correct,
    }


def analytics(cases, observations):
    totals = {}
    for split in ("development", "heldout"):
        selected = [observations[case.case_id] for case in cases if case.split == split]
        total = Counter(cases=len(selected))
        for row in selected:
            total["parsed"] += row["parsed"]
            total["regressions"] += row["regression"]
            total[f"diagnostic/{row['reported'][1]}"] += 1
            total["value_matches"] += row["scalar_match"] is True
            total["trace_matches"] += row["trace_match"] is True
        totals[split] = dict(total)
    return totals


def corpus_identity(cases):
    return digest([asdict(case) for case in cases])


def review_eligible(change, report, cases, observed_review, current_epoch):
    observations = report["observations"]
    if observations.keys() != {case.case_id for case in cases}:
        return False
    for case in cases:
        row = observations[case.case_id]
        if row["expected"] != list(EXPECTED[case.kind]) or row["regression"] != (row["expected"] != row["reported"]):
            return False
    if report["totals"] != analytics(cases, observations):
        return False
    if report["totals"]["heldout"]["regressions"] or report["totals"]["development"]["regressions"]:
        return False
    expected = Review(change, digest(report), corpus_identity(cases), "review-authority", current_epoch, "approve")
    return observed_review == expected


def check():
    cases = corpus()
    active = {case.case_id for case in cases if case.split == "development"}
    heldout = {case.case_id for case in cases if case.split == "heldout"}
    assert len(active) == 8 and len(heldout) == 12 and not active.intersection(heldout)
    corpus_id = corpus_identity(cases)
    evaluation_source = sha256(Path(__file__).read_bytes()).hexdigest()
    rows = {}
    regressions = {}
    for candidate, axis in CANDIDATES.items():
        observations = {case.case_id: evaluate(case, candidate) for case in cases}
        report = {"totals": analytics(cases, observations), "observations": observations}
        identity = digest([candidate, axis, evaluation_source])
        approval = Review(identity, digest(report), corpus_id, "review-authority", 8, "approve")
        admitted = review_eligible(identity, report, cases, approval, 8)
        regressions[candidate] = (report["totals"]["development"]["regressions"],
                                  report["totals"]["heldout"]["regressions"])
        assert admitted == (candidate in {"baseline", "layout"}), (candidate, regressions[candidate])
        rows[candidate] = {"axis": axis, "identity": identity, "report": report, "eligible": admitted}
    assert regressions == {
        "baseline": (0, 0), "layout": (0, 0), "dropped-ordered-effects": (0, 4),
        "omitted-obligation": (0, 2), "collapsed-diagnostic": (0, 2), "scalar-only-verdict": (0, 2),
    }
    assert rows["baseline"]["report"]["totals"]["heldout"]["parsed"] == 10
    assert all(item["report"]["totals"]["heldout"]["parsed"] == 10 for item in rows.values())
    assert rows["layout"]["report"]["observations"] != rows["baseline"]["report"]["observations"]

    report = rows["layout"]["report"]
    identity = rows["layout"]["identity"]
    good = Review(identity, digest(report), corpus_id, "review-authority", 8, "approve")
    fixed = {
        "missing-review": None,
        "wrong-reviewer": replace(good, reviewer="candidate-author"),
        "old-epoch": replace(good, epoch=7),
        "reviewer-refused": replace(good, disposition="decline"),
        "other-corpus": replace(good, corpus=corpus_id[::-1]),
        "other-change": replace(good, change=rows["baseline"]["identity"]),
        "other-metrics": replace(good, metrics=digest(rows["baseline"]["report"])),
        "exact": good,
    }
    controls = {key: review_eligible(identity, report, cases, value, 8) for key, value in fixed.items()}
    omitted = {"totals": report["totals"], "observations": {key: value for key, value in
               report["observations"].items() if key != sorted(heldout)[0]}}
    regressed = rows["scalar-only-verdict"]
    altered = json.loads(json.dumps(regressed["report"]))
    altered["totals"]["heldout"]["regressions"] = 0
    controls["missing-heldout-row"] = review_eligible(
        identity, omitted, cases, replace(good, metrics=digest(omitted)), 8)
    controls["inconsistent-aggregate"] = review_eligible(
        regressed["identity"], altered, cases,
        replace(good, metrics=digest(altered), change=regressed["identity"]), 8)
    assert {key for key, value in controls.items() if value} == {"exact"}
    return {"cases": [asdict(case) for case in cases], "corpus_id": corpus_id, "evaluation_sha256": evaluation_source,
            "candidate_cases": len(cases) * len(rows), "records": rows, "review_controls": controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    artifacts = (FRONTEND / "contract.py", HERE.parent / "HYBRID-PROFILE-01/replay.py",
                 HERE.parent / "CROSS-PROFILE-SPG-01/run.py")
    pins = {}
    for artifact in artifacts:
        path = artifact.relative_to(ROOT).as_posix()
        archived = check_output(["git", "show", f"{PIN}:{path}"], cwd=ROOT)
        assert artifact.read_bytes() == archived
        pins[path] = sha256(archived).hexdigest()
    args.output.write_text(json.dumps({"basis": PIN, "basis_sha256": pins, **check()},
                                     sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
