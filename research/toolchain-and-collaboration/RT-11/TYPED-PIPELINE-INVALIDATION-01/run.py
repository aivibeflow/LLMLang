"""Exercise scoped keys for six actions on a closed arithmetic pipeline."""

import ast
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import platform

ACTIONS = ("type", "contract", "optimization", "code_generation", "tests", "proof")


def key(kind, inputs):
    blob = json.dumps({"kind": kind, "inputs": inputs}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass(frozen=True)
class Inputs:
    source: str = "x + (1 + 1)"
    contract_maximum: int = 7
    finite_domain: tuple[int, ...] = tuple(range(6))
    target: str = "stack-profile-v1"
    test_cases: tuple[tuple[int, int], ...] = ((0, 2), (2, 4))
    verifier: str = "finite-checker-v1"


def parse(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return "integer", node.value
    if isinstance(node, ast.Name) and node.id == "x":
        return "argument",
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = parse(node.left), parse(node.right)
        if left is not None and right is not None:
            return "add", left, right
    return None


def evaluate(expr, argument):
    if expr[0] == "integer":
        return expr[1]
    if expr[0] == "argument":
        return argument
    return evaluate(expr[1], argument) + evaluate(expr[2], argument)


def normalize(expr):
    if expr[0] == "integer":
        return 0, expr[1]
    if expr[0] == "argument":
        return 1, 0
    left_coefficient, left_constant = normalize(expr[1])
    right_coefficient, right_constant = normalize(expr[2])
    return left_coefficient + right_coefficient, left_constant + right_constant


def execute(program, argument):
    register = argument
    for instruction, immediate in program["instructions"]:
        if instruction == "mul":
            register *= immediate
        elif instruction == "add":
            register += immediate
    return register


def pipeline(inputs):
    tree = ast.parse(inputs.source.strip(), mode="eval").body
    structural_ast = ast.dump(tree, include_attributes=False)
    keys = {"type": key("type", {"ast": structural_ast, "expected": "Int-to-Int"})}
    source_map = key("source-map", {"exact_source": inputs.source, "ast": structural_ast})
    typed = parse(tree)
    if typed is None:
        return {"keys": keys, "source_map": source_map, "type_passed": False,
                "withheld": list(ACTIONS[1:])}

    specification = {"maximum": inputs.contract_maximum, "domain": inputs.finite_domain}
    contract_inputs = {"typed": typed, "specification": specification}
    keys["contract"] = key("contract", contract_inputs)
    keys["optimization"] = key("optimization", {"typed": typed, "optimizer": "affine-v1"})
    affine = normalize(typed)
    keys["code_generation"] = key("code", {"optimized": affine, "target": inputs.target})
    code = {"target": inputs.target, "instructions": [("mul", affine[0]), ("add", affine[1])]}
    keys["tests"] = key("tests", {"code": code, "cases": inputs.test_cases})
    keys["proof"] = key("finite-verification", contract_inputs | {"verifier": inputs.verifier})

    refuted_arguments = [n for n in inputs.finite_domain if evaluate(typed, n) > inputs.contract_maximum]
    assert all(evaluate(typed, n) == execute(code, n) for n in inputs.finite_domain)
    return {
        "keys": keys, "source_map": source_map, "type_passed": True, "optimized": affine, "code": code,
        "contract_refuted_at": refuted_arguments,
        "failed_tests": [n for n, expected in inputs.test_cases if execute(code, n) != expected],
        "finite_verification": "REFUTED" if refuted_arguments else "AGREES_IN_DECLARED_DOMAIN",
    }


def main():
    initial = Inputs()
    baseline = pipeline(initial)
    cases = {
        "formatting": (replace(initial, source="x  +  (1 + 1)"), []),
        "equivalent_ast_change": (replace(initial, source="x + 2"), ["type", "contract", "optimization", "proof"]),
        "changed_behavior": (replace(initial, source="x + 3"), list(ACTIONS)),
        "changed_contract": (replace(initial, contract_maximum=6), ["contract", "proof"]),
        "changed_finite_domain": (replace(initial, finite_domain=tuple(range(5))), ["contract", "proof"]),
        "changed_target": (replace(initial, target="stack-profile-v2"), ["code_generation", "tests"]),
        "changed_tests": (replace(initial, test_cases=((1, 3),)), ["tests"]),
        "changed_verifier": (replace(initial, verifier="finite-checker-v2"), ["proof"]),
    }
    observed = {}
    for name, (inputs, expected_changes) in cases.items():
        result = pipeline(inputs)
        changes = [action for action in ACTIONS if baseline["keys"][action] != result["keys"][action]]
        assert changes == expected_changes, (name, changes)
        observed[name] = result | {"changed_actions": changes,
                                   "source_map_changed": result["source_map"] != baseline["source_map"]}
    assert observed["formatting"]["source_map_changed"]
    assert observed["equivalent_ast_change"]["optimized"] == baseline["optimized"]
    assert observed["equivalent_ast_change"]["code"] == baseline["code"]
    assert observed["changed_behavior"]["contract_refuted_at"] == [5]
    assert observed["changed_contract"]["contract_refuted_at"] == [5]
    assert observed["changed_behavior"]["failed_tests"] == [0, 2]

    invalid = pipeline(replace(initial, source='x + "bad"'))
    assert not invalid["type_passed"] and invalid["keys"]["type"] != baseline["keys"]["type"]
    assert invalid["withheld"] == list(ACTIONS[1:])
    insufficient_type_key = key("type-interface-only", {"expected": "Int-to-Int"})
    return {
        "schema": "llmlang-rt11-typed-pipeline-invalidation/1", "python": platform.python_version(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "baseline": baseline, "edits": observed, "type_invalid_control": invalid,
        "type_interface_only_control": {"shared_key": insufficient_type_key,
                                        "baseline_accepted": True, "invalid_edit_accepted": False},
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
