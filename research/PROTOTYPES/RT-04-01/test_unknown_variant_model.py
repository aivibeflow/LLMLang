import json
import unittest

from unknown_variant_model import (
    DecodeError,
    KnownState,
    OpaqueState,
    UnknownCasePolicy,
    decode_v1,
    encode_state,
)


class UnknownVariantTests(unittest.TestCase):
    def test_known_v1_cases_decode_and_reencode(self):
        for wire, expected in (
            (b'{"state":{"kind":"ready"}}', KnownState("ready", {})),
            (
                b'{"state":{"kind":"failed","code":17}}',
                KnownState("failed", {"code": 17}),
            ),
        ):
            decoded = decode_v1(wire, UnknownCasePolicy.REJECT)
            self.assertEqual(decoded, expected)
            self.assertEqual(json.loads(encode_state(decoded)), json.loads(wire))

    def test_reject_policy_returns_decode_error_for_new_case(self):
        wire = b'{"state":{"kind":"suspended","until":200,"meta":{"x":1}}}'
        self.assertIsInstance(decode_v1(wire, UnknownCasePolicy.REJECT), DecodeError)

    def test_fallback_policy_accepts_but_discards_unknown_case_data(self):
        wire = b'{"state":{"kind":"suspended","until":200}}'
        decoded = decode_v1(wire, UnknownCasePolicy.FALLBACK)
        self.assertEqual(decoded, KnownState("other", {}))
        self.assertEqual(
            json.loads(encode_state(decoded)), {"state": {"kind": "other"}}
        )

    def test_preserve_policy_relays_unknown_nested_data(self):
        wire = b'{"state":{"kind":"suspended","until":200,"meta":{"x":[1,2]}}}'
        decoded = decode_v1(wire, UnknownCasePolicy.PRESERVE)
        self.assertIsInstance(decoded, OpaqueState)
        self.assertEqual(json.loads(encode_state(decoded)), json.loads(wire))

    def test_preservation_is_semantic_not_byte_for_byte(self):
        wire = b'{ "state" : { "until" : 200, "kind" : "suspended" } }'
        decoded = decode_v1(wire, UnknownCasePolicy.PRESERVE)
        self.assertEqual(json.loads(encode_state(decoded)), json.loads(wire))
        self.assertNotEqual(encode_state(decoded), wire)

    def test_malformed_known_case_is_not_treated_as_unknown(self):
        wire = b'{"state":{"kind":"failed","code":"bad"}}'
        for policy in UnknownCasePolicy:
            self.assertIsInstance(decode_v1(wire, policy), DecodeError)

    def test_unknown_case_without_discriminator_is_malformed(self):
        for policy in UnknownCasePolicy:
            self.assertIsInstance(
                decode_v1(b'{"state":{"until":200}}', policy), DecodeError
            )


if __name__ == "__main__":
    unittest.main()
