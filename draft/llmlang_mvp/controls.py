"""Exercise review fidelity, exact pins, and independent rejection gates."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from .__main__ import FIXTURES, load_program
from . import contract, frontend, review, runtime, verify


def require(condition, message, detail=None):
    if not condition:
        raise AssertionError(f"{message}: {detail!r}")


def rejected(label, diagnostic, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except ValueError as exc:
        require(diagnostic in str(exc), label, str(exc))
    else:
        raise AssertionError(label)


def review_controls(work, program, definitions, inputs, pointer_prefix):
    private, public = work / "reviewer.pem", work / "reviewer.pub.pem"
    other_private, other_public = work / "other.pem", work / "other.pub.pem"
    for secret, key in ((private, public), (other_private, other_public)):
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", secret], check=True)
        subprocess.run(["openssl", "pkey", "-in", secret, "-pubout", "-out", key], check=True)
    key_id = review.public_key_id(public)
    reviewer = "Synthetic review control"
    receipt = work / "review.json"
    packet = review.review_packet(
        program, definitions, inputs, contract_pointer_prefix=pointer_prefix, require_pass=True,
    )
    require("JSON Pointer /contracts/add/public/ensures/0" in packet, "clause source reference")
    require('"id":"T-0003-06"' in packet and '"observed":{"error":"DivisionByZero"}' in packet,
            "review packet contains a source-executed error scenario")
    identity = review.packet_id(packet)
    review.write_review_receipt(receipt, identity, reviewer, private)
    review.verify_review_receipt(receipt, identity, reviewer, public, key_id=key_id)
    rejected("a different trusted reviewer must be rejected", "trusted reviewer",
             review.verify_review_receipt, receipt, identity, "An untrusted name", public, key_id=key_id)
    rejected("a key different from the configured identity must be rejected", "configured identity",
             review.verify_review_receipt, receipt, identity, reviewer, other_public, key_id=key_id)

    changed_scenarios = work / "changed-scenarios.json"
    changed_scenarios.write_bytes(review.DEFAULT_SCENARIOS.read_bytes() + b"\n")
    changed_packet = review.review_packet(
        program, definitions, inputs, contract_pointer_prefix=pointer_prefix, scenarios_path=changed_scenarios,
    )
    changed_identity = review.packet_id(changed_packet)
    rejected("a stale scenario approval must be rejected", "exact packet",
             review.verify_review_receipt, receipt, changed_identity, reviewer, public, key_id=key_id)

    tampered = work / "tampered.json"
    document = json.loads(receipt.read_text(encoding="utf-8"))
    document["packet"] = changed_identity
    tampered.write_text(json.dumps(document), encoding="utf-8")
    rejected("editing the signed packet identity must be rejected", "signature verification failed",
             review.verify_review_receipt, tampered, changed_identity, reviewer, public, key_id=key_id)
    return receipt, reviewer, public, key_id


def run(boogie, z3):
    source = FIXTURES / "calculator.llmlang"
    contracts = FIXTURES / "calculator.contracts.json"
    program, definitions, inputs, pointer_prefix = load_program(source, contracts)
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

    with TemporaryDirectory(prefix="llmlang-controls-") as temp:
        work = Path(temp)
        changed_contracts = work / "restricted.json"
        changed_source = work / "incorrect.llmlang"
        receipt, reviewer, public, key_id = review_controls(work, program, definitions, inputs, pointer_prefix)
        check(program, definitions, "VERIFIED", "baseline")
        document = json.loads((FIXTURES / "calculator.contracts.legacy.json").read_text(encoding="utf-8"))
        document["add"]["provided"]["requires"] = ["left > 0"]
        changed_contracts.write_text(json.dumps(document), encoding="utf-8")
        restricted, pairs, changed_inputs, changed_prefix = load_program(source, changed_contracts)
        packet = review.review_packet(
            restricted, pairs, changed_inputs, contract_pointer_prefix=changed_prefix, previous_contracts_path=contracts,
        )
        require("JSON Pointer /add/provided/requires/0" in packet, "legacy clause source reference")
        require('"change":"added","clause":"requirement-1"' in packet, "semantic diff shows added requirement")
        rejected("an approval of a different contract must be rejected", "exact packet",
                 review.verify_review_receipt, receipt, review.packet_id(packet), reviewer, public, key_id=key_id)
        rejected("a review with an observed domain mismatch cannot be accepted", "T-0003-12",
                 review.review_packet, restricted, pairs, changed_inputs,
                 contract_pointer_prefix=changed_prefix, require_pass=True)
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
        incorrect, pairs, incorrect_inputs, incorrect_prefix = load_program(changed_source, contracts)
        rejected("a review with a source outcome mismatch cannot be accepted", "T-0003-01",
                 review.review_packet, incorrect, pairs, incorrect_inputs,
                 contract_pointer_prefix=incorrect_prefix, require_pass=True)
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
    hashes = {
        name: contract.contract_hash(definition) for name in pairs
    }
    graph = frontend.parse(call_source, provided_contract_hashes=hashes)
    check(graph, pairs, "VERIFIED", "modular call with closed provider proof")
    old_functions = graph["functions"]
    old_callee = old_functions["callee"]["impl_hash"]
    old_caller = old_functions["caller"]["impl_hash"]

    replacement = frontend.parse(
        call_source.replace("return x\n", "return x + 0\n"), provided_contract_hashes=hashes,
    )
    new_functions = replacement["functions"]
    new_callee = new_functions["callee"]["impl_hash"]
    require(old_callee != new_callee, "a replacement body must have its own implementation identity")
    require(old_caller != new_functions["caller"]["impl_hash"], "updating an exact pin must change the caller identity")
    require(old_functions["caller"]["body"][0][1][3] == old_callee, "old caller retains its original binding")
    require(new_functions["caller"]["body"][0][1][3] == new_callee, "new caller pins the conforming replacement")
    check(replacement, pairs, "VERIFIED", "conforming replacement with the same public Contract")

    mixed = deepcopy(graph)
    mixed["functions"]["callee"] = new_functions["callee"]
    rejected("old caller with replacement must fail execution", "stale", runtime.evaluate, mixed, "caller", [17])
    report = check(mixed, pairs, "UNSUPPORTED", "old caller cannot verify against the replacement")
    require("mismatched implementation pin" in report["diagnostic"], "exact pin proof diagnostic", report)
    for snapshot in (graph, replacement):
        require(runtime.evaluate(snapshot, "caller", [17]).value == 17, "still-pinned snapshot executes correctly")
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
