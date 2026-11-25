"""Normalize a restricted two-variable SMT-LIB assertion into affine branches."""

from collections.abc import Iterator
from itertools import product
import re

Row = tuple[int, int, int]
Branch = tuple[Row, ...]
VARIABLES = {"v0": (1, 0, 0), "v1": (0, 1, 0)}
TOKEN = re.compile(r"\s+|[()]|[A-Za-z_][A-Za-z_0-9-]*|[0-9]+|<=|=|[+\-]")


class Unsupported(ValueError):
    """The input cannot be lowered by the stated restricted profile."""


def tokenize(text):
    offset = 0
    while offset < len(text):
        token = TOKEN.match(text, offset)
        if token is None:
            raise Unsupported(f"Unsupported token at byte {offset}")
        offset = token.end()
        if not token[0].isspace():
            yield token[0]


def read(token, tokens):
    if token == ")":
        raise Unsupported("Unexpected closing parenthesis")
    if token != "(":
        return token
    parts = []
    for part in tokens:
        if part == ")":
            return tuple(parts)
        parts.append(read(part, tokens))
    raise Unsupported("Unclosed list")


def assertion(text):
    tokens = iter(tokenize(text))
    commands = [read(token, tokens) for token in tokens]
    prefix = [("set-logic", "QF_LIA"), ("declare-const", "v0", "Int"),
              ("declare-const", "v1", "Int")]
    if len(commands) != 6 or commands[:3] != prefix or commands[4:] != [("check-sat",), ("exit",)]:
        raise Unsupported("Expected the exact closed two-declaration query profile")
    match commands[3]:
        case ("assert", body):
            return body
        case _:
            raise Unsupported("Expected one assertion")


def add(left: Row, right: Row) -> Row:
    return tuple(x + y for x, y in zip(left, right, strict=True))


def scale(multiplier: int, term: Row) -> Row:
    return tuple(multiplier * coefficient for coefficient in term)


def forms(term, guards) -> Iterator[tuple[Branch, Row]]:
    if isinstance(term, str):
        if term in VARIABLES:
            yield (), VARIABLES[term]
        elif term.isdecimal():
            yield (), (0, 0, int(term))
        else:
            raise Unsupported(f"Unsupported integer atom {term!r}")
        return

    match term:
        case ("+", left, right) | ("-", left, right):
            operation = 1 if term[0] == "+" else -1
            for (left_path, a), (right_path, b) in product(forms(left, guards), forms(right, guards)):
                yield left_path + right_path, add(a, scale(operation, b))
        case ("-", argument):
            for path, row in forms(argument, guards):
                yield path, scale(-1, row)
        case ("ite", condition, yes, no):
            guards.add(condition)
            for side, selected in ((True, yes), (False, no)):
                for guard, (path, row) in product(branches(condition, side, guards), forms(selected, guards)):
                    yield guard + path, row
        case _:
            raise Unsupported(f"Unsupported integer expression {term!r}")


def branches(formula, positive, guards) -> Iterator[Branch]:
    match formula:
        case ("not", argument):
            yield from branches(argument, not positive, guards)
        case ("and", left, right) | ("or", left, right):
            if (formula[0] == "and") == positive:
                for lhs, rhs in product(branches(left, positive, guards), branches(right, positive, guards)):
                    yield lhs + rhs
            else:
                yield from branches(left, positive, guards)
                yield from branches(right, positive, guards)
        case ("<=", left, right) | ("=", left, right):
            for (guard1, lhs), (guard2, rhs) in product(forms(left, guards), forms(right, guards)):
                guard = guard1 + guard2
                delta = add(lhs, scale(-1, rhs))
                opposite = scale(-1, delta)
                if positive and formula[0] == "<=":
                    yield (*guard, delta)
                elif positive:
                    yield (*guard, delta, opposite)
                else:
                    yield (*guard, add(opposite, (0, 0, 1)))
                    if formula[0] == "=":
                        yield (*guard, add(delta, (0, 0, 1)))
        case _:
            raise Unsupported(f"Unsupported Boolean expression {formula!r}")


def normalize(formula):
    guards = set()
    paths = {
        tuple(sorted({row for row in branch if row[:2] != (0, 0) or row[2] > 0}))
        for branch in branches(formula, True, guards)
    }
    return sorted(paths), sorted(guards, key=repr)


def weight_witness(branch):
    """Eliminate each variable, tracking integer nonnegative row weights."""
    row_count = len(branch)
    working = [(row, tuple(int(index == j) for j in range(row_count)))
               for index, row in enumerate(branch)]
    for column in range(3):
        for row, weights in working:
            if row[:2] == (0, 0) and row[2] > 0:
                return weights
        if column == 2:
            break

        positive = [item for item in working if item[0][column] > 0]
        negative = [item for item in working if item[0][column] < 0]
        combined = {row: weights for row, weights in working if row[column] == 0}
        for (lhs, left_weight), (rhs, right_weight) in product(positive, negative):
            m, n = -rhs[column], lhs[column]
            row = add(scale(m, lhs), scale(n, rhs))
            weights = tuple(m * left + n * right for left, right in zip(left_weight, right_weight, strict=True))
            combined.setdefault(row, weights)
        working = sorted(combined.items())
    return None


def lean(term):
    if isinstance(term, str):
        if term == "v0":
            return "x"
        if term == "v1":
            return "y"
        if term.isdecimal():
            return f"({term} : Int)"
        raise Unsupported(f"Unexpected atom {term!r}")

    match term:
        case ("not", value):
            return f"(¬ {lean(value)})"
        case ("-", value):
            return f"(-{lean(value)})"
        case ("ite", condition, yes, no):
            return f"(if {lean(condition)} then {lean(yes)} else {lean(no)})"
        case (("+" | "-" | "<=" | "=" | "and" | "or") as operation, left, right):
            symbol = {"<=": "≤", "and": "∧", "or": "∨"}.get(operation, operation)
            return f"({lean(left)} {symbol} {lean(right)})"
        case _:
            raise Unsupported(f"Unexpected term {term!r}")
