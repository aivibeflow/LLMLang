import itertools
import unittest

from schema_evolution_model import (
    Config,
    DecodeError,
    NullPolicy,
    UnknownFieldPolicy,
    decode_v1,
    decode_v2,
    encode_v1,
    encode_v2,
)


class SchemaEvolutionTests(unittest.TestCase):
    def test_four_version_pairs_under_strict_and_permissive_unknown_policy(self):
        config = Config(4, True)
        v1_wire = encode_v1(config)
        v2_wire = encode_v2(config)

        self.assertEqual(decode_v1(v1_wire), Config(4, False))
        self.assertEqual(decode_v2(v1_wire), Config(4, False))
        self.assertIsInstance(decode_v1(v2_wire), DecodeError)
        self.assertEqual(
            decode_v1(v2_wire, UnknownFieldPolicy.IGNORE), Config(4, False)
        )
        self.assertEqual(decode_v2(v2_wire), config)

    def test_finite_producer_consumer_policy_product(self):
        # Exhaust producer versions and consumer unknown-field/default policies.
        observations = []
        for producer_version, consumer_version, policy, default in itertools.product(
            (1, 2), (1, 2), tuple(UnknownFieldPolicy), (False, True)
        ):
            wire = (
                encode_v1(Config(2, True))
                if producer_version == 1
                else encode_v2(Config(2, True))
            )
            if consumer_version == 1:
                decoded = decode_v1(wire, policy)
            else:
                decoded = decode_v2(
                    wire, enabled_default=default, unknown_fields=policy
                )
            observations.append((producer_version, consumer_version, policy, default, decoded))
        self.assertEqual(len(observations), 16)
        self.assertTrue(all(not isinstance(row[-1], DecodeError) for row in observations if row[0] == 1))
        self.assertEqual(
            sum(isinstance(row[-1], DecodeError) for row in observations if row[0] == 2 and row[1] == 1),
            2,
        )

    def test_adding_defaulted_field_changes_old_wire_semantics_when_default_changes(self):
        old_wire = encode_v1(Config(9, False))
        self.assertEqual(decode_v2(old_wire, enabled_default=False), Config(9, False))
        self.assertEqual(decode_v2(old_wire, enabled_default=True), Config(9, True))

    def test_explicit_false_is_not_affected_by_default_change(self):
        explicit = encode_v2(Config(9, False))
        self.assertEqual(decode_v2(explicit, enabled_default=False), Config(9, False))
        self.assertEqual(decode_v2(explicit, enabled_default=True), Config(9, False))

    def test_null_policy_is_independent_of_absent_default(self):
        null_wire = b'{"count":9,"enabled":null}'
        self.assertIsInstance(decode_v2(null_wire, enabled_default=True), DecodeError)
        self.assertEqual(
            decode_v2(
                null_wire,
                enabled_default=True,
                null_policy=NullPolicy.TREAT_AS_ABSENT,
            ),
            Config(9, True),
        )

    def test_unknown_field_is_not_the_same_as_absent_known_field(self):
        payload = b'{"count":9,"future":1}'
        self.assertIsInstance(decode_v2(payload), DecodeError)
        self.assertEqual(
            decode_v2(payload, unknown_fields=UnknownFieldPolicy.IGNORE),
            Config(9, False),
        )


if __name__ == "__main__":
    unittest.main()
