import unittest

from rt04_owned_call import check_owned_call


HANDLE_RESULT = {"Result": [{"Owned": "Handle"}, "String"]}
HANDLE_WITH_CLEANUP_ERROR = {
    "ErrorWithValue": [{"Owned": "Handle"}, "String", "CleanupError"]
}


class OwnedCallBoundary(unittest.TestCase):
    def test_result_success_requires_consuming_owned_value(self):
        result = check_owned_call(HANDLE_RESULT, {
            "ok": {"actions": ["release"]},
            "error": {"actions": []},
        })
        self.assertEqual(result.status, "ACCEPTED")
        self.assertEqual(dict(result.terminal_owners), {"error": "none", "ok": "released"})

    def test_error_with_value_requires_cleanup_on_both_owned_paths(self):
        result = check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"actions": ["transfer"]},
            "error_with_value": {"actions": ["release"]},
        })
        self.assertEqual(result.status, "ACCEPTED")

    def test_propagation_must_preserve_owned_value_in_output_type(self):
        safe = check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"actions": ["release"]},
            "error_with_value": {
                "actions": ["propagate_owned"], "output_carries_owned": True,
            },
        })
        unsafe = check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
            "ok": {"actions": ["release"]},
            "error_with_value": {"actions": ["propagate_owned"]},
        })
        self.assertEqual(safe.status, "ACCEPTED")
        self.assertIn("error_with_value:PROPAGATION_DROPS_OWNERSHIP", unsafe.findings)

    def test_rejects_drop_duplicate_and_use_after_move(self):
        cases = [
            (["ignore"], "ok:LEAKED_OWNERSHIP"),
            (["duplicate", "release"], "ok:DUPLICATE_OWNER"),
            (["transfer", "use"], "ok:USE_AFTER_MOVE"),
            (["release", "transfer"], "ok:MULTIPLE_CONSUMPTIONS"),
        ]
        for actions, finding in cases:
            with self.subTest(actions=actions):
                result = check_owned_call(HANDLE_RESULT, {
                    "ok": {"actions": actions}, "error": {"actions": []},
                })
                self.assertEqual(result.status, "REJECTED")
                self.assertIn(finding, result.findings)

    def test_unknown_type_and_missing_outcome_fail_closed(self):
        unknown = check_owned_call({"Result": ["Int", "String"]}, {
            "ok": {"actions": []}, "error": {"actions": []},
        })
        incomplete = check_owned_call(HANDLE_RESULT, {
            "ok": {"actions": ["release"]},
        })
        self.assertEqual(unknown.status, "UNKNOWN")
        self.assertEqual(incomplete.status, "UNKNOWN")

    def test_invalid_envelope_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            check_owned_call(HANDLE_WITH_CLEANUP_ERROR, {
                "ok": {"actions": ["release"]},
                "error_with_value": {
                    "actions": ["propagate_owned"], "output_carries_owned": 1,
                },
            })


if __name__ == "__main__":
    unittest.main()
