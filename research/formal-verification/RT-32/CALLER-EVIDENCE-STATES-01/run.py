#!/usr/bin/env python3
"""Verify version-bound states for proof publication and assumption discharge."""

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
ARCHIVE = "7871ded14f9e56ff855757b1fa91b8d4e2904c75"
CORPUS = "research/formal-verification/RT-32/CORE-OBLIGATION-CORPUS-01/evidence.json"
CORPUS_SHA256 = "bf313c1f62aa7085b3009eb473359478c40cf82715475adec1ecb636bc7fe195"
ROLES = ("modular", "provider", "leaf")


@dataclass(frozen=True)
class Key:
    role: str
    version: str
    subject: str
    contract: str
    theorem: str
    imports: str
    toolchain: str


@dataclass(frozen=True)
class Evidence:
    key: Key
    disposition: str
    admitted: bool = True


def key(role, generation):
    # This late caller's contract and generic theorem are generation independent.
    revision = "abstract" if role == "modular" else generation
    return Key(role, revision, f"{role}/{revision}", f"{role}/contract",
               f"{role}/theorem", f"{role}/imports", "lean/4.36.0")


def status(present):
    statuses = {item.disposition for item in present}
    if {"checked", "refuted"} <= statuses:
        return "conflict"
    for choice in ("checked", "refuted", "rejected", "unsupported", "unknown", "pending"):
        if choice in statuses:
            return choice
    return "pending"


def resolve(generation, receipts):
    roles = {}
    for role in ROLES:
        expected = key(role, generation)
        roles[role] = status(item for item in receipts if item.admitted and item.key == expected)
    if all(value == "checked" for value in roles.values()):
        return "closed", roles
    return ("conditional" if roles["modular"] == "checked" else roles["modular"]), roles


def matrix():
    options = (None, "checked", "pending", "unknown", "unsupported", "rejected",
               "refuted", "stale", "unapproved")
    counts = Counter()
    for row in product(options, repeat=len(ROLES)):
        candidate = []
        for role, state in zip(ROLES, row, strict=True):
            if state == "stale":
                candidate.append(Evidence(replace(key(role, "b"), subject="different"), "checked"))
            elif state == "unapproved":
                candidate.append(Evidence(key(role, "b"), "checked", admitted=False))
            elif state:
                candidate.append(Evidence(key(role, "b"), state))
        result, _ = resolve("b", candidate)
        expected = "closed" if row == ("checked",) * len(ROLES) else (
            "conditional" if row[0] == "checked" else
            "pending" if row[0] in (None, "stale", "unapproved") else row[0])
        if result != expected:
            raise AssertionError((row, result, expected))
        counts[result] += 1
    return counts


def schedules():
    events = {
        "modular": Evidence(key("modular", "a"), "checked"),
        "old_provider": Evidence(key("provider", "a"), "checked"),
        "old_leaf": Evidence(key("leaf", "a"), "checked"),
        "activate": None,
        "new_provider": Evidence(key("provider", "b"), "checked"),
        "new_leaf": Evidence(key("leaf", "b"), "checked"),
        "new_unknown": Evidence(key("leaf", "b"), "unknown"),
    }
    expected_events = {
        "a": {"modular", "old_provider", "old_leaf"},
        "b": {"modular", "new_provider", "new_leaf"},
    }
    counts = Counter()
    controls = {}
    for schedule in permutations(events):
        generation, seen, receipts = "a", set(), []
        counts["schedules"] += 1
        for i, step in enumerate(schedule, 1):
            seen.add(step)
            if step == "activate":
                generation = "b"
            else:
                receipts.append(events[step])
            actual, _ = resolve(generation, receipts)
            correct = expected_events[generation] <= seen
            if (actual == "closed") != correct:
                raise AssertionError((schedule, i, actual))
            counts["prefixes"] += 1
            counts["closed_prefixes"] += correct
            generic = {receipt.key.role for receipt in receipts if receipt.disposition == "checked"}
            if set(ROLES) <= generic and not correct:
                counts["scope_free_false_closures"] += 1
                controls.setdefault("scope_free", [schedule, i])
            latest_exact = {receipt.key.role: receipt.disposition for receipt in receipts
                            if receipt.key == key(receipt.key.role, generation)}
            if correct and latest_exact.get("leaf") == "unknown":
                counts["latest_job_loses_closed_evidence"] += 1
                controls.setdefault("latest_job", [schedule, i])
    return counts, controls


def trust_controls():
    expected = key("provider", "b")
    baseline = [Evidence(key(role, "b"), "checked") for role in ROLES]
    controls = {}
    for name in ("subject", "version", "contract", "theorem", "imports", "toolchain"):
        wrong = Evidence(replace(expected, **{name: "different"}), "checked")
        controls[name] = resolve("b", [baseline[0], wrong, baseline[2]])[0]
    controls["unapproved_provenance"] = resolve(
        "b", [baseline[0], replace(baseline[1], admitted=False), baseline[2]])[0]
    controls["conflicting_exact_provider"] = resolve(
        "b", [*baseline, Evidence(expected, "refuted")])[1]["provider"]
    if controls != dict.fromkeys(("subject", "version", "contract", "theorem", "imports",
                                  "toolchain", "unapproved_provenance"), "conditional") | {
        "conflicting_exact_provider": "conflict",
    }:
        raise AssertionError(controls)
    return controls


if __name__ == "__main__":
    corpus = subprocess.check_output(["git", "show", f"{ARCHIVE}:{CORPUS}"])
    if sha256(corpus).hexdigest() != CORPUS_SHA256:
        raise AssertionError("Compiled antecedent ledger digest changed")
    archived = json.loads(corpus)["adversarial_evidence"]["compiled_admission_cases"]
    counts, witnesses = schedules()
    print(json.dumps({
        "schema": "llmlang-caller-evidence-discharge-states/1", "python": platform.python_version(),
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Discharge.lean", "axioms.txt")},
        "archive_revision": ARCHIVE, "archive_sha256": CORPUS_SHA256,
        "archived_compiled_claim_results": archived,
        "state_matrix": matrix(), "schedule_counts": counts, "schedule_witnesses": witnesses,
        "trust_controls": trust_controls(),
    }, indent=2))
