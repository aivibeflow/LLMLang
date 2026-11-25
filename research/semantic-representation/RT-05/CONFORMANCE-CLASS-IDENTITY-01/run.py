#!/usr/bin/env python3
"""Compare class definition, candidate discovery and finite evidence identities."""

from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "OPERATION-IDENTITY-01" / "evidence.json"
CHECKER = "complete-u8-native-observations/1"
INPUT_RANGE = range(256)
PROFILES = (
    ("wrap-general", "wrap", "x86_64", 3),
    ("wrap-short", "wrap", "x86_64", 2),
    ("saturate-general", "saturate", "x86_64", 3),
    ("wrap-aarch64", "wrap", "aarch64", 3),
)
VARIANTS = (
    "exact", "absent", "different-class", "different-implementation", "stale-checker", "different-ledger",
)


def key(domain, payload):
    data = json.dumps((domain, payload), sort_keys=True, separators=(",", ":")).encode("ascii")
    return sha256(data).hexdigest()


def observed_relation(value, trace, argument, mode, maximum):
    if len(trace) > maximum:
        return False
    if trace == ("read", "commit"):
        return value == argument
    if trace == ("read", "advance", "commit"):
        expected = (argument + 1) % 256 if mode == "wrap" else min(argument + 1, 255)
        return value == expected
    return False


def observed_membership(archive, provider, mode, machine, maximum):
    traces = archive["trace_codebook"]
    values = bytes.fromhex(provider["result_bytes_hex"])
    matches = sum(
        observed_relation(value, tuple(traces[trace]), index, mode, maximum)
        for index, value, trace in zip(INPUT_RANGE, values, provider["trace_codes"], strict=True)
    )
    return {
        "matching_rows": matches,
        "target_admitted": (
            archive["host"]["system"], archive["host"]["architecture"],
        ) == ("Linux", machine),
    }


def decide(class_hash, implementation, ledger_digest, receipt):
    if receipt is None:
        return "pending"
    subject = (receipt["class_hash"], receipt["implementation"], receipt["checker"], receipt["ledger"])
    if subject != (class_hash, implementation, CHECKER, ledger_digest):
        return "pending"
    good = receipt["target_admitted"] and receipt["matching_rows"] == len(INPUT_RANGE)
    return "conforming" if good else "refuted"


def different_identity(value):
    return key("unrelated-fixture-identity/1", value)


def alternate_receipt(subject, variant, other_class, other_impl):
    if variant == "absent":
        return None
    receipt = dict(subject)
    if variant == "different-class":
        receipt["class_hash"] = other_class
    if variant == "different-implementation":
        receipt["implementation"] = other_impl
    if variant == "stale-checker":
        receipt["checker"] = "obsolete-fixture-checker"
    if variant == "different-ledger":
        receipt["ledger"] = different_identity(receipt["ledger"])
    return receipt


def snapshots(rows):
    wrapped = {row["provider"]: row["implementation_hash"] for row in rows if row["context"] == "wrap"}
    specs = (
        ("initial", "native-byte", ("stay", "mixed")),
        ("expanded", "native-byte", ("stay", "mixed", "advance")),
        ("reordered", "native-byte", ("advance", "mixed", "stay")),
        ("other-scope", "all-byte", ("advance", "mixed", "stay")),
    )
    return {
        name: {"scope": scope, "members": sorted(wrapped[provider] for provider in providers),
               "candidate_set_hash": key("candidate-set/1", (scope, sorted(wrapped[p] for p in providers)))}
        for name, scope, providers in specs
    }


def evidence_cases(archive, classes, ledger_digest):
    cases = []
    for name, mode, machine, maximum in PROFILES:
        definition = classes[name]
        class_hash = definition["class_hash"]
        other_class = next(item["class_hash"] for key, item in classes.items() if key != name)
        providers = [row for row in archive["rows"] if row["context"] == mode]
        for provider in providers:
            implementation = provider["implementation_hash"]
            other_impl = next(row["implementation_hash"] for row in providers
                              if row["implementation_hash"] != implementation)
            observation = observed_membership(archive, provider, mode, machine, maximum)
            subject = {
                "class_hash": class_hash, "implementation": implementation, "checker": CHECKER,
                "ledger": ledger_digest, **observation,
            }
            for variant in VARIANTS:
                receipt = alternate_receipt(subject, variant, other_class, other_impl)
                expected = "pending"
                if variant == "exact":
                    eligible = observation["target_admitted"] and observation["matching_rows"] == 256
                    expected = "conforming" if eligible else "refuted"
                if decide(class_hash, implementation, ledger_digest, receipt) != expected:
                    raise AssertionError(f"Unfaithful disposition for {name}, {provider['provider']}, {variant}")
                cases.append({
                    "class": name, "provider": provider["provider"], "variant": variant,
                    "expected": expected, "receipt": receipt,
                    "keys": {
                        "class_only": class_hash,
                        "class_and_implementation": key("subject/1", (class_hash, implementation)),
                        "exact_evidence_request": key(
                            "membership-request/1", (class_hash, implementation, CHECKER, ledger_digest, receipt)
                        ),
                    },
                })
    return cases


def results():
    archive_bytes = SOURCE.read_bytes()
    archive = json.loads(archive_bytes)
    ledger_digest = sha256(archive_bytes).hexdigest()
    classes = {}
    for name, mode, machine, maximum in PROFILES:
        operation, = {row["op_hash"] for row in archive["rows"] if row["context"] == mode}
        definition = {"op_hash": operation, "target": ["Linux", machine], "maximum_events": maximum,
                      "criteria": "membership in all 256 correlated value and ordered event pairs"}
        classes[name] = {
            **definition, "class_hash": key("conformance-class/1", definition),
            "interpreted_contract_hash": key("interpreted-contract/1", (archive["contract"], mode)),
        }
    candidates = snapshots(archive["rows"])
    if not (
        candidates["initial"]["candidate_set_hash"] != candidates["expanded"]["candidate_set_hash"]
        == candidates["reordered"]["candidate_set_hash"]
        != candidates["other-scope"]["candidate_set_hash"]
    ):
        raise AssertionError("Candidate-set identities do not preserve the declared scope and order boundary")
    cases = evidence_cases(archive, classes, ledger_digest)
    established = {
        case["receipt"]["implementation"] for case in cases
        if case["class"] == "wrap-general" and case["expected"] == "conforming"
    }
    for snapshot in candidates.values():
        snapshot["class_hash"] = classes["wrap-general"]["class_hash"]
        snapshot["finite_conforming_matches"] = sorted(established.intersection(snapshot["members"]))
    collisions = dict.fromkeys(cases[0]["keys"], 0)
    for left, right in combinations(cases, 2):
        for projection in collisions:
            if left["keys"][projection] == right["keys"][projection] and left["expected"] != right["expected"]:
                collisions[projection] += 1
    if collisions["exact_evidence_request"] or len({c["class_hash"] for c in classes.values()}) != len(classes):
        raise AssertionError("Exact class or evidence request identities collapsed")
    return {
        "schema": "llmlang-conformance-class-identity/1", "python": platform.python_version(),
        "source_ledger_sha256": ledger_digest,
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "relation_template_hash": key("contract-template/1", archive["contract"]),
        "classes": classes, "candidate_snapshots": candidates,
        "evidence_cases": cases, "distinct_disposition_pairs_with_same_key": collisions,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
