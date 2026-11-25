"""Compare scoped proof identities, exact CAS checks and independently gated admission."""
import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import runpy
from subprocess import check_output
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PACKAGE = ROOT / "research/packages-and-ecosystem/PROTOTYPES/PACKAGE-IDENTITY-01"
SIGNER = ROOT / "research/toolchain-and-collaboration/RT-11/SIGNED-REBUILD-ADMISSION-01/run.py"
PIN = "7e9b90e9c512379d1af387e5ae63a522653f263d"
sys.path.insert(0, str(PACKAGE))
from cache_index import expected_action_key, validate_cache_index
from language_version import registry_digest
from package_identity import digest as canonical_digest

SIGNERS = runpy.run_path(str(SIGNER))
COMPONENTS = ("syntax", "core_semantics")
PROPERTIES = ("integer-result", "event-trace")


def ref(value):
    return canonical_digest("proof-fixture-reference/1", value)


@dataclass(frozen=True, order=True)
class Dependency:
    role: str
    subject: str


class IncompleteInventory(ValueError):
    pass


@dataclass(frozen=True)
class Specification:
    claim: str = "translation-preserves"
    hypotheses: tuple = ("input-available", "range-checked")
    arithmetic: str = "return-add"
    trace: str = "read-then-write"
    source_map: str = "source-correspondence-v1"
    backend: str = "solver-a"
    limits: int = 4
    certificate: bytes = b"fixture certificate bytes"
    checker: str = "checker-a"
    imports: str = "pinned-imports-a"
    provider: str = "provider-a"
    occurrence: str = "body/left"
    policy: str = "no-unknown-assumptions"
    epoch: int = 8
    note: str = "experimental"


def required(spec, property_kind):
    by_property = {
        "integer-result": Dependency("arithmetic-projection", ref(spec.arithmetic)),
        "event-trace": Dependency("ordered-trace-projection", ref(spec.trace)),
    }
    return (by_property[property_kind], Dependency("source-correspondence", ref(spec.source_map)),
            Dependency("observation-semantics", ref(property_kind + "/semantics/1")))


def package_record(spec, obligation, dependencies, artifact):
    options = {
        "action_kind": "proof-verification-execution",
        "action_implementation": ref("typed-obligation-action/1"),
        "input_hashes": [obligation, *(canonical_digest("typed-dependency/1", [item.role, item.subject])
                                      for item in sorted(dependencies))],
        "language_version": "1.0",
        "language_component_registry_digest": registry_digest(COMPONENTS),
        "toolchain_identity": ref(spec.backend),
        "target_profile_digest": ref("formal-model/profile-v1"),
        "configuration_digest": ref(["ceiling", spec.limits]),
        "runtime_identity": ref("local-runtime-a"),
        "status": "success",
        "determinism": "byte_deterministic",
        "dependency_complete": True,
        "output_artifacts": [artifact],
    }
    return {"action_key": expected_action_key(options, COMPONENTS), **options}


def identities(spec, property_kind, declarations):
    expected = required(spec, property_kind)
    if len(declarations) != len(expected) or set(declarations) != set(expected):
        raise IncompleteInventory("declared dependency roles differ from the current property inventory")
    obligation = canonical_digest("obligation/1", [
        spec.claim, property_kind, list(spec.hypotheses), "typed-scope/1",
    ])
    artifact = canonical_digest("proof-artifact/1", ["fixture-certificate/1", spec.certificate])
    execution = package_record(spec, obligation, declarations, artifact)
    check = canonical_digest("proof-check-action/1", [
        obligation, artifact, ref(spec.checker), ref(spec.imports), "checker-options/1",
    ])
    closure = canonical_digest("proof-closure/1", [
        obligation, check, [[item.role, item.subject] for item in sorted(expected)],
        spec.occurrence, ref(spec.provider), "premises-discharged",
    ])
    admission = canonical_digest("proof-admission/1", [closure, spec.policy, spec.epoch])
    return {"obligation": obligation, "execution": execution["action_key"], "artifact": artifact,
            "check": check, "closure": closure, "admission": admission}, execution


