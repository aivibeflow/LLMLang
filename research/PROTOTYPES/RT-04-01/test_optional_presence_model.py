import unittest

from optional_presence_model import (
    DecodeFailure,
    FieldState,
    Presence,
    UninitializedRead,
    decode_integer_field,
    encode_json_field,
    encode_nested_optional,
    encode_optional,
    encode_presence_nullable,
    encode_result_presence,
    read_uninitialized,
)


class OptionalPresenceModelTests(unittest.TestCase):
    def test_decode_distinguishes_absent_null_and_value(self):
        self.assertEqual(decode_integer_field(b"{}"), FieldState(Presence.ABSENT))
        self.assertEqual(
            decode_integer_field(b'{"value":null}'), FieldState(Presence.NULL)
        )
        self.assertEqual(
            decode_integer_field(b'{"value":7}'), FieldState(Presence.VALUE, 7)
        )

    def test_one_level_optional_collapses_absent_and_null(self):
        absent = FieldState(Presence.ABSENT)
        null = FieldState(Presence.NULL)
        self.assertEqual(encode_optional(absent), encode_optional(null))

    def test_nested_optional_preserves_three_states(self):
        states = [
            FieldState(Presence.ABSENT),
            FieldState(Presence.NULL),
            FieldState(Presence.VALUE, 7),
        ]
        self.assertEqual(len({encode_nested_optional(item) for item in states}), 3)

    def test_presence_bit_and_nullable_payload_preserve_three_states(self):
        states = [
            FieldState(Presence.ABSENT),
            FieldState(Presence.NULL),
            FieldState(Presence.VALUE, 7),
        ]
        self.assertEqual(len({encode_presence_nullable(item) for item in states}), 3)

    def test_decode_failure_is_result_error_not_absence(self):
        failure = decode_integer_field(b'{"value":"seven"}')
        self.assertIsInstance(failure, DecodeFailure)
        self.assertEqual(encode_result_presence(failure)[0], "error")
        self.assertEqual(
            encode_result_presence(FieldState(Presence.ABSENT))[0], "ok"
        )

    def test_uninitialized_read_is_a_distinct_failure(self):
        with self.assertRaises(UninitializedRead):
            read_uninitialized()

    def test_json_round_trip_preserves_each_presence_state(self):
        for state in (
            FieldState(Presence.ABSENT),
            FieldState(Presence.NULL),
            FieldState(Presence.VALUE, 7),
        ):
            encoded = encode_json_field(state)
            self.assertEqual(decode_integer_field(encoded), state)

    def test_boolean_is_not_accepted_as_integer_payload(self):
        self.assertIsInstance(decode_integer_field(b'{"value":true}'), DecodeFailure)


if __name__ == "__main__":
    unittest.main()
