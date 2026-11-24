from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from composition import Backend, Claim, Plan, decode_receipt, digest
from transition_experiment import read_pinned


def claim(name, *, scope="unbounded", premises=()):
    return Claim(name, "revision-1", "equality", digest(name), digest("domain"),
                 "all-boundaries", scope, premises)


def analysis(plan, *receipts):
    return plan.evaluate(receipts, {receipt.key for receipt in receipts})


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.kernel = Backend("kernel", "1", digest("translation"), digest("config"), ("unbounded",))
        self.solver = Backend("solver", "1", digest("translation"), digest("config"), ("finite",))
        self.artifact = digest("opaque artifact")

    def test_unresolved_correspondence_leaves_claim_conditional(self):
        correspondence = claim("correspondence")
        program = claim("program", premises=("correspondence",))
        plan = Plan([program, correspondence], [self.kernel], mandatory=("program",))
        asserted = plan.receipt("program", self.kernel, self.artifact, "support")
        results, _, overall = analysis(plan, asserted)
        self.assertEqual(results["program"]["status"], "conditional")
        self.assertEqual(results["program"]["blocked_premises"], ["correspondence"])
        checked_premise = plan.receipt("correspondence", self.kernel, self.artifact, "support")
        results, rejected, overall = analysis(plan, asserted, checked_premise)
        self.assertFalse(rejected)
        self.assertEqual(overall, "proven")

    def test_bounded_prerequisite_cannot_discharge_unbounded_claim(self):
        finite = claim("premise", scope="finite")
        program = claim("program", premises=("premise",))
        plan = Plan([finite, program], [self.kernel, self.solver], mandatory=("program",))
        parent = plan.receipt("program", self.kernel, self.artifact, "support")
        child = plan.receipt("premise", self.solver, self.artifact, "support")
        results, rejected, overall = analysis(plan, parent, child)
        self.assertFalse(rejected)
        self.assertEqual(results["premise"]["status"], "bounded-agreement")
        self.assertEqual(overall, "conditional")
        wrong_scope = plan.receipt("program", self.solver, self.artifact, "support")
        _, rejected, _ = analysis(plan, wrong_scope)
        self.assertEqual(rejected[wrong_scope.key], "ineligible-backend")

    def test_refutation_under_unresolved_premise_is_conditional(self):
        premise = claim("premise", scope="finite")
        program = claim("program", scope="finite", premises=("premise",))
        plan = Plan([premise, program], [self.solver])
        objection = plan.receipt("program", self.solver, self.artifact, "counterexample")
        results, _, overall = analysis(plan, objection)
        self.assertEqual(results["program"]["status"], "conditional")
        self.assertEqual(results["program"]["observed_verdicts"], ["counterexample"])

    def test_transitive_change_invalidates_cached_receipt(self):
        leaf = claim("leaf")
        mid = claim("mid", premises=("leaf",))
        root = claim("root", premises=("mid",))
        initial = Plan([leaf, mid, root], [self.kernel])
        cached = initial.receipt("root", self.kernel, self.artifact, "support")
        updated = Plan([replace(leaf, revision="revision-2"), mid, root], [self.kernel])
        results, rejected, overall = analysis(updated, cached)
        self.assertEqual(rejected[cached.key], "stale-premises")
        self.assertEqual(results["root"]["status"], "insufficient")
        self.assertEqual(cached.claim, updated.receipt("root", self.kernel, self.artifact, "support").claim)

    def test_scope_configuration_and_translation_changes_reject_reuse(self):
        program = claim("program", scope="finite")
        initial = Plan([program], [self.solver])
        cached = initial.receipt("program", self.solver, self.artifact, "support")
        variants = [
            (replace(program, revision="revision-2"), self.solver, "different-claim"),
            (replace(program, domain=digest("other bound")), self.solver, "different-claim"),
            (replace(program, projection="final-only"), self.solver, "different-claim"),
            (program, replace(self.solver, configuration=digest("new config")), "ineligible-backend"),
            (program, replace(self.solver, translator=digest("new translator")), "ineligible-backend"),
            (program, replace(self.solver, tool="2"), "ineligible-backend"),
        ]
        for changed, backend, reason in variants:
            with self.subTest(reason=reason, changed=changed, backend=backend):
                _, rejected, _ = analysis(Plan([changed], [backend]), cached)
                self.assertEqual(rejected[cached.key], reason)

    def test_conflict_wins_over_other_results(self):
        valid = claim("checked", scope="finite")
        missing = claim("missing", scope="finite")
        plan = Plan([valid, missing], [self.solver])
        support = plan.receipt("checked", self.solver, self.artifact, "support")
        against = plan.receipt("checked", self.solver, digest("other artifact"), "counterexample")
        results, _, overall = analysis(plan, support, against)
        self.assertEqual(overall, "conflict")
        results, _, overall = analysis(plan, support)
        self.assertEqual(overall, "insufficient")
        self.assertEqual(results["checked"]["status"], "bounded-agreement")
        with self.assertRaises(ValueError):
            Plan([valid], [self.solver], mandatory=("missing",))

    def test_unknown_timeout_and_unsupported_remain_observable(self):
        plan = Plan([claim("checked", scope="finite")], [self.solver])
        receipts = [plan.receipt("checked", self.solver, self.artifact, status)
                    for status in ("unknown", "timeout", "unsupported")]
        results, _, overall = analysis(plan, *receipts)
        self.assertEqual(results["checked"], {
            "status": "insufficient", "blocked_premises": [],
            "observed_verdicts": ["timeout", "unknown", "unsupported"],
        })

    def test_receipt_shape_does_not_authorize_a_verdict(self):
        plan = Plan([claim("checked", scope="finite")], [self.solver])
        claimed = plan.receipt("checked", self.solver, self.artifact, "support")
        self.assertEqual(decode_receipt(json.dumps(asdict(claimed))), claimed)
        results, rejected, _ = plan.evaluate([claimed], set())
        self.assertEqual(rejected[claimed.key], "unverified")
        self.assertEqual(results["checked"]["status"], "insufficient")
        altered = replace(claimed, verdict="counterexample")
        _, rejected, _ = plan.evaluate([altered], {claimed.key})
        self.assertEqual(rejected[altered.key], "unverified")

    def test_decoder_rejects_extra_fields_wrong_types_and_duplicates(self):
        plan = Plan([claim("checked", scope="finite")], [self.solver])
        receipt = asdict(plan.receipt("checked", self.solver, self.artifact, "support"))
        for input_ in [json.dumps({**receipt, "proven": True}),
                       json.dumps({**receipt, "backend": []}),
                       json.dumps({**receipt, "artifact": "unsigned"}),
                       json.dumps(receipt)[:-1] + ', "verdict": "support"}']:
            with self.subTest(input_=input_), self.assertRaises(ValueError):
                decode_receipt(input_)

    def test_cycle_missing_premise_and_duplicate_claim_are_rejected(self):
        first = claim("first", premises=("second",))
        second = claim("second", premises=("first",))
        for invalid in [[first, second], [first], [first, first]]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                Plan(invalid, [self.kernel])

    def test_pinned_artifacts_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observations"
            path.write_bytes(b'"altered"')
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                read_pinned(path, self.artifact)


if __name__ == "__main__":
    unittest.main()