OC = {"obligation", "execution", "check", "closure", "admission"}
DEP = {"execution", "closure", "admission"}
CHECK = {"check", "closure", "admission"}
TRANSITIONS = (
    ("claim", "different-claim", OC),
    ("hypotheses", ("range-checked", "input-available"), OC),
    ("arithmetic", "return-subtract", {"integer-result": DEP, "event-trace": set()}),
    ("trace", "write-then-read", {"integer-result": set(), "event-trace": DEP}),
    ("source_map", "source-correspondence-v2", DEP),
    ("backend", "solver-b", {"execution"}),
    ("limits", 9, {"execution"}),
    ("certificate", b"different certificate bytes", {"artifact", *CHECK}),
    ("checker", "checker-b", CHECK),
    ("imports", "pinned-imports-b", CHECK),
    ("provider", "provider-b", {"closure", "admission"}),
    ("occurrence", "body/right", {"closure", "admission"}),
    ("policy", "different-assurance", {"admission"}),
    ("epoch", 9, {"admission"}),
    ("note", "edited discussion", set()),
)


def matrix(base):
    counted = {}
    for property_kind in PROPERTIES:
        original, record = identities(base, property_kind, required(base, property_kind))
        wrapper = {"schema": "llmlang.cache-index", "schema_version": 1, "records": [record]}
        assert validate_cache_index(wrapper, COMPONENTS) == wrapper
        different = Counter()
        totals = Counter()
        for switches in product((False, True), repeat=len(TRANSITIONS)):
            selected = [transition for active, transition in zip(switches, TRANSITIONS) if active]
            variant = replace(base, **{field: value for field, value, _ in selected})
            keys, _ = identities(variant, property_kind, required(variant, property_kind))
            changed = {kind for kind in keys if original[kind] != keys[kind]}
            wanted = set().union(*(scope[property_kind] if isinstance(scope, dict) else scope
                                   for _, _, scope in selected))
            assert changed == wanted, (property_kind, selected, changed, wanted)
            totals.update(changed)
            for left, right in (("artifact", "check"), ("obligation", "execution"), ("closure", "admission")):
                if left not in changed and right in changed:
                    different[f"{left}=>{right}"] += 1
        projections = required(base, property_kind)
        for order in permutations(projections):
            assert identities(base, property_kind, order)[0] == original
        for invalid in (projections[1:], (*projections[:-1], projections[0]),
                        (replace(projections[0], role="wrong-role"), *projections[1:])):
            try:
                identities(base, property_kind, invalid)
            except IncompleteInventory:
                pass
            else:
                raise AssertionError(("incomplete provenance admitted", invalid))
        legacy = package_record(base, original["obligation"], projections[1:], original["artifact"])
        unchecked = {**wrapper, "records": [legacy]}
        assert validate_cache_index(unchecked, COMPONENTS)
        counted[property_kind] = {"matrix": 2 ** len(TRANSITIONS), "invalidations": dict(totals),
                                  "false-key-substitutions": dict(different),
                                  "canonical_orders": 6, "independent_role_refusals": 3,
                                  "generic_cache_shape_accepts_missing_declared_role": True}
    return counted


def admission(signed, keys, allowed, signers, cas, checked):
    try:
        message = json.loads(signed.message)
    except (TypeError, ValueError):
        return "invalid-envelope"
    if not isinstance(message, dict) or set(message) != {"issuer", "keys", "format"}:
        return "invalid-envelope"
    issuer = message["issuer"]
    if not isinstance(issuer, str) or issuer not in allowed or not signers.verify(signed, issuer):
        return "issuer-or-signature"
    if message["format"] != "fixture-proof-admission/1" or message["keys"] != keys:
        return "wrong-binding"
    raw = cas.get(keys["artifact"])
    if raw is None or canonical_digest("proof-artifact/1", ["fixture-certificate/1", raw]) != keys["artifact"]:
        return "artifact-unavailable"
    if checked != (keys["check"], keys["closure"], "checked"):
        return "independent-check-unavailable"
    return "admitted"


