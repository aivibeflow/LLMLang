"""Experimental evidence composition over exact claims and trusted receipts."""
from collections import defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

PROTOCOL = "rt33-evidence-composition-v1"
VERDICTS = {"support", "counterexample", "unknown", "timeout", "unsupported"}
POSITIVE = {"bounded-agreement", "proven"}


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(data).hexdigest()


def is_digest(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class Claim:
    name: str
    revision: str
    obligation: str
    subject: str
    domain: str
    projection: str
    scope: str
    premises: tuple[str, ...] = ()

    @property
    def key(self):
        fields = asdict(self)
        fields["premises"] = sorted(self.premises)
        return digest((PROTOCOL, fields))


@dataclass(frozen=True)
class Backend:
    name: str
    tool: str
    translator: str
    configuration: str
    scopes: tuple[str, ...]

    @property
    def key(self):
        return digest((PROTOCOL, asdict(self)))


@dataclass(frozen=True)
class Receipt:
    claim: str
    closure: str
    backend: str
    artifact: str
    verdict: str

    @property
    def key(self):
        return digest((PROTOCOL, asdict(self)))


def decode_receipt(raw):
    """Decode shape only. A verifier must separately authorize the exact receipt."""
    def exact_fields(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("duplicate receipt field")
        return result

    data = json.loads(raw, object_pairs_hook=exact_fields)
    fields = {"claim", "closure", "backend", "artifact", "verdict"}
    if (not isinstance(data, dict) or set(data) != fields
            or any(not is_digest(data[field]) for field in fields - {"verdict"})
            or not isinstance(data["verdict"], str) or data["verdict"] not in VERDICTS):
        raise ValueError("invalid evidence receipt")
    return Receipt(**data)


class Plan:
    """Trusted declarations. Evidence cannot choose its own required premises."""
    def __init__(self, claims, backends, *, mandatory=None):
        self._claims = {claim.name: claim for claim in claims}
        self._backends = {backend.key: backend for backend in backends}
        if len(self._claims) != len(claims):
            raise ValueError("duplicate claim name")
        self._mandatory = tuple(sorted(self._claims)) if mandatory is None else tuple(mandatory)
        if (len(set(self._mandatory)) != len(self._mandatory)
                or not set(self._mandatory) <= self._claims.keys()):
            raise ValueError("invalid mandatory claims")
        self._closures = {}
        self._order = []
        visiting = set()

        def visit(name):
            if name in self._closures:
                return self._closures[name]
            if name in visiting:
                raise ValueError("cycle in evidence plan")
            if name not in self._claims:
                raise ValueError(f"missing premise {name}")
            claim = self._claims[name]
            if claim.scope not in {"finite", "unbounded"}:
                raise ValueError(f"invalid scope for {name}")
            if (len(set(claim.premises)) != len(claim.premises)
                    or name in claim.premises):
                raise ValueError(f"invalid premises for {name}")
            visiting.add(name)
            premises = [(premise, visit(premise)) for premise in sorted(claim.premises)]
            closure = digest((PROTOCOL, claim.key, premises))
            visiting.remove(name)
            self._closures[name] = closure
            self._order.append(name)
            return closure

        for name in sorted(self._claims):
            visit(name)

    def receipt(self, name, backend, artifact, verdict):
        return Receipt(self._claims[name].key, self._closures[name], backend.key, artifact, verdict)

    def evaluate(self, candidates, authorized):
        """The caller supplies exact receipt keys authenticated by its verification path."""
        current = {claim.key: name for name, claim in self._claims.items()}
        admitted = defaultdict(set)
        rejected = {}
        for receipt in candidates:
            name = current.get(receipt.claim)
            backend = self._backends.get(receipt.backend)
            if receipt.key not in authorized:
                reason = "unverified"
            elif not is_digest(receipt.artifact) or receipt.verdict not in VERDICTS:
                reason = "unsupported-receipt"
            elif name is None:
                reason = "different-claim"
            elif receipt.closure != self._closures[name]:
                reason = "stale-premises"
            elif backend is None or self._claims[name].scope not in backend.scopes:
                reason = "ineligible-backend"
            else:
                admitted[name].add(receipt.verdict)
                continue
            rejected[receipt.key] = reason

        results = {}
        for name in self._order:
            claim = self._claims[name]
            evidence = admitted[name]
            blocked = [premise for premise in claim.premises
                       if not self._discharged(claim.scope, results[premise]["status"])]
            if "support" in evidence and "counterexample" in evidence:
                status = "conflict"
            elif evidence.isdisjoint({"support", "counterexample"}):
                status = "insufficient"
            elif blocked:
                status = "conditional"
            elif "counterexample" in evidence:
                status = "refuted"
            else:
                status = "proven" if claim.scope == "unbounded" else "bounded-agreement"
            results[name] = {"status": status, "blocked_premises": blocked,
                             "observed_verdicts": sorted(evidence)}
        return results, rejected, _aggregate(results, self._mandatory)

    @staticmethod
    def _discharged(scope, status):
        return status == "proven" or (scope == "finite" and status == "bounded-agreement")


def _aggregate(results, mandatory):
    statuses = [results[name]["status"] for name in mandatory]
    for status in ("conflict", "refuted", "insufficient", "conditional", "bounded-agreement"):
        if status in statuses:
            return status
    if statuses and all(status in POSITIVE for status in statuses):
        return "proven"
    return "insufficient"
