"""Compare bounded Knowledge Context selection with exact tokenizer receipts."""
import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import random

import tiktoken

TOKENIZER = "cl100k_base"
RENDERER = "context-text/1"
MANDATORY = frozenset(("contract", "test"))
RESERVE = 8
EXTRAS = (-1, 0, 1, 6, 12, 15, 20, 25, 30, 35, 45, 60, 80)
CANARY = "SYNTHETIC-PRIVATE-CONTEXT"
TOPICS = {
    "quota": ("Reserved capacity stays charged until settlement.",
              "Replay a child cancellation and compare the parent balance.",
              "Constraint review:"),
    "unicode": ("Сравнить исходное состояние и итоговую трассу.",
                "仕様は確定した結果と観測を区別する。",
                "Проверка:"),
    "compiler": ("Preserve the declared operation's exact call binding.",
                 "Check the same result after changing the representation.",
                 "Target contract:"),
    "archive": ("Hash every logical table before publishing the archive.",
                "Verify that a reopened pinned Snapshot reconstructs the index.",
                "Archive evidence:"),
}


def hash_text(value):
    return sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Source:
    name: str
    weight: int
    snapshot: str
    permitted: bool
    raw: str
    approved_excerpt: str | None = None


def inventory(topic):
    contract, test, _ = TOPICS[topic]
    return [
        Source("contract", 0, topic, True, contract),
        Source("test", 0, topic, True, test),
        Source("appendix", 12, topic, True,
               "This optional appendix follows a reconstructed trace and describes related choices. "
               "It supplies background for a later review of independent alternatives and retained records."),
        Source("comparison", 7, topic, True, "Check result re-use."),
        Source("note", 7, topic, True, "Tag the report:"),
        Source("reference", 6, topic, True, "See record 17:"),
        Source("excerpt", 5, topic, True,
               CANARY + " must be excluded from the requested view.", "Approved excerpt."),
        Source("closed", 80, topic, False, CANARY),
        Source("old", 60, topic + "-previous", True, "A stale observation enters review."),
    ]


def project(scope, items):
    accepted = {}
    omitted = {}
    for source in items:
        why = ("stale-snapshot" if source.snapshot != scope else
               "permission" if not source.permitted else None)
        if why is None:
            accepted[source.name] = source
        else:
            omitted[source.name] = why
    if MANDATORY - set(accepted):
        return None, omitted
    return accepted, omitted


def render(header, chosen):
    blocks = []
    for source in sorted(chosen, key=lambda source: (source.name not in MANDATORY, source.name)):
        visible = source.raw if source.approved_excerpt is None else source.approved_excerpt
        blocks.append(f"{source.name}:\n{visible}\n")
    return header + "\n".join(blocks)


def exact_tokens(encoding, text):
    return len(encoding.encode_ordinary(text))


def estimate_tokens(encoding, header, chosen):
    blocks = [render("", (source,)) for source in chosen]
    return exact_tokens(encoding, header) + sum(exact_tokens(encoding, block) for block in blocks) + max(
        0, len(blocks) - 1
    ) * exact_tokens(encoding, "\n")


def exact_receipt(scope, tokenizer_digest, chosen, exclusions, text, tokens, budget):
    return {
        "snapshot": scope, "renderer": RENDERER, "tokenizer": TOKENIZER, "encoding_digest": tokenizer_digest,
        "prompt_digest": hash_text(text), "exact_tokens": tokens, "reserve": RESERVE,
        "total_budget": budget,
        "selected": [
            {"name": item.name,
             "source_digest": hash_text(item.raw) if item.approved_excerpt is None else None,
             "projection_digest": hash_text(item.raw if item.approved_excerpt is None else item.approved_excerpt)}
            for item in sorted(chosen, key=lambda item: item.name)
        ],
        "omissions": dict(sorted(exclusions.items())),
    }


def subsets(values):
    return (group for count in range(len(values) + 1) for group in combinations(values, count))


