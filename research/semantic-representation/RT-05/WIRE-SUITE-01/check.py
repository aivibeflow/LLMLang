"""Check a typed canonical store boundary with explicitly versioned digest suites."""

from collections import Counter
from hashlib import new, sha256
from itertools import product
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


HERE = Path(__file__).resolve().parent
WIRE = HERE.parent / "CANONICAL-WIRE-01"
sys.path.insert(0, str(WIRE))
from run import PROFILE, controls, hash_bytes, python_status

BASE = "42402234d7caee9bcdd7c3d26e3f4eb041d4d37d"
REGISTRY = {"sha256": 64, "sha512": 128}
POLICIES = {"current": frozenset(("sha512",)), "historical": frozenset(REGISTRY)}
DIGESTS = ("current-shape", "other-digest", "uppercase", "short")
ADDRESS = re.compile(r"([a-z][a-z0-9]*):([0-9a-f]+)", flags=re.ASCII)


def admit(wire, typed_status, locator, policy):
    match = ADDRESS.fullmatch(locator)
    if not match:
        return "locator-shape"
    suite, digest = match.groups()
    if suite not in REGISTRY:
        return "unknown-suite"
    if len(digest) != REGISTRY[suite]:
        return "locator-shape"
    if suite not in POLICIES[policy]:
        return "suite-out-of-scope"
    if typed_status != "accept":
        return typed_status
    return "accepted" if new(suite, wire).hexdigest() == digest else "digest"


def prepare():
    fixture = [item for item in controls() if item["name"] in {
        "canonical-operation", "canonical-contract", "whitespace", "duplicate-key",
        "invalid-utf8", "int-negative-zero", "wrong-version",
    }]
    result = []
    for item, domain in product(fixture, ("operation", "contract")):
        bytes_value = bytes.fromhex(item["raw_hex"])
        synthetic = {**item, "algorithm": "sha256", "digest": hash_bytes(bytes_value),
                     "expected_domain": domain}
        expected = item["expected"][0]
        if item["name"] == "whitespace":
            expected = "noncanonical"
        if expected in {"accept", "noncanonical", "typed"} and domain != item["expected_domain"]:
            expected = "domain"
        result.append((synthetic, bytes_value, expected))
    return result


def check():
    prepared = prepare()
    node = subprocess.check_output(["node", WIRE / "decode.mjs"],
                                   input=json.dumps([frame for frame, _, _ in prepared]).encode())
    node_status = json.loads(node)
    totals = Counter()
    for (frame, raw, expected_typed), result in zip(prepared, node_status, strict=True):
        assert python_status(frame)[0] == result[0] == expected_typed
        for suite, policy, spelling in product(REGISTRY, POLICIES, DIGESTS):
            exact = new(suite, raw).hexdigest()
            variants = {"current-shape": exact, "other-digest": "0" * len(exact),
                        "uppercase": exact.upper(), "short": exact[:16]}
            actual = admit(raw, expected_typed, f"{suite}:{variants[spelling]}", policy)
            if spelling in {"uppercase", "short"}:
                expected = "locator-shape"
            elif (suite, policy) == ("sha256", "current"):
                expected = "suite-out-of-scope"
            elif expected_typed != "accept":
                expected = expected_typed
            else:
                expected = "accepted" if spelling == "current-shape" else "digest"
            assert actual == expected
            totals[actual] += 1
    assert admit(b"", "accept", "sha999:0123", "current") == "unknown-suite"
    assert admit(b"", "accept", "0123", "historical") == "locator-shape"
    assert admit(b"", "accept", "sha256:" + "f" * 128, "historical") == "locator-shape"
    return {"typed_cases": len(prepared), "requests": sum(totals.values()), "dispositions": dict(totals)}


def ledger_hashes():
    result = {}
    for study in ("CANONICAL-WIRE-01", "CROSS-RUNTIME-I64-01", "CROSS-RUNTIME-F64-01", "DIGEST-MIGRATION-01"):
        path = f"research/semantic-representation/RT-05/{study}/evidence.json"
        raw = subprocess.check_output(["git", "show", f"{BASE}:{path}"])
        result[study] = sha256(raw).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps({
        "base": BASE, "wire_profile": PROFILE, "registry": REGISTRY, "results": check(),
        "source_sha256": {name: sha256((WIRE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "decode.mjs")},
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "ledger_sha256": ledger_hashes(), "python": platform.python_version(),
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
    }, indent=2, sort_keys=True))
