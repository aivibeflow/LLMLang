"""Symbolic execution of the verified, acyclic Scenario 96A LLVM subset."""

from dataclasses import dataclass
import re


INPUTS = ("a", "b", "enabled")
ENTRY = re.compile(
    r"define (?:(?:range\(i32 0, 2\)|noundef) )?i32 @probe_0\(i32 %a, i32 %b, i32 %enabled, "
    r"ptr (?:nocapture readonly )?%emit, ptr (?:nocapture writeonly )?%out\)(?: local_unnamed_addr)? \{"
)
INTRINSIC = "declare { i32, i1 } @llvm.sadd.with.overflow.i32(i32, i32)"
ADDRESS = r"[\w.]+"
OPERAND = r"(?:%[\w.]+|-?\d+)"
PHI_ARM = rf"\[\s*({OPERAND}),\s*%({ADDRESS})\s*\]"


class Unsupported(ValueError):
    """No admitted LLVM semantics for this artifact."""


@dataclass(frozen=True)
class Path:
    conditions: tuple[str, ...]
    status: str
    effects: tuple[str, ...]
    stores: tuple[str, ...]


def form(operator, *arguments):
    return "(" + " ".join((operator, *arguments)) + ")"


def conjunction(*arguments):
    return form("and", *arguments) if len(arguments) > 1 else next(iter(arguments), "true")


def disjunction(*arguments):
    return form("or", *arguments) if len(arguments) > 1 else next(iter(arguments), "false")


def bits(number, width=32):
    return f"(_ bv{number % 2**width} {width})"


def module(ir):
    lines = [line.partition(";")[0].strip() for line in ir.splitlines()]
    lines = [line for line in lines if line]
    entries = [index for index, line in enumerate(lines) if ENTRY.fullmatch(line)]
    if len(entries) != 1 or lines.count("}") != 1:
        raise Unsupported("expected one admitted probe definition")
    start, end = entries[0], lines.index("}")
    triple = 'target triple = "x86_64-unknown-linux-gnu"'
    header_patterns = (
        re.escape(triple), r'source_filename = "<stdin>"',
        r'target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"',
        re.escape(INTRINSIC) + r"(?: #0)?",
        r"attributes #0 = \{ (?:mustprogress )?nocallback nofree nosync nounwind speculatable willreturn memory\(none\) \}",
    )
    if triple not in lines[:start] or start >= end or any(
        not any(re.fullmatch(pattern, line) for pattern in header_patterns)
        for line in lines[:start] + lines[end + 1:]
    ):
        raise Unsupported("unexpected module declaration or attributes")
    blocks = {}
    for line in lines[start + 1:end]:
        match = re.fullmatch(rf"({ADDRESS}):", line)
        if match:
            block = match[1]
            if block in blocks:
                raise Unsupported(f"duplicate block {block}")
            blocks[block] = []
        elif not blocks:
            raise Unsupported("missing leading block label")
        else:
            blocks[block].append(line)
    if "entry" not in blocks:
        raise Unsupported("missing entry block")
    return blocks


def intrinsic(left, right):
    def sign(operand):
        return form("(_ extract 31 31)", operand)

    summed = form("bvadd", left, right)
    overflow = conjunction(form("=", sign(left), sign(right)), form("distinct", sign(left), sign(summed)))
    return summed, overflow


