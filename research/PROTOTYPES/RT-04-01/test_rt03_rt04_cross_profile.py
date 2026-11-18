import unittest

from rt04_model import check_program


def observe(profile, trace, declared_effects=()):
    """Check only the RT-03 observation envelope; this is not an evaluator."""
    if profile not in {"A", "D"}:
        raise ValueError("the shared corpus currently covers RT-03 profiles A and D")
    events = tuple(trace["events"])
    result = trace["result"]
    if profile == "A":
        return "ACCEPTED" if not events else "REJECTED"
    undeclared = {event["effect"] for event in events} - set(declared_effects)
    return "REJECTED" if undeclared else "ACCEPTED"


class RT03RT04CrossProfileTests(unittest.TestCase):
    def test_pure_return_is_admissible_in_both_rt03_profiles_and_rt04_vectors(self):
        trace = {"events": [], "result": {"ok": 7}}
        self.assertEqual(observe("A", trace), "ACCEPTED")
        self.assertEqual(observe("D", trace), "ACCEPTED")
        program = {"functions": {"entry": {"result": "Int"}}}
        self.assertEqual(check_program(program, "A").status, "ACCEPTED")
        self.assertEqual(check_program(program, "B").status, "ACCEPTED")

    def test_io_trace_is_outside_rt03_a_but_explicitly_admissible_in_d(self):
        trace = {
            "events": [{"effect": "fs.read", "resource": "/config"}],
            "result": {"ok": "contents"},
        }
        self.assertEqual(observe("A", trace, {"fs.read"}), "REJECTED")
        self.assertEqual(observe("D", trace, {"fs.read"}), "ACCEPTED")

        # RT-04 checker A accepts this closed effect under ambient authority.
        # This is a cross-profile mismatch, not a contradiction in either model.
        ambient = {
            "ambient_capabilities": ["fs.read"],
            "functions": {"entry": {"effects": ["fs.read"], "requires": ["fs.read"]}},
        }
        self.assertEqual(check_program(ambient, "A").status, "ACCEPTED")

        # RT-04 checker B can represent explicit effect/capability declarations.
        scoped = {
            "capability_grants": {
                "config-read": {"capability": "fs.read", "scope": "/config"}
            },
            "functions": {
                "entry": {
                    "effects": ["fs.read"],
                    "effect_row": "e",
                    "grants": ["config-read"],
                    "capability_requirements": [
                        {"capability": "fs.read", "scope": "/config"}
                    ],
                }
            },
        }
        self.assertEqual(check_program(scoped, "B").status, "ACCEPTED")

    def test_rt03_d_observes_effect_order_but_rt04_summaries_do_not(self):
        first = {
            "events": [
                {"effect": "fs.write", "resource": "/a", "value": "1"},
                {"effect": "fs.write", "resource": "/a", "value": "2"},
            ],
            "result": {"ok": None},
        }
        reversed_trace = {
            "events": list(reversed(first["events"])),
            "result": {"ok": None},
        }
        declared = {"fs.write"}
        self.assertEqual(observe("D", first, declared), "ACCEPTED")
        self.assertEqual(observe("D", reversed_trace, declared), "ACCEPTED")
        self.assertNotEqual(first["events"], reversed_trace["events"])

        program = {"functions": {"entry": {"effects": ["fs.write"]}}}
        result = check_program(program, "B")
        self.assertEqual(dict(result.inferred_effects)["entry"], ("fs.write",))
        # The current checker summary is a set-like label summary, not a trace.

    def test_open_effect_row_does_not_establish_rt03_d_effect_declaration(self):
        trace = {
            "events": [{"effect": "net.send", "resource": "remote"}],
            "result": {"ok": None},
        }
        self.assertEqual(observe("D", trace, {"fs.read"}), "REJECTED")
        # Prototype B accepts unknown labels when an open row variable is present.
        # Its row variable is only an annotation; no row unification is implemented.
        program = {
            "functions": {
                "entry": {"effects": ["net.send"], "effect_row": "e"}
            }
        }
        self.assertEqual(check_program(program, "B").status, "ACCEPTED")


if __name__ == "__main__":
    unittest.main()
