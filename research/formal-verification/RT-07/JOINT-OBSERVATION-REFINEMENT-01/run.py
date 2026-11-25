#!/usr/bin/env python3
"""Check exact and projected nondeterministic observation relations."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
TRACES = ((), ("read",), ("read", "write"), ("write", "read"))
OUTCOMES = tuple(product(("return", "error"), TRACES))
MASKS = range(1 << len(OUTCOMES))


def select(mask):
    return [outcome for bit, outcome in enumerate(OUTCOMES) if mask & (1 << bit)]


def image(mask, components):
    projected = 0
    for bit, component in enumerate(components):
        if mask & (1 << bit):
            projected |= 1 << component
    return projected


def subset(candidate, reference):
    return candidate & ~reference == 0


def compare():
    counts = Counter()
    samples = {}
    digest = sha256()
    tags_by_outcome = tuple(i // len(TRACES) for i in range(len(OUTCOMES)))
    histories_by_outcome = tuple(i % len(TRACES) for i in range(len(OUTCOMES)))
    tags = [image(mask, tags_by_outcome) for mask in MASKS]
    histories = [image(mask, histories_by_outcome) for mask in MASKS]
    observes = []
    for truth in MASKS:
        outputs = tuple((truth >> i) & 1 for i in range(len(OUTCOMES)))
        observes.append([image(mask, outputs) for mask in MASKS])

    # Pack all contexts that see each Boolean value into one integer per run set.
    may_true = [sum(1 << truth for truth in MASKS if observes[truth][mask] & 2) for mask in MASKS]
    may_false = [sum(1 << truth for truth in MASKS if observes[truth][mask] & 1)
                 for mask in MASKS]
    failures = {"tag": 0, "trace": 0, "marginals": 0}
    for candidate, reference in product(MASKS, repeat=2):
        joint = subset(candidate, reference)
        tag = subset(tags[candidate], tags[reference])
        trace = subset(histories[candidate], histories[reference])
        marginal = tag and trace
        distinguishing = ((may_true[candidate] & ~may_true[reference])
                          | (may_false[candidate] & ~may_false[reference]))
        if joint != (distinguishing == 0):
            raise AssertionError((candidate, reference))
        if joint and not marginal:
            raise AssertionError("A projection lost an exact refinement")

        counts["ordered_set_pairs"] += 1
        counts["joint_refinements"] += joint
        counts["joint_equalities"] += candidate == reference
        equal_marginals = (tags[candidate], histories[candidate]) == (
            tags[reference], histories[reference])
        counts["marginal_equalities"] += equal_marginals
        counts["false_marginal_refinements"] += marginal and not joint
        for policy, refines in (("tag", tag), ("trace", trace), ("marginals", marginal)):
            if refines:
                failures[policy] |= distinguishing

        if equal_marginals and distinguishing:
            bit = (distinguishing & -distinguishing).bit_length() - 1
            samples.setdefault("equal_marginals_with_context_mismatch", {
                "candidate": select(candidate), "reference": select(reference),
                "context_true_on": select(bit),
            })
        digest.update(bytes((joint, tag, trace)))
        digest.update(distinguishing.to_bytes(len(MASKS) // 8, "little"))

    if failures["marginals"] != (failures["tag"] & failures["trace"]):
        raise AssertionError("Expected only contexts that depend on one reported field")
    safe_contexts = {name: len(MASKS) - count.bit_count() for name, count in failures.items()}
    assert safe_contexts == {"tag": 4, "trace": 16, "marginals": 18}
    return counts, safe_contexts, samples, digest.hexdigest()


if __name__ == "__main__":
    counts, safe, witnesses, digest = compare()
    print(json.dumps({
        "schema": "llmlang-joint-observation-refinement/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Refinement.lean", "axioms.txt")},
        "outcome_order": OUTCOMES, "contexts": len(MASKS),
        "counts": counts, "preserved_contexts": safe, "witnesses": witnesses,
        "ordered_checks_sha256": digest,
    }, indent=2))