def paths(ir):
    blocks = module(ir)
    reached = set()

    def visit(label, previous, visited, environment, conditions, effects, stores):
        if label in visited or label not in blocks:
            raise Unsupported(f"cyclic or missing block {label}")
        reached.add(label)
        values = environment.copy()

        def operand(token, sort=32):
            if token.startswith("%"):
                if token[1:] in values and values[token[1:]][0] == sort:
                    return values[token[1:]][1]
                raise Unsupported(f"missing or incorrectly typed value {token} on {label}")
            if sort == 32 and re.fullmatch(r"-?\d+", token):
                return bits(int(token))
            raise Unsupported(f"unsupported operand {token}")

        for index, line in enumerate(blocks[label]):
            if line.startswith(("br ", "ret ")) and index != len(blocks[label]) - 1:
                raise Unsupported(f"trailing instruction in {label}")
            if match := re.fullmatch(rf"br i1 (%{ADDRESS}), label %({ADDRESS}), label %({ADDRESS})", line):
                condition = operand(match[1], 1)
                yield from visit(match[2], label, visited | {label}, values, (*conditions, condition), effects, stores)
                yield from visit(match[3], label, visited | {label}, values,
                                 (*conditions, form("not", condition)), effects, stores)
                return
            if match := re.fullmatch(rf"br label %({ADDRESS})", line):
                yield from visit(match[1], label, visited | {label}, values, conditions, effects, stores)
                return
            if match := re.fullmatch(rf"ret i32 ({OPERAND})", line):
                yield Path(conditions, operand(match[1]), effects, stores)
                return
            if match := re.fullmatch(rf"(?:tail )?call void %emit\(i32 ({OPERAND})\)", line):
                effects = (*effects, operand(match[1]))
                continue
            if match := re.fullmatch(rf"store i32 ({OPERAND}), ptr %out, align 4", line):
                stores = (*stores, operand(match[1]))
                continue
            assignment = re.fullmatch(rf"%({ADDRESS}) = (.+)", line)
            if assignment is None or assignment[1] in values:
                raise Unsupported(f"unsupported LLVM instruction {line}")
            name, expression = assignment.groups()
            if match := re.fullmatch(rf"icmp (eq|ne) i32 ({OPERAND}), ({OPERAND})", expression):
                op = "=" if match[1] == "eq" else "distinct"
                values[name] = 1, form(op, operand(match[2]), operand(match[3]))
            elif match := re.fullmatch(rf"add i32 ({OPERAND}), ({OPERAND})", expression):
                values[name] = 32, form("bvadd", operand(match[1]), operand(match[2]))
            elif match := re.fullmatch(rf"select i1 (%{ADDRESS}), i32 ({OPERAND}), i32 ({OPERAND})", expression):
                values[name] = 32, form("ite", operand(match[1], 1), operand(match[2]), operand(match[3]))
            elif match := re.fullmatch(
                rf"(?:tail )?call \{{ i32, i1 \}} @llvm\.sadd\.with\.overflow\.i32\(i32 ({OPERAND}), i32 ({OPERAND})\)",
                expression,
            ):
                values[name] = "pair", intrinsic(operand(match[1]), operand(match[2]))
            elif match := re.fullmatch(rf"extractvalue \{{ i32, i1 \}} (%{ADDRESS}), ([01])", expression):
                member = int(match[2])
                values[name] = (32, 1)[member], operand(match[1], "pair")[member]
            elif expression.startswith("phi i32 "):
                arms = expression.removeprefix("phi i32 ")
                if not re.fullmatch(rf"{PHI_ARM}(?:,\s*{PHI_ARM})*", arms):
                    raise Unsupported(f"malformed phi {line}")
                inputs = {edge: token for token, edge in re.findall(PHI_ARM, arms)}
                if previous not in inputs:
                    raise Unsupported(f"missing phi predecessor {previous}")
                # Resolve every phi in the predecessor environment, prior to the
                # parallel assignments at the destination's block entry.
                token = inputs[previous]
                if token.startswith("%") and token[1:] not in environment:
                    raise Unsupported(f"value {token} unavailable on phi edge")
                values[name] = 32, operand(token)
            else:
                raise Unsupported(f"unsupported LLVM instruction {line}")
        raise Unsupported(f"unterminated block {label}")

    result = tuple(visit("entry", None, set(), {name: (32, name) for name in INPUTS}, (), (), ()))
    if reached != set(blocks):
        raise Unsupported(f"unreachable blocks {sorted(set(blocks) - reached)}")
    return result


def sequence_matches(actual, expected):
    if len(actual) != len(expected):
        return "false"
    return conjunction(*(form("=", x, y) for x, y in zip(actual, expected, strict=True)))


def disagreement(exits, components):
    # The source rule interprets operands as mathematical signed integers. 33
    # bits suffice to represent their exact sum before the signed range check.
    widened = form("bvadd", *(form("(_ sign_extend 1)", name) for name in ("a", "b")))
    enabled = form("distinct", "enabled", bits(0))
    overflow = conjunction(enabled, disjunction(form("bvslt", widened, bits(-2**31, 33)),
                                                form("bvsgt", widened, bits(2**31 - 1, 33))))
    value = form("ite", enabled, form("(_ extract 31 0)", widened), "b")

    def matches(exit, status, effects, stores):
        properties = {
            "status": form("=", exit.status, bits(status)),
            "effects": sequence_matches(exit.effects, effects),
            "stores": sequence_matches(exit.stores, stores),
        }
        return conjunction(*(properties[component] for component in components))

    clauses = []
    for exit in exits:
        failed = matches(exit, 1, ("a",), ())
        succeeded = matches(exit, 0, ("a", value), (value,))
        same_observation = form("ite", overflow, failed, succeeded)
        clauses.append(conjunction(*exit.conditions, form("not", same_observation)))
    return disjunction(*clauses)


def smt_query(predicate, witness=None):
    declarations = [f"(declare-const {name} (_ BitVec 32))" for name in INPUTS]
    constraints = [] if witness is None else [
        f"(assert (= {name} {bits(value)}))" for name, value in zip(INPUTS, witness, strict=True)
    ]
    return "\n".join(["(set-logic QF_BV)", *declarations, f"(assert {predicate})", *constraints, "(check-sat)", ""])
