#!/usr/bin/env python3
"""Compare reference continuations, bytecode resume and exact effect settlement."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = runpy.run_path(str(HERE.parent / "STACK-VM-FUEL-01/run.py"))
PROFILE = "fixture-resumable-source-fuel/1"
SCENARIOS = ("original", "alter-reply", "cancel-first", "fail-second")


class Refusal(ValueError):
    pass


class Terminal(Exception):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return sha256(encode(value)).hexdigest()


def subject(tree, identity="execution-A", epoch=3):
    return {"source": digest(tree), "instance": identity, "profile": PROFILE, "policy_epoch": epoch}


def request(context, path, sequence, operation, default):
    return {
        "context": context, "call_path": list(path), "sequence": sequence,
        "operation": operation, "default": default,
    }


def observation(status, result, charged, remaining):
    return {"status": status, "result": result, "committed_effects": charged, "remaining_fuel": remaining}


def reference(tree, fuel, context):
    committed = []
    count = 0

    def evaluate(node, path):
        nonlocal fuel, count
        if fuel == 0:
            raise Terminal("exhausted")
        fuel -= 1
        match node:
            case ("constant", value):
                return value
            case ("emit", operation, default):
                waiting = request(context, path, count, operation, default)
                count += 1
                receipt = yield waiting
                assert receipt["request"] == digest(waiting)
                if receipt["status"] != "completed":
                    raise Terminal(receipt["status"])
                received = receipt["value"]
                committed.append([operation, list(path), received])
                return received
            case ("add", first, second):
                a = yield from evaluate(first, (*path, 0))
                b = yield from evaluate(second, (*path, 1))
                return a + b
            case ("if", test, yes, no):
                select = yield from evaluate(test, (*path, 0))
                return (yield from evaluate(yes if select else no, (*path, 1 if select else 2)))
            case _:
                raise ValueError(node)

    try:
        result = yield from evaluate(tree, ())
    except Terminal as stopped:
        return observation(str(stopped), None, committed, fuel)
    return observation("returned", result, committed, fuel)


def lower(tree):
    program = []

    def emit(instruction, argument=None):
        index = len(program)
        program.append((instruction, argument))
        return index

    def node(tree, path):
        emit("tick")
        match tree:
            case ("constant", value):
                emit("constant", value)
            case ("emit", operation, default):
                emit("request", [list(path), operation, default])
            case ("add", first, second):
                node(first, (*path, 0))
                node(second, (*path, 1))
                emit("sum")
            case ("if", test, yes, no):
                node(test, (*path, 0))
                branch = emit("branch")
                node(yes, (*path, 1))
                jump = emit("jump")
                program[branch] = ("branch", len(program))
                node(no, (*path, 2))
                program[jump] = ("jump", len(program))
            case _:
                raise ValueError(tree)

    node(tree, ())
    emit("return")
    return program


class VM:
    def __init__(self, program, fuel, context):
        self.program = program
        self.state = {
            "code": digest(program), "context": context, "fuel": fuel,
            "position": 0, "sequence": 0, "operands": [], "committed_effects": [],
            "waiting": None, "terminal": None,
        }

    def run(self):
        state = self.state
        assert state["waiting"] is None and state["terminal"] is None
        operands = state["operands"]
        while True:
            operation, argument = self.program[state["position"]]
            state["position"] += 1
            match operation:
                case "tick":
                    if state["fuel"] == 0:
                        return self.stop("exhausted")
                    state["fuel"] -= 1
                case "constant":
                    operands.append(argument)
                case "sum":
                    right = operands.pop()
                    operands[-1] += right
                case "branch":
                    if not operands.pop():
                        state["position"] = argument
                case "jump":
                    state["position"] = argument
                case "request":
                    path, name, default = argument
                    state["waiting"] = request(state["context"], path, state["sequence"], name, default)
                    state["sequence"] += 1
                    return state["waiting"]
                case "return":
                    assert len(operands) == 1
                    return self.stop("returned", operands[0])

    def stop(self, status, result=None):
        self.state["terminal"] = observation(status, result, self.state["committed_effects"], self.state["fuel"])
        return self.state["terminal"]

    def receive(self, receipt):
        waiting = self.state["waiting"]
        if waiting is None or receipt.get("request") != digest(waiting):
            raise Refusal("receipt-context")
        status = receipt.get("status")
        value = receipt.get("value")
        if (status == "completed" and type(value) is not int
                or status in ("failed", "cancelled") and value is not None
                or status not in ("completed", "failed", "cancelled")):
            raise Refusal("receipt-shape")
        self.state["waiting"] = None
        if status != "completed":
            return self.stop(status)
        self.state["committed_effects"].append([waiting["operation"], waiting["call_path"], value])
        self.state["operands"].append(value)
        return self.run()

    def freeze(self):
        assert self.state["waiting"] is not None
        return encode(self.state)

    @classmethod
    def thaw(cls, raw, checkpoint_id, program, context):
        state = json.loads(raw)
        if raw != encode(state) or digest(state) != checkpoint_id:
            raise Refusal("checkpoint-bytes")
        if state["context"] != context or state["code"] != digest(program):
            raise Refusal("checkpoint-context")
        result = cls(program, 0, context)
        result.state = state
        return result


def answer(waiting, policy):
    status = "completed"
    if policy == "cancel-first" and waiting["sequence"] == 0:
        status = "cancelled"
    if policy == "fail-second" and waiting["sequence"] == 1:
        status = "failed"
    value = waiting["default"] + (policy == "alter-reply") if status == "completed" else None
    return {"request": digest(waiting), "status": status, "value": value}


def from_reference(generator, argument=None):
    try:
        return generator.send(argument)
    except StopIteration as stopped:
        return stopped.value


def evaluate(tree, budget, policy, counters):
    context = subject(tree)
    program = lower(tree)
    source = reference(tree, budget, context)
    vm = VM(program, budget, context)
    reference_out = from_reference(source)
    candidate = vm.run()
    previous_reply = None
    previous_name = None
    while "call_path" in reference_out:
        assert reference_out == candidate
        checkpoint = vm.freeze()
        vm = VM.thaw(checkpoint, digest(vm.state), program, context)
        assert vm.freeze() == checkpoint
        reply = answer(reference_out, policy)
        if previous_reply is not None:
            try:
                vm.receive(previous_reply)
            except Refusal as error:
                assert str(error) == "receipt-context"
            else:
                raise AssertionError("stale receipt accepted")
            assert vm.freeze() == checkpoint
            counters["reused_receipts_refused"] += 1
            counters["same_operation_name"] += previous_name == reference_out["operation"]
        previous_reply = reply
        previous_name = reference_out["operation"]
        candidate = vm.receive(reply)
        reference_out = from_reference(source, reply)
        counters["checkpoint_restorations"] += 1
    assert reference_out == candidate
    if policy == "original":
        status, result, names, left = PREVIOUS["reference"](tree, budget)
        assert candidate == observation(status, result, candidate["committed_effects"], left)
        assert names == [event[0] for event in candidate["committed_effects"]]
        counters["original_reference_agreements"] += 1
    return candidate


def adversarial():
    tree = ("add", ("emit", "same", 3), ("emit", "same", 5))
    program = lower(tree)
    context = subject(tree)
    vm = VM(program, 7, context)
    waiting = vm.run()
    checkpoint = vm.freeze()
    checkpoint_id = digest(vm.state)
    changes = deepcopy(vm.state)
    changes["fuel"] += 1
    controls = {}

    def check(name, failure, operation):
        try:
            operation()
        except Refusal as error:
            assert str(error) == failure
        else:
            raise AssertionError(name)
        controls[name] = failure

    check("changed stored budget", "checkpoint-bytes",
          lambda: VM.thaw(encode(changes), checkpoint_id, program, context))
    check("changed execution", "checkpoint-context",
          lambda: VM.thaw(checkpoint, checkpoint_id, program, subject(tree, "execution-B")))
    check("changed policy epoch", "checkpoint-context",
          lambda: VM.thaw(checkpoint, checkpoint_id, program, subject(tree, epoch=4)))
    altered_code = program[:-1] + [("jump", 0)]
    check("changed bytecode", "checkpoint-context",
          lambda: VM.thaw(checkpoint, checkpoint_id, altered_code, context))
    bad = answer(waiting, "original") | {"value": False}
    check("malformed effect response", "receipt-shape", lambda: vm.receive(bad))
    assert vm.freeze() == checkpoint
    vm2 = VM.thaw(checkpoint, checkpoint_id, program, context)
    assert vm.receive(answer(waiting, "original")) == vm2.receive(answer(waiting, "original"))
    return controls


def experiment():
    counters = Counter()
    terms = Counter()
    for tree, fuel, policy in product(tuple(PREVIOUS["corpus"]()), range(9), SCENARIOS):
        result = evaluate(tree, fuel, policy, counters)
        terms[result["status"]] += 1
    return {
        "format": "resumable-execution-01", "counts": counters, "terminal_states": terms,
        "treated_cases": sum(terms.values()), "control_refusals": adversarial(),
    }


if __name__ == "__main__":
    evidence = experiment()
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
