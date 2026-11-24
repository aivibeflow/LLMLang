#!/usr/bin/env python3
"""Screen the pinned Markdown corpus for high textual overlap and record scoped reviews."""

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path, PurePosixPath
import platform
import re

from audit_research_relocation import git

BASELINE = "43060fa2fb8bfa8178ce4f444e6e5a210ec94f2f"
WINDOW = 8
SHARED_MINIMUM = 24
JACCARD_MINIMUM = .025
CONTAINMENT_MINIMUM = .07
REVIEWED = [
    ("LLMLang-CONCEPT.md", "LLMLang-CONCEPT.ru.md", "Language companions",
     "The authored concepts share structure and some passages. The newer English concept has the RT-36 proposal beyond the Russian companion's recorded coverage."),
    ("PROTOTYPE-20-RESULTS.md", "RESEARCH-SCENARIO-20-DEPENDENCY-DISCOVERY-AND-SEMANTIC-CLASSIFICATION.md",
     "Proposed study and bounded implementation", "The result covers normalized observations supplied to the prototype. The scenario describes filters and broader discovery sources."),
    ("PROTOTYPE-21-RESULTS.md", "RESEARCH-SCENARIO-21-COUNTERFACTUAL-DEPENDENCY-DETECTION.md",
     "Proposed study and bounded implementation", "The result compares supplied paired runs and leaves automated interventions and dependency completeness open."),
    ("PROTOTYPE-28-RESULTS.md", "RESEARCH-SCENARIO-28-TYPED-IR-AND-PROOF-BOUNDARY.md",
     "Proposed study and bounded implementation", "The result exercises typed-IR and query-evidence records with finite controls. The scenario defines the broader typed-IR and proof-boundary scope."),
    ("RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md", "RESEARCH-SCENARIO-96B-LLVM-BYTE-VIEW-PRESERVATION.md",
     "Distinct experimental scopes", "The shared native pipeline evaluates integer overflow, shifts and effect order in 96A and logical view identity and bounds in 96B."),
    ("RESEARCH-SCENARIO-123-CLOSE-CALL-BOUNDARY.md", "RESEARCH-SCENARIO-125-CLOSE-REENTRY-AND-COVERAGE.md",
     "Distinct experimental scopes", "The call-boundary comparison tests close policies. The later study varies reentry and dependent coverage, including backup resources."),
    ("RESEARCH-SCENARIO-107-SOURCE-DERIVED-CALL-ALIASES.md", "RESEARCH-SCENARIO-108-PATH-SENSITIVE-ALIAS-PRECISION.md",
     "Distinct experimental scopes", "The source adapter extracts aliases and calls for a bounded AST. The later precision study retains alternatives along path valuations."),
    ("RT-07-CPC-NULLARY-ALIAS-BINDING.md", "RT-07-SOURCE-WIRE-LOGOS-ACCEPTANCE.md",
     "Distinct experimental scopes", "The alias result checks parser binding conditions. The wire result binds scoped source assertions and a replayed refutation."),
]
CONTROLS = [
    ("RESEARCH-SCENARIO-31-STRICT-QF-LIA-PROFILE.md", "RESEARCH-SCENARIO-32-CANONICAL-TYPED-RELATIONAL-QUERY-IR.md",
     "Prior section-level supersession of the text-oriented query representation"),
    ("GIT-SEMANTIC-REPOSITORY.md", "GIT-REPRESENTATION-AND-SEMANTIC-MERGE.md",
     "Prior section-level supersession of current-architecture guidance and the embedded proposal"),
    ("RESEARCH-RELATED-PROJECTS.md", "RESEARCH-DEEP-COMPARISON.md",
     "Prior scoped supersession of overlapping project claims"),
    ("LLMLang-FORMAL-VERIFICATION.md", "LLMLang-FORMAL-VERIFICATION.ru.md",
     "Maintained language companions with reciprocal navigation"),
]


def word_windows(text):
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"(?<=\])\((?:[^()]|\([^()]*\))*\)", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    words = re.findall(r"[^\W_]+", text.casefold())
    return set(zip(*(words[offset:] for offset in range(WINDOW))))


def documents():
    result = {}
    for entry in git("ls-tree", "-r", "-z", BASELINE, "research/").split(b"\0"):
        if not entry:
            continue
        hdr, raw_path = entry.split(b"\t", 1)
        _, kind, oid = hdr.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if kind == "blob" and Path(path).suffix in {".md", ".mdx"}:
            text = git("cat-file", "blob", oid).decode("utf-8")
            result[path] = (oid, word_windows(text))
    return result


def rough_candidates(documents_by_path):
    gram_files = defaultdict(list)
    for path, (_, grams) in documents_by_path.items():
        for gram in grams:
            gram_files[gram].append(path)
    common = Counter()
    for paths in gram_files.values():
        common.update(combinations(paths, 2))
    return common


def metrics(docs, first, second, shared):
    first_n, second_n = (len(docs[path][1]) for path in (first, second))
    return shared / (first_n + second_n - shared), shared / min(first_n, second_n)


def review_role(first, second):
    names = frozenset(PurePosixPath(p).name for p in (first, second))
    if names == {"README.md"} and all(len(PurePosixPath(p).parts) == 3 for p in (first, second)):
        return "Shared index language", "The direction indexes share heading, navigation and scope language and link distinct study families."
    for a, b, role, finding in REVIEWED:
        if names == {a, b}:
            return role, finding
    raise ValueError(f"Unreviewed candidate {first} and {second}")


def compare():
    docs = documents()
    matched = rough_candidates(docs)
    cases = []
    strict_count = 0
    for (first, second), shared in sorted(matched.items()):
        jac, contained = metrics(docs, first, second, shared)
        if shared >= 64 and (jac >= .14 or contained >= .33):
            strict_count += 1
        if shared < SHARED_MINIMUM or (jac < JACCARD_MINIMUM and contained < CONTAINMENT_MINIMUM):
            continue
        role, finding = review_role(first, second)
        cases.append({
            "paths": [first, second], "blobs": [docs[first][0], docs[second][0]],
            "shared_windows": shared, "jaccard": round(jac, 6), "containment": round(contained, 6),
            "role": role, "scope_finding": finding,
        })

    controls = []
    selected = {frozenset(case["paths"]) for case in cases}
    for a, b, known_relationship in CONTROLS:
        first, = [p for p in docs if PurePosixPath(p).name == a]
        second, = [p for p in docs if PurePosixPath(p).name == b]
        shared = len(docs[first][1] & docs[second][1])
        jac, contained = metrics(docs, first, second, shared)
        controls.append({
            "paths": [first, second], "blobs": [docs[first][0], docs[second][0]],
            "shared_windows": shared, "jaccard": round(jac, 6), "containment": round(contained, 6),
            "candidate_selected": frozenset((first, second)) in selected,
            "known_relationship": known_relationship,
        })

    population = len(docs)
    return {
        "schema": "rt00-corpus-text-overlap-v1",
        "baseline": BASELINE,
        "environment": {"python": platform.python_version(),
                        "git": git("--version").decode("ascii").strip()},
        "thresholds": {"word_window": WINDOW, "min_shared": SHARED_MINIMUM,
                       "min_jaccard_or_min_containment": [JACCARD_MINIMUM, CONTAINMENT_MINIMUM]},
        "documents": population,
        "pair_population": population * (population - 1) // 2,
        "initial_stricter_filter_candidates": strict_count,
        "candidate_role_counts": dict(sorted(Counter(row["role"] for row in cases).items())),
        "candidates": cases,
        "known_relationship_controls": controls,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compare()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("documents", "pair_population", "candidate_role_counts")}, indent=2))
