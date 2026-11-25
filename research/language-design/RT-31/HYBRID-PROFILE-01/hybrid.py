"""Structured control and effects with infix scalar islands."""
import json

from profiles import BINARY, FrontendError, parse as parse_legacy, render as render_legacy, validate

VERSION = "hybrid/1"
FIELDS = {
    "scalar": {"kind", "expr"},
    "if": {"kind", "condition", "then", "else"},
    "emit": {"kind", "event", "value"},
    "call": {"kind", "binding", "target", "arguments"},
    "binary": {"kind", "operator", "left", "right"},
}


class HybridError(FrontendError):
    def __init__(self, message, path=(), offset=None, inner_offset=None):
        super().__init__(message, offset)
        self.path = path
        self.inner_offset = inner_offset


def scalar(term):
    if type(term) in (int, bool):
        return True
    tag, *children = term
    return tag == "arg" or (tag in BINARY and all(scalar(child) for child in children))


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HybridError("duplicate JSON field")
        result[key] = value
    return result


def decode(node, path):
    kind = node.get("kind") if type(node) is dict else None
    if type(kind) is not str or kind not in FIELDS or set(node) != FIELDS[kind]:
        raise HybridError("invalid hybrid expression node", path)

    if kind == "scalar":
        expression = node["expr"]
        if type(expression) is not str:
            raise HybridError("expected scalar expression string", (*path, "expr"))
        try:
            term = parse_legacy("infix/1", expression)
        except FrontendError as err:
            raise HybridError("invalid embedded scalar", (*path, "expr"), inner_offset=err.offset) from err
        if not scalar(term):
            raise HybridError("control or effects require a structured node", (*path, "expr"))
        return term
    if kind == "if":
        return ["if", *(decode(node[key], (*path, key)) for key in ("condition", "then", "else"))]
    if kind == "emit":
        if type(node["event"]) is not str:
            raise HybridError("expected event name", (*path, "event"))
        return ["emit", node["event"], decode(node["value"], (*path, "value"))]
    if kind == "call":
        if node["binding"] not in ("op", "pin") or type(node["target"]) is not str:
            raise HybridError("invalid call binding", path)
        if type(node["arguments"]) is not list:
            raise HybridError("expected argument list", (*path, "arguments"))
        children = [decode(value, (*path, "arguments", index))
                    for index, value in enumerate(node["arguments"])]
        return [node["binding"], node["target"], *children]

    operator = node["operator"]
    if type(operator) is not str or operator not in BINARY:
        raise HybridError("invalid structured operator", (*path, "operator"))
    return [operator, decode(node["left"], (*path, "left")), decode(node["right"], (*path, "right"))]


def parse(source):
    if not source.isascii():
        raise HybridError("fixture requires ASCII source")
    try:
        envelope = json.loads(source, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as err:
        raise HybridError("invalid structured expression", offset=err.pos) from err
    if type(envelope) is not dict or set(envelope) != {"profile", "expression"}:
        raise HybridError("invalid hybrid envelope")
    if envelope["profile"] != VERSION:
        raise HybridError("unsupported hybrid profile", ("profile",))
    term = decode(envelope["expression"], ("expression",))
    validate(term)
    return term


def render(term):
    validate(term)

    def emit(node):
        if scalar(node):
            return {"kind": "scalar", "expr": render_legacy("infix/1", node)}
        kind, *parts = node
        if kind == "if":
            condition, yes, no = map(emit, parts)
            return {"kind": "if", "condition": condition, "then": yes, "else": no}
        if kind == "emit":
            name, value = parts
            return {"kind": "emit", "event": name, "value": emit(value)}
        if kind in ("op", "pin"):
            target, *children = parts
            return {"kind": "call", "binding": kind, "target": target, "arguments": list(map(emit, children))}
        left, right = map(emit, parts)
        return {"kind": "binary", "operator": kind, "left": left, "right": right}

    return json.dumps({"profile": VERSION, "expression": emit(term)}, separators=(",", ":"))
