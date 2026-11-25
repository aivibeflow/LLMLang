#!/usr/bin/env python3
"""Compare local retrieval channels with exact snapshot-bound compatibility."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import product
import json
import math
from pathlib import Path
import platform
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, make_snapshot

DOMAIN = tuple(range(-2, 4))
TOP_K = 3
CHANNELS = ("structured", "lexical", "single_vector", "multi_aspect", "hybrid")
ACCESS = {"core": {"core"}, "extended": {"core", "alternative"}, "review": {"core", "review"}}
# These are closed fixture concepts, not judgments produced by the rankers.
FAMILIES = {
    "absolute": ("absolute sign-free value", "distance from zero", abs),
    "clamp": ("clamp negative values", "floor at zero", lambda x: max(0, x)),
    "successor": ("increment integer", "next counting value", lambda x: x + 1),
    "double": ("double input", "scale by two", lambda x: 2 * x),
    "sign": ("classify sign", "identify polarity", lambda x: (x > 0) - (x < 0)),
    "square": ("square input", "multiply by itself", lambda x: x * x),
}
SYNONYMS = {
    "absolute": "magnitude", "distance": "magnitude", "clamp": "clamp", "floor": "clamp",
    "increment": "successor", "next": "successor", "double": "double", "scale": "double",
    "classify": "polarity", "polarity": "polarity", "square": "square", "itself": "square",
}
VARIANTS = ("base", "alias", "alternative", "effect", "narrow", "consume",
            "failure", "incorrect", "wrong_type", "uncertain", "hidden_literal", "hidden_alias")
PACKAGES = {"alternative": "alternative", "uncertain": "review",
            "hidden_literal": "foreign", "hidden_alias": "foreign"}


@dataclass(frozen=True)
class Card:
    logical: str
    artifact: str
    package: str
    text: str
    purpose: str
    contract: tuple[str, ...]
    fixture_variant: str


@dataclass(frozen=True)
class Index:
    root: str
    cards: tuple[Card, ...]


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def concepts(text):
    return {SYNONYMS.get(term, term) for term in words(text)}


def fingerprint(tokens):
    counts = Counter()
    for token in tokens:
        slot = sha256(token.encode()).digest()[0] % 16
        counts[slot] += 1
    return counts


def cosine(left, right):
    numerator = sum(weight * right.get(key, 0) for key, weight in left.items())
    denominator = math.sqrt(sum(value**2 for value in left.values())
                            * sum(value**2 for value in right.values()))
    return numerator / denominator if denominator else 0.0


def jaccard(left, right):
    return len(left & right) / len(left | right) if left or right else 0.0


def catalog():
    store = ContentStore()
    cards = []
    proven = set()
    for family, (literal, alias, expected) in FAMILIES.items():
        for variant in VARIANTS:
            implementation = "base" if variant == "alias" else variant
            precondition = [n for n in DOMAIN if variant != "narrow" or n >= 0]
            values = [None if variant == "failure" and n == 0 else
                      expected(n) + int(variant == "incorrect" and n == 1) for n in DOMAIN]
            body = {
                "implementation": implementation, "precondition": precondition, "outcomes": values,
                "type": "Bool" if variant == "wrong_type" else "Int",
                "ownership": "consume" if variant == "consume" else "borrow",
                "effects": ["read"] if variant == "effect" else [],
            }
            artifact = store.put("rt35-fixture-function-v1", body)
            if variant != "uncertain":
                proven.add(artifact)
            surface = alias if variant in {"alias", "alternative", "failure", "hidden_alias"} else literal
            text = surface
            if variant not in {"effect", "failure", "hidden_literal", "hidden_alias"}:
                text += " total pure integer"
            contract = (body["type"], "borrow", "pure", "total")
            cards.append(Card(f"{family}/{variant}", artifact, PACKAGES.get(variant, "core"),
                              text, literal, contract, variant))
    snapshot = make_snapshot({card.logical: card.artifact for card in cards})
    receipts = {(snapshot.root_hash, artifact) for artifact in proven}
    return store, snapshot, tuple(cards), receipts


def compatibility(body, expected, checked):
    if body["type"] != "Int":
        return "type"
    if body["ownership"] != "borrow":
        return "ownership"
    if body["effects"]:
        return "effect"
    if body["precondition"] != list(DOMAIN):
        return "precondition"
    if any(outcome is None for outcome in body["outcomes"]):
        return "failure"
    if body["outcomes"] != expected:
        return "postcondition"
    return "compatible" if checked else "unknown"


def active(index, snapshot, scope):
    if index.root != snapshot.root_hash:
        raise ValueError("Derived index has a stale semantic snapshot")
    selection = snapshot.mapping
    return authorized_cards(index.cards, selection, scope)


def authorized_cards(cards, selection, scope):
    return tuple(card for card in cards if card.package in ACCESS[scope]
                 and selection.get(card.logical) == card.artifact)


def scores(card, phrase):
    intent = words(phrase)
    raw = words(card.text)
    concept = concepts(phrase)
    exact_contract = set(card.contract)
    desired = {"Int", "borrow", "pure", "total"}
    return {
        "structured": len(exact_contract & desired),
        "lexical": jaccard(raw, intent),
        "single_vector": cosine(fingerprint(raw), fingerprint(intent)),
        "multi_aspect": 0.55 * jaccard(concepts(card.purpose), concept)
                        + 0.35 * jaccard(concepts(card.text), concept)
                        + 0.1 * jaccard(exact_contract, desired),
    }


def rank(cards, phrase):
    entries = [(card, scores(card, phrase)) for card in cards]
    ranked = {}
    for key in CHANNELS[:-1]:
        order = sorted(entries, key=lambda row: (-row[1][key], row[0].logical))
        unique = {}
        for card, _ in order:
            unique.setdefault(card.artifact, card)
        ranked[key] = list(unique.values())

    combined = Counter()
    by_artifact = {card.artifact: card for card in cards}
    for key in ("lexical", "multi_aspect", "structured"):
        for position, row in enumerate(ranked[key]):
            combined[row.artifact] += 1 / (20 + position)
    artifacts = sorted(combined, key=lambda artifact: (-combined[artifact], artifact))
    ranked["hybrid"] = [by_artifact[artifact] for artifact in artifacts]
    return ranked


def full_policy(decisions):
    suitable = [artifact for artifact, decision in decisions.items() if decision == "compatible"]
    if len(suitable) > 1:
        return {"status": "ambiguous", "artifact": None}
    if "unknown" in decisions.values():
        return {"status": "pending", "artifact": None}
    if not suitable:
        return {"status": "no_match", "artifact": None}
    return {"status": "bound", "artifact": suitable[0]}


def candidate_fixture_oracle(cards, family):
    return {card.artifact for card in cards if card.logical.startswith(family + "/")
            and card.fixture_variant in {"base", "alias", "alternative"}}


def evaluate(index, snapshot, registry, store, receipts):
    results = []
    metrics = {channel: Counter(queries=0, hit=0, recall_numerator=0, recall_denominator=0,
                                unsafe_top1=0, false_unique=0, postfilter_loss=0,
                                reciprocal_rank_total=0.0, ndcg_total=0.0)
               for channel in CHANNELS}
    for family, phrasing, scope in product(FAMILIES, (0, 1), ACCESS):
        phrase = FAMILIES[family][phrasing]
        expected = [FAMILIES[family][2](x) for x in DOMAIN]
        visible = active(index, snapshot, scope)
        truth = authorized_cards(registry, snapshot.mapping, scope)
        compatible = candidate_fixture_oracle(truth, family)
        decisions = {card.artifact: compatibility(store.get(card.artifact).payload, expected,
                                                     (snapshot.root_hash, card.artifact) in receipts) for card in truth}
        assert {artifact for artifact, verdict in decisions.items() if verdict == "compatible"} == compatible
        selection = full_policy(decisions)
        assert selection["status"] == {"core": "bound", "extended": "ambiguous", "review": "pending"}[scope]
        invocation = None
        if selection["artifact"]:
            assert selection["artifact"] in snapshot.mapping.values() and selection["artifact"] in compatible
            invocation = store.get(selection["artifact"]).payload["outcomes"][DOMAIN.index(2)]
            assert invocation == FAMILIES[family][2](2)

        local = rank(visible, phrase)
        global_rank = rank(index.cards, phrase)
        per_channel = {}
        for channel in CHANNELS:
            admitted = local[channel][:TOP_K]
            shortlist = [card.artifact for card in admitted]
            top = decisions[shortlist[0]]
            found = [position for position, artifact in enumerate(shortlist, 1) if artifact in compatible]
            recovered = len(found)
            late = {card.artifact for card in global_rank[channel][:TOP_K]
                    if card.package in ACCESS[scope]}
            early_count = len(set(shortlist) & compatible)
            late_count = len(late & compatible)
            predicate = full_policy({artifact: decisions[artifact] for artifact in shortlist})
            false_unique = predicate["status"] == "bound" and selection["status"] != "bound"
            row = metrics[channel]
            row["queries"] += 1
            row["hit"] += recovered > 0
            row["recall_numerator"] += recovered
            row["recall_denominator"] += len(compatible)
            row["unsafe_top1"] += top != "compatible"
            row["false_unique"] += false_unique
            row["postfilter_loss"] += late_count < early_count
            row["reciprocal_rank_total"] += 1 / found[0] if found else 0
            ideal = sum(1 / math.log2(position + 1) for position in range(1, len(compatible) + 1))
            row["ndcg_total"] += sum(1 / math.log2(position + 1) for position in found) / ideal
            per_channel[channel] = {
                "shortlist": shortlist, "top_decision": top, "compatible_found": recovered,
                "postfilter_compatible_found": late_count,
                "shortlist_selection": predicate["status"],
            }
        results.append({"family": family, "phrase": phrase, "scope": scope,
                        "complete_selection": selection, "invocation_at_input_2": invocation,
                        "compatible": sorted(compatible),
                        "channels": per_channel})
    for values in metrics.values():
        values["mrr_at_3"] = round(values.pop("reciprocal_rank_total") / values["queries"], 6)
        values["ndcg_at_3"] = round(values.pop("ndcg_total") / values["queries"], 6)
        values["precision_at_3"] = round(values["recall_numerator"] / (TOP_K * values["queries"]), 6)
    assert any(values["postfilter_loss"] for values in metrics.values())
    assert any(values["false_unique"] for values in metrics.values())
    return metrics, results


def stale_control(index, snapshot, registry, store, receipts):
    name = "absolute/base"
    old = snapshot.mapping[name]
    replacement = store.get(old).payload
    replacement["outcomes"][0] = 999
    new = store.put("rt35-fixture-function-v1", replacement)
    current = make_snapshot({**snapshot.mapping, name: new}, (snapshot.root_hash,))
    try:
        active(index, current, "core")
    except ValueError:
        pass
    else:
        raise AssertionError("A stale index was eligible to bind")
    # Renaming only the index root still leaves the old exact row outside the selection.
    misleading = replace(index, root=current.root_hash)
    assert name not in {card.logical for card in active(misleading, current, "core")}
    expected = [abs(value) for value in DOMAIN]
    alias = snapshot.mapping["absolute/alias"]
    assert compatibility(store.get(alias).payload, expected, (current.root_hash, alias) in receipts) == "unknown"

    def selection(catalog):
        decisions = {card.artifact: compatibility(store.get(card.artifact).payload, expected,
                                                     (snapshot.root_hash, card.artifact) in receipts) for card in catalog}
        return full_policy(decisions)["status"]
    trusted = authorized_cards(registry, snapshot.mapping, "extended")
    truncated = tuple(card for card in index.cards if card.logical != "absolute/alternative")
    assert selection(active(replace(index, cards=truncated), snapshot, "extended")) == "bound"
    assert selection(trusted) == "ambiguous"
    return {"old_snapshot": snapshot.root_hash, "current_snapshot": current.root_hash,
            "old_artifact": old, "new_artifact": new, "stale_index": "refused",
            "mismatched_row_with_current_index_label": "excluded",
            "previous_snapshot_receipt_for_unchanged_artifact": "unknown",
            "missing_compatible_index_entry": {"index_only": "bound", "trusted_selection": "ambiguous"}}


def run():
    store, snapshot, cards, receipts = catalog()
    index = Index(snapshot.root_hash, cards)
    metrics, rows = evaluate(index, snapshot, cards, store, receipts)
    return {
        "schema": "llmlang-rt35-scoped-retrieval/1", "python": platform.python_version(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "snapshot": snapshot.root_hash, "domain": DOMAIN, "candidate_cards": len(cards),
        "distinct_objects": len({card.artifact for card in cards}), "k": TOP_K,
        "queries": len(rows), "metrics": metrics, "stale_index": stale_control(index, snapshot, cards, store, receipts),
        "binding_summary": Counter(row["complete_selection"]["status"] for row in rows),
        "observations": rows,
    }


if __name__ == "__main__":
    result = run()
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
