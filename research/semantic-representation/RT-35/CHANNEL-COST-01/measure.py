"""Measure exact bounded retrieval channels over materialized fixture projections."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import importlib.util
from itertools import product
import json
import os
from pathlib import Path
import platform
from random import Random
from statistics import median, quantiles
import sys
from time import perf_counter_ns


HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "SCOPED-RETRIEVAL-01" / "run.py"
spec = importlib.util.spec_from_file_location("scoped_retrieval_fixtures", FIXTURE)
R = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = R
spec.loader.exec_module(R)
CHANNELS = ("structured", "lexical", "single_vector", "multi_aspect", "hybrid")
HYBRID = ("lexical", "multi_aspect", "structured")
DESIRED = frozenset(("Int", "borrow", "pure", "total"))


def features(channel, card):
    if channel == "structured":
        return tuple(sorted(card.contract))
    if channel == "lexical":
        return tuple(sorted(R.words(card.text)))
    if channel == "single_vector":
        return tuple(sorted(R.fingerprint(R.words(card.text)).items()))
    if channel == "multi_aspect":
        return (tuple(sorted(R.concepts(card.purpose))), tuple(sorted(R.concepts(card.text))),
                tuple(sorted(card.contract)))
    return {method: features(method, card) for method in HYBRID}


def score(channel, rows, phrase):
    raw = R.words(phrase)
    concept = R.concepts(phrase)
    if channel == "structured":
        return [len(set(value) & DESIRED) for value in rows]
    if channel == "lexical":
        return [R.jaccard(set(value), raw) for value in rows]
    if channel == "single_vector":
        query = R.fingerprint(raw)
        return [R.cosine(dict(value), query) for value in rows]
    return [0.55 * R.jaccard(set(purpose), concept)
            + 0.35 * R.jaccard(set(text), concept)
            + 0.1 * R.jaccard(set(contract), DESIRED)
            for purpose, text, contract in rows]


def ranked(channel, cards, table, phrase):
    def single(method, rows):
        scores = score(method, rows, phrase)
        order = sorted(zip(cards, scores, strict=True), key=lambda row: (-row[1], row[0].logical))
        return tuple(dict.fromkeys(card.artifact for card, _ in order))

    rows = [table[card.logical] for card in cards]
    if channel != "hybrid":
        return single(channel, rows)
    combined = Counter()
    for method in HYBRID:
        for position, artifact in enumerate(single(method, [row[method] for row in rows])):
            combined[artifact] += 1 / (20 + position)
    return tuple(sorted(combined, key=lambda artifact: (-combined[artifact], artifact)))


def exact_queries(cards, snapshot):
    return [(R.authorized_cards(cards, snapshot.mapping, scope), R.FAMILIES[family][variant])
            for family, variant, scope in product(R.FAMILIES, (0, 1), R.ACCESS)]


def payload(table):
    return json.dumps(table, sort_keys=True, separators=(",", ":")).encode()


def interval(values):
    cuts = quantiles(values, n=10, method="inclusive")
    return {"median": median(values), "p10": cuts[0], "p90": cuts[-1]}


def run(cpu, blocks, seed):
    assert cpu in os.sched_getaffinity(0) and blocks >= 2
    os.sched_setaffinity(0, {cpu})
    _, snapshot, corpus, _ = R.catalog()
    queries = exact_queries(corpus, snapshot)
    tables = {channel: {card.logical: features(channel, card) for card in corpus} for channel in CHANNELS}
    digest = sha256()
    for cards, phrase in queries:
        reference = R.rank(cards, phrase)
        for method, table in tables.items():
            observed = ranked(method, cards, table, phrase)
            assert observed == tuple(card.artifact for card in reference[method])
            digest.update(payload(observed))
    changed = replace(corpus[0], text=corpus[0].text + " bounded replacement")
    replacement_corpus = (changed, *corpus[1:])
    for channel, table in tables.items():
        updated = {**table, changed.logical: features(channel, changed)}
        rebuilt = {card.logical: features(channel, card) for card in replacement_corpus}
        assert payload(updated) == payload(rebuilt)

    random = Random(seed)
    samples = {channel: {"query_batch_ns": [], "row_update_ns": []} for channel in CHANNELS}
    for _ in range(blocks):
        order = list(CHANNELS)
        random.shuffle(order)
        for channel in order:
            table = tables[channel]
            started = perf_counter_ns()
            for cards, phrase in queries:
                ranked(channel, cards, table, phrase)
            samples[channel]["query_batch_ns"].append(perf_counter_ns() - started)
            work = table.copy()
            start = perf_counter_ns()
            for _ in range(100):
                work[changed.logical] = features(channel, changed)
                work[corpus[0].logical] = features(channel, corpus[0])
            elapsed = perf_counter_ns() - start
            assert work == table
            samples[channel]["row_update_ns"].append(elapsed / 200)

    return {
        "python": platform.python_version(), "kernel": platform.release(),
        "cpu_model": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
        "cpu": cpu, "blocks": blocks, "seed": seed, "cards": len(corpus),
        "artifact_ids": len({card.artifact for card in corpus}), "query_count": len(queries),
        "matched_full_rankings": len(queries) * len(CHANNELS), "ranking_digest": digest.hexdigest(),
        "serialized_feature_bytes": {ch: len(payload(table)) for ch, table in tables.items()},
        "raw_samples": samples,
        "summary": {ch: {key: interval(values) for key, values in profiles.items()}
                    for ch, profiles in samples.items()},
        "sources": {name: sha256(path.read_bytes()).hexdigest()
                    for name, path in (("measure.py", Path(__file__)), ("fixture", FIXTURE))},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu", required=True, type=int)
    parser.add_argument("--blocks", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.cpu, arguments.blocks, arguments.seed), sort_keys=True, indent=2))