def replay(scope, items, encoding, encoding_digest, budget):
    if len({item.name for item in items}) != len(items):
        return {"status": "ambiguous-inventory"}
    accepted, omissions = project(scope, items)
    if accepted is None:
        return {"status": "missing-required", "omissions": omissions}
    mandatory = tuple(item for item in accepted.values() if item.name in MANDATORY)
    optional = tuple(sorted((item for item in accepted.values() if item.name not in MANDATORY),
                            key=lambda item: (-item.weight, item.name)))
    header = TOPICS[scope][2] + "\n\n"
    available = budget - RESERVE
    if exact_tokens(encoding, render(header, mandatory)) > available:
        return {"status": "mandatory-over-budget", "omissions": omissions}

    def cost(selection):
        return exact_tokens(encoding, render(header, (*mandatory, *selection)))

    def value(selection):
        return sum(item.weight for item in selection)

    def greedy(token_cost):
        chosen = ()
        for candidate in optional:
            proposal = (*chosen, candidate)
            if token_cost(proposal) <= available:
                chosen = proposal
        return chosen

    optimum = min(
        (selection for selection in subsets(optional) if cost(selection) <= available),
        key=lambda selection: (-value(selection), -len(selection), tuple(sorted(item.name for item in selection))),
    )
    exact_greedy = greedy(cost)
    additive = greedy(lambda selection: estimate_tokens(encoding, header, (*mandatory, *selection)))
    assert cost(optimum) <= available and cost(exact_greedy) <= available
    assert value(optimum) >= value(exact_greedy)
    if cost(additive) <= available:
        assert value(optimum) >= value(additive)
    chosen = (*mandatory, *optimum)
    missing = {item.name: "budget-selection" for item in optional if item not in optimum}
    text = render(header, chosen)
    assert CANARY not in text
    return {
        "status": "ready", "approximate_tokens_for_exact_selection": estimate_tokens(encoding, header, chosen),
        "utility": {"exact_optimum": value(optimum), "exact_greedy": value(exact_greedy),
                    "additive_greedy": value(additive)},
        "additive_candidate_would_exceed": cost(additive) > available,
        "receipt": exact_receipt(scope, encoding_digest, chosen, {**omissions, **missing},
                                 text, cost(optimum), budget),
    }


def compare(encoding, encoding_digest):
    rng = random.Random(339)
    order_checks = 0
    cases = []
    for topic, extra in product(TOPICS, EXTRAS):
        source = inventory(topic)
        scope = TOPICS[topic][2] + "\n\n"
        required = [item for item in source if item.name in MANDATORY]
        baseline = exact_tokens(encoding, render(scope, required))
        budget = baseline + RESERVE + extra
        expected = replay(topic, source, encoding, encoding_digest, budget)
        for _ in range(6):
            rng.shuffle(source)
            assert replay(topic, source, encoding, encoding_digest, budget) == expected
            order_checks += 1
        cases.append({"topic": topic, "budget": budget, **expected})
    controls = {}
    for variant in ("permission", "stale-snapshot"):
        source = inventory("quota")
        source[0] = (replace(source[0], permitted=False) if variant == "permission"
                     else replace(source[0], snapshot="incorrect"))
        result = replay("quota", source, encoding, encoding_digest, budget=10_000)
        assert result == {"status": "missing-required", "omissions": {
            "closed": "permission", "old": "stale-snapshot", "contract": variant,
        }}
        controls[variant] = result["status"]
    conflict = inventory("quota")
    conflict.append(replace(conflict[0], raw="Conflicting mandatory evidence."))
    assert replay("quota", conflict, encoding, encoding_digest, 10_000) == {"status": "ambiguous-inventory"}
    controls["conflicting-source-identity"] = "ambiguous-inventory"
    maximum = replay("quota", inventory("quota"), encoding, encoding_digest, 10_000)
    redacted = next(row for row in maximum["receipt"]["selected"] if row["name"] == "excerpt")
    assert redacted["source_digest"] is None and redacted["projection_digest"] == hash_text("Approved excerpt.")
    controls["approved-excerpt"] = "exact projected digest without original content digest"
    # An undelimited fragment counter can err in either direction.
    boundaries = []
    for left, right in (("evidence", "test"), ("scope:", "test")):
        separate = exact_tokens(encoding, left) + exact_tokens(encoding, right)
        exact = exact_tokens(encoding, left + right)
        boundaries.append({"separate": separate, "concatenated": exact, "fragments": [left, right]})
    assert [(row["separate"], row["concatenated"]) for row in boundaries] == [(3, 4), (3, 2)]
    ready = [case for case in cases if case["status"] == "ready"]
    counts = {
        "budget_cases": len(cases), "assembled": len(ready), "blocked_by_mandatory_budget": len(cases) - len(ready),
        "input_order_checks": order_checks,
        "exact_greedy_loses_utility": sum(row["utility"]["exact_greedy"] < row["utility"]["exact_optimum"] for row in ready),
        "additive_greedy_loses_utility": sum(row["utility"]["additive_greedy"] < row["utility"]["exact_optimum"] for row in ready),
        "additive_greedy_overruns": sum(row["additive_candidate_would_exceed"] for row in ready),
        "additive_estimate_differs": sum(row["approximate_tokens_for_exact_selection"] != row["receipt"]["exact_tokens"]
                                         for row in ready),
    }
    assert counts["input_order_checks"] == 312 and counts["assembled"] == 48
    assert counts["exact_greedy_loses_utility"] > 0 and counts["additive_estimate_differs"] > 0
    return {"tiktoken": tiktoken.__version__, "counts": counts, "controls": controls,
            "undelimited_counterexamples": boundaries, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--encoding-file", required=True, type=Path)
    args = parser.parse_args()
    encoding_digest = sha256(args.encoding_file.read_bytes()).hexdigest()
    assert encoding_digest == "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
    assert tiktoken.__version__ == "0.12.0"
    encoding = tiktoken.get_encoding(TOKENIZER)
    args.output.write_text(json.dumps(compare(encoding, encoding_digest), indent=2) + "\n")


if __name__ == "__main__":
    main()
