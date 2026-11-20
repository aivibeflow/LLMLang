"""Check the Rust generator without requiring a Rust toolchain in Python CI."""

from unittest import TestCase

from rt04_rust_owned_probe import generate
from rt04_shared_owned_handlers import PRESERVE_SOURCE, RECOVER_SOURCE


class RustOwnedGeneratorTests(TestCase):
    def test_emission_uses_resolved_arguments_and_transfer_timing(self):
        source = RECOVER_SOURCE.replace("make(a, b", "make(b, a").replace(
            "destination_alias = d", "destination_alias = source_alias",
        )
        generated = generate(source, "after_cleanup")
        self.assertIn("const EARLY_TRANSFER: bool = false;", generated)
        self.assertIn("const FIRST: [usize; 2] = [1, 0];", generated)
        self.assertIn("const SECOND: [usize; 2] = [2, 2];", generated)
        self.assertEqual(generated, generate(source, "after_cleanup"))

    def test_only_checked_release_arms_consume_the_handle(self):
        preserve = generate(PRESERVE_SOURCE, "before_cleanup")
        release = generate(RECOVER_SOURCE, "before_cleanup")
        close = 'handle.close(trace, "caller_handle", _disposition)'
        self.assertNotIn(close, preserve)
        self.assertIn('trace.event("match", "error_with_handle", "release_first");', release)
        self.assertEqual(release.count(close), 1)

    def test_rejects_unsupported_callee_and_release_without_authority(self):
        invalid_callee = RECOVER_SOURCE.replace("move(handle)", "move(local)")
        with self.assertRaisesRegex(ValueError, "expected the COR-13 callee"):
            generate(invalid_callee, "before_cleanup")
        invalid_arm = RECOVER_SOURCE.replace(
            'case "error_reconcile":\n        preserve()', 'case "error_reconcile":\n        release_first()',
        )
        with self.assertRaisesRegex(ValueError, "requires a usable handle"):
            generate(invalid_arm, "before_cleanup")
