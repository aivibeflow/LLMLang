from copy import deepcopy
from pathlib import Path
import runpy
import unittest

from . import contract_profiles as profile


SUBJECT = "sha256:" + "a" * 64
REFERENCE = "sha256:" + "b" * 64
REQUIRED = "sha256:" + "c" * 64
PUBLIC = "sha256:" + "d" * 64
PROVIDED = "sha256:" + "e" * 64
EXAMPLES = Path(__file__).parent / "trace_examples"


def event(name, tick, **fields):
    return {"name": name, "tick": tick, "fields": fields}


def example():
    pin = {"implementation": SUBJECT, "required": REQUIRED, "public": PUBLIC, "provided": PROVIDED}
    clauses = [
        {"kind": "invariant", "field": "balance"},
        {"kind": "frame", "fields": ["balance"]},
        {"kind": "effects", "events": ["release", "acquire", "advance", "call"]},
        {"kind": "ownership", "acquire": "acquire", "release": "release", "field": "resource"},
        {"kind": "atomicity", "outcomes": ["partial", "error"], "fields": ["balance"],
         "events": ["release", "acquire"]},
        {"kind": "decreases", "event": "advance", "field": "rank"},
        {"kind": "protocol", "initial": "ready", "terminal": ["ended"], "transitions": [
            ["ready", "acquire", "working"], ["working", "advance", "working"],
            ["working", "call", "working"], ["working", "release", "ended"],
        ]},
        {"kind": "deadline", "trigger": "acquire", "response": "release", "ticks": 3},
        {"kind": "authority", "event": "acquire", "field": "principal", "allowed": ["operator"]},
        {"kind": "budget", "event": "advance", "maximum": 2},
        {"kind": "comparison", "reference_subject": REFERENCE, "inputs": ["balance"], "outputs": ["balance"]},
        {"kind": "binding", "event": "call", **pin},
    ]
    contract = {
        "schema": profile.CONTRACT, "state": {"balance": "I64", "guard": "Bool"},
        "events": {
            "acquire": {"resource": "Symbol", "principal": "Symbol"},
            "advance": {"rank": "I64"}, "call": {field: "Hash" for field in pin},
            "release": {"resource": "Symbol"}, "notice": {},
        },
        "clauses": [dict(clause, id=clause["kind"]) for clause in clauses],
    }
    trace = {
        "schema": profile.TRACE, "subject": SUBJECT, "complete": True, "outcome": "success",
        "pre": {"balance": 100, "guard": True}, "post": {"balance": 90, "guard": True},
        "events": [
            event("acquire", 0, resource="buffer", principal="operator"),
            event("advance", 1, rank=2), event("advance", 2, rank=1),
            event("call", 3, **pin), event("release", 3, resource="buffer"),
        ],
    }
    reference = deepcopy(trace)
    reference["subject"] = REFERENCE
    return contract, trace, reference


