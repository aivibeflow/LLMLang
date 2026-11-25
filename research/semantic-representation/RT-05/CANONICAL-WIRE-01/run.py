#!/usr/bin/env python3
"""Exercise strict and normalizing identity admission in both fixture runtimes."""

from collections import Counter
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ENCODERS = HERE.parents[1] / "PROTOTYPES" / "IDENTITY-BYTES-01"
sys.path.insert(0, str(ENCODERS))
from compare import DOMAINS, python_result

PROFILE = "llmlang.identity-fixture/1"
OPER = "operation"
POLICIES = ("strict", "normalizing", "raw_only")


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def hash_bytes(raw):
    return sha256(raw).hexdigest()


def frame(name, raw, expected, *, domain=OPER, claim=None, algorithm="sha256"):
    return {
        "name": name, "raw_hex": raw.hex(), "expected_domain": domain,
        "digest": hash_bytes(raw) if claim is None else claim, "algorithm": algorithm,
        "expected": expected,
    }


def controls():
    term = ["map", [["e\u0301", ["list", [["int", "9007199254740993"], ["bool", True]]]],
                    ["\uffff", ["text", "é"]], ["\U00010000", ["text", "line\nend"]]]]
    base = [PROFILE, OPER, term]
    canonical = compact(base)
    canonical_digest = hash_bytes(canonical)
    demand = ("accept", "accept", "accept")
    cases = [frame(f"canonical-{domain}", compact([PROFILE, domain, term]), demand, domain=domain)
             for domain in sorted(DOMAINS)]
    for index, rows in enumerate(permutations(term[1])):
        raw = compact([PROFILE, OPER, ["map", rows]])
        same = raw == canonical
        cases.append(frame(
            f"map-order-{index}", raw,
            demand if same else ("noncanonical", "accept", "digest"), claim=canonical_digest,
        ))
    cases.extend((
        frame("whitespace", b" " + canonical + b"\n", ("noncanonical", "accept", "digest"),
              claim=canonical_digest),
        frame("escaped-unicode", json.dumps(base, ensure_ascii=True, separators=(",", ":")).encode(),
              ("noncanonical", "accept", "digest"), claim=canonical_digest),
        frame("raw-hash-unsorted", compact([PROFILE, OPER, ["map", list(reversed(term[1]))]]),
              ("noncanonical", "digest", "accept")),
        frame("valid-composed-text", compact([PROFILE, OPER, ["text", "é"]]), demand),
        frame("valid-decomposed-text", compact([PROFILE, OPER, ["text", "e\u0301"]]), demand),
        frame("invalid-utf8", canonical.replace(b"line", b"\xffline"), ("malformed", "malformed", "accept")),
        frame("utf8-bom", b"\xef\xbb\xbf" + canonical, ("malformed", "malformed", "accept")),
        frame("trailing-expression", canonical + b"[]", ("malformed", "malformed", "accept")),
        frame("wrong-version", compact(["unrecognized/9", OPER, term]), ("envelope", "envelope", "accept")),
        frame("wrong-domain", compact([PROFILE, "contract", term]), ("domain", "domain", "accept")),
        frame("missing-domain", compact([PROFILE, term]), ("envelope", "envelope", "accept")),
        frame("duplicate-key", compact([PROFILE, OPER, ["map", [term[1][0], term[1][0]]]]),
              ("typed", "typed", "accept")),
        frame("int-negative-zero", compact([PROFILE, OPER, ["int", "-0"]]), ("typed", "typed", "accept")),
        frame("bare-unsafe-integer", compact([PROFILE, OPER, ["int", 9007199254740993]]),
              ("typed", "typed", "accept")),
        frame("escaped-lone-surrogate", b'["llmlang.identity-fixture/1","operation",["text","\\ud800"]]',
              ("typed", "typed", "accept")),
        frame("unsupported-algorithm", canonical, ("algorithm", "algorithm", "digest"), algorithm="sha512"),
        frame("uppercase-address", canonical, ("address", "address", "digest"), claim=canonical_digest.upper()),
        frame("truncated-address", canonical, ("address", "address", "digest"), claim=canonical_digest[:32]),
        frame("wrong-address", canonical, ("digest", "digest", "digest"), claim="0" * 64),
    ))
    return cases


def python_status(frame):
    raw = bytes.fromhex(frame["raw_hex"])
    raw_only = "accept" if frame["algorithm"] == "sha256" and frame["digest"] == hash_bytes(raw) else "digest"
    try:
        wire = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return "malformed", "malformed", raw_only
    if type(wire) is not list or len(wire) != 3 or wire[0] != PROFILE:
        return "envelope", "envelope", raw_only
    if wire[1] != frame["expected_domain"]:
        return "domain", "domain", raw_only
    normalized = python_result(wire[1:])
    if normalized is None:
        return "typed", "typed", raw_only
    if frame["algorithm"] != "sha256":
        return "algorithm", "algorithm", raw_only
    if not re.fullmatch(r"[0-9a-f]{64}", frame["digest"]):
        return "address", "address", raw_only
    canonical, digest = normalized
    normalizing = "accept" if digest == frame["digest"] else "digest"
    return ("noncanonical" if canonical.encode("utf-8") != raw else normalizing), normalizing, raw_only


def results():
    cases = controls()
    command = ["node", HERE / "decode.mjs"]
    node = subprocess.run(command, input=json.dumps(cases), check=True, text=True,
                          capture_output=True, timeout=30)
    statuses = json.loads(node.stdout)
    totals = {policy: Counter() for policy in POLICIES}
    for case, javascript in zip(cases, statuses, strict=True):
        python = python_status(case)
        if python != tuple(javascript) or python != case["expected"]:
            raise AssertionError((case["name"], case["expected"], python, javascript))
        for policy, status in zip(POLICIES, python, strict=True):
            totals[policy][status] += 1
    return {
        "schema": "llmlang-canonical-wire-admission/1", "python": platform.python_version(),
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "source_sha256": {
            path.name: hash_bytes(path.read_bytes())
            for path in (Path(__file__), HERE / "decode.mjs", ENCODERS / "compare.py", ENCODERS / "encode.mjs")
        },
        "policies": POLICIES, "outcome_counts": totals, "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
