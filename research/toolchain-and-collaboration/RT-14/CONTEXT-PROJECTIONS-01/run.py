"""Compare exact Knowledge Context references with excerpts and summaries."""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

PURPOSE = {
    "call-validation": {"contract": ("precondition", "error"), "test": ("assertion", "edge-case")},
    "recovery-audit": {"contract": ("error", "effects"), "test": ("edge-case", "settlement")},
}
ROLES = ("contract", "test")
GATES = ("none", "projection", "full")
FORMS = ("exact", "excerpt", "summary", "ranked")
VARIANTS = ("current", "old-snapshot", "wrong-purpose", "wrong-reader", "stale-source",
            "missing-field", "wrong-field", "missing-check", "wrong-checker")
SOURCES = {
    "snapshot-a": {
        "contract": {"precondition": "length<=32", "error": "refuse",
                     "effects": "keeps-file", "documentation": "draft explanation"},
        "test": {"assertion": "unchanged on error", "edge-case": "oversize",
                 "settlement": "terminates", "historical-note": "first review"},
    },
    "snapshot-b": {
        "contract": {"precondition": "length<=16", "error": "retry",
                     "effects": "uses-private-stage", "documentation": "draft explanation"},
        "test": {"assertion": "new error on timeout", "edge-case": "interrupted",
                 "settlement": "redrive", "historical-note": "first review"},
    },
}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Check:
    snapshot: str
    purpose: str
    reader: str
    role: str
    original_digest: str
    projection_digest: str
    fields: tuple[str, ...]
    issuer: str


@dataclass(frozen=True)
class Entry:
    snapshot: str
    purpose: str
    reader: str
    role: str
    form: str
    original_digest: str
    visible: tuple[tuple[str, str], ...] | str
    check: Check | None = None


def projection(snapshot, purpose, role):
    source = SOURCES[snapshot][role]
    return tuple(sorted((field, source[field]) for field in PURPOSE[purpose][role]))


def receipt(entry, issuer="trusted-projection"):
    return Check(entry.snapshot, entry.purpose, entry.reader, entry.role, entry.original_digest,
                 digest(entry.visible), tuple(key for key, _ in entry.visible), issuer)


def render(snapshot, purpose, role, form):
    source = SOURCES[snapshot][role]
    if form == "exact":
        visible = tuple(sorted(source.items()))
    elif form == "excerpt":
        visible = projection(snapshot, purpose, role)
    else:
        visible = "candidate may help explain the reviewed operation"
    entry = Entry(snapshot, purpose, "reader-a", role, form, digest(source), visible)
    return replace(entry, check=receipt(entry)) if form == "excerpt" else entry


def mutate(entry, variant, alternate):
    if variant == "old-snapshot":
        return replace(entry, snapshot=alternate)
    if variant == "wrong-purpose":
        return replace(entry, purpose="previous-purpose")
    if variant == "wrong-reader":
        return replace(entry, reader="another-reader")
    if variant == "stale-source":
        return replace(entry, original_digest=digest(SOURCES[alternate][entry.role]))
    if variant in ("missing-field", "wrong-field") and entry.form in ("exact", "excerpt"):
        old = entry.visible
        visible = old[1:] if variant == "missing-field" else ((old[0][0], "changed"), *old[1:])
        changed = replace(entry, visible=visible)
        return replace(changed, check=receipt(changed)) if entry.form == "excerpt" else changed
    if variant == "missing-check":
        return replace(entry, check=None)
    if variant == "wrong-checker" and entry.form == "excerpt":
        return replace(entry, check=receipt(entry, "untrusted-projection"))
    return entry


def bound(entry, snapshot, purpose, grant):
    return (
        grant != "none" and (entry.form != "exact" or grant == "full")
        and (entry.snapshot, entry.purpose, entry.reader) == (snapshot, purpose, "reader-a")
        and entry.original_digest == digest(SOURCES[snapshot][entry.role])
    )


def classify(entry, snapshot, purpose, grant):
    if not bound(entry, snapshot, purpose, grant):
        return "refused"
    if entry.form == "exact":
        canonical = tuple(sorted(SOURCES[snapshot][entry.role].items()))
        return "mandatory" if entry.visible == canonical else "refused"
    if entry.form == "excerpt":
        canonical = projection(snapshot, purpose, entry.role)
        return "mandatory" if entry.visible == canonical and entry.check == receipt(entry) else "refused"
    return "support-only"


def oracle(form, variant, grant):
    if variant in ("old-snapshot", "wrong-purpose", "wrong-reader", "stale-source") or grant == "none":
        return "refused"
    feasible = {
        "exact": {"current", "missing-check", "wrong-checker"} if grant == "full" else set(),
        "excerpt": {"current"},
    }
    if form in feasible:
        return "mandatory" if variant in feasible[form] else "refused"
    return "support-only"


def check():
    states, counts = Counter(), Counter()
    witnesses = {}
    for snapshot, purpose, role, form, variant, grant in product(
        SOURCES, PURPOSE, ROLES, FORMS, VARIANTS, GATES,
    ):
        alternate = next(value for value in SOURCES if value != snapshot)
        entry = mutate(render(snapshot, purpose, role, form), variant, alternate)
        encountered = classify(entry, snapshot, purpose, grant)
        correct = oracle(form, variant, grant)
        assert encountered == correct, (entry, variant, grant, encountered, correct)
        states[(form, encountered)] += 1
        counts["cases"] += 1
        counts["role_or_rank_only_incorrect_mandatory"] += correct != "mandatory"
        counts["binding_only_incorrect_mandatory"] += bound(entry, snapshot, purpose, grant) and correct != "mandatory"
        if snapshot == "snapshot-b" and purpose == "call-validation" and role == "contract" and grant == "full":
            if (form, variant) in (("excerpt", "current"), ("excerpt", "missing-field"),
                                    ("summary", "current"), ("summary", "stale-source")):
                witnesses[f"{form}/{variant}"] = {"entry": asdict(entry), "outcome": encountered}
    assert counts["cases"] == 864
    assert sum(amount for (form, category), amount in states.items() if category == "mandatory") == 40
    assert counts["role_or_rank_only_incorrect_mandatory"] == 824
    assert counts["binding_only_incorrect_mandatory"] == 240

    summary_a = render("snapshot-a", "call-validation", "contract", "summary")
    summary_b = render("snapshot-b", "call-validation", "contract", "summary")
    assert summary_a.visible == summary_b.visible and summary_a.original_digest != summary_b.original_digest
    mandatory_statuses = {}
    for name, combination in {
        "exact-plus-excerpt": ("exact", "excerpt"),
        "exact-plus-summary": ("exact", "summary"),
        "excerpt-plus-ranked": ("excerpt", "ranked"),
    }.items():
        states_for_task = [classify(render("snapshot-b", "call-validation", role, form),
                                    "snapshot-b", "call-validation", "full")
                           for role, form in zip(ROLES, combination)]
        mandatory_statuses[name] = "complete" if states_for_task == ["mandatory", "mandatory"] else "incomplete"
    assert mandatory_statuses == {
        "exact-plus-excerpt": "complete",
        "exact-plus-summary": "incomplete",
        "excerpt-plus-ranked": "incomplete",
    }
    return {
        "counts": dict(counts),
        "formats": {
            form: {level: states[(form, level)] for level in ("mandatory", "support-only", "refused")}
            for form in FORMS
        },
        "compound_context_controls": mandatory_statuses,
        "equal_summary_text_hides_source_difference": True,
        "witnesses": witnesses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(), indent=2) + "\n")


if __name__ == "__main__":
    main()
