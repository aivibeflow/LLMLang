"""Check typed producer authority and exact subjects at LLMLang handoffs."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


AUTHORITY = {
    "proposal": "llm-author",
    "package-integrity": "artifact-registry",
    "compiled-artifact": "compiler",
    "plugin-request": "plugin",
    "observed-result": "external-verifier",
    "execution-grant": "runtime-supervisor",
}
REQUIRED = {
    "validate-candidate": ("proposal", "package-integrity"),
    "accept-artifact": ("proposal", "package-integrity", "compiled-artifact", "observed-result"),
    "perform-host-effect": ("compiled-artifact", "observed-result", "plugin-request", "execution-grant"),
}


@dataclass(frozen=True)
class Context:
    project: str
    candidate: str
    artifact: str
    profile: str
    effect: str
    epoch: int


@dataclass(frozen=True)
class Claim:
    kind: str
    producer: str
    context: Context
    authenticated: bool = True


BASE = Context("fixture-project", "candidate-a", "artifact-a", "bounded-profile", "fixture:write-result", 10)


def admits(action, context, claims):
    if len(claims) != len(REQUIRED[action]) or {claim.kind for claim in claims} != set(REQUIRED[action]):
        return False
    return all(claim.authenticated and claim.producer == AUTHORITY[claim.kind] and claim.context == context
               for claim in claims)


def decide():
    counts = Counter()
    role_denials = Counter()
    context_denials = Counter()
    examples = {}
    for action, kinds in REQUIRED.items():
        expected = {kind: Claim(kind, AUTHORITY[kind], BASE) for kind in kinds}
        assert admits(action, BASE, tuple(expected.values()))
        for kind, foreign, authenticated, context in product(
            kinds, AUTHORITY.values(), (False, True),
            (BASE, replace(BASE, project="other"), replace(BASE, candidate="candidate-b"),
             replace(BASE, artifact="artifact-b"), replace(BASE, profile="different"),
             replace(BASE, effect="fixture:read-other"), replace(BASE, epoch=9))
        ):
            claims = expected | {kind: Claim(kind, foreign, context, authenticated)}
            accepted = admits(action, BASE, tuple(claims.values()))
            authorized = authenticated and foreign == AUTHORITY[kind] and context == BASE
            assert accepted == authorized
            counts[f"{action}/{'accept' if accepted else 'refuse'}"] += 1
            if authenticated and context == BASE and foreign != AUTHORITY[kind]:
                role_denials[action] += 1
            if authenticated and context != BASE and foreign == AUTHORITY[kind]:
                context_denials[action] += 1
        full = list(expected.values())
        examples[action] = {
            "missing_required": admits(action, BASE, full[:-1]),
            "duplicated_required": admits(action, BASE, [*full, full[0]]),
            "changed_handoff_subject": admits(action, replace(BASE, epoch=11), full),
        }
        assert not any(examples[action].values())
    runtime = tuple(Claim(kind, AUTHORITY[kind], BASE) for kind in REQUIRED["perform-host-effect"])
    assert not admits("perform-host-effect", BASE, [
        replace(claim, producer="plugin") if claim.kind == "execution-grant" else claim for claim in runtime
    ])
    assert not admits("perform-host-effect", BASE, [
        replace(claim, producer="artifact-registry") if claim.kind == "observed-result" else claim for claim in runtime
    ])
    return {"python": platform.python_version(), "candidate_context": asdict(BASE), "authority": AUTHORITY,
            "handoffs": REQUIRED, "counts": counts, "total": sum(counts.values()),
            "sole_wrong_role_controls": role_denials, "sole_wrong_context_controls": context_denials,
            "structural_controls": examples, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(decide(), sort_keys=True, indent=2))
