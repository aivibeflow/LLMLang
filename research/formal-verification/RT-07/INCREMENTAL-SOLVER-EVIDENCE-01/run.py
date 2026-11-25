#!/usr/bin/env python3
"""Check incremental SMT replies and attach independent evidence to the effective scope."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
INPUTS = range(4)
HEADER = ("(set-logic QF_LIA)", "(set-option :produce-models true)",
          "(declare-const x Int)", "(declare-const p Bool)")
OUTPUT = re.compile(r"(unsat|sat|unknown)|\(\(x\s+(\d+)\)\s+\(p\s+(true|false)\)\)")


def digest(value):
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class Context:
    threshold: int
    lower: int
    upper: int | None
    enabled: bool

    def satisfiable(self):
        return self.upper is None or (self.lower <= self.upper and (not self.enabled or self.threshold <= self.upper))

    def assumption(self):
        return "(check-sat-assuming (" + ("p" if self.enabled else "(not p)") + "))"

    def guard(self):
        return f"(assert (=> p (>= x {self.threshold})))"

    def bounds(self):
        lower = f"(assert (>= x {self.lower}))"
        if self.upper is None:
            return (lower,)
        return lower, f"(assert (<= x {self.upper}))"

    def context_key(self):
        return digest("\n".join((*HEADER, self.guard(), *self.bounds(), self.assumption())) + "\n")

    def statement(self):
        flag = str(self.enabled).lower()
        return f"∃ x, Admitted {self.lower} {self.threshold} (some {self.upper}) {flag} x"

    def model_valid(self, number, flag):
        return (flag == self.enabled and self.lower <= number
                and (self.upper is None or number <= self.upper)
                and (not flag or self.threshold <= number))


def query(row):
    tail = ("(get-value (x p))",) if row.satisfiable() else ()
    return row.assumption(), *tail


def session(threshold):
    commands = [*HEADER, Context(threshold, 0, None, False).guard()]
    rows = []

    def check(lower, upper):
        for enabled in (False, True):
            row = Context(threshold, lower, upper, enabled)
            rows.append(row)
            commands.extend(query(row))

    for lower in INPUTS:
        commands.extend(("(push 1)", *Context(threshold, lower, None, False).bounds()))
        check(lower, None)
        for upper in INPUTS:
            commands.extend(("(push 1)", Context(threshold, lower, upper, False).bounds()[1]))
            check(lower, upper)
            commands.append("(pop 1)")
        check(lower, None)
        commands.append("(pop 1)")
    return commands, rows


def command(args, cwd, stdin=None):
    return subprocess.run(args, cwd=cwd, input=stdin, text=True, capture_output=True,
                          check=True, timeout=30).stdout


def solve(backend, commands, rows):
    script = "\n".join((*commands, "(exit)")) + "\n"
    raw = command(backend, HERE, script)
    parts = list(OUTPUT.finditer(raw))
    if OUTPUT.sub("", raw).strip():
        raise AssertionError(f"Unrecognized solver output: {raw!r}")
    values = iter(parts)
    for row in rows:
        answer = next(values).group(1)
        expected = "sat" if row.satisfiable() else "unsat"
        if answer != expected:
            raise AssertionError((backend[0], row, answer, expected))
        if answer == "sat":
            model = next(values)
            if model.group(2) is None or not row.model_valid(int(model.group(2)), model.group(3) == "true"):
                raise AssertionError((backend[0], row, "Invalid model", model.group(0)))
    if next(values, None) is not None:
        raise AssertionError(f"Additional output: {raw!r}")
    return digest(script), digest(raw)


def lean_refutations(rows):
    proof = (HERE / "Interval.lean").read_text()
    lines = [proof, "namespace IncrementalEvidence"]
    labels = {}
    for row in rows:
        if row.satisfiable():
            continue
        name = f"refuted_{len(labels):03d}"
        flag = str(row.enabled).lower()
        key = row.context_key()
        labels[key] = name
        lines += [
            f"-- Effective SMT context sha256: {key}",
            f"theorem {name} : ¬ ({row.statement()}) := by",
            "  intro witness",
            f"  have bounds := (boundedSat {row.lower} {row.threshold} {row.upper} {flag}).mp witness",
            f"  exact (by decide : ¬ ({row.lower} ≤ ({row.upper} : Int) ∧",
            f"    ({flag} = true → {row.threshold} ≤ ({row.upper} : Int)))) bounds",
            f"#print axioms {name}",
        ]
    source = "\n".join([*lines, "end IncrementalEvidence", ""])
    with TemporaryDirectory(prefix="llmlang-context-proof-") as temporary:
        root = Path(temporary)
        (root / "Generated.lean").write_text(source)
        transcript = command(["lean", "-DwarningAsError=true", "Generated.lean"], root)
        if len(transcript.splitlines()) != len(labels) + 2:
            raise AssertionError(transcript)
        if any("depends on axioms: [propext]" not in line for line in transcript.splitlines()):
            raise AssertionError(transcript)
    return {"generated_source_sha256": digest(source), "axiom_transcript_sha256": digest(transcript),
            "refutations": labels}


def reuse_counts(rows, refutations):
    counts = Counter()
    receipts = [row for row in rows if row.context_key() in refutations]
    for receipt, requested in product(receipts, rows):
        if receipt.assumption() != requested.assumption():
            continue
        counts["same_command_uses"] += 1
        same_session = receipt.threshold == requested.threshold
        if same_session:
            counts["same_session_same_command_uses"] += 1
        if receipt.context_key() == requested.context_key():
            counts["exact_context_matches"] += 1
        elif requested.satisfiable():
            counts["wrong_context_with_sat_witness"] += 1
            if same_session:
                counts["wrong_context_with_sat_witness_in_same_session"] += 1
        else:
            counts["wrong_context_also_unsat"] += 1
    return counts


def run():
    sessions = [session(threshold) for threshold in INPUTS]
    all_rows = [row for _, rows in sessions for row in rows]
    distinct = list(dict.fromkeys(all_rows))
    independently_checked = lean_refutations(distinct)
    results = {}
    for backend in (("cvc5", "--incremental", "--lang=smt2"), ("z3", "-smt2", "-in")):
        transcript = [solve(backend, commands, rows) for commands, rows in sessions]
        fresh = []
        for row in distinct:
            commands = (*HEADER, row.guard(), *row.bounds(), *query(row))
            fresh.append(solve(backend, commands, [row]))
        results[backend[0]] = {
            "version": command([backend[0], "--version"], HERE).splitlines()[0],
            "incremental_script_and_reply_sha256": transcript,
            "fresh_script_and_reply_ledger_sha256": digest(json.dumps(fresh, separators=(",", ":"))),
        }
    exact = reuse_counts(all_rows, independently_checked["refutations"])
    if exact["exact_context_matches"] != len(independently_checked["refutations"]):
        raise AssertionError(exact)
    stale_positive = Context(1, 0, 0, False)
    stale_negative = Context(1, 0, 0, True)
    if not stale_positive.model_valid(0, False) or stale_negative.model_valid(0, False):
        raise AssertionError("Assumption polarity is not enforced in model validation")
    return {
        "schema": "llmlang-incremental-solver-evidence/1", "python": platform.python_version(),
        "lean": command(["lean", "--version"], HERE).strip(),
        "sources_sha256": {name: digest((HERE / name).read_bytes()) for name in ("Interval.lean", "run.py")},
        "incremental_checks_per_solver": len(all_rows), "fresh_queries_per_solver": len(distinct),
        "sat_models_per_solver": sum(row.satisfiable() for row in all_rows),
        "distinct_reappearing_contexts": len(all_rows) - len(distinct),
        "solvers": results, "lean_evidence": independently_checked, "proof_reuse": exact,
        "model_rebinding_control": {"valid_query": stale_positive.context_key(),
                                    "refused_query": stale_negative.context_key(),
                                    "retained_model": [0, False]},
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
