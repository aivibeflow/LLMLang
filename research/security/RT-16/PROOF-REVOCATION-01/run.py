"""Replay the Lean revocation model and exact recovery controls."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
SUBJECT = "checked-program-13"


@dataclass(frozen=True)
class Receipt:
    signer: str = "primary"
    checker: str = "checker-v1"
    implementation: str = "implementation-v1"
    issued: int = 0
    subject: str = SUBJECT
    authenticated: bool = True

    @property
    def identity(self):
        return sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Revocation:
    field: str
    value: str
    observed_at: int
    effective_from: int


@dataclass(frozen=True)
class Dependent:
    subject: str
    receipt_id: str


POLICIES = {
    "unchanged": (),
    "prospective-signer": (Revocation("signer", "primary", 6, 6),),
    "retroactive-checker": (Revocation("checker", "checker-v1", 6, 3),),
    "prior-implementation": (Revocation("implementation", "implementation-v1", 6, 0),),
}
CANDIDATES = {
    "original": {},
    "new-signer-only": {"signer": "alternate"},
    "rechecked": {"signer": "alternate", "checker": "checker-v2"},
    "different-implementation": {"implementation": "implementation-v2"},
    "different-subject": {"subject": "other-program"},
    "unauthenticated": {"authenticated": False},
}


def suitable(item, events, view):
    return (item.authenticated and item.subject == SUBJECT and item.issued <= view
            and not any(event.observed_at <= view and event.effective_from <= item.issued
                        and getattr(item, event.field) == event.value for event in events))


def current(item, events, cached_view, latest_view):
    return cached_view == latest_view and suitable(item, events, cached_view)


def linked(dependent, item, events, view):
    return (dependent.subject == item.subject and dependent.receipt_id == item.identity
            and current(item, events, view, view))


def reference(case, candidate, issued, now):
    if candidate in {"different-subject", "unauthenticated"} or issued > now:
        return False
    if now < 6:
        return True
    if case == "prospective-signer" and issued >= 6:
        return candidate in {"new-signer-only", "rechecked"}
    if case == "retroactive-checker" and issued >= 3:
        return candidate == "rechecked"
    if case == "prior-implementation":
        return candidate == "different-implementation"
    return True


def verify(lean):
    summary = {}
    for policy, candidate, issued, now in product(POLICIES, CANDIDATES, range(9), range(10)):
        item = Receipt(issued=issued, **CANDIDATES[candidate])
        events = POLICIES[policy]
        expected = reference(policy, candidate, issued, now)
        accepted = current(item, events, now, now)
        cached = item.issued <= now and suitable(item, events, issued)
        if accepted != expected:
            raise AssertionError((policy, candidate, issued, now, expected, accepted))
        counts = summary.setdefault(policy, Counter())
        counts["cases"] += 1
        counts["current_accepted"] += accepted
        counts["cached_accepted"] += cached
        counts["cached_incorrect_acceptance"] += cached and not expected

    prior = Receipt(issued=4)
    new_key_same_checker = replace(prior, signer="alternate", issued=7)
    independent_recheck = replace(new_key_same_checker, checker="checker-v2")
    different_subject = replace(independent_recheck, subject="other-program")
    existing = Dependent(SUBJECT, prior.identity)
    relinked = Dependent(SUBJECT, independent_recheck.identity)
    events = POLICIES["retroactive-checker"]

    recovery = {
        "accepted_in_historical_view": suitable(prior, events, 4),
        "old_receipt_current": current(prior, events, 7, 7),
        "stale_policy_view_current": current(prior, events, 4, 7),
        "new_signer_same_compromised_checker": current(new_key_same_checker, events, 7, 7),
        "independent_recheck": current(independent_recheck, events, 7, 7),
        "old_dependent_with_replacement": linked(existing, independent_recheck, events, 7),
        "relinked_dependent_with_replacement": linked(relinked, independent_recheck, events, 7),
        "different_subject": current(different_subject, events, 7, 7),
        "blocked_implementation_with_same_subject":
            current(independent_recheck, POLICIES["prior-implementation"], 7, 7),
    }
    assert {key for key, result in recovery.items() if result} == {
        "accepted_in_historical_view", "independent_recheck", "relinked_dependent_with_replacement",
    }

    checker = subprocess.run([lean, str(HERE / "Revocation.lean")], check=True,
                             capture_output=True, text=True, timeout=60)
    assertions = checker.stdout.splitlines()
    if checker.stderr or [row.split("'")[1] for row in assertions] != [
        "revocation_persists", "unseen_event_does_not_apply", "issuance_before_cutoff_is_unaffected",
        "replacement_does_not_validate_old_dependency",
    ]:
        raise ValueError((checker.stdout, checker.stderr))
    return {
        "lean": subprocess.check_output([lean, "--version"], text=True, timeout=10).strip(),
        "theorems": assertions,
        "total_cases": sum(row["cases"] for row in summary.values()),
        "matrix": summary,
        "recovery_controls": recovery,
        "receipt_identities": {"previous": prior.identity, "independent_recheck": independent_recheck.identity},
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("Revocation.lean", "run.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    print(json.dumps(verify(parser.parse_args().lean), indent=2))