class ContractProfilesTest(unittest.TestCase):
    def test_round_trip_and_deterministic_evidence(self):
        contract, trace, reference = example()
        rendering = profile.checked_render(contract)
        reconstructed = profile.parse_controlled(rendering)
        self.assertEqual(reconstructed, profile.normalize_contract(contract))
        report = profile.check_trace(contract, trace, reference=reference)
        self.assertEqual(report["status"], "CHECKED")
        self.assertEqual({row["status"] for row in report["clauses"]}, {"CHECKED"})
        contract["clauses"].reverse()
        self.assertEqual(profile.check_trace(contract, trace, reference=reference), report)
        self.assertEqual(profile.checked_render(contract), rendering)

        changed = rendering.replace("within 3 ticks", "within 2 ticks")
        changed_contract = profile.parse_controlled(changed)
        changed_report = profile.check_trace(changed_contract, trace, reference=reference)
        self.assertNotEqual(changed_report["contract_hash"], report["contract_hash"])
        self.assertNotEqual(changed_report["evidence_hash"], report["evidence_hash"])
        self.assertEqual(changed_report["status"], "VIOLATED")

    def test_negative_observations(self):
        contract, trace, reference = example()

        def violation(kind, update):
            with self.subTest(kind=kind):
                witness = deepcopy(trace)
                update(witness)
                report = profile.check_trace(contract, witness, reference=reference)
                self.assertEqual(report["status"], "VIOLATED")
                row = next(row for row in report["clauses"] if row["kind"] == kind)
                self.assertEqual(row["status"], "VIOLATED", report)

        violation("invariant", lambda t: t["post"].update(balance=-1))
        violation("frame", lambda t: t["post"].update(guard=False))
        violation("effects", lambda t: t["events"].append(event("notice", 3)))
        violation("ownership", lambda t: t["events"].pop())
        violation("atomicity", lambda t: t.update(outcome="error"))
        violation("decreases", lambda t: t["events"][2]["fields"].update(rank=2))
        violation("protocol", lambda t: t["events"].insert(0, event("advance", 0, rank=3)))
        violation("deadline", lambda t: t["events"][-1].update(tick=4))
        violation("authority", lambda t: t["events"][0]["fields"].update(principal="guest"))
        violation("budget", lambda t: t["events"].insert(3, event("advance", 2, rank=0)))
        violation("comparison", lambda t: t["post"].update(balance=91))
        violation("binding", lambda t: t["events"][3]["fields"].update(provided=PUBLIC))

    def test_open_premises_and_missing_or_incomplete_evidence(self):
        contract, trace, reference = example()
        self.assertEqual(profile.check_trace(contract, trace)["status"], "UNKNOWN")
        changed_reference = deepcopy(reference)
        changed_reference["pre"]["balance"] = 200
        self.assertEqual(profile.check_trace(contract, trace, reference=changed_reference)["status"], "UNKNOWN")
        trace["complete"] = False
        trace["outcome"] = None
        del trace["events"][-1]
        self.assertEqual(profile.check_trace(contract, trace, reference=reference)["status"], "UNKNOWN")
        trace["events"].append(event("notice", 4))
        rows = {row["id"]: row["status"] for row in profile.check_trace(contract, trace)["clauses"]}
        self.assertEqual(rows["deadline"], "VIOLATED")

        contract, trace, reference = example()
        contract["clauses"].append({"id": "foreign", "kind": "assumption", "premise": REQUIRED})
        report = profile.check_trace(profile.parse_controlled(profile.checked_render(contract)), trace, reference=reference)
        self.assertEqual(report["status"], "CONDITIONAL")
        row = next(row for row in report["clauses"] if row["id"] == "foreign")
        self.assertEqual(row["open_premise"], REQUIRED)

    def test_strict_rejection(self):
        contract, trace, _ = example()
        with self.assertRaisesRegex(profile.ProfileError, "unsupported Contract schema"):
            profile.normalize_contract(dict(contract, schema="llmlang-trace-contract/v2"))
        with self.assertRaisesRegex(profile.ProfileError, "unsupported trace clause"):
            profile.normalize_contract(dict(contract, clauses=[{"kind": "fairness"}]))
        with self.assertRaisesRegex(profile.ProfileError, "unexpected controlled"):
            profile.parse_controlled(profile.checked_render(contract) + "Trust me.\n")
        with self.assertRaisesRegex(profile.ProfileError, "invalid or duplicate controlled"):
            profile.parse_controlled(profile.checked_render(contract).replace(
                "rank as I64", "rank as I64, rank as Bool",
            ))
        with self.assertRaisesRegex(profile.ProfileError, "invalid controlled protocol transition"):
            profile.parse_controlled(profile.checked_render(contract).replace(
                "ready + acquire -> working", "ready -> acquire + working",
            ))
        with self.assertRaisesRegex(profile.ProfileError, "nondeterministic"):
            protocol = next(clause for clause in contract["clauses"] if clause["kind"] == "protocol")
            protocol["transitions"].append(["ready", "acquire", "ended"])
            profile.normalize_contract(contract)
        contract, trace, _ = example()
        trace["events"][1]["fields"]["rank"] = True
        with self.assertRaisesRegex(profile.ProfileError, "expected I64"):
            profile.check_trace(contract, trace)
        trace["events"][1]["fields"]["rank"] = 2
        trace["events"][3]["tick"] = 0
        with self.assertRaisesRegex(profile.ProfileError, "nondecreasing"):
            profile.check_trace(contract, trace)

    def test_cleanup_benchmark_slice(self):
        benchmark = EXAMPLES.parents[2] / "research/formal-verification/PROOF-OBLIGATION-BENCHMARK"
        cleanup = runpy.run_path(str(benchmark / "oracles.py"))["cleanup"]
        contract = {
            "schema": profile.CONTRACT, "state": {},
            "events": {"acquire": {"resource": "Symbol"}, "release": {"resource": "Symbol"}},
            "clauses": [{"id": "O1", "kind": "ownership", "acquire": "acquire",
                         "release": "release", "field": "resource"}],
        }
        for mutation in (False, True):
            for (count, failed), expected in cleanup(mutation):
                with self.subTest(mutation=mutation, count=count, failed=failed):
                    resources = [f"r{index}" for index in range(count)]
                    released = resources[:-1] if mutation and failed else resources
                    trace = {
                        "schema": profile.TRACE, "subject": SUBJECT, "pre": {}, "post": {},
                        "complete": True, "outcome": "error" if failed else "success",
                        "events": [event("acquire", index, resource=resource)
                                   for index, resource in enumerate(resources)]
                        + [event("release", count + index, resource=resource)
                           for index, resource in enumerate(reversed(released))],
                    }
                    self.assertEqual(profile.check_trace(contract, trace)["status"],
                                     "CHECKED" if expected else "VIOLATED")

    def test_corpus_failure_branch(self):
        contract = profile.read(EXAMPLES / "withdrawal.contract.json")
        observation = profile.read(EXAMPLES / "withdrawal-failure.trace.json")
        self.assertEqual(profile.check_trace(contract, observation)["status"], "CHECKED")
        observation["post"]["balance"] = 98  # CF-006 MUT-06
        self.assertEqual(profile.check_trace(contract, observation)["status"], "VIOLATED")


if __name__ == "__main__":
    unittest.main()
