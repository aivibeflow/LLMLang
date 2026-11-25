"""Three versioned expression profiles for the closed typed SPG fixture."""
import ast
import json
import re

from src.spg_representation import RepresentationError, _infix


PROFILES = ("infix/1", "json-tree/1", "s-expression/1")
TOKEN = re.compile(r'\s+|[()]|(?:"(?:[^"\\\r\n]|\\.)*"|-?(?:0|[1-9][0-9]*)|[A-Za-z_][A-Za-z_0-9]*)(?=$|[\s()])')
BINARY = {"add": "+", "sub": "-", "eq": "=="}


class FrontendError(ValueError):
    def __init__(self, message, offset=None):
        super().__init__(message)
        self.offset = offset


def validate(term):
    if type(term) in (int, bool):
        return
    match term:
        case ["arg", str()]:
            return
        case [("add" | "sub" | "eq"), left, right]:
            children = (left, right)
        case ["if", test, yes, no]:
            children = (test, yes, no)
        case ["emit", str(), tail]:
            children = (tail,)
        case [("op" | "pin"), str(), *children]:
            pass
        case _:
            raise FrontendError("unsupported abstract expression shape")
    for child in children:
        validate(child)


def parse_sexpr(source):
    tokens = []
    position = 0
    while position < len(source):
        token = TOKEN.match(source, position)
        if token is None:
            raise FrontendError("unexpected token", position)
        if not token[0].isspace():
            tokens.append((token[0], position))
        position = token.end()
    tokens.append(("", len(source)))
    index = 0

    def read():
        nonlocal index
        value, offset = tokens[index]
        if not value or value == ")":
            raise FrontendError("expected expression", offset)
        index += 1
        if value == "(":
            tag, inner_offset = tokens[index]
            if not tag or not tag[0].isalpha():
                raise FrontendError("expected expression tag", inner_offset)
            index += 1
            elements = [tag]
            while tokens[index][0] != ")":
                elements.append(read())
            index += 1
            return elements
        if value.startswith('"') or value[0].isdigit() or value[0] == "-" or value in ("true", "false"):
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise FrontendError("invalid atom", offset + exc.pos) from exc
        raise FrontendError("unexpected bare name", offset)

    term = read()
    if tokens[index][0]:
        raise FrontendError("trailing expression", tokens[index][1])
    return term


def parse(profile, source):
    if profile not in PROFILES:
        raise FrontendError("unknown syntax profile")
    if not source.isascii():
        raise FrontendError("fixture source must use ASCII")
    try:
        if profile == "infix/1":
            tree = ast.parse(source, mode="eval")
            term = _infix(tree.body)
        elif profile == "json-tree/1":
            term = json.loads(source)
        else:
            term = parse_sexpr(source)
    except SyntaxError as exc:
        offset = None if exc.offset is None else sum(
            len(line) for line in source.splitlines(keepends=True)[:max((exc.lineno or 1) - 1, 0)]
        ) + max(exc.offset - 1, 0)
        raise FrontendError("invalid infix expression", offset) from exc
    except json.JSONDecodeError as exc:
        raise FrontendError("invalid JSON expression", exc.pos) from exc
    except RepresentationError as exc:
        raise FrontendError(str(exc)) from exc
    validate(term)
    return term


def render(profile, term):
    if profile not in PROFILES:
        raise FrontendError("unknown syntax profile")
    validate(term)

    def show(value):
        if profile == "infix/1":
            if type(value) in (int, bool):
                return repr(value)
            tag, *fields = value
            if tag == "arg":
                return fields[0]
            if tag in BINARY:
                left, right = map(show, fields)
                return f"({left} {BINARY[tag]} {right})"
            if tag == "if":
                test, yes, no = map(show, fields)
                return f"({yes} if {test} else {no})"
            label, *children = fields
            return tag + "(" + ", ".join([json.dumps(label), *map(show, children)]) + ")"
        if not isinstance(value, list):
            return json.dumps(value)
        tag, *fields = value
        return "(" + " ".join([tag, *map(show, fields)]) + ")"

    if profile == "json-tree/1":
        return json.dumps(term, separators=(",", ":"))
    return show(term)
