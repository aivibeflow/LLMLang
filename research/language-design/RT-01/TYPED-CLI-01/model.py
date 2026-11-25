"""Resolve exact CLI recipes and run the independent interpreted implementation."""

import json
import operator
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, make_snapshot

HANDLERS = {"hello": "write_literal", "echo": "join_arguments", "calculator": "checked_record"}
OPERATIONS = {"add": operator.add, "subtract": operator.sub, "multiply": operator.mul}
I64_MIN = -(2**63)
I64_MAX = 2**63 - 1


def admit(programs):
    if not isinstance(programs, dict) or set(programs) != set(HANDLERS):
        raise ValueError("The fixture requires exactly the three CLI entry points")
    hello, echo, calculator = (programs[name] for name in HANDLERS)
    for name, handler in HANDLERS.items():
        if not isinstance(programs[name], dict) or programs[name].get("handler") != handler:
            raise ValueError("Unsupported entry effect")
    if set(hello) != {"handler", "literal"} or not isinstance(hello["literal"], str):
        raise ValueError("Invalid literal entry")
    if (set(echo) != {"handler", "keep_empty", "separator", "suffix"}
            or type(echo["keep_empty"]) is not bool
            or not all(isinstance(echo[field], str) for field in ("separator", "suffix"))):
        raise ValueError("Invalid argument join")
    if (set(calculator) != {"handler", "separators", "terminator", "operations", "division",
                           "diagnostics", "diagnostic_stream"}
            or not calculator["separators"] or len(set(calculator["separators"])) != len(calculator["separators"])
            or not all(type(byte) is int and byte in {9, 13, 32} for byte in calculator["separators"])
            or calculator["terminator"] != 10
            or set(calculator["operations"]) - {"+", "-", "*", "/"}
            or set(calculator["operations"].values()) - (set(OPERATIONS) | {"divide"})
            or calculator["division"] not in {"toward_zero", "floor"}
            or calculator["diagnostic_stream"] not in {"stdout", "stderr"}
            or set(calculator["diagnostics"]) != {"invalid", "zero", "overflow"}
            or not all(isinstance(text, str) for text in calculator["diagnostics"].values())):
        raise ValueError("Invalid checked calculation")
    store = ContentStore()
    entries = {name: store.put("rt01-typed-cli-entry-v1", {
        "parameters": "posix-byte-argv+stdin", "completion": "stdio+status", "body": body,
    }) for name, body in programs.items()}
    return store, make_snapshot(entries)


def body_for(store, snapshot, entry):
    return store.get(snapshot.mapping[entry]).payload["body"]


def write_bytes(fd, data):
    try:
        while data:
            written = os.write(fd, data)
            data = data[written:]
    except BrokenPipeError:
        return 1
    return 0


def fail(recipe, reason):
    channel = 2 if recipe["diagnostic_stream"] == "stderr" else 1
    write_bytes(channel, recipe["diagnostics"][reason].encode())
    return 1


def signed_number(token):
    if not re.fullmatch(rb"[+-]?[0-9]+", token):
        raise ValueError
    magnitude = token.lstrip(b"+-").lstrip(b"0") or b"0"
    if len(magnitude) > 19:
        raise ValueError
    value = int(magnitude) * (-1 if token.startswith(b"-") else 1)
    if not I64_MIN <= value <= I64_MAX:
        raise ValueError
    return value


def checked_calculator(recipe):
    delimiter = bytes([recipe["terminator"]])
    text = sys.stdin.buffer.readline().removesuffix(delimiter)
    separators = bytes(recipe["separators"])
    fields = [token for token in re.split(b"[" + re.escape(separators) + b"]+", text) if token]
    if len(fields) != 3:
        return fail(recipe, "invalid")
    try:
        left, right = signed_number(fields[0]), signed_number(fields[2])
        operation = recipe["operations"][fields[1].decode("ascii")]
    except (ValueError, KeyError):
        return fail(recipe, "invalid")
    if operation == "divide":
        if right == 0:
            return fail(recipe, "zero")
        if recipe["division"] == "floor":
            answer = left // right
        else:
            answer = abs(left) // abs(right) * (-1 if (left < 0) != (right < 0) else 1)
    else:
        answer = OPERATIONS[operation](left, right)
    if not I64_MIN <= answer <= I64_MAX:
        return fail(recipe, "overflow")
    return write_bytes(1, f"{answer}\n".encode("ascii"))


def execute(recipe, arguments):
    handler = recipe["handler"]
    if handler == "write_literal":
        return write_bytes(1, recipe["literal"].encode())
    if handler == "join_arguments":
        values = [os.fsencode(arg) for arg in arguments if recipe["keep_empty"] or arg]
        return write_bytes(1, recipe["separator"].encode().join(values) + recipe["suffix"].encode())
    return checked_calculator(recipe)


if __name__ == "__main__":
    source, pinned, entry, *arguments = sys.argv[1:]
    store, snapshot = admit(json.loads(Path(source).read_bytes()))
    if snapshot.root_hash != pinned:
        raise SystemExit(2)
    raise SystemExit(execute(body_for(store, snapshot, entry), arguments))
