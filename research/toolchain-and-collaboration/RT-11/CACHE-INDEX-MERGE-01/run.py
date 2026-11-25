"""Compare cache index union and consumer-side evidence checks."""

from collections import Counter
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2] / "packages-and-ecosystem" / "PROTOTYPES" / "PACKAGE-IDENTITY-01"
sys.path.insert(0, str(PACKAGE))

from cache_index import CACHE_SCHEMA, CACHE_SCHEMA_VERSION, expected_action_key
from language_version import registry_digest
from package_identity import PackageFormatError
from merge import artifact_id, lookup, merge

BASELINE = "e42d50a353f6c0fb92bf5728d66da115f2e407ce"
COMPONENTS = ("syntax", "core_semantics", "type_system", "effects_execution", "modules_packages")
PAYLOAD = b"expected artifact bytes"
OTHER = b"independent result bytes"
EXTRA = b"manifest side output"
FIRST = artifact_id(PAYLOAD)
SECOND = artifact_id(OTHER)
EXTRA_ID = artifact_id(EXTRA)
ARTIFACTS = {FIRST: PAYLOAD, SECOND: OTHER, EXTRA_ID: EXTRA}
AUTHORITIES = {"builder-a", "builder-b"}


def record(**changes):
    row = {
        "action_key": "", "action_kind": "compile",
        "action_implementation": artifact_id(b"implementation"),
        "input_hashes": [artifact_id(b"inputs")], "language_version": "1.3.2.1.0",
        "language_component_registry_digest": registry_digest(COMPONENTS),
        "toolchain_identity": artifact_id(b"toolchain"),
        "target_profile_digest": artifact_id(b"target"),
        "configuration_digest": artifact_id(b"configuration"),
        "runtime_identity": artifact_id(b"runtime"),
        "status": "success", "determinism": "byte_deterministic",
        "dependency_complete": True, "output_artifacts": [FIRST],
    } | changes
    row["action_key"] = expected_action_key(row, COMPONENTS)
    return row


def index(producer, evidence="review-v1", *rows):
    return producer, evidence, {"schema": CACHE_SCHEMA, "schema_version": CACHE_SCHEMA_VERSION,
                                "records": sorted(rows or (record(),), key=lambda r: r["action_key"])}


def replay():
    action = record()["action_key"]
    good = index("builder-a")
    duplicate = index("builder-b")
    disagree = index("builder-b", "review-v1", record(output_artifacts=[SECOND]))
    outside = index("outside-policy", "review-v1", record(output_artifacts=[SECOND]))
    results = []

    def check(label, expected, *, indexes=(good,), artifacts=ARTIFACTS, verified=True, count=1,
              scope="review-v1", authorities=AUTHORITIES, key=action):
        merged = merge(indexes, COMPONENTS)
        if verified is True:
            authenticated = {row.identity for rows in merged.values() for row in rows}
        else:
            authenticated = verified or set()
        value = lookup(merged, key, required_evidence=scope, authorities=authorities, verified=authenticated,
                       artifacts=artifacts, required_outputs=count)
        assert value[0] == expected
        results.append({"case": label, "status": value[0], "result": value[1],
                        "candidate_count": sum(map(len, merged.values()))})

    check("one exact result", "hit")
    check("duplicate identical candidate receipt", "hit", indexes=(good, good))
    check("two authorized receipts agree", "hit", indexes=(good, duplicate))
    check("authorized receipt absent", "no-applicable-attestation", verified=False)
    original_receipt = merge((good,), COMPONENTS)[action][0].identity
    check("old attestation cannot authorize changed output", "no-applicable-attestation",
          indexes=(disagree,), verified={original_receipt})
    check("scope change", "no-applicable-attestation", scope="review-v2")
    check("producer revoked", "no-applicable-attestation", authorities=set())
    check("different action", "miss", key=record(action_kind="test")["action_key"])
    check("outside-policy contributor cannot admit conflicting result", "hit", indexes=(good, outside))
    check("only outside-policy index", "no-applicable-attestation", indexes=(outside,))
    check("authorized conflicting bytes", "conflict", indexes=(good, disagree))
    check("conflict remains when other blob is evicted", "conflict", indexes=(good, disagree), artifacts={FIRST: PAYLOAD})
    check("authorized disagreement on terminal status", "conflict",
          indexes=(good, index("builder-b", "review-v1", record(status="rejected"))))
    check("byte reuse cannot consume semantic-only result", "no-exact-byte-candidate",
          indexes=(index("builder-b", "review-v1", record(determinism="semantic_deterministic")),))
    check("required artifact evicted", "artifact-missing", artifacts={})
    check("verified payload rematerialized", "hit")
    check("wrong bytes under addressed entry", "artifact-integrity-error", artifacts={FIRST: OTHER})
    incomplete = index("builder-a", "review-v1", record(output_artifacts=[FIRST, EXTRA_ID]))
    check("side output unavailable", "artifact-missing", indexes=(incomplete,), artifacts={FIRST: PAYLOAD}, count=2)
    check("side output present", "hit", indexes=(incomplete,), count=2)
    check("record omits required output", "output-shape-mismatch", count=2)

    for row in (record(dependency_complete=False), record(status="timeout"), record(determinism="nondeterministic")):
        try:
            merge((index("builder-a", "review-v1", row),), COMPONENTS)
        except PackageFormatError as error:
            results.append({"case": str(error), "status": "structural-rejection",
                            "result": None, "candidate_count": 0})
        else:
            raise AssertionError(row)

    samples = (good, duplicate, disagree, outside)
    canonical = merge(samples, COMPONENTS)
    orderings = list(permutations(samples))
    assert all(merge(order, COMPONENTS) == canonical for order in orderings)
    return {
        "schema": "rt11-cache-index-merge-v1", "baseline": BASELINE,
        "python": platform.python_version(), "result_counts": dict(Counter(row["status"] for row in results)),
        "merge_orderings": len(orderings), "cases": results,
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                          for path in (HERE / "run.py", HERE / "merge.py", PACKAGE / "cache_index.py",
                                       PACKAGE / "package_identity.py", PACKAGE / "language_version.py")},
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
