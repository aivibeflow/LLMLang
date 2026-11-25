"""Check candidate RT-04 semantic field identity and exact observation receipt boundaries."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


BASE = "688fe5dab78c69d495bc7e7d366008f69cbbba58"
PUBLIC = ("type", "ownership", "effect-order", "error", "public-capability", "protocol")
PROVIDER = ("body", "private-cleanup", "resolved-aliases")
EVIDENCE = ("target", "checker", "assumptions", "observation")
OTHER = ("display-name", "source-position")
PROJECTIONS = ("error", "error+ownership", "error+ownership+next-admission")


def identity(domain, fields):
    raw = json.dumps([domain, fields], sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


def keys(edit):
    def version(fields):
        return {field: int(field == edit) for field in fields}

    operation = identity("public-operation", version(PUBLIC))
    implementation = identity("implementation", version(PROVIDER))
    claim = identity("body-refines-operation", [operation, implementation, version(EVIDENCE)])
    source = identity("source-correspondence", [operation, implementation, int(edit == "source-position")])
    return operation, implementation, claim, source


def identity_checks():
    expected = {
        **{field: (True, False, True, True) for field in PUBLIC},
        **{field: (False, True, True, True) for field in PROVIDER},
        **{field: (False, False, True, False) for field in EVIDENCE},
        "display-name": (False, False, False, False),
        "source-position": (False, False, False, True),
    }
    original = keys(None)
    rows = {}
    for field in (*PUBLIC, *PROVIDER, *EVIDENCE, *OTHER):
        changed = tuple(a != b for a, b in zip(original, keys(field), strict=True))
        assert changed == expected[field]
        rows[field] = changed
    return rows


def applicability_controls():
    outcomes = Counter()
    for required, observed, current_body, current_assumptions, verified in product(
        PROJECTIONS, PROJECTIONS, (False, True), (False, True), (False, True),
    ):
        exact = identity("receipt", [required, "body-v2", "assumptions-v2"])
        received = identity("receipt", [observed, "body-v2" if current_body else "body-v1",
                                        "assumptions-v2" if current_assumptions else "assumptions-v1"])
        accepted = verified and received == exact
        assert accepted == (required == observed and current_body and current_assumptions and verified)
        outcomes["applicable" if accepted else "withheld"] += 1
    return dict(outcomes)


def archive():
    paths = (
        "research/language-design/RT-04/CLEANUP-IDENTITY-01/evidence.json",
        "research/semantic-representation/RT-05/PUBLIC-OBLIGATIONS-01/evidence.json",
        "research/semantic-representation/RT-05/CANDIDATE-ENVELOPES-01/evidence.json",
        "research/formal-verification/RT-07/RT-07-JOINT-OBSERVATION-REFINEMENT-2026-11-25.md",
    )
    return {path: sha256(subprocess.check_output(["git", "show", f"{BASE}:{path}"])).hexdigest()
            for path in paths}


if __name__ == "__main__":
    print(json.dumps({
        "revision": BASE, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "key_order": ("operation", "implementation", "proof-scope", "source-correspondence"),
        "field_edits": identity_checks(), "receipt_cases": applicability_controls(), "archives": archive(),
    }, sort_keys=True, indent=2))
