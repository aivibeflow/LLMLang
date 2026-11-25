"""Generate and check separate finite body and public refinement obligations."""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path


PROPERTIES = ("state", "effect", "authority", "ownership", "progress", "resource")


@dataclass(frozen=True)
class Outcome:
    state: str
    effect: tuple[str, ...]
    authority: str
    ownership: str
    progress: int
    resource: int


GOOD = Outcome("committed", ("reserve", "publish"), "scoped", "returned", 1, 2)
WITNESSES = {
    "state": "open", "effect": ("publish", "reserve"), "authority": "foreign",
    "ownership": "lost", "progress": 3, "resource": 5,
}
ALLOWED_INPUTS = ("first", "retry")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def identity(domain, rows):
    return sha256(encoded([domain, rows])).hexdigest()


def permitted(outcome, bound, name):
    observed, allowed = getattr(outcome, name), getattr(bound, name)
    return observed <= allowed if name in {"resource", "progress"} else observed == allowed


def body_check(body, contract, domain, name):
    if not domain:
        return "infeasible-scope"
    if contract is None:
        return "unknown"
    if set(domain) - body.keys() or any(body[subject] is None for subject in domain):
        return "refuted-coverage"
    return "verified" if all(permitted(body[subject], contract, name) for subject in domain) else "refuted"


def refinement_check(provider, public, provider_domain, public_domain, name):
    if not public_domain:
        return "infeasible-scope"
    if provider is None:
        return "unknown"
    if set(public_domain) - set(provider_domain):
        return "refuted-coverage"
    return "verified" if permitted(provider, public, name) else "refuted"


def generate():
    records = []
    for name, profile in product(PROPERTIES, (
        "exact", "body-fault", "refinement-fault", "coverage-gap", "domain-gap",
        "public-empty", "unsupported",
    )):
        failure = replace(GOOD, **{name: WITNESSES[name]})
        public = GOOD
        provider = None if profile == "unsupported" else failure if profile == "refinement-fault" else GOOD
        body = {key: provider for key in ALLOWED_INPUTS}
        if profile == "body-fault":
            body["retry"] = failure
        if profile == "coverage-gap":
            body.pop("retry")
        provider_domain = ALLOWED_INPUTS[:1] if profile == "domain-gap" else ALLOWED_INPUTS
        public_domain = () if profile == "public-empty" else ALLOWED_INPUTS
        body_subject = identity("body", {key: asdict(value) if value else None for key, value in body.items()})
        provider_subject = identity("provider", [asdict(provider) if provider else None, provider_domain])
        public_subject = identity("public", [asdict(public), public_domain])
        body_key = identity("body-correctness", [body_subject, provider_subject, name, "finite-model/1"])
        refinement_key = identity("refinement", [provider_subject, public_subject, name, "finite-model/1"])
        actual = (body_check(body, provider, provider_domain, name),
                  refinement_check(provider, public, provider_domain, public_domain, name))
        expected = {
            "exact": ("verified", "verified"), "body-fault": ("refuted", "verified"),
            "refinement-fault": ("verified", "refuted"), "coverage-gap": ("refuted-coverage", "verified"),
            "domain-gap": ("verified", "refuted-coverage"), "public-empty": ("verified", "infeasible-scope"),
            "unsupported": ("unknown", "unknown"),
        }[profile]
        assert actual == expected and body_key != refinement_key
        records.append({
            "property": name, "profile": profile,
            "body_subject": body_subject, "provider_subject": provider_subject, "public_subject": public_subject,
            "body_key": body_key, "refinement_key": refinement_key,
            "verdicts": actual, "admitted": set(actual) == {"verified"},
        })
    indexed = {(row["property"], row["profile"]): row for row in records}
    for name in PROPERTIES:
        exact = indexed[name, "exact"]
        assert indexed[name, "body-fault"]["refinement_key"] == exact["refinement_key"]
        assert indexed[name, "body-fault"]["body_key"] != exact["body_key"]
        assert indexed[name, "public-empty"]["body_key"] == exact["body_key"]
        assert indexed[name, "public-empty"]["refinement_key"] != exact["refinement_key"]
    return records


if __name__ == "__main__":
    obligations = generate()
    print(json.dumps({
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "checks": len(obligations) * 2, "admitted_property_pairs": sum(row["admitted"] for row in obligations),
        "obligations": obligations,
    }, sort_keys=True, indent=2))
