"""Derive continuations for a restricted, concretely executable source fragment."""

import ast
from dataclasses import dataclass


class UnsupportedSource(ValueError):
    """The source falls outside the checked fixture grammar."""


@dataclass(frozen=True)
class Instruction:
    kind: str
    data: tuple = ()
    next: tuple[int, ...] = ()
    span: tuple[int, int, int, int] | None = None


def arguments(expression, name, arity):
    if not (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == name
        and len(expression.args) == arity
        and not expression.keywords
    ):
        raise UnsupportedSource(f"Expected {name} with {arity} positional arguments")
    return expression.args


def literal(node):
    if not isinstance(node, ast.Constant) or type(node.value) is not str:
        raise UnsupportedSource("Expected a string literal")
    return node.value


def flag(node):
    if isinstance(node, ast.Name) and node.id in {"x", "y"}:
        return node.id
    if isinstance(node, ast.Constant) and type(node.value) is bool:
        return node.value
    raise UnsupportedSource("Expected Bool parameter or literal")


def source_span(node):
    return node.lineno, node.end_lineno, node.col_offset, node.end_col_offset


class Lowering:
    def __init__(self, *, eager=False, skip_return_cleanup=False):
        self.nodes = []
        self.eager = eager
        self.skip_return_cleanup = skip_return_cleanup

    def add(self, kind, data=(), next=(), span=None):
        index = len(self.nodes)
        self.nodes.append(Instruction(kind, data, next, span))
        return index

    def condition(self, node, yes, no):
        if isinstance(node, ast.BoolOp) and len(node.values) == 2:
            left, right = node.values
            via_right = self.condition(right, yes, no)
            if isinstance(node.op, ast.And):
                shortcut = self.condition(right, no, no) if self.eager else no
                return self.condition(left, via_right, shortcut)
            if isinstance(node.op, ast.Or):
                shortcut = self.condition(right, yes, yes) if self.eager else yes
                return self.condition(left, shortcut, via_right)
        if isinstance(node, ast.Call):
            label, value = arguments(node, "probe", 2)
            return self.add("probe", (literal(label), flag(value)), (yes, no), source_span(node))
        return self.add("test", (flag(node),), (yes, no), source_span(node))

    def cleanup(self, operation, resume, error):
        if not isinstance(operation, ast.Expr):
            raise UnsupportedSource("Finally requires a cleanup call")
        resource, = arguments(operation.value, "close_slot", 1)
        return self.add("close", (literal(resource),), (resume, error), source_span(operation.value))

    def statement(self, node, resume, returned, error):
        if isinstance(node, ast.If):
            yes = self.block(node.body, resume, returned, error)
            no = self.block(node.orelse, resume, returned, error)
            return self.condition(node.test, yes, no)
        if isinstance(node, ast.Try):
            if node.handlers or node.orelse or len(node.finalbody) != 1:
                raise UnsupportedSource("Only try with one finally cleanup is supported")
            operation, = node.finalbody
            after_normal = self.cleanup(operation, resume, error)
            after_return = self.cleanup(operation, returned, error)
            after_error = self.cleanup(operation, error, error)
            if self.skip_return_cleanup:
                after_return = returned
            return self.block(node.body, after_normal, after_return, after_error)
        if isinstance(node, ast.Return):
            resource, = arguments(node.value, "stage", 1)
            return self.add("stage", (literal(resource),), (returned,), source_span(node.value))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id in {"open_slot", "emit", "fail"}:
                name = call.func.id
                label, = arguments(call, name, 1)
                return self.add(name, (literal(label),), (error if name == "fail" else resume,),
                                source_span(call))
        raise UnsupportedSource(f"Unsupported statement at line {node.lineno}")

    def block(self, statements, resume, returned, error):
        for statement in reversed(statements):
            resume = self.statement(statement, resume, returned, error)
        return resume


def lower(source, **options):
    module = ast.parse(source)
    if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
        raise UnsupportedSource("Expected one plain function")
    fn, = module.body
    args = fn.args
    if (
        fn.name != "entry" or fn.decorator_list or fn.returns is not None or fn.type_params
        or args.posonlyargs or args.vararg or args.kwonlyargs or args.kwarg or args.defaults
        or [(argument.arg, argument.annotation) for argument in args.args]
        != [("x", None), ("y", None)]
    ):
        raise UnsupportedSource("Expected an undecorated entry(x, y)")
    cfg = Lowering(**options)
    fallthrough = cfg.add("fallthrough")
    returned = cfg.add("returned")
    error = cfg.add("error")
    start = cfg.block(fn.body, fallthrough, returned, error)
    return start, cfg.nodes


def execute(graph, flags, close_errors, *, replace_error=False):
    current, nodes = graph
    trace = []
    slots = {}
    staged = None
    causes = []
    visited = set()

    def truth(value):
        return flags[value] if isinstance(value, str) else value

    while current not in visited:
        visited.add(current)
        node = nodes[current]
        kind = node.kind
        if kind == "fallthrough":
            raise ValueError("Fixture falls through without a declared outcome")
        if kind in {"returned", "error"}:
            handle = "none"
            if staged is not None:
                handle = "caller" if kind == "returned" else "pending"
            return {
                "trace": trace, "result": staged if kind == "returned" else None,
                "errors": causes, "slots": slots,
                "handle": handle,
            }

        edge = 0
        label, *operands = node.data
        if kind == "test":
            edge = int(not truth(label))
        elif kind == "probe":
            value = truth(operands[0])
            trace.append([list(node.span), "probe", label, value])
            edge = int(not value)
        elif kind == "open_slot":
            if label in slots:
                raise ValueError(f"Repeated acquisition at span {node.span}")
            slots[label] = "live"
            trace.append([list(node.span), "open", label])
        elif kind == "emit":
            trace.append([list(node.span), "emit", label])
        elif kind == "stage":
            if staged is not None:
                raise ValueError("Fixture stages more than one handle")
            staged = label
            trace.append([list(node.span), "stage", label])
        elif kind == "fail":
            causes = [label]
            trace.append([list(node.span), "fail", label])
        elif kind == "close":
            if slots.get(label) != "live":
                raise ValueError(f"Cleanup without a live slot at span {node.span}")
            failed = close_errors[label]
            slots[label] = "debt" if failed else "released"
            trace.append([list(node.span), "close", label, not failed])
            if failed:
                cause = f"close:{label}"
                causes = [cause] if replace_error else [*causes, cause]
                edge = 1
        else:
            raise AssertionError(kind)
        current = node.next[edge]
    raise ValueError("Cycle encountered in an acyclic fixture")
