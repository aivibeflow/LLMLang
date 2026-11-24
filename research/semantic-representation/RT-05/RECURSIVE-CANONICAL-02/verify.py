"""Compare canonical traversal with the published exhaustive group experiment."""

from dataclasses import replace
from hashlib import sha256
from itertools import permutations, product
import json
from math import factorial

from canonical import Call, Definition, External, canonicalize, rooted_rows
from src.recursive_identity import RecursiveIdentityError, publish_definitions
from src.semantic_graph import ContentStore


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def relabel(definitions, mapping, order):
    return {
        mapping[name]: replace(definitions[name], body=tuple(
            Call(mapping[token.target]) if isinstance(token, Call) else token
            for token in definitions[name].body
        ))
        for name in order
    }


def orbit_relation(selection):
    return {(x, y) for x, y in product(selection, repeat=2) if selection[x] == selection[y]}


def exhaust_three():
    nodes = ("a", "b", "c")
    labeled_orders = tuple(permutations(nodes))
    reverse_labels = {name: chr(122 - i) for i, name in enumerate(nodes)}
    by_traversal = {}
    by_exhaustion = {}
    rejected, valid, changed_bytes, renames = 0, 0, 0, 0
    expected_partitions = set()
    for calls in product(nodes, repeat=6):
        targets = {name: calls[2 * i:2 * i + 2] for i, name in enumerate(nodes)}
        definitions = {name: Definition(tuple(map(Call, row))) for name, row in targets.items()}
        # An independent fixed-point reachability oracle for this three-member corpus.
        reaches_all = all({
            t for mid in (root, *targets[root]) for t in (mid, *targets[mid])
        } == set(nodes) for root in nodes)
        if not reaches_all:
            try:
                canonicalize(definitions)
            except ValueError:
                rejected += 1
                continue
            raise AssertionError("Accepted a non-strongly-connected group")
        valid += 1
        canonical = canonicalize(definitions)
        store = ContentStore()
        old_positions = publish_definitions(store, definitions, "structural")
        group = store.get(store.get(old_positions[nodes[0]]).dependencies[0].target_hash)
        old_rows = group.payload_json.encode()
        require(by_exhaustion.setdefault(old_rows, canonical.rows) == canonical.rows, "Split equivalent group")
        require(by_traversal.setdefault(canonical.rows, old_rows) == old_rows, "Merged distinct group")
        changed_bytes += old_rows != canonical.rows

        automorphisms = set()
        for order in labeled_orders:
            bijection = dict(zip(nodes, order))
            if all(tuple(bijection[t] for t in targets[x]) == targets[bijection[x]] for x in nodes):
                automorphisms.update(bijection.items())
        require(orbit_relation(canonical.positions) == orbit_relation(old_positions) == automorphisms,
                "Member equality differs from explicit automorphisms")
        expected_partitions.add(len(set(canonical.positions.values())))
        for order in labeled_orders:
            renamed = canonicalize(relabel(definitions, reverse_labels, order))
            require(renamed.rows == canonical.rows, "Renaming altered group bytes")
            require(renamed.positions == {reverse_labels[k]: v for k, v in canonical.positions.items()},
                    "Renaming altered member position")
            renames += 1

    return {"enumerated": valid + rejected, "accepted": valid, "rejected_non_scc": rejected,
            "isomorphism_classes": len(by_traversal), "class_bijection": True,
            "renamed_cases": renames, "member_class_counts": sorted(expected_partitions),
            "legacy_rows_differ": changed_bytes}


def ring(size, mark):
    names = [str(i) for i in range(size)]
    return {name: Definition((
        "marked" if mark and i == 0 else "unmarked",
        Call(names[(i + 1) % size]),
        Call(names[(i + 2) % size]),
    ), f"slot-{i}") for i, name in enumerate(names)}


