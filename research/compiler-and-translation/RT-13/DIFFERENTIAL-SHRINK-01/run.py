#!/usr/bin/env python3
"""Replay differential witnesses and shrink them without losing the claim."""

from collections import Counter
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REVISION = "409d51c2de9026f12cc42450b29fcbe622a716cd"
MUTATION_DIR = "research/compiler-and-translation/RT-13/STATE-RESULT-MUTATIONS-01"
ARCHIVE_SHA256 = "eb05a5dd8f287d4b4a1195e88d470bc3640a73898e14b9d14cafcc2c921bf32e"
SEEDS = (17705, 17706, 17707, 17708)
SAMPLES = 384


def read_archive(path, digest):
    data = subprocess.check_output(["git", "show", f"{REVISION}:{path}"])
    if sha256(data).hexdigest() != digest:
        raise AssertionError(f"Unexpected archived input: {path}")
    return data


def load(directory):
    archive = json.loads(read_archive(f"{MUTATION_DIR}/evidence.json", ARCHIVE_SHA256))
    for path, digest in archive["sources_sha256"].items():
        file = directory / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(read_archive(path, digest))
    spec = spec_from_file_location("pinned_rewrite_mutations", directory / MUTATION_DIR / "run.py")
    model = module_from_spec(spec)
    spec.loader.exec_module(model)
    return model, archive["sources_sha256"]


def compare(model, program, initial, mutation, *, independent=False):
    source = model.observe(program, initial)
    target = model.optimize(model.mutate(program, mutation))
    emitted = model.observe(target, initial)
    if independent and (source != model.machine(program, initial)
                        or emitted != model.machine(target, initial)):
        raise AssertionError((program, initial, mutation, source, emitted))
    return source, emitted, target


def breaks(model, case, mutation, claim):
    source, target, _ = compare(model, *case, mutation)
    return source != target and (claim == "complete" or
                                 model.project(source)["event_multiset"] ==
                                 model.project(target)["event_multiset"])


def rank(model, case):
    tree, cell = case
    return model.size(tree), cell, tree


def rewrites(model, tree):
    yield from model.LEAVES
    tag, *children = tree
    if tag in model.FORMERS:
        left, right = children
        yield left
        yield right
        yield from ((tag, replacement, right) for replacement in rewrites(model, left))
        yield from ((tag, left, replacement) for replacement in rewrites(model, right))


def smaller(model, case):
    tree, cell = case
    variants = {(tree, 0), *((replacement, cell) for replacement in rewrites(model, tree))}
    return sorted((other for other in variants if rank(model, other) < rank(model, case)),
                  key=lambda other: rank(model, other))


def identify(model, case):
    tree, cell = case
    canonical = json.dumps(tree, separators=(",", ":")).encode("ascii")
    return {"nodes": model.size(tree), "cell": cell, "tree_sha256": sha256(canonical).hexdigest()}


def shrink(model, case, mutation, claim):
    initial_case = case
    steps = []
    while True:
        candidates = smaller(model, case)
        choice = next((trial for trial in candidates if breaks(model, trial, mutation, claim)),
                      None)
        if choice is None:
            break
        case = choice
        compare(model, *case, mutation, independent=True)
        steps.append(identify(model, case))
    source, target, output = compare(model, *case, mutation, independent=True)
    if not breaks(model, case, mutation, claim):
        raise AssertionError("Shrinking invalidated the distinguishing observation")
    return {"start": identify(model, initial_case), "end": case,
            "nodes_before": model.size(initial_case[0]), "nodes_after": model.size(case[0]),
            "steps": steps, "smaller_candidates_refused": len(candidates),
            "emitted": output, "source_observation": source, "target_observation": target}


def witnesses(model, seed):
    programs = model.generated(model.LEAVES, model.FORMERS, SAMPLES, 7, seed)
    first = {}
    for tree, cell in product(programs, (0, 1)):
        expected = model.observe(tree, cell)
        preserved = model.optimize(tree)
        if not (model.observe(preserved, cell) == expected == model.machine(tree, cell)
                == model.machine(preserved, cell)):
            raise AssertionError((seed, tree, cell))
        for mutation in model.MUTATIONS:
            source, target, _ = compare(model, tree, cell, mutation)
            if source != target:
                first.setdefault((mutation, "complete"), (tree, cell))
                if model.project(source)["event_multiset"] == model.project(target)["event_multiset"]:
                    first.setdefault((mutation, "order_only"), (tree, cell))
    return first, len(set(programs))


def run(model, sources):
    # The closed corpus contains every one-, three- and five-node typed tree.
    prefix = sorted(model.reference.model.corpus(), key=model.size)
    minima = {}
    for mutation in model.MUTATIONS:
        for claim in ("complete", "order_only"):
            first = next(((tree, cell) for tree, cell in product(prefix, (0, 1))
                          if breaks(model, (tree, cell), mutation, claim)), None)
            if first:
                minima[(mutation, claim)] = model.size(first[0])

    strict_control = ("strict", ("write", 0), ("write", 1)), 0
    assert breaks(model, strict_control, "exchange_write_order", "complete")
    assert not breaks(model, strict_control, "exchange_write_order", "order_only")
    counts = Counter()
    results = {}
    for seed in SEEDS:
        found, distinct = witnesses(model, seed)
        counts["generated_rows"] += 2 * SAMPLES
        counts["distinct_trees_per_seed_total"] += distinct
        results[str(seed)] = {}
        for (mutation, claim), case in sorted(found.items()):
            report = shrink(model, case, mutation, claim)
            minimum = minima[(mutation, claim)]
            report["minimum_nodes_in_exhaustive_corpus"] = minimum
            if report["nodes_after"] < minimum:
                raise AssertionError("A smaller witness should be present in the closed corpus")
            counts["witnesses"] += 1
            counts["order_only_witnesses"] += claim == "order_only"
            counts["shrunk"] += bool(report["steps"])
            counts["reached_corpus_minimum"] += report["nodes_after"] == minimum
            results[str(seed)][f"{mutation}/{claim}"] = report
    assert counts["witnesses"] >= len(SEEDS) * len(model.MUTATIONS)
    return {
        "schema": "llmlang-differential-shrinking/1", "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "archived_revision": REVISION, "archived_metadata_sha256": ARCHIVE_SHA256,
        "archived_sources": sources, "seeds": SEEDS, "samples_per_seed": SAMPLES,
        "counts": counts, "results": results,
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as work:
        model, sources = load(Path(work))
        print(json.dumps(run(model, sources), indent=2))
