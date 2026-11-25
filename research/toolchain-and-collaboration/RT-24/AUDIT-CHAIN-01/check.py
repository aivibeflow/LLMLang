"""Check signed audit ordering and distinct roles on one synthetic change set."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
SIGN_SOURCE = HERE.parents[3] / "research" / "security" / "RT-16" / "BUILD-ATTESTATION-01" / "run.py"
spec = importlib.util.spec_from_file_location("rt24_signing", SIGN_SOURCE)
SIGN = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = SIGN
spec.loader.exec_module(SIGN)

DECISIONS = {"author": "submitted", "validator": "verified", "reviewer": "approved",
             "publisher": "committed"}
ROLES = tuple(DECISIONS)
RECORD = "fixture-change-audit:v1"
CONTEXT = {"candidate": "fixture-tree:exact", "scope": "binding:reserve", "epoch": 7}
GENESIS = "0" * 64


def identity(record):
    return sha256(record.payload).hexdigest()


def checked(openssl, scratch, chain, public, checkpoint):
    if len(chain) != len(ROLES):
        return "missing-lifecycle-event"
    predecessor = GENESIS
    for ordinal, (role, record) in enumerate(zip(ROLES, chain, strict=True)):
        claim = json.loads(record.payload)
        if claim.get("role") != role or claim.get("ordinal") != ordinal:
            return "wrong-role-or-order"
        if claim.get("record") != RECORD or claim.get("decision") != DECISIONS[role]:
            return "wrong-event-disposition"
        if any(claim.get(field) != value for field, value in CONTEXT.items()):
            return "wrong-subject-or-policy"
        if claim.get("previous") != predecessor:
            return "chain-discontinuity"
        data, signature = scratch / "verified-event", scratch / "verified-signature"
        data.write_bytes(record.payload)
        signature.write_bytes(record.signature)
        result = SIGN.execute([openssl, "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey",
                               str(public[role]), "-in", str(data), "-sigfile", str(signature)],
                              scratch, check=False)
        if result.returncode:
            return "invalid-role-signature"
        predecessor = identity(record)
    return "verified" if predecessor == checkpoint else "unexpected-tail"


def run(openssl, scratch):
    keys = {role: SIGN.keys(openssl, scratch, role) for role in ROLES}
    public = {role: pair[1] for role, pair in keys.items()}

    def sign(role, claim):
        return SIGN.sign(openssl, scratch, keys[role][0], claim)

    def sequence(overrides=None):
        overrides = overrides or {}
        chain = []
        for ordinal, role in enumerate(ROLES):
            claim = {"record": RECORD, **CONTEXT, "role": role, "ordinal": ordinal,
                     "previous": identity(chain[-1]) if chain else GENESIS,
                     "decision": DECISIONS[role]}
            override = overrides.get(role, {})
            actor = override.get("signer", role)
            chain.append(sign(actor, {**claim, **{k: v for k, v in override.items() if k != "signer"}}))
        return chain

    base = sequence()
    tail = identity(base[-1])
    cases = {
        "complete": (base, tail),
        "missing_review": ([base[0], base[1], base[3]], tail),
        "swapped_review_and_validation": ([base[0], base[2], base[1], base[3]], tail),
        "author_signs_review": (sequence({"reviewer": {"signer": "author"}}), tail),
        "approval_for_other_scope": (sequence({"reviewer": {"scope": "binding:other"}}), tail),
        "signed_disapproval": (sequence({"reviewer": {"decision": "refused"}}), tail),
        "old_policy": (sequence({"validator": {"epoch": 6}}), tail),
        "different_candidate": (sequence({"publisher": {"candidate": "fixture-tree:other"}}), tail),
        "unlinked_approval": (sequence({"reviewer": {"previous": GENESIS}}), tail),
        "wrong_checkpoint": (base, GENESIS),
    }
    results = {name: checked(openssl, scratch, chain, checkpoint=checkpoint, public=public)
               for name, (chain, checkpoint) in cases.items()}
    assert results == {
        "complete": "verified", "missing_review": "missing-lifecycle-event",
        "swapped_review_and_validation": "wrong-role-or-order", "author_signs_review": "invalid-role-signature",
        "approval_for_other_scope": "wrong-subject-or-policy", "old_policy": "wrong-subject-or-policy",
        "signed_disapproval": "wrong-event-disposition",
        "different_candidate": "wrong-subject-or-policy", "unlinked_approval": "chain-discontinuity",
        "wrong_checkpoint": "unexpected-tail",
    }
    return {"python": platform.python_version(), "openssl": SIGN.execute([openssl, "version"], scratch).stdout.strip(),
            "roles": ROLES, "checkpoint": tail, "subject": CONTEXT, "results": results,
            "record_payloads": [json.loads(record.payload) for record in base],
            "sources_sha256": {"check.py": sha256(Path(__file__).read_bytes()).hexdigest(),
                               "signing_fixture": sha256(SIGN_SOURCE.read_bytes()).hexdigest()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt24-audit-chain-") as scratch:
        print(json.dumps(run(args.openssl, Path(scratch)), sort_keys=True, indent=2))
