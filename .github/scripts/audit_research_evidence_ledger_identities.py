#!/usr/bin/env python3
"""Check declared identities in the pinned research evidence.json population."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import platform
import re

from audit_research_relocation import git, research_tree

BASELINE = "d2e32df3ff25ef28dc66750b3e14e777d7cd7d35"
MAP_FIELDS = (
    "archive_replay_sources_sha256", "input_sources_sha256", "runner_sha256",
    "source_digests", "source_sha256", "sources", "sources_sha256",
)
ENVIRONMENT_KEYS = {"environment", "filesystem", "kernel", "linux", "os", "platform", "system"}
TRACKED_ALIASES = {
    ("GENERATED-RUST-INTEGERS-01", "input_sources_sha256", "integer_fixture.py"):
        "research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01/integer_fixture.py",
    ("GENERATED-RUST-INTEGERS-01", "input_sources_sha256", "llvm_integer_probe.py"):
        "research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01/llvm_integer_probe.py",
    ("INDEXED-JOURNAL-RECOVERY-01", "source_digests", "test_rt23_commit_recovery.py"):
        "research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_commit_recovery.py",
    ("INDEXED-JOURNAL-RECOVERY-01", "source_digests", "test_rt24_merge_tree_gate.py"):
        "research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_merge_tree_gate.py",
    ("LLVM-DYNAMIC-ROUNDING-01", "source_sha256", "host_c"):
        "research/compiler-and-translation/RT-13/LLVM-DYNAMIC-ROUNDING-01/host.c",
    ("LLVM-F64-I64-LOWERING-01", "source_sha256", "evidence.json"):
        "research/semantic-representation/RT-05/F64-I64-CONVERSION-01/evidence.json",
    ("LLVM-FP-FLAGS-01", "source_sha256", "run.py"):
        "research/compiler-and-translation/RT-13/BINARY64-CONTRACTION-01/run.py",
}
GENERATED_SOURCE_LABELS = {
    "CROSS-PROFILE-CLEANUP-01": {"rust", "cpp"},
    "LLVM-DYNAMIC-ROUNDING-01": {"generated_header", "generated_ir"},
    "NAMED-RECORD-01": {"rust", "python"},
    "UNICODE-BINDING-01": {"node", "python", "rust"},
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def observations(ledger, contents, tree):
    folder = PurePosixPath(ledger).parent
    for field in MAP_FIELDS:
        entries = contents.get(field)
        if field == "runner_sha256" and isinstance(entries, str):
            entries = {"run.py": entries}
        if not isinstance(entries, dict):
            continue
        for name, expected in sorted(entries.items()):
            row = {"field": field, "label": name}
            if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
                yield {**row, "outcome": "outside-flat-sha256-shape"}
                continue
            row["expected_sha256"] = expected
            alias = TRACKED_ALIASES.get((folder.name, field, name))
            target = alias or str(folder / name)
            if target in tree and target != ledger:
                blob = tree[target][0]
                actual = sha256(git("cat-file", "blob", blob)).hexdigest()
                status = "match" if actual == expected else "mismatch"
                yield {**row, "outcome": status, "path": target, "git_blob": blob,
                       "actual_sha256": actual, "explicit_path_alias": bool(alias)}
                continue
            generated_lean = (
                field == "archive_replay_sources_sha256"
                and folder.name == "F64-EXTREMA-GUARD-01"
                and re.fullmatch(r"Replay[0-9]+\.lean", name)
            )
            generated_source = (
                field == "source_sha256" and name in GENERATED_SOURCE_LABELS.get(folder.name, ())
            )
            status = "generated-source-requires-replay" if generated_lean or generated_source else "unresolved-path"
            yield {**row, "outcome": status}


def audit():
    tree = research_tree(BASELINE)
    totals = Counter()
    ledgers = []
    for path, (blob, _) in sorted(tree.items()):
        if PurePosixPath(path).name != "evidence.json":
            continue
        contents = json.loads(git("cat-file", "blob", blob))
        if not isinstance(contents, dict):
            raise ValueError(f"Expected an object in {path}")
        rows = list(observations(path, contents, tree))
        totals.update(row["outcome"] for row in rows)
        ledgers.append({
            "path": path,
            "git_blob": blob,
            "reported_python": contents.get("python"),
            "top_level_environment_keys": sorted(ENVIRONMENT_KEYS.intersection(contents)),
            "identity_observations": rows,
        })
    return {
        "schema": "rt00-evidence-ledger-identities-v1",
        "baseline": BASELINE,
        "audit_environment": {"python": platform.python_version(),
                              "git": git("--version").decode().strip()},
        "ledger_count": len(ledgers),
        "ledgers_with_identity_observations": sum(bool(row["identity_observations"]) for row in ledgers),
        "ledgers_with_top_level_environment_keys": sum(bool(row["top_level_environment_keys"]) for row in ledgers),
        "top_level_python_count": sum(row["reported_python"] is not None for row in ledgers),
        "identity_outcome_counts": dict(totals),
        "ledgers": ledgers,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
