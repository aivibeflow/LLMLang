"""Compare a tree interpreter and a stack VM at every bounded fuel cut."""

from itertools import product
import json
import platform


class Exhausted(Exception):
    pass


def reference(tree, fuel):
    events = []

    def evaluate(node):
        nonlocal fuel
        if fuel == 0:
            raise Exhausted
        fuel -= 1
        match node:
            case ("constant", value):
                return value
            case ("emit", label, value):
                events.append(label)
                return value
            case ("add", left, right):
                return evaluate(left) + evaluate(right)
            case ("if", test, yes, no):
                return evaluate(yes if evaluate(test) else no)
            case _:
                raise ValueError(node)

    try:
        value = evaluate(tree)
    except Exhausted:
        return "exhausted", None, events, fuel
    return "returned", value, events, fuel


def lower(tree):
    code = []

    def emit(op, arg=None):
        index = len(code)
        code.append((op, arg))
        return index

    def compile_node(node):
        emit("charge")
        match node:
            case ("constant", value):
                emit("push", value)
            case ("emit", label, value):
                emit("event", label)
                emit("push", value)
            case ("add", left, right):
                compile_node(left)
                compile_node(right)
                emit("add")
            case ("if", test, yes, no):
                compile_node(test)
                branch = emit("if-zero")
                compile_node(yes)
                end = emit("jump")
                code[branch] = ("if-zero", len(code))
                compile_node(no)
                code[end] = ("jump", len(code))
            case _:
                raise ValueError(node)

    compile_node(tree)
    emit("halt")
    return code


def vm(code, fuel, source_steps):
    stack = []
    events = []
    counter = 0
    while True:
        op, arg = code[counter]
        spends_fuel = op == "charge" if source_steps else op not in ("charge", "halt")
        if spends_fuel:
            if fuel == 0:
                return "exhausted", None, events, fuel
            fuel -= 1
        counter += 1
        match op:
            case "charge":
                pass
            case "push":
                stack.append(arg)
            case "event":
                events.append(arg)
            case "add":
                right = stack.pop()
                stack[-1] += right
            case "if-zero":
                if not stack.pop():
                    counter = arg
            case "jump":
                counter = arg
            case "halt":
                assert len(stack) == 1
                return "returned", stack[0], events, fuel
            case _:
                raise ValueError(op)


def corpus():
    leaves = (("constant", 0), ("constant", 3), ("emit", "a", 0),
              ("emit", "a", 2), ("emit", "b", -1))
    yield from leaves
    yield from (("add", left, right) for left, right in product(leaves, repeat=2))
    yield from (("if", test, yes, no) for test, yes, no in product(leaves, repeat=3))
    for test, left, right in product(leaves, repeat=3):
        yield "if", test, ("add", left, right), ("emit", "alternate", 1)
        yield "add", ("if", test, left, right), ("emit", "after", 2)


def study():
    counters = {
        "source_step_mismatches": 0,
        "opcode_step_effect_mismatches": 0,
        "opcode_step_terminal_mismatches": 0,
        "opcode_step_value_or_effect_or_terminal_mismatches": 0,
    }
    trees = list(corpus())
    for tree in trees:
        code = lower(tree)
        for fuel in range(13):
            oracle = reference(tree, fuel)
            source = vm(code, fuel, source_steps=True)
            opcode = vm(code, fuel, source_steps=False)
            counters["source_step_mismatches"] += source != oracle
            counters["opcode_step_effect_mismatches"] += opcode[2] != oracle[2]
            counters["opcode_step_terminal_mismatches"] += opcode[0] != oracle[0]
            counters["opcode_step_value_or_effect_or_terminal_mismatches"] += opcode[:3] != oracle[:3]

    example = ("if", ("emit", "condition", 0), ("emit", "yes", 1), ("emit", "no", 2))
    code = lower(example)
    examples = {
        str(fuel): {
            "reference": reference(example, fuel),
            "source_vm": vm(code, fuel, source_steps=True),
            "opcode_vm": vm(code, fuel, source_steps=False),
        }
        for fuel in range(7)
    }
    assert counters == {
        "source_step_mismatches": 0,
        "opcode_step_effect_mismatches": 580,
        "opcode_step_terminal_mismatches": 898,
        "opcode_step_value_or_effect_or_terminal_mismatches": 1280,
    }
    assert examples["1"]["reference"] == ("exhausted", None, [], 0)
    assert examples["1"]["opcode_vm"] == ("exhausted", None, ["condition"], 0)
    assert examples["3"]["reference"] == ("returned", 2, ["condition", "no"], 0)
    return {
        "python": platform.python_version(),
        "tree_count": len(trees),
        "fuel_values": [0, 12],
        "cases": len(trees) * 13,
        "mismatches": counters,
        "example_tree": example,
        "example_code": code,
        "example_cuts": examples,
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