def scale():
    samples = []
    for size, marked in product((3, 6, 8, 16, 32, 64, 128), (False, True)):
        definitions = ring(size, marked)
        candidate = canonicalize(definitions)
        names = list(definitions)
        mapping = {name: f"qualified/{size - 1 - int(name)}" for name in names}
        reversed_graph = relabel(definitions, mapping, reversed(names))
        rerun = canonicalize(reversed_graph)
        require(rerun.rows == candidate.rows, "Scale rename changed canonical bytes")
        require(rerun.positions == {mapping[k]: v for k, v in candidate.positions.items()},
                "Scale rename changed canonical member positions")
        expected_orbits = size if marked else 1
        require(len(set(candidate.positions.values())) == expected_orbits, "Unexpected ring member orbits")

        legacy = "search-bound"
        store = ContentStore()
        try:
            old_group = publish_definitions(store, definitions, "structural")
        except RecursiveIdentityError as error:
            require(size > 6 and str(error) == "recursive component exceeds structural search bound",
                    "Unexpected reference rejection")
        else:
            require(size <= 6 and orbit_relation(old_group) == orbit_relation(candidate.positions),
                    "Ring member partitions disagree")
            legacy = "pass"
        keyed = publish_definitions(store, definitions, "keyed")
        require(len(set(keyed.values())) == size, "Keyed addressing failed to keep members distinct")
        samples.append({
            "members": size, "marked": marked, "root_candidates": candidate.candidates,
            "body_tokens_visited": candidate.tokens_visited, "member_classes": expected_orbits,
            "reference": legacy, "reference_permutations_examined": factorial(size) if size <= 6 else 0,
            "keyed_member_addresses": len(set(keyed.values())),
            "traversal_payload_sha256": sha256(candidate.rows).hexdigest(),
        })
    return samples


def controls():
    s = ContentStore()
    pin_a, pin_b = (s.put("external", {"id": value}) for value in (1, 2))
    base = {"a": Definition(("a", Call("b"), Call("a"), External(pin_a), True)),
            "b": Definition(("b", Call("a")))}
    original = canonicalize(base)
    swapped = {"a": Definition(("a", Call("a"), Call("b"), External(pin_a), True)), "b": base["b"]}
    new_pin = {"a": Definition(("a", Call("b"), Call("a"), External(pin_b), True)), "b": base["b"]}
    int_literal = {"a": Definition(("a", Call("b"), Call("a"), External(pin_a), 1)), "b": base["b"]}
    for changed in (swapped, new_pin, int_literal):
        require(canonicalize(changed).rows != original.rows, "Erased distinct typed payload")
    chosen_a, _ = rooted_rows(base, "a")
    chosen_b, _ = rooted_rows(base, "b")
    require(chosen_a != chosen_b, "The arbitrary-root control needs two different encodings")
    for malformed in ({}, {"a": Definition((Call("missing"),))}, {"a": Definition((1.5,))}):
        try:
            canonicalize(malformed)
        except ValueError:
            continue
        raise AssertionError("Malformed input was accepted")
    return {"preserved_call_order": True, "preserved_external_pin": True, "typed_literal_distinct": True,
            "arbitrary_root_fails": True, "malformed_inputs_rejected": 3}


def lexical_control():
    # With two-digit positions JSON's lexical order differs from numeric order.
    result = canonicalize(ring(11, True))
    rows = json.loads(result.rows)
    positions = {i: i for i in range(len(rows))}
    positions[1], positions[10] = 10, 1
    permuted = [None] * len(rows)
    for i, row in enumerate(rows):
        permuted[positions[i]] = {"body": [
            {"local_call": positions[token["local_call"]]} if "local_call" in token else token
            for token in row["body"]
        ]}
    encoded = json.dumps(permuted, sort_keys=True, separators=(",", ":")).encode()
    require(encoded < result.rows, "Expected a lower legal permutation outside the traversal candidates")
    return {"members": len(rows), "traversal_first_row": rows[0],
            "smaller_permutation_first_row": permuted[0],
            "traversal_sha256": sha256(result.rows).hexdigest(),
            "smaller_permutation_sha256": sha256(encoded).hexdigest()}


if __name__ == "__main__":
    evidence = {"three_member_corpus": exhaust_three(), "scale": scale(), "controls": controls(),
                "lexical_control": lexical_control()}
    print(json.dumps(evidence, indent=2, sort_keys=True))
