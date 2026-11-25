"""Evaluate bounded exact KNN and approximate KD-tree discovery with provenance."""
import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

import numpy as np
from scipy import __version__ as scipy_version
from scipy.spatial import cKDTree

DIMENSIONS = 12
SIZE_PER_PARTITION = 256
K = 8
FINGERPRINT = "gaussian-fingerprint-v1"
CHANNELS = {
    "scoped-exact": 0.0,
    "scoped-ann-0.6": 0.6,
    "scoped-ann-1.5": 1.5,
    "global-exact-postfilter": 0.0,
}
PARTITIONS = tuple(product(("library-a", "library-b", "library-c"), ("i32", "bytes"),
                           ("pure", "read")))


def digest(value):
    data = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return sha256(data).hexdigest()


@dataclass(frozen=True)
class Function:
    identity: str
    partition: tuple[str, str, str]
    evidence: str


@dataclass(frozen=True)
class Receipt:
    root: str
    function: str
    contract: str
    result: str


def build_corpus(seed):
    rng = np.random.default_rng(seed)
    vectors = rng.normal(size=(len(PARTITIONS) * SIZE_PER_PARTITION, DIMENSIONS))
    functions = []
    for partition in PARTITIONS:
        for local in range(SIZE_PER_PARTITION):
            meaning = {"namespace_signature_effect": partition, "local_function": local}
            result = ("proved" if local % 5 == 0
                      else "unknown" if local % 7 == 0 else "incompatible")
            functions.append(Function(digest(meaning), partition, result))
    root = digest(sorted(function.identity for function in functions))
    return rng, vectors, functions, root


def vector_digest(vector):
    return sha256(np.asarray(vector, dtype="<f8").tobytes()).hexdigest()


def compatible(function, root, required, receipt):
    if receipt is None:
        return "pending"
    if (receipt.root, receipt.function, receipt.contract) != (root, function.identity, required):
        return "pending"
    if receipt.result == "proved":
        return "admitted"
    return "excluded" if receipt.result == "incompatible" else "pending"


def make_indexes(vectors):
    indices = {
        partition: np.arange(index * SIZE_PER_PARTITION, (index + 1) * SIZE_PER_PARTITION)
        for index, partition in enumerate(PARTITIONS)
    }
    trees = {
        partition: cKDTree(vectors[selected], leafsize=8)
        for partition, selected in indices.items()
    }
    return trees, indices, cKDTree(vectors, leafsize=8)


def query(tree, indices, vector, eps):
    distances, rows = tree.query(vector, k=K, eps=eps, workers=1)
    return [(int(indices[index]), float(distance)) for distance, index in zip(distances, rows)]


def brute_force(vectors, rows, vector):
    squares = np.sum((vectors[rows] - vector) ** 2, axis=1)
    ranking = sorted(zip(squares, rows))[:K]
    return [(int(row), float(np.sqrt(square))) for square, row in ranking]


def admitted_pairs(functions, required, receipts, root, ranked):
    return {row for row, _ in ranked
            if compatible(functions[row], root, required, receipts.get(functions[row].identity)) == "admitted"}


def receipts_for(functions, root, contract):
    return {record.identity: Receipt(root, record.identity, contract, record.evidence)
            for record in functions if record.evidence != "unknown"}


