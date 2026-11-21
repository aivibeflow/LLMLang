"""Cross-check typed canonical identity bytes between Python and JavaScript."""

import hashlib
from itertools import permutations, product
import json
from pathlib import Path
import re
import subprocess


DOMAINS = {"contract", "operation", "implementation", "class", "candidate-set", "evidence"}
ENCODERS = Path(__file__).resolve().parent


def checked_text(value):
    if type(value) is not str:
        raise ValueError("expected string")
    value.encode("utf-8")
    return value


def normalize(term):
    match term:
        case ["int", str(text)] if re.fullmatch(r"-?[1-9][0-9]*|0", text):
            return term
        case ["bool", bool()]:
            return term
        case ["text", value]:
            return ["text", checked_text(value)]
        case ["list", list(values)]:
            return ["list", [normalize(value) for value in values]]
        case ["map", list(rows)]:
            entries = {}
            for row in rows:
                match row:
                    case [key, value]:
                        key = checked_text(key)
                        if key in entries:
                            raise ValueError("duplicate map key")
                        entries[key] = normalize(value)
                    case _:
                        raise ValueError("invalid map row")
            keys = sorted(entries, key=lambda key: key.encode("utf-8"))
            return ["map", [[key, entries[key]] for key in keys]]
        case _:
            raise ValueError("invalid typed value")


def python_result(record):
    try:
        domain, term = record
        if domain not in DOMAINS:
            raise ValueError("unknown domain")
        payload = json.dumps(["llmlang.identity-fixture/1", domain, normalize(term)],
                             ensure_ascii=False, separators=(",", ":"))
        return [payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()]
    except (TypeError, ValueError):
        return None


def node_results(records):
    source = "\n".join(map(json.dumps, records)) + "\n"
    result = subprocess.run(["node", str(ENCODERS / "encode.mjs")], input=source,
                            text=True, encoding="utf-8", capture_output=True, check=True, timeout=30)
    return [json.loads(line) for line in result.stdout.split("\n") if line]


def compare():
    ints = ["0", "1", "-1", "9007199254740992", "9007199254740993",
            "-9223372036854775808", "9223372036854775807", str(2**128)]
    texts = ["", "é", "e\u0301", "\u2028", "\x00\n\b", "\uffff", "\U00010000", '"\\']
    atoms = ([["int", value] for value in ints] + [["text", value] for value in texts]
             + [["bool", True], ["bool", False]])
    valid = list(product(sorted(DOMAINS), atoms))
    map_rows = [["\U00010000", ["int", "1"]], ["\uffff", ["text", "2"]],
                ["e\u0301", ["list", [["bool", False], ["int", ints[-1]]]]]]
    maps = [("class", ["map", list(order)]) for order in permutations(map_rows)]
    sequence = [("class", ["list", atoms[:3]]), ("class", ["list", list(reversed(atoms[:3]))])]
    malformed = [("operation", term) for term in (
        ["int", "-0"], ["int", "01"], ["int", "+1"], ["int", 1], ["int", "1\n"],
        ["bool", 1], ["text", "\ud800"], ["map", [["x", ["int", "1"]], ["x", ["int", "1"]]]],
        ["map", [["\udfff", ["int", "1"]]]], ["unknown", None],
    )] + [("unsupported", ["int", "1"])]
    fixtures = valid + maps + sequence + malformed
    python = list(map(python_result, fixtures))
    node = node_results(fixtures)
    assert len(python) == len(node)
    for fixture, expected, actual in zip(fixtures, python, node):
        assert expected == actual, (fixture, expected, actual)
    assert all(outcome is not None for outcome in python[:-len(malformed)])
    assert all(outcome is None for outcome in python[-len(malformed):])
    assert len({python_result(record)[1] for record in valid}) == len(valid)
    assert len({python_result(record)[1] for record in maps}) == 1
    assert python_result(sequence[0]) != python_result(sequence[1])
    assert python_result(maps[0])[0].index("\uffff") < python_result(maps[0])[0].index("\U00010000")

    collision = subprocess.check_output(["node", "-e",
        "console.log(JSON.parse('9007199254740992') === JSON.parse('9007199254740993'))"],
        text=True, timeout=30).strip()
    assert collision == "true"
    witness = python_result(("operation", ["int", "9007199254740993"]))
    print(f"{len(fixtures)} comparisons: {len(fixtures) - len(malformed)} accepted, "
          f"{len(malformed)} rejected; exact integer witness {witness[1]}")


if __name__ == "__main__":
    compare()
