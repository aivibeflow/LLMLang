"""Exercise review fidelity, exact pins, and independent rejection gates."""

import argparse
from copy import deepcopy
import json
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

from .__main__ import FIXTURES, load_program, packet_id, review_packet, verify_review_receipt
from . import contract, frontend, runtime, verify


def require(condition, message, detail=None):
    if not condition:
        raise AssertionError(f"{message}: {detail!r}")


def run(boogie, z3):
    source = FIXTURES / "calculator.llmlang"
    contracts = FIXTURES / "calculator.contracts.json"
    program, definitions, inputs = load_program(source, contracts)
    for pair in definitions.values():
        for definition in pair.values():
            require(
                contract.parse_controlled(contract.checked_render(definition)) == definition,
                "review text must reconstruct the normalized contract",
            )

    public_add = definitions["add"]["public"]
    div = program["functions"]["div"]["impl_hash"]
    require(runtime.evaluate(program, "div", [-7, 2]).value == -3, "signed division")
    require(runtime.evaluate(program, "div", [1, 0]).error == "DivisionByZero", "division error")

    def check(graph, pairs, expected, label):
        report = verify.verify(graph, pairs, boogie=boogie, z3=z3)
        require(report["status"] == expected, label, report)
        print(f"{label}: {expected}")
        return report

    check(program, definitions, "VERIFIED", "baseline")

    with TemporaryDirectory(prefix="llmlang-controls-") as temp:
        work = Path(temp)
        changed_contracts = work / "restricted.json"
        changed_source = work / "incorrect.llmlang"
        receipt = work / "review.json"
        packet = packet_id(review_packet(program, definitions, inputs))
        receipt.write_text(json.dumps({
            "schema": "llmlang-local-review/v1", "packet": packet,
            "decision": "approved", "reviewer": "synthetic test",
        }), encoding="utf-8")
        verify_review_receipt(receipt, packet)
        document = json.loads(contracts.read_text(encoding="utf-8"))
        document["add"]["provided"]["requires"] = ["left > 0"]
        changed_contracts.write_text(json.dumps(document), encoding="utf-8")
        restricted, pairs, changed_inputs = load_program(source, changed_contracts)
        try:
            verify_review_receipt(
                receipt, packet_id(review_packet(restricted, pairs, changed_inputs))
            )
        except ValueError:
            pass
        else:
            raise AssertionError("an approval of a different review packet must be rejected")
        require(pairs["add"]["public"] == public_add, "public Contract is unchanged")
        require(
            restricted["functions"]["add"]["impl_hash"] != program["functions"]["add"]["impl_hash"],
            "provided Contract change must change the implementation identity",
        )
        require(restricted["functions"]["div"]["impl_hash"] == div, "unrelated identity changed")
        report = check(restricted, pairs, "REJECTED", "stronger provider precondition")
        row = next(item for item in report["checks"] if item["function"] == "add")
        require(row["body"] == "verified" and row["refinement"] == "error",
                "refinement must fail independently", row)

        changed_source.write_text(
            source.read_text(encoding="utf-8").replace("return left + right", "return left"),
            encoding="utf-8",
        )
        incorrect, pairs, _ = load_program(changed_source, contracts)
        report = check(incorrect, pairs, "REJECTED", "body violates its provided Contract")
        row = next(item for item in report["checks"] if item["function"] == "add")
        require(row["body"] == "error" and row["refinement"] == "verified",
                "body verification must fail independently", row)
        require(runtime.evaluate(incorrect, "add", [2, 3]).value == 2,
                "reference execution must reproduce the incorrect body on a known witness")

    call_source = """def callee(x: int) -> int:
    return x

def caller(x: int) -> int:
    return callee(x)
"""
    definition = contract.parse_contract({
        "parameters": {"x": "I64"}, "returns": "I64",
        "requires": [], "ensures": ["result == x"], "errors": {},
    })
    pairs = {name: {"public": definition, "provided": definition}
             for name in ("caller", "callee")}
    graph = frontend.parse(call_source, provided_contract_hashes={
        name: contract.contract_hash(definition) for name in pairs
    })
    check(graph, pairs, "VERIFIED", "modular call with closed provider proof")
    require(runtime.evaluate(graph, "caller", [17]).value == 17, "exact resolved call")
    modified = deepcopy(graph)
    modified["functions"]["callee"]["impl_hash"] = "stale"
    try:
        runtime.evaluate(modified, "caller", [17])
    except ValueError as exc:
        require("stale" in str(exc), "stale call diagnostic", str(exc))
    else:
        raise AssertionError("stale call must be rejected")
    require(runtime.evaluate(graph, "caller", [17]).value == 17, "original snapshot changed")
    print("checked CNL round trips and immutable call pins")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boogie", default="boogie")
    parser.add_argument("--z3", default="z3")
    args = parser.parse_args()
    run(args.boogie, args.z3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
