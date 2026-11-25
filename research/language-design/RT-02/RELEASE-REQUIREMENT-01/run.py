#!/usr/bin/env python3
"""Compare a source-blind reading, an independent oracle and checked Lean claims."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from oracle import READING, from_source


HERE = Path(__file__).resolve().parent
GRANT_FIELDS = ("principal", "workspace", "artifact", "revision", "epoch")
RECEIPT_FIELDS = ("operation", "workspace", "artifact", "revision", "payload")
REQUEST = dict(zip(RECEIPT_FIELDS, (11, 13, 17, 19, 29)))
CALLER = 31
EPOCH = 37
CODES = ("denied", "released", "replayed", "conflict")
THEOREMS = (
    "exactRelease", "exactReplay", "noRepeatedEffect", "staleReleaseDenied",
    "noUnauthorizedReceiptDisclosure",
)


def digest(value):
    return sha256(value).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def invoke(command, cwd, data=None):
    env = {"LC_ALL": "C", "TZ": "UTC", "PATH": os.environ["PATH"]}
    return subprocess.run(command, cwd=cwd, env=env, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=30).stdout


def render(model, root):
    return invoke([sys.executable, "-B", HERE / "reconstruct.py"], root, encoded(model)).decode()


def mutate_mask(seed, fields, mask):
    return {**seed, **{field: seed[field] + 1 for bit, field in enumerate(fields) if (mask >> bit) & 1}}


def candidates():
    grant_source = dict(zip(GRANT_FIELDS, (CALLER, 13, 17, 19, EPOCH)))
    grants = [None] + [{**mutate_mask(grant_source, GRANT_FIELDS, mask), "role": role}
                       for mask in range(32) for role in ("release", "observe")]
    receipts = [None] + [mutate_mask(REQUEST, RECEIPT_FIELDS, mask) for mask in range(32)]
    return grants, receipts


def decide(model, request, principal, epoch, grant, stored, *, earlier_epoch=None):
    if grant is None:
        return "denied"
    decision_epoch = epoch if model["epoch_source"] == "decision-current" else earlier_epoch
    current = {**request, "principal": principal, "epoch": decision_epoch}
    exact = all(grant[field] == current[field] for field in model["grant_binding"])
    if stored is None:
        return "released" if exact and grant["role"] == model["new_grant_role"] else "denied"
    same_receipt = all(stored[field] == request[field] for field in model["receipt_binding"])
    if model["disclosure_order"] == "conflict-before-authority" and not same_receipt:
        return "conflict"
    if not exact or grant["role"] != model["retry_grant_role"]:
        return "denied"
    return "replayed" if same_receipt else "conflict"


def scope_controls(model):
    grants, receipts = candidates()
    release_grant, read_grant = grants[1:3]
    expected = [
        ("still-current", EPOCH, release_grant, None, "released"),
        ("revoked-before-release", EPOCH + 1, release_grant, None, "denied"),
        ("revoked-grant-absent", EPOCH + 1, None, None, "denied"),
        ("replacement-release-grant", EPOCH + 1, {**release_grant, "epoch": EPOCH + 1}, None, "released"),
        ("expired-observer", EPOCH + 1, read_grant, receipts[1], "denied"),
        ("new-observer-after-release-authority-loss", EPOCH + 1,
         {**read_grant, "epoch": EPOCH + 1}, receipts[1], "replayed"),
    ]
    stale = {**model, "epoch_source": "prepared"}
    rows = []
    for name, epoch, grant, receipt, expected_outcome in expected:
        control = from_source(REQUEST, CALLER, epoch, grant, receipt)
        checked = decide(model, REQUEST, CALLER, epoch, grant, receipt)
        old_epoch = decide(stale, REQUEST, CALLER, epoch, grant, receipt, earlier_epoch=EPOCH)
        assert control == checked == expected_outcome
        rows.append({"case": name, "current_epoch": epoch, "grant": grant, "receipt": receipt,
                     "expected": control, "prepared_epoch_mutant": old_epoch})
    assert sum(row["expected"] != row["prepared_epoch_mutant"] for row in rows) == 4
    return rows


def verify_lean(tool, root, expected):
    version = invoke([tool, "--version"], root).decode().strip()
    assert "4.36.0" in version and "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    output = invoke([tool, "--run", HERE / "Release.lean"], root).decode().splitlines()
    used = [re.fullmatch(r"'ReleaseFixture\.(\w+)' does not depend on any axioms", line)
            for line in output[:-1]]
    assert all(used) and tuple(match[1] for match in used) == THEOREMS
    codes = tuple(map(int, output[-1].split(",")))
    assert codes == tuple(CODES.index(value) for value in expected)
    assert len(codes) == 2145
    negative_claims = {
        "allow-stale-grant": "ReleaseFixture.gate 31 38 ReleaseFixture.seedRequest "
                             "(some (ReleaseFixture.grantAt 0 .release)) none = .released",
        "replay-changed-payload": "ReleaseFixture.gate 31 37 ReleaseFixture.seedRequest "
                                  "(some (ReleaseFixture.grantAt 0 .observe)) "
                                  "(some (ReleaseFixture.priorAt 16)) = .replayed",
    }
    for name, claim in negative_claims.items():
        candidate = root / "Negative.lean"
        original = (HERE / "Release.lean").read_text()
        candidate.write_text(original + f"\nexample : {claim} := by rfl\n")
        result = subprocess.run([tool, candidate], cwd=root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=20)
        assert result.returncode and "rfl" in result.stdout and "not definitionally equal" in result.stdout, result.stdout
    return {"version": version, "checker_sha256": digest(Path(tool).read_bytes()),
            "formalization_sha256": digest((HERE / "Release.lean").read_bytes()),
            "checked_theorems": list(THEOREMS), "axioms": [], "finite_codes": list(codes),
            "kernel_refused_claims": negative_claims}


def assess(model_id, verified, alleged, reading_matches, mismatches):
    if not reading_matches or mismatches:
        return "revise"
    if alleged is None:
        return "withhold-proof-required"
    if alleged != {"model_sha256": model_id,
                   "formalization_sha256": verified["formalization_sha256"],
                   "checker_sha256": verified["checker_sha256"],
                   "theorems": list(THEOREMS), "scope": "Lean release gate"}:
        return "withhold-proof-mismatch"
    return "eligible-for-review-in-checked-model"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lean", type=lambda value: str(Path(value).resolve()), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    model = json.loads((HERE / "contract.json").read_bytes())
    model_id = digest(encoded(model))
    mutants = {
        "ignore-principal": {**model, "grant_binding": [field for field in GRANT_FIELDS
                                                       if field != "principal"]},
        "ignore-epoch": {**model, "grant_binding": list(GRANT_FIELDS[:-1])},
        "ignore-payload": {**model, "receipt_binding": list(RECEIPT_FIELDS[:-1])},
        "wrong-replay-role": {**model, "retry_grant_role": "release"},
        "conflict-before-authority": {**model, "disclosure_order": "conflict-before-authority"},
    }
    grants, receipts = candidates()
    cases = [(grant, receipt) for grant in grants for receipt in receipts]
    expected = [from_source(REQUEST, CALLER, EPOCH, grant, receipt) for grant, receipt in cases]
    with tempfile.TemporaryDirectory(prefix="rt02-release-") as scratch:
        root = Path(scratch)
        baseline = render(model, root)
        assert baseline == READING
        assert [decide(model, REQUEST, CALLER, EPOCH, grant, receipt) for grant, receipt in cases] == expected
        proof = verify_lean(args.lean, root, expected)
        readings = {name: render(variant, root) for name, variant in mutants.items()}
        defects = {}
        for name, variant in mutants.items():
            assert readings[name] != READING
            differences = []
            for index, ((grant, receipt), wanted) in enumerate(zip(cases, expected)):
                actual = decide(variant, REQUEST, CALLER, EPOCH, grant, receipt)
                if actual != wanted:
                    differences.append([index, wanted, actual])
            assert differences
            defects[name] = {"case_differences": differences, "reconstruction": readings[name]}
        assert render({**model, "epoch_source": "prepared"}, root) != READING
    receipt = {"model_sha256": model_id, "formalization_sha256": proof["formalization_sha256"],
               "checker_sha256": proof["checker_sha256"], "theorems": list(THEOREMS),
               "scope": "Lean release gate"}
    variants = {
        "checked": (receipt, True, 0),
        "finite-only": (None, True, 0),
        "stale-model": ({**receipt, "model_sha256": digest(encoded(mutants["ignore-epoch"]))}, True, 0),
        "wrong-scope": ({**receipt, "scope": "native deployment"}, True, 0),
        "missing-theorem": ({**receipt, "theorems": list(THEOREMS[:-1])}, True, 0),
        "wrong-checker": ({**receipt, "checker_sha256": "0" * 64}, True, 0),
        "changed-formalization": ({**receipt, "formalization_sha256": "0" * 64}, True, 0),
        "changed-reading": (receipt, False, 0),
        "semantic-mismatch": (receipt, True, 1),
    }
    outcomes = {name: assess(model_id, proof, *case) for name, case in variants.items()}
    assert Counter(outcomes.values()) == {"eligible-for-review-in-checked-model": 1,
                                        "withhold-proof-required": 1, "withhold-proof-mismatch": 5,
                                        "revise": 2}
    record = {"source_sha256": digest((HERE / "requirements.txt").read_bytes()),
              "oracle_sha256": digest((HERE / "oracle.py").read_bytes()),
              "model_sha256": model_id, "reconstruction": baseline,
              "proof": proof, "proof_admission": outcomes, "receipt": receipt,
              "baseline_outcomes": dict(Counter(expected)), "scope_and_epoch_controls": scope_controls(model),
              "mutant_observations": defects}
    args.out.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
