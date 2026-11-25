"""Regression controls for the scalar Contract IR interchange."""

import copy
import json
from pathlib import Path
import unittest

from . import contract, contract_wire, frontend


class ContractWireTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).with_name("calculator.contracts.json")
        self.definitions = contract_wire.loads(fixture.read_text(encoding="utf-8"))
        self.document = contract_wire.to_wire(self.definitions)

    def test_canonical_wire_and_cnl_preserve_contract_hash(self):
        wire = contract_wire.dumps(self.definitions)
        typed, prefix = contract_wire.load_document(wire)
        self.assertEqual(prefix, "/contracts")
        self.assertEqual(typed, self.definitions)
        self.assertEqual(contract_wire.dumps(typed), wire)
        for name, pair in typed.items():
            for role, value in pair.items():
                rendered = contract.checked_render(value)
                reparsed = contract.parse_controlled(rendered)
                self.assertEqual(contract.contract_hash(reparsed),
                                 contract.contract_hash(self.definitions[name][role]))

    def test_migrated_fixture_preserves_legacy_implementation_pins(self):
        fixture = Path(__file__).with_name("calculator.contracts.legacy.json")
        legacy, prefix = contract_wire.load_document(fixture.read_text(encoding="utf-8"))
        self.assertEqual(prefix, "")
        self.assertEqual(legacy, self.definitions)
        source = fixture.with_name("calculator.llmlang").read_text(encoding="utf-8")

        def lower(pairs):
            return frontend.parse(source, provided_contract_hashes={
                name: contract.contract_hash(pair["provided"]) for name, pair in pairs.items()
            })

        self.assertEqual(lower(legacy), lower(self.definitions))

    def test_order_and_mathematical_integers_survive_exchange(self):
        definition = contract.parse_contract({
            "parameters": {"z": "I64", "a": "Bool"}, "returns": "Bool",
            "requires": ["a and (z < 18446744073709551616 and not False)"],
            "ensures": ["result == a"], "errors": {},
        })
        encoded = contract_wire.dumps({"pick": {"public": definition, "provided": definition}})
        decoded = contract_wire.loads(encoded)["pick"]["public"]
        self.assertIn('"value":"18446744073709551616"', encoded)
        self.assertEqual(decoded.parameters, (("z", "I64"), ("a", "Bool")))
        self.assertEqual(decoded, definition)
        self.assertTrue(contract.holds(decoded.requires, {"z": -(2**63), "a": True}))
        self.assertFalse(contract.holds(decoded.requires, {"z": 0, "a": False}))

    def test_schema_profile_and_duplicate_members_are_rejected(self):
        for member, invalid in (("schema", "llmlang-contract-ir/v2"), ("profile", "other-v1")):
            with self.subTest(member=member):
                with self.assertRaisesRegex(contract.ContractError, f"unsupported .*{member}"):
                    contract_wire.loads(json.dumps(self.document | {member: invalid}))
        text = contract_wire.dumps(self.definitions).replace(
            '"profile":"scalar-v1"', '"profile":"scalar-v1","profile":"scalar-v1"',
        )
        with self.assertRaisesRegex(contract.ContractError, "duplicate"):
            contract_wire.loads(text)

    def test_types_arity_members_and_scope_are_checked(self):
        cases = (
            ({"op": "ref", "type": "Int", "name": "result"}, "unbound"),
            ({"op": "ref", "type": "Bool", "name": "left"}, "mistyped"),
            ({"op": "literal", "type": "Bool", "value": 1}, "literal"),
            ({"op": "literal", "type": "Int", "value": "01"}, "literal"),
            ({"op": "literal", "type": "Int", "value": "1"}, "Bool clause"),
            ({"op": "literal", "type": "Bool", "value": True, "ignored": True}, "members"),
            ({"op": "not", "type": "Bool", "args": []}, "arity"),
            ({"op": "quotient", "type": "Bool", "args": []}, "must return Int"),
            ({"op": "xor", "type": "Bool", "args": []}, "unsupported operator"),
            ({"op": "and", "type": "Bool", "args": [
                {"op": "literal", "type": "Bool", "value": True},
                {"op": "literal", "type": "Int", "value": "1"},
            ]}, "requires Bool"),
        )
        for invalid, diagnostic in cases:
            with self.subTest(node=invalid):
                doc = copy.deepcopy(self.document)
                doc["contracts"]["add"]["public"]["requires"] = [invalid]
                with self.assertRaisesRegex(contract.ContractError, diagnostic):
                    contract_wire.from_wire(doc)

    def test_legacy_functions_may_be_named_schema(self):
        fixture = Path(__file__).with_name("calculator.contracts.legacy.json")
        document = json.loads(fixture.read_text(encoding="utf-8"))
        format_names = ("schema", "profile", "contracts")
        pairs, prefix = contract_wire.load_document(json.dumps(
            {name: document["add"] for name in format_names}
        ))
        self.assertEqual(prefix, "")
        self.assertEqual(pairs["schema"], self.definitions["add"])


if __name__ == "__main__":
    unittest.main()
