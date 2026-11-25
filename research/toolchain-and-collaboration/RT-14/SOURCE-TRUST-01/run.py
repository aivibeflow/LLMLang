"""Check purpose-bound completeness with a finite SQLite inventory."""
import argparse
from collections import Counter
from dataclasses import astuple, dataclass, replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import sqlite3

REQUIREMENTS = {
    "verify": {"contract": {"project"}, "test": {"project", "verification"}},
    "explain": {"contract": {"project"}, "reference": {"project", "approved-external"}},
}
PRIMARY = {"contract": "project", "test": "verification", "reference": "approved-external"}
STATES = ("present", "stale", "missing", "unknown", "untrusted", "conflict")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return sha256(encode(value).encode()).hexdigest()


@dataclass(frozen=True, order=True)
class Reply:
    snapshot: str
    purpose: str
    role: str
    source: str
    locator: str
    revision: int
    state: str
    value: str


def nominal(purpose, role, source, state="present", value="approved-value"):
    return Reply("snapshot-2", purpose, role, source, f"{source}/{role}", 2, state, value)


def replies(purpose, role, state):
    primary = nominal(purpose, role, PRIMARY[role])
    derived = nominal(purpose, role, "derived", value="different-derived-text")
    if state == "present":
        return (primary, derived)
    if state == "stale":
        return (replace(primary, revision=1), derived)
    if state == "missing":
        return (replace(primary, state="absent", value=""), derived)
    if state == "unknown":
        return (derived,)
    if state == "untrusted":
        wrong_binding = replace(primary, purpose="other-purpose")
        return (wrong_binding, derived)
    return (primary, replace(primary, source="project", locator=f"project/{role}",
                             value="divergent-current-value"))


def inventory(purpose, entries, finalized):
    with sqlite3.connect(":memory:") as store:
        store.executescript("""
            CREATE TABLE replies (
              snapshot TEXT, purpose TEXT, role TEXT, source TEXT, locator TEXT,
              revision INTEGER, state TEXT, value TEXT
            );
            CREATE TABLE seal (snapshot TEXT, purpose TEXT, hash TEXT);
        """)
        store.executemany("INSERT INTO replies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", map(astuple, entries))
        if finalized:
            store.execute("INSERT INTO seal VALUES (?, ?, ?)",
                          ("snapshot-2", purpose, digest(sorted(set(map(astuple, entries))))))
        observed = sorted({Reply(*values) for values in store.execute("SELECT * FROM replies")})
        seal = store.execute("SELECT * FROM seal").fetchone()
        return observed, seal


def classify_role(entries, purpose, role):
    authorized = [item for item in entries
                  if (item.snapshot, item.purpose, item.role) == ("snapshot-2", purpose, role)
                  and item.source in REQUIREMENTS[purpose][role]
                  and item.locator == f"{item.source}/{role}"]
    current = [item for item in authorized if item.revision == 2]
    values = {item.value for item in current if item.state == "present"}
    absent = any(item.state == "absent" for item in current)
    if len(values) > 1 or (values and absent):
        return "conflict", None
    if values:
        return "present", next(iter(values))
    if absent:
        return "missing", None
    if authorized:
        return "stale", None
    if any(item.role == role and item.source in REQUIREMENTS[purpose][role] for item in entries):
        return "untrusted", None
    return "unknown", None


def evaluate(purpose, entries, seal):
    statuses = {role: classify_role(entries, purpose, role) for role in REQUIREMENTS[purpose]}
    exact_digest = digest([astuple(item) for item in entries])
    if seal != ("snapshot-2", purpose, exact_digest):
        result = "unsealed"
    elif all(status == "present" for status, _ in statuses.values()):
        result = "complete"
    else:
        result = "incomplete"
    return {
        "result": result, "statuses": statuses, "inventory_digest": exact_digest,
        "requirements_digest": digest({role: sorted(sources) for role, sources in REQUIREMENTS[purpose].items()}),
    }


def check():
    counts = Counter()
    examples = {}
    for purpose in REQUIREMENTS:
        roles = tuple(REQUIREMENTS[purpose])
        for first, second, finalized in product(STATES, STATES, (False, True)):
            data = replies(purpose, roles[0], first) + replies(purpose, roles[1], second)
            expected = "unsealed"
            if finalized:
                expected = "complete" if (first, second) == ("present", "present") else "incomplete"
            expected_statuses = dict(zip(roles, (first, second)))
            prior = None
            for order in sorted(set(permutations(data))):
                entries, seal = inventory(purpose, order, finalized)
                result = evaluate(purpose, entries, seal)
                assert result["result"] == expected, (purpose, data, result, expected)
                assert {role: status for role, (status, _) in result["statuses"].items()} == expected_statuses
                assert prior is None or prior == result
                prior = result
                counts[expected] += 1
                naive = all(any(item.role == role and item.state == "present" for item in order)
                            for role in roles)
                counts["role_presence_false_complete"] += naive and expected != "complete"
            if purpose == "verify" and finalized and first == "present":
                examples[second] = prior

    purpose = "verify"
    baseline = replies(purpose, "contract", "present") + replies(purpose, "test", "present")
    entries, seal = inventory(purpose, baseline, True)
    complete = evaluate(purpose, entries, seal)
    assert complete["result"] == "complete"
    controls = {}
    for name, modified, alternate_seal, result in (
        ("duplicate-reply", baseline + (baseline[0],), seal, "complete"),
        ("retired-source", baseline[:-2], seal, "unsealed"),
        ("other-snapshot-seal", baseline, ("snapshot-1", *seal[1:]), "unsealed"),
        ("other-purpose-seal", baseline, (seal[0], "explain", seal[2]), "unsealed"),
        ("changed-authoritative-value", (replace(baseline[0], value="replacement"), *baseline[1:]),
         seal, "unsealed"),
        ("approved-authorities-agree", baseline + (nominal(purpose, "test", "project"),),
         None, "complete"),
        ("approved-authorities-disagree",
         baseline + (nominal(purpose, "test", "project", value="different"),), None, "incomplete"),
        ("affirmative-and-absent",
         baseline + (nominal(purpose, "test", "project", state="absent", value=""),), None, "incomplete"),
        ("wrong-locator", (replace(baseline[0], locator="other/path"), *baseline[1:]), None, "incomplete"),
    ):
        new_entries, new_seal = inventory(purpose, modified, True)
        observed = evaluate(purpose, new_entries, alternate_seal or new_seal)
        assert observed["result"] == result, (name, observed, result)
        if name == "duplicate-reply":
            assert observed == complete
        controls[name] = observed
    return {"sqlite": sqlite3.sqlite_version, "logical_cases": 144, "orders": dict(counts),
            "observations": examples, "controls": controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    arguments.output.write_text(json.dumps(check(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
