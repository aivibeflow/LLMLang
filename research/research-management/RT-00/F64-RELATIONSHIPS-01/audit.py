"""Compare archived binary64 observations at one research/all revision."""

import hashlib
import json
import subprocess
from itertools import product

BASELINE = "41ce460f60ce9965145ed5767a94b0983e32b5b5"
IDENTITY = "research/semantic-representation/RT-05/CROSS-RUNTIME-F64-01"
EXTREMA = "research/semantic-representation/RT-05/NATIVE-F64-MINMAX-01"
CONVERSION = "research/semantic-representation/RT-05/F64-I64-CONVERSION-01"
GUARD = "research/formal-verification/RT-32/F64-EXTREMA-GUARD-01"
LLVM = "research/compiler-and-translation/RT-13/LLVM-F64-I64-LOWERING-01"
CANONICAL_NAN = "7ff8000000000000"
POSITIVE_ZERO = "0000000000000000"
NEGATIVE_ZERO = "8000000000000000"
ONE = "3ff0000000000000"
SIGNALING_NAN = "7ff0000000000001"


def git(*args):
    return subprocess.check_output(["git", *args])


def is_nan(word):
    return (int(word, 16) & 0x7fff_ffff_ffff_ffff) > 0x7ff0_0000_0000_0000


def normalize_nan(word):
    return CANONICAL_NAN if is_nan(word) else word


def normalize_zero(word):
    return POSITIVE_ZERO if word == NEGATIVE_ZERO else word


def projected_outputs(outputs):
    return tuple(map(normalize_nan, outputs))


def main():
    ledger = {}
    pins = {}
    for path in (IDENTITY, EXTREMA, CONVERSION, GUARD, LLVM):
        spec = f"{BASELINE}:{path}/evidence.json"
        raw = git("show", spec)
        ledger[path] = json.loads(raw)
        pins[path] = {
            "git_blob": git("rev-parse", spec).decode().strip(),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    assert ledger[GUARD]["native_archive_sha256"] == pins[EXTREMA]["sha256"]
    assert ledger[LLVM]["source_sha256"]["evidence.json"] == pins[CONVERSION]["sha256"]

    literal = {row["bits"]: row for row in ledger[IDENTITY]["observations"]}
    extrema = {tuple(row["operands"]): row["results"] for row in ledger[EXTREMA]["observations"]}
    words = ledger[EXTREMA]["input_words"]
    families = ledger[EXTREMA]["profiles"]
    assert len(words) == 32 and set(extrema) == set(product(words, repeat=2))
    assert len(ledger[GUARD]["archive_equalities"]) == len(extrema)
    for word in set(words) & literal.keys():
        assert literal[word]["decisions"]["canonical_nan"]["bits"] == normalize_nan(word)
        assert literal[word]["decisions"]["same_value_zero"]["bits"] == normalize_zero(normalize_nan(word))

    mismatches = {family: {"nan_only": 0, "zero_only": 0} for family in families}
    unanimous = 0
    for operands, native in extrema.items():
        assert native.keys() == families.keys()
        original = {family: projected_outputs(outputs) for family, outputs in native.items()}
        unanimous += len(set(original.values())) == 1
        for label, transform in (("nan_only", normalize_nan), ("zero_only", normalize_zero)):
            replaced = extrema[tuple(map(transform, operands))]
            for family in families:
                mismatches[family][label] += original[family] != projected_outputs(replaced[family])
    assert unanimous == ledger[GUARD]["guard_admitted_in_archive"]
    assert len(extrema) - unanimous == ledger[GUARD]["guard_refused_in_archive"]

    native_conversion = ledger[CONVERSION]["observations"]
    tag_by_error = {"range": 1, "nonfinite": 2}
    expected = []
    for row in native_conversion:
        status = row["checked_trunc"]
        tag, value = (0, status[1:]) if status.startswith("v") else (tag_by_error[status], "0")
        expected.append({"input": row["input"], "tag": tag, "value": value})
    assert len(expected) == len({row["input"] for row in expected}) == ledger[LLVM]["inputs"] == 216
    checked_routes = ["bits_branch", "ordered_branch", "ordered_select", "guarded_saturate"]
    llvm = ledger[LLVM]["native_observations"]
    for route in checked_routes:
        assert llvm[route] == expected, route
    saturation_mismatches = sum(actual != target for actual, target in zip(llvm["saturate"], expected, strict=True))

    unary = {row["input"]: [row["tag"], row["value"]] for row in expected}
    examples = {
        "glibc_signaling_nan_and_one": {
            "original": projected_outputs(extrema[SIGNALING_NAN, ONE]["glibc"]),
            "canonicalized_operand": projected_outputs(extrema[CANONICAL_NAN, ONE]["glibc"]),
        },
        "node_mixed_zeros": {
            "original": projected_outputs(extrema[POSITIVE_ZERO, NEGATIVE_ZERO]["node"]),
            "positive_only_operands": projected_outputs(extrema[POSITIVE_ZERO, POSITIVE_ZERO]["node"]),
        },
        "checked_conversion_signed_zeros": {word: unary[word] for word in (POSITIVE_ZERO, NEGATIVE_ZERO)},
        "checked_conversion_nan_samples": {word: unary[word] for word in (SIGNALING_NAN, CANONICAL_NAN)},
    }
    print(json.dumps({
        "baseline": BASELINE,
        "archive_pins": pins,
        "extrema": {
            "pairs_per_family": len(extrema),
            "literal_identity_words_in_common": len(set(words) & literal.keys()),
            "unanimous_pairs": unanimous,
            "input_replacement_mismatches": mismatches,
        },
        "conversion": {
            "rows_per_route": len(expected),
            "matching_checked_routes": checked_routes,
            "plain_saturation_mismatches": saturation_mismatches,
        },
        "examples": examples,
    }, indent=2))


if __name__ == "__main__":
    main()