def comparison():
    rng, vectors, functions, root = build_corpus(35_091)
    trees, indices, global_tree = make_indexes(vectors)
    global_rows = np.arange(len(functions))
    contract = digest({"required_behavior": "synthetic contract parity", "version": 1})
    receipts = receipts_for(functions, root, contract)
    query_cases = [(partition, rng.normal(size=DIMENSIONS))
                   for partition in PARTITIONS for _ in range(16)]
    stats = {
        name: {"scoped_neighbors_recovered": 0, "returned_candidates": 0,
               "scoped_compatible_recovered": 0, "empty_shortlists": 0,
               "admitted": 0, "excluded": 0, "pending": 0}
        for name in CHANNELS
    }
    examples = {}
    exact_compatible = 0
    approximation_controls = 0
    for number, (partition, vector) in enumerate(query_cases, start=1):
        allowed = indices[partition]
        gold = brute_force(vectors, allowed, vector)
        gold_rows = {row for row, _ in gold}
        gold_admitted = {row for row, _ in gold if functions[row].evidence == "proved"}
        exact_compatible += len(gold_admitted)
        channel_rows = {}
        for channel, eps in CHANNELS.items():
            global_channel = channel == "global-exact-postfilter"
            ranked = query(global_tree, global_rows, vector, eps) if global_channel else query(
                trees[partition], allowed, vector, eps
            )
            scoped = [(rank, row, distance) for rank, (row, distance) in enumerate(ranked, start=1)
                      if functions[row].partition == partition]
            candidates = [(row, distance) for _, row, distance in scoped]
            if not global_channel:
                assert len(candidates) == K and len({row for row, _ in candidates}) == K
                assert candidates[-1][1] <= (1 + eps) * gold[-1][1] + 1e-12
            if channel == "scoped-exact":
                assert [row for row, _ in gold] == [row for row, _ in candidates]
            admitted = admitted_pairs(functions, contract, receipts, root, candidates)
            assert admitted == {row for row, _ in candidates if functions[row].evidence == "proved"}
            stats[channel]["scoped_neighbors_recovered"] += len(gold_rows & {row for row, _ in candidates})
            stats[channel]["scoped_compatible_recovered"] += len(gold_admitted & admitted)
            stats[channel]["returned_candidates"] += len(candidates)
            stats[channel]["empty_shortlists"] += not candidates
            receipt_rows = []
            for position, (rank, row, distance) in enumerate(scoped, start=1):
                assert functions[row].partition == partition
                actual_distance = float(np.linalg.norm(vectors[row] - vector))
                assert abs(distance - actual_distance) < 1e-12
                function = functions[row]
                proof = receipts.get(function.identity)
                result = compatible(function, root, contract, proof)
                stats[channel][result] += 1
                receipt_rows.append({
                    "channel": channel, "rank_from_index": rank,
                    "rank_after_scope_filter": position, "epsilon": eps,
                    "distance": round(distance, 9), "function_hash": function.identity,
                    "fingerprint_digest": vector_digest(vectors[row]), "compatibility": result,
                    "receipt_digest": digest(asdict(proof)) if proof is not None else None,
                })
            channel_rows[channel] = receipt_rows
        query_trace = {"partition": partition, "query_id": number,
                       "query_vector_digest": vector_digest(vector), "rows": channel_rows}
        if number == 1:
            examples["first_query"] = query_trace
        returned = {row["function_hash"] for row in channel_rows["scoped-ann-1.5"]}
        exact = {functions[row].identity for row in gold_rows}
        if returned != exact:
            approximation_controls += 1
            examples.setdefault("first_approximation_difference", query_trace)

    proved = next(item for item in functions if item.evidence == "proved")
    receipt = receipts[proved.identity]
    assert compatible(proved, root, contract, receipt) == "admitted"
    controls = {
        "stale_root": compatible(proved, root, contract, replace(receipt, root="stale")),
        "wrong_contract": compatible(proved, root, contract, replace(receipt, contract="previous")),
        "wrong_function": compatible(proved, root, contract, replace(receipt, function="different")),
        "missing_receipt": compatible(proved, root, contract, None),
    }
    assert list(controls.values()) == ["pending"] * 4
    assert approximation_controls > 0 and exact_compatible > 0
    return {
        "numpy": np.__version__, "scipy": scipy_version, "fingerprint": FINGERPRINT,
        "metric": "euclidean-distance", "dimensions": DIMENSIONS, "k": K,
        "catalog_root": root, "required_contract": contract, "corpus_size": len(functions),
        "queries": len(query_cases), "exact_neighbor_pairs": len(query_cases) * K,
        "exact_compatible_pairs": exact_compatible,
        "channel_totals": stats, "loose_approximation_changed_queries": approximation_controls,
        "compatibility_controls": controls, "examples": examples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(comparison(), indent=2) + "\n")


if __name__ == "__main__":
    main()
