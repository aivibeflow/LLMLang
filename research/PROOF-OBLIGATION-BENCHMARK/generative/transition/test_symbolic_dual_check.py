import json
import unittest

from symbolic_dual_check import confirm_replay, parse_model


class SymbolicWitnessTests(unittest.TestCase):
    def test_signed_integer_model(self):
        self.assertEqual(parse_model(b"sat\n((v0 (- 3)) (v1 0))\n"), [-3, 0])
        self.assertEqual(parse_model(b"sat\n( (v0 7) (v1 (- 2)) )\n"), [7, -2])

    def test_rejects_unknown_invalid_or_extra_model_data(self):
        for raw in (b"unknown\n", b"sat\n((v1 0) (v0 1))\n",
                    b"sat\n((v0 01) (v1 2))\n", b"sat\n((v0 1) (v1 2) (v2 0))\n",
                    b"sat\n((v0 1.0) (v1 2))\n"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_model(raw)

    def test_exact_replay_and_numeric_types(self):
        checked = {"input": [-3, 1], "observed": [[-3, 3], [-3, 0]],
                   "specified": [[-3, 0], [-3, 0]], "mismatch": True}
        self.assertEqual(confirm_replay(json.dumps(checked), [-3, 1]), checked)
        for invalid in ({**checked, "mismatch": False}, {**checked, "input": [-3, True]},
                        {**checked, "observed": [[-3, 0], [-3, 0]]}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                confirm_replay(json.dumps(invalid), [-3, 1])


if __name__ == "__main__":
    unittest.main()
