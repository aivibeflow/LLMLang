"""Orthogonal falsification probes for three bounded Stage 0.2 scientific claims.

No scientific proof / accepted design decision is implied. The reference decoders
and fairness transition engine below do not invoke the subject implementation.
They share Python's JSON parser and the stated finite observation model, which
are explicit trust-boundary limitations. Git counterexamples use only Git CLI.
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get(
    "LLMLANG_ORACLE_MODEL_DIR",
    str(ROOT / "research" / "PROTOTYPES" / "RT-04-01"),
)).resolve()
sys.path.insert(0, str(MODEL_DIR))
import schema_evolution_model as schema
import scheduler_fairness_model as fairness


MISSING = object()


def expected_decode_object(obj, version: int, unknown: str, default: bool, null: str):
    """Specification-oriented decision table, separate from schema._decode."""
    if not isinstance(obj, dict):
        return "ERROR"
    recognized = ("count",) if version == 1 else ("count", "enabled")
    if unknown == "reject" and any(k not in recognized for k in obj):
        return "ERROR"
    value = obj.get("count", MISSING)
    if type(value) is not int:
        return "ERROR"
    if version == 1:
        return (value, False)
    enabled = obj.get("enabled", MISSING)
    if enabled is MISSING or (enabled is None and null == "treat_as_absent"):
        enabled = default
    if type(enabled) is not bool:
        return "ERROR"
    return (value, enabled)


def independent_periodic_cycle(initial: bool, word: tuple[str, ...], intermittent: bool):
    """A different, symbolic enabledness transition table for finite cycles.

    The oracle separately counts B-runs, so an apparent cycle with a B step
    cannot be mistaken for a starving periodic execution.
    """
    enabled = initial
    b_runs = 0
    bits = []
    for item in word:
        bits.append(enabled)
        if item == "enable":
            if not intermittent or enabled:
                return None
            enabled = True
        elif item == "disable":
            if not intermittent or not enabled:
                return None
            enabled = False
        elif item == "run_a":
            pass
        elif item == "run_b":
            if not enabled:
                return None
            b_runs += 1
            enabled = not intermittent
        else:
            raise AssertionError(f"unexpected oracle action: {item}")
    if enabled != initial or b_runs:
        return None
    return tuple(bits)


class IndependentSchemaOracle(unittest.TestCase):
    def test_cross_product_against_separate_decision_table(self):
        choices_count = (MISSING, None, False, -3, 0, 7, 1.5, "7")
        choices_enabled = (MISSING, None, False, True, 0, 1, "true", [], {})
        extras = (MISSING, 0, "opaque")
        n = 0
        accepted = 0
        rejected = 0
        for count, enabled, extra in itertools.product(
            choices_count, choices_enabled, extras
        ):
            obj = {}
            if count is not MISSING:
                obj["count"] = count
            if enabled is not MISSING:
                obj["enabled"] = enabled
            if extra is not MISSING:
                obj["future"] = extra
            encoded = json.dumps(obj, separators=(",", ":")).encode("utf-8")
            for version, unknown, default, null in itertools.product(
                (1, 2), ("reject", "ignore"),
                (False, True), ("reject", "treat_as_absent")
            ):
                expected = expected_decode_object(obj, version, unknown, default, null)
                policy = schema.UnknownFieldPolicy(unknown)
                if version == 1:
                    observed = schema.decode_v1(encoded, policy)
                else:
                    observed = schema.decode_v2(
                        encoded, enabled_default=default,
                        unknown_fields=policy,
                        null_policy=schema.NullPolicy(null),
                    )
                if expected == "ERROR":
                    self.assertIsInstance(observed, schema.DecodeError, (obj, version, unknown, default, null))
                    rejected += 1
                else:
                    self.assertEqual((observed.count, observed.enabled), expected,
                                     (obj, version, unknown, default, null))
                    accepted += 1
                n += 1
        self.assertEqual(n, 8 * 9 * 3 * 2 * 2 * 2 * 2)
        self.assertGreater(accepted, 0)
        self.assertGreater(rejected, 0)
        print(f"INDEPENDENT_SCHEMA_CASES={n} ACCEPTED={accepted} REJECTED={rejected}")

    def test_malformed_json_and_non_object_inputs_fail_closed(self):
        for payload in (b"{", b"\xff", b"[]", b"null", b"3", b'"text"'):
            for decode in (schema.decode_v1, schema.decode_v2):
                with self.subTest(payload=payload, decode=decode.__name__):
                    self.assertIsInstance(decode(payload), schema.DecodeError)

    def test_duplicate_object_member_is_outside_claimed_schema_model(self):
        # Python JSON accepts a duplicate key and keeps the final value. This
        # intentional limitation is NOT evidence of canonical wire safety.
        raw = b'{"count":1,"count":2}'
        self.assertEqual(schema.decode_v1(raw), schema.Config(2, False))
        self.assertEqual(json.loads(raw)["count"], 2)


class IndependentFairnessOracle(unittest.TestCase):
    def test_exhaustive_small_action_words_against_second_transition_engine(self):
        alphabet = ("enable", "disable", "run_a", "run_b")
        actions = {
            "enable": fairness.Action.ENABLE_B,
            "disable": fairness.Action.DISABLE_B,
            "run_a": fairness.Action.RUN_A,
            "run_b": fairness.Action.RUN_B,
        }
        checked = 0
        legal = 0
        weak_but_not_strong = 0
        for intermittent in (False, True):
            for initial in (False, True):
                for size in range(1, 7):
                    for word in itertools.product(alphabet, repeat=size):
                        expected = independent_periodic_cycle(initial, word, intermittent)
                        scenario = tuple(actions[x] for x in word)
                        start = fairness.State(initial)
                        if expected is None:
                            with self.assertRaises(ValueError):
                                fairness.replay_cycle(start, scenario, intermittent=intermittent)
                        else:
                            observed = fairness.replay_cycle(
                                start, scenario, intermittent=intermittent,
                            )
                            self.assertEqual(tuple(s.b_enabled for s in observed), expected)
                            # Finite cycle repeated forever: a continuously
                            # enabled B cannot starve under weak fairness;
                            # any enabled point excludes starvation under strong.
                            weak_ref = expected.count(False) > 0
                            strong_ref = expected.count(True) == 0
                            self.assertEqual(fairness.weak_fair_cycle(observed), weak_ref)
                            self.assertEqual(fairness.strong_fair_cycle(observed), strong_ref)
                            self.assertTrue(not strong_ref or weak_ref)
                            weak_but_not_strong += int(weak_ref and not strong_ref)
                            legal += 1
                        checked += 1
        self.assertEqual(checked, 4 * sum(4 ** size for size in range(1, 7)))
        self.assertGreater(legal, 0)
        self.assertGreater(weak_but_not_strong, 0)
        print(f"INDEPENDENT_FAIRNESS_WORDS={checked} LEGAL_CYCLES={legal} WEAK_ONLY={weak_but_not_strong}")

    def test_round_robin_two_task_order_and_rejected_cursor(self):
        for cursor in ("A", "B"):
            expected = ("A", "B").index("B") if cursor == "A" else 0
            self.assertEqual(fairness.round_robin_first_b(cursor), expected)
        for cursor in ("", "C", "AB"):
            with self.assertRaises(ValueError):
                fairness.round_robin_first_b(cursor)


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args],
                          check=True, capture_output=True, text=True)


def make_clean_but_incomplete_merge(root: Path) -> tuple[int, set[str], set[str]]:
    git(root, "init", "-q")
    git(root, "config", "user.name", "Independent evidence test")
    git(root, "config", "user.email", "quality@example.invalid")
    (root / "program").mkdir()
    (root / "program" / "manifest.json").write_text(
        json.dumps({"sources": ["callee.json"]}), encoding="utf-8"
    )
    (root / "program" / "callee.json").write_text('{"callable":"v1"}\n', encoding="utf-8")
    (root / "notes.txt").write_text("base\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    base_branch = git(root, "branch", "--show-current").stdout.strip()
    git(root, "checkout", "-qb", "ours")
    git(root, "rm", "-q", "program/callee.json")
    git(root, "commit", "-qm", "remove retained callable")
    git(root, "checkout", "-qb", "theirs", base_branch)
    (root / "notes.txt").write_text("edited in theirs\n", encoding="utf-8")
    git(root, "add", "notes.txt")
    git(root, "commit", "-qm", "edit unrelated file")
    git(root, "checkout", "-q", "ours")
    merged = git(root, "merge", "--no-ff", "--no-edit", "theirs")
    tree_paths = set(git(root, "ls-tree", "-r", "--name-only", "HEAD", "program").stdout.splitlines())
    declared = set(json.loads((root / "program" / "manifest.json").read_text())["sources"])
    return merged.returncode, declared, {p.removeprefix("program/") for p in tree_paths if p != "program/manifest.json"}


class IndependentGitInventoryOracle(unittest.TestCase):
    def test_git_clean_merge_does_not_imply_declared_source_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, expected, actual = make_clean_but_incomplete_merge(root)
            self.assertEqual(code, 0)
            self.assertEqual(expected, {"callee.json"})
            self.assertEqual(actual, set())
            self.assertNotEqual(expected, actual)
            print("INDEPENDENT_GIT_WITNESS=clean-merge-with-missing-declared-source")

    def test_explicit_source_retention_repairs_closed_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, expected, actual = make_clean_but_incomplete_merge(root)
            self.assertNotEqual(expected, actual)
            (root / "program" / "callee.json").write_text('{"callable":"v1"}\n', encoding="utf-8")
            git(root, "add", "program/callee.json")
            git(root, "commit", "-qm", "retain exact declared source")
            tree_paths = set(git(root, "ls-tree", "-r", "--name-only", "HEAD", "program").stdout.splitlines())
            actual = {p.removeprefix("program/") for p in tree_paths if p != "program/manifest.json"}
            self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
