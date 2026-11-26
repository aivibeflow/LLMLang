"""Exercise model extraction and independent replay with the pinned verifier."""

import unittest

from . import contract, frontend, verify


def definition(parameters, *, returns="I64", requires=(), ensures=(), errors=None):
    return contract.parse_contract({
        "parameters": parameters,
        "returns": returns,
        "requires": list(requires),
        "ensures": list(ensures),
        "errors": errors or {},
    })


def check(source, contracts):
    graph = frontend.parse(source, provided_contract_hashes={
        name: contract.contract_hash(pair["provided"])
        for name, pair in contracts.items()
    })
    report = verify.verify(graph, contracts)
    return report, {row["function"]: row for row in report["checks"]}


class CounterexampleTests(unittest.TestCase):
    def test_forged_literal_cannot_enter_generated_obligations(self):
        exact = definition({}, ensures=("result == 0",))
        graph = frontend.parse(
            "def implementation() -> int:\n    return 0\n",
            provided_contract_hashes={"implementation": contract.contract_hash(exact)},
        )
        implementation = graph["functions"]["implementation"]
        implementation["body"][0][1] = ["i64", "0"]
        payload = {key: value for key, value in implementation.items() if key != "impl_hash"}
        implementation["impl_hash"] = frontend._digest(payload)
        report = verify.verify(graph, {"implementation": {"public": exact, "provided": exact}})
        self.assertEqual(report["status"], "UNSUPPORTED", report)
        self.assertIn("invalid signed 64-bit SPG literal", report["diagnostic"])

    def test_contradictory_preconditions_block_vacuous_verification(self):
        empty = definition(
            {"x": "I64", "flag": "Bool"},
            requires=("x >= 0 and flag", "x < 0 or not flag"),
            ensures=("result != x",),
        )
        report, rows = check(
            "def implementation(x: int, flag: bool) -> int:\n    return x\n",
            {"implementation": {"public": empty, "provided": empty}},
        )
        self.assertEqual(report["status"], "REJECTED", report)
        row = rows["implementation"]
        self.assertEqual(row["body"], "verified")
        self.assertEqual(row["refinement"], "verified")
        self.assertEqual(row["domains"]["public"]["status"], "empty")
        self.assertEqual(row["domains"]["provided"]["status"], "empty")

    def test_a_constrained_nonempty_domain_has_a_checked_witness(self):
        singleton = definition(
            {"x": "I64", "flag": "Bool"},
            requires=("x == -9223372036854775808 and flag",), ensures=("result == x",),
        )
        report, rows = check(
            "def implementation(x: int, flag: bool) -> int:\n    return x\n",
            {"implementation": {"public": singleton, "provided": singleton}},
        )
        self.assertEqual(report["status"], "VERIFIED", report)
        self.assertEqual(report["boogie_summary"]["expected_input_domain_probe_errors"], 2)
        for domain in rows["implementation"]["domains"].values():
            self.assertEqual(domain["status"], "inhabited")
            self.assertEqual(domain["arguments"], {"x": -(2**63), "flag": True})

    def test_body_error_is_replayed_at_the_solver_input(self):
        exact = definition({"x": "I64", "flag": "Bool"}, ensures=("result == x",))
        report, rows = check(
            """def changed(x: int, flag: bool) -> int:
    if x == -4214113:
        return builtin__fail("DivisionByZero")
    return x
""",
            {"changed": {"public": exact, "provided": exact}},
        )
        self.assertEqual(report["status"], "REJECTED", report)
        witness, = rows["changed"]["body_counterexamples"]
        self.assertEqual(witness["status"], "confirmed-source", witness)
        self.assertEqual(witness["arguments"], {"x": -4214113, "flag": False}, witness)
        self.assertEqual(witness["observed_outcome"], {"value": None, "error": "DivisionByZero"})

    def test_provider_precondition_requires_a_public_input(self):
        public = definition({"x": "I64"}, ensures=("result == x",))
        provided = definition({"x": "I64"}, requires=("x != -62",), ensures=("result == x",))
        report, rows = check(
            "def implementation(x: int) -> int:\n    return x\n",
            {"implementation": {"public": public, "provided": provided}},
        )
        self.assertEqual(report["status"], "REJECTED", report)
        witness, = rows["implementation"]["refinement_counterexamples"]
        self.assertEqual(witness, {
            "status": "confirmed-contract", "kind": "provider-precondition",
            "arguments": {"x": -62},
        })

    def test_weaker_guarantee_is_a_contract_failure_without_a_source_failure(self):
        public = definition({"flag": "Bool"}, returns="Bool", ensures=("result == flag",))
        provided = definition(
            {"flag": "Bool"}, returns="Bool", ensures=("result == flag",),
            errors={"InvalidInput": ["flag"]},
        )
        report, rows = check(
            "def implementation(flag: bool) -> bool:\n    return flag\n",
            {"implementation": {"public": public, "provided": provided}},
        )
        self.assertEqual(report["status"], "REJECTED", report)
        witness, = rows["implementation"]["refinement_counterexamples"]
        self.assertEqual(witness["status"], "confirmed-contract", witness)
        self.assertEqual(witness["kind"], "provider-guarantee")
        self.assertEqual(witness["arguments"], {"flag": True})
        self.assertEqual(witness["model_outcome"], {"value": None, "error": "InvalidInput"})
        self.assertEqual(witness["observed_outcome"], {"value": True, "error": None})

    def test_public_guarantee_can_also_be_refuted_by_source_execution(self):
        properties = {"flag": "Bool"}
        public = definition(properties, returns="Bool", ensures=("result == flag",))
        provided = definition(properties, returns="Bool", ensures=("not result",))
        report, rows = check(
            "def implementation(flag: bool) -> bool:\n    return False\n",
            {"implementation": {"public": public, "provided": provided}},
        )
        self.assertEqual(report["status"], "REJECTED", report)
        witness, = rows["implementation"]["refinement_counterexamples"]
        self.assertEqual(witness["status"], "confirmed-source", witness)
        self.assertEqual(witness["arguments"], {"flag": True})
        self.assertEqual(witness["model_outcome"], witness["observed_outcome"])

    def test_invalid_callee_precondition_is_replayed_with_concrete_arguments(self):
        caller = definition({"x": "I64"}, ensures=("result == x",))
        callee = definition({"y": "I64"}, requires=("y != 6200",), ensures=("result == y",))
        report, rows = check(
            """def caller(x: int) -> int:
    return callee(x)

def callee(y: int) -> int:
    return y
""",
            {"caller": {"public": caller, "provided": caller},
             "callee": {"public": callee, "provided": callee}},
        )
        self.assertEqual(report["status"], "REJECTED", report)
        witnesses = rows["caller"]["body_counterexamples"]
        confirmed = [witness for witness in witnesses if witness["status"] == "confirmed-source"]
        self.assertEqual(len(confirmed), 1, witnesses)
        self.assertEqual(confirmed[0]["arguments"], {"x": 6200})
        self.assertEqual(confirmed[0]["invalid_call"], {"callee": "callee", "arguments": {"y": 6200}})

    def test_abstract_modular_model_does_not_become_a_source_counterexample(self):
        exact = definition({"x": "I64"}, ensures=("result == x",))
        loose = definition({"x": "I64"})
        report, rows = check(
            """def caller(x: int) -> int:
    return callee(x)

def callee(x: int) -> int:
    return x
""",
            {"caller": {"public": exact, "provided": exact},
             "callee": {"public": loose, "provided": loose}},
        )
        self.assertEqual(report["status"], "UNKNOWN", report)
        witness, = rows["caller"]["body_counterexamples"]
        self.assertEqual(witness["status"], "unconfirmed", witness)
        self.assertEqual(witness["observed_outcome"]["value"], witness["arguments"]["x"])
        self.assertNotIn("*** MODEL", report["diagnostic"])


if __name__ == "__main__":
    unittest.main()
