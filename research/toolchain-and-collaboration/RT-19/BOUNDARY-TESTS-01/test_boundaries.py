"""Exercise the RT-19 prototype with an explicit policy adapter and I/O fault injection."""

from dataclasses import replace
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, defaultTestLoader, mock, TestResult


HERE = Path(__file__).resolve().parent
ROUNDTRIP = HERE.parent / "TOOLCHAIN-ROUNDTRIP-01" / "run.py"
POLICY = HERE.parents[2] / "security" / "PROTOTYPES" / "RT-16-AUTHORIZATION-01" / "policy.py"


def load(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = load("toolchain_boundary_roundtrip", ROUNDTRIP)
P = load("toolchain_boundary_policy", POLICY)


class Boundaries(TestCase):
    def setUp(self):
        scratch = TemporaryDirectory(prefix="rt19-integrated-controls-")
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name)
        self.server = R.InMemoryToolchain()
        uploaded = self.path / "baseline.json"
        self.expected_base = R.write_input(uploaded, sorted(R.BASE), compact=False)
        base = self.server.import_snapshot(uploaded)
        self.assertEqual(base, self.expected_base)
        self.workspace = self.server.open_workspace(base)

    def prepare(self, value):
        return R.apply(self.server, self.workspace,
                       R.make_changes(self.server, self.workspace, value, value))

    def test_source_snapshot_and_typed_changes_match(self):
        for value in (-15, 0, 42):
            with self.subTest(value=value):
                self.workspace = self.server.open_workspace(self.expected_base)
                typed = self.prepare(value)
                source = {
                    "contract:offset": ("contract", {"increment": value}),
                    "implementation:offset": ("implementation", {"increment": value}),
                    "export:offset": ("export", {"name": "смещение"}),
                }
                document = R.document(source, reversed(tuple(source)))
                file = self.path / f"import-{value}.json"
                file.write_text(json.dumps(document, indent=2, ensure_ascii=False))
                independent = R.InMemoryToolchain().import_snapshot(file)
                self.assertEqual(typed.working_snapshot, independent)
                self.assertIsNotNone(R.validate(self.server, typed))

    def test_exact_approval_precedes_acceptance(self):
        typed = self.prepare(2)
        proof = R.validate(self.server, typed)
        agent = P.Principal("fixture-agent", P.PrincipalKind.AGENT)
        reviewer = P.Principal("fixture-reviewer", P.PrincipalKind.HUMAN)
        request = P.Request(agent, P.Action.ACCEPT, "fixture-repo", self.expected_base,
                            typed.working_snapshot)
        grant = P.Capability(agent.subject, request.repository, frozenset((request.action,)), self.expected_base)
        approval = P.Approval(reviewer, request.binding, "fixture-nonce", 10)

        for unavailable in (None, replace(approval, approver=agent),
                            replace(approval, binding=replace(request, target="other").binding)):
            self.assertFalse(P.authorize(request, grant, unavailable, 1).allowed)
            current = self.server.get_workspace(typed.workspace_id)
            self.assertEqual(current.working_snapshot, typed.working_snapshot)
            self.assertNotEqual(current.state, "accepted")
        self.assertTrue(P.authorize(request, grant, approval, 1).allowed)
        self.assertEqual(R.accept(self.server, proof), typed.working_snapshot)

    def test_export_replace_failure_keeps_destination_and_cleanup(self):
        typed = self.prepare(2)
        accepted = R.accept(self.server, R.validate(self.server, typed))
        destination = self.path / "artifact.json"
        destination.write_bytes(b"prior visible destination")
        witness = R.digest(destination.read_bytes())
        with mock.patch("toolchain.os.replace", side_effect=OSError("fixture replace failure")):
            with self.assertRaisesRegex(OSError, "fixture replace failure"):
                self.server.export_snapshot(accepted, destination, expected_file_hash=witness)
        self.assertEqual(destination.read_bytes(), b"prior visible destination")
        self.assertFalse(list(self.path.glob(".llmlang-export-*")))
        self.server.export_snapshot(accepted, destination, expected_file_hash=witness)
        self.assertEqual(destination.read_bytes(), R.expected_export(accepted, 2))

    def test_stale_validation_cannot_accept_later_workspace(self):
        previous = self.prepare(1)
        receipt = R.validate(self.server, previous)
        R.apply(self.server, previous, [R.Change("add", "note:different", None, "note", {"text": "another"})])
        with self.assertRaises(R.StaleRevision):
            R.accept(self.server, receipt)
        self.assertNotEqual(self.server.get_workspace(previous.workspace_id).state, "accepted")


if __name__ == "__main__":
    suite = defaultTestLoader.loadTestsFromTestCase(Boundaries)
    result = TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        raise AssertionError((result.errors, result.failures))
    print(json.dumps({"tests": result.testsRun, "source_edit_cases": 3, "fault": "replace",
                      "sources": {p.name: sha256(p.read_bytes()).hexdigest()
                                  for p in (Path(__file__), ROUNDTRIP, POLICY, R.TOOLCHAIN / "toolchain.py")}},
                     sort_keys=True, indent=2))