def signature_controls(base, directory):
    def current(spec):
        return identities(spec, PROPERTIES[0], required(spec, PROPERTIES[0]))[0]

    signers = SIGNERS["Signers"](directory)
    exact = current(base)
    store = {exact["artifact"]: base.certificate}

    def envelope(issuer, keys):
        return {"issuer": issuer, "keys": keys, "format": "fixture-proof-admission/1"}

    checked = (exact["check"], exact["closure"], "checked")
    old = signers.sign(envelope("alice", exact))
    next_keys = current(replace(base, epoch=9))
    assert next_keys["artifact"] == exact["artifact"] and next_keys["closure"] == exact["closure"]
    refreshed = signers.sign(envelope("bob", next_keys))
    other_occurrence = current(replace(base, occurrence="body/right"))
    mismatched = signers.sign(envelope("alice", other_occurrence))
    forged_payload = b"replacement bytes with a signed claim"
    forged_keys = current(replace(base, certificate=forged_payload))
    forged = signers.sign(envelope("alice", forged_keys))
    visitor = signers.sign(envelope("visitor", exact))
    damaged_signature = replace(old, signature=bytes([old.signature[0] ^ 1]) + old.signature[1:])
    scenarios = (
        ("exact", old, exact, {"alice"}, store, checked, "admitted"),
        ("missing-payload", old, exact, {"alice"}, {}, checked, "artifact-unavailable"),
        ("missing-check", old, exact, {"alice"}, store, None, "independent-check-unavailable"),
        ("signed-rehashed-artifact", forged, forged_keys, {"alice"},
         {forged_keys["artifact"]: forged_payload}, checked, "independent-check-unavailable"),
        ("second-occurrence", mismatched, exact, {"alice"}, store, checked, "wrong-binding"),
        ("closure-with-unknown-assumption", old, exact, {"alice"}, store,
         (exact["check"], exact["closure"], "unknown"), "independent-check-unavailable"),
        ("unapproved-signer", visitor, exact, {"alice"}, store, checked, "issuer-or-signature"),
        ("revoked-signer", old, exact, set(), store, checked, "issuer-or-signature"),
        ("damaged-signature", damaged_signature, exact, {"alice"}, store, checked, "issuer-or-signature"),
        ("old-policy-epoch", old, next_keys, {"alice"}, store, checked, "wrong-binding"),
        ("refresh-under-current-policy", refreshed, next_keys, {"bob"}, store, checked, "admitted"),
        ("corrupt-cas", old, exact, {"alice"}, {exact["artifact"]: b"other"}, checked, "artifact-unavailable"),
    )
    outcomes = {}
    for label, signed, keys, allowed, cas, evidence, expected in scenarios:
        decision = admission(signed, keys, allowed, signers, cas, evidence)
        assert decision == expected, (label, decision, expected)
        outcomes[label] = decision
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    pinned = {}
    for path in (SIGNER, *(PACKAGE / name for name in ("package_identity.py", "cache_index.py",
                                                       "language_version.py"))):
        location = path.relative_to(ROOT).as_posix()
        archived = check_output(["git", "show", f"{PIN}:{location}"], cwd=ROOT)
        assert path.read_bytes() == archived
        pinned[location] = sha256(archived).hexdigest()
    base = Specification()
    with TemporaryDirectory() as directory:
        exact_results = signature_controls(base, Path(directory))
    result = {"basis": PIN, "source_hashes": pinned, "keys_by_property": matrix(base),
              "signed_controls": exact_results,
              "openssl": check_output(["/usr/bin/openssl", "version"], text=True).strip()}
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
