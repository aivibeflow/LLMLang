#!/usr/bin/env python3
"""Read and evaluate one admitted state/Result fixture request."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / "THREE-SEMANTICS-01" / "run.py"
spec = spec_from_file_location("state_result_denotation", MODEL)
model = module_from_spec(spec)
spec.loader.exec_module(model)

SCHEMA = "llmlang-state-result-reference/1"
MAX_BYTES = 65536
MAX_DEPTH = 32


class AdmissionError(ValueError):
    pass


def parse_program(value, depth=0):
    if depth > MAX_DEPTH:
        raise AdmissionError("expression-depth")
    if not isinstance(value, list) or not value or type(value[0]) is not str:
        raise AdmissionError("expression-shape")
    tag, *operands = value
    if tag in {"skip", "read", "fail"} and not operands:
        return (tag,)
    if tag == "write" and len(operands) == 1 and type(operands[0]) is int and operands[0] in (0, 1):
        return tag, operands[0]
    if tag in model.FORMERS and len(operands) == 2:
        return tag, parse_program(operands[0], depth + 1), parse_program(operands[1], depth + 1)
    raise AdmissionError("unsupported-expression")


def evaluate_request(raw):
    if len(raw) > MAX_BYTES:
        raise AdmissionError("input-size")
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise AdmissionError("malformed-json") from error
    if not isinstance(request, list) or len(request) != 3 or request[0] != SCHEMA:
        raise AdmissionError("request-schema")
    _, initial, expression = request
    if type(initial) is not int or initial not in model.INITIAL:
        raise AdmissionError("initial-cell")
    (tag, value), state, trace = model.denote(parse_program(expression), initial)
    return {"result": {tag: value}, "final_cell": state, "trace": trace}


if __name__ == "__main__":
    payload = sys.stdin.buffer.read(MAX_BYTES + 1)
    try:
        observation = evaluate_request(payload)
    except AdmissionError as error:
        print(json.dumps({"error": str(error)}))
        sys.exit(2)
    print(json.dumps(observation, separators=(",", ":")))
