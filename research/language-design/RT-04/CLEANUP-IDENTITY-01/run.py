"""Inspect exact receipt sensitivity against archived cleanup observations."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
sys.path.insert(0, str(RESEARCH / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))

from src.semantic_graph import digest, verification_key

BASELINE = "5317a6a66c53886d5d8885b7262d07ad0a3e79fa"
NATIVE = HERE.parent / "owned-contract-replay" / "results.json"
PROOF = RESEARCH / "formal-verification" / "RT-32" / "SOURCE-CLEANUP-KERNEL-01" / "evidence.json"
FIELDS = {
    "cleanup-only": ("cleanup_reported",),
    "caller-owned": ("cleanup_reported", "owned_handle_forwarded"),
    "later-admission": ("cleanup_reported", "second"),
    "combined": ("cleanup_reported", "owned_handle_forwarded", "second"),
}


def replay():
    native = json.loads(NATIVE.read_bytes())
    proof = json.loads(PROOF.read_bytes())
    assert native["native_trace_comparisons"] == 256
    assert proof["source_agreement"] == proof["resource_completion"] == 8
    assert proof["mutation_inequalities"] == 4
    provider_bytes = native["generated_rust_sha256"]
    original = provider_bytes["before_cleanup"]
    staged = provider_bytes["after_cleanup"]
    assert original != staged

    rows = []
    for row in native["observations"]:
        case = {field: row[field] for field in ("identities", "wants_value", "local_close", "handle_close")}
        equal = {name: all(row["early"][key] == row["staged"][key] for key in fields)
                 for name, fields in FIELDS.items()}

        # The candidate claim is scoped to one caller view and exact input. Its
        # assertion stays fixed while the provider under test is replaced.
        subject = digest({"kind": "cleanup-caller-contract", "case": case})
        source = native["source_fixture_sha256"]

        def key(provider, projection):
            closure = digest({"source": source, "provider": provider})
            return verification_key(subject, closure, "scoped-native-fixture-v1",
                                    {"projection": projection}, ("typed-caller-model",))

        exact = key(original, "combined")
        changed_provider = key(staged, "combined")
        changed_projection = key(original, "cleanup-only")
        assert len({exact, changed_provider, changed_projection}) == 3
        assert equal["cleanup-only"] and not equal["combined"]
        rows.append({
            "case": case, "observations_equal": equal,
            "strong_reuse_with_cleanup_only_key_would_be_incorrect": equal["cleanup-only"] and not equal["combined"],
            "exact_claim_key": exact, "different_provider_key": changed_provider,
            "different_projection_key": changed_projection,
        })

    counts = Counter(name for row in rows for name, same in row["observations_equal"].items() if same)
    return {
        "schema": "rt04-cleanup-subject-proof-boundary-v1", "baseline": BASELINE,
        "python": platform.python_version(), "comparison_count": len(rows),
        "equal_by_projection": {name: counts[name] for name in FIELDS},
        "incorrect_strong_reuses": sum(row["strong_reuse_with_cleanup_only_key_would_be_incorrect"] for row in rows),
        "source_sha256": {path.relative_to(RESEARCH).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in (NATIVE, PROOF, HERE / "run.py")},
        "cases": rows,
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
