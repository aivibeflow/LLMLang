"""Check snapshot-pinned Knowledge Context pages with current read authorization."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import runpy
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REFERENCE = HERE.parent / "KNOWLEDGE-CONTEXT-01/run.py"
MODEL = runpy.run_path(str(REFERENCE))
BASELINE = "4678c1535b6136e3c667f8eca8511ef06b3089d3"
POLICIES = ("pinned-grant", "live-page", "exact-scope")
UNAVAILABLE = {"status": "unavailable"}
ACTOR = "reviewer"
SCOPE = MODEL["Scope"]()
ENTRIES = MODEL["BASIS"]
ROLES = tuple(entry.role for entry in ENTRIES)


def encode(value):
    return MODEL["canonical"](value)


def hash_value(value):
    return hashlib.sha256(encode(value)).hexdigest()


class Reader:
    def __init__(self, policy):
        self.policy = policy
        required = {entry.role: entry.reference() for entry in ENTRIES[:2]}
        self.context = MODEL["exact"](ENTRIES, SCOPE, 50, required, {"note"})
        assert self.context["status"] == "ready"
        self.manifest = self.context["manifest"]
        self.cursors = {}

    def cursor(self, index):
        token = hash_value([self.context["manifest_sha256"], ACTOR, ROLES, index])
        self.cursors[token] = index
        return token

    def authorized(self, actor, scope, role=None):
        if actor != ACTOR:
            return False
        if self.policy == "pinned-grant":
            return True
        bindings = self.manifest["bindings"]
        if self.policy == "exact-scope" and scope.revision != self.manifest["scope_revision"]:
            return False
        roles = (role,) if role is not None else ROLES
        return all(bindings[key]["source"] in scope.read for key in roles)

    def inspect(self, actor, scope):
        if not self.authorized(actor, scope):
            return UNAVAILABLE
        return {"status": "ready", "manifest": self.manifest,
                "manifest_sha256": self.context["manifest_sha256"], "first_cursor": self.cursor(0)}

    def page(self, actor, scope, sources, token):
        if token not in self.cursors:
            return UNAVAILABLE
        index = self.cursors[token]
        role = ROLES[index]
        if not self.authorized(actor, scope, role):
            return UNAVAILABLE
        reference = self.manifest["bindings"][role]
        entry = sources.get((self.manifest["snapshot"], reference["source"]))
        if entry is None or entry.reference() != reference or entry.role != role:
            return UNAVAILABLE
        more = index + 1 < len(ROLES)
        row = {"role": role, "reference": reference, "text": entry.content}
        return {"status": "page", "entry": row, "next_cursor": self.cursor(index + 1) if more else None,
                "rendered_sha256": None if more else self.context["rendered_sha256"]}


def exchange(reader, actor, scope, sources, query, serialized):
    if serialized:
        query = json.loads(encode(query))
    if query["method"] == "inspect":
        result = reader.inspect(actor, scope)
    else:
        assert query["method"] == "page"
        result = reader.page(actor, scope, sources, query["cursor"])
    return json.loads(encode(result)) if serialized else result


def schedule(policy, case, serialized):
    reader = Reader(policy)
    sources = {(entry.snapshot, entry.source): entry for entry in ENTRIES}
    inspect = {"method": "inspect"}

    def page(scope, token, actor=ACTOR):
        return exchange(reader, actor, scope, sources, {"method": "page", "cursor": token}, serialized)

    opened = exchange(reader, ACTOR, SCOPE, sources, inspect, serialized)
    first = page(SCOPE, opened["first_cursor"])
    assert first["entry"]["role"] == "contract"
    scope = SCOPE
    second_token = first["next_cursor"]
    actor = ACTOR
    if case == "optional-revoked":
        scope = replace(scope, revision="scope-2", read=scope.read - {"design#1"})
    elif case == "mandatory-revoked":
        scope = replace(scope, revision="scope-2", read=scope.read - {"test#1"})
    elif case == "rotated-equivalent-scope":
        scope = replace(scope, revision="scope-2")
    elif case == "other-principal":
        actor = "observer"
    elif case == "unknown-cursor":
        second_token = "unused-fixture-cursor"
    elif case == "missing-source":
        sources.pop(("snap-7", "test#1"))
    elif case == "only-new-snapshot-retained":
        entry = sources.pop(("snap-7", "test#1"))
        newer = replace(entry, snapshot="snap-8")
        sources[(newer.snapshot, newer.source)] = newer
    elif case == "changed-source-bytes":
        sources[("snap-7", "test#1")] = replace(ENTRIES[1], content="different test evidence")
    elif case == "new-snapshot-retains-old":
        newer = replace(ENTRIES[1], snapshot="snap-8", content="newer test evidence")
        sources[(newer.snapshot, newer.source)] = newer
    elif case != "unchanged":
        raise AssertionError(case)

    fresh_inspection = exchange(reader, actor, scope, sources, inspect, serialized)
    second = page(scope, second_token, actor)
    second_again = page(scope, second_token, actor)
    assert second_again == second
    third = page(scope, second["next_cursor"], actor) if second["status"] == "page" else UNAVAILABLE
    pages = (first, second, third)
    sent = [row["entry"] for row in pages if row["status"] == "page"]
    completed = third["status"] == "page"
    if completed:
        joined = "".join(row["text"] + "\n" for row in sent).encode()
        assert hashlib.sha256(joined).hexdigest() == third["rendered_sha256"]
    else:
        assert all(row.get("rendered_sha256") is None for row in pages)
    allowed = [row["reference"]["source"] for row in sent[1:] if row["reference"]["source"] not in scope.read]
    return {"opened": opened, "fresh_inspection": fresh_inspection, "pages": list(pages),
            "content_sent_after_revocation": allowed, "assembled_view_completed": completed}


def main():
    variants = {
        "unchanged": (3, 3, 3),
        "optional-revoked": (3, 2, 1),
        "mandatory-revoked": (3, 1, 1),
        "rotated-equivalent-scope": (3, 3, 1),
        "other-principal": (1, 1, 1),
        "unknown-cursor": (1, 1, 1),
        "missing-source": (1, 1, 1),
        "only-new-snapshot-retained": (1, 1, 1),
        "changed-source-bytes": (1, 1, 1),
        "new-snapshot-retains-old": (3, 3, 3),
    }
    rows = {}
    for name, expected in variants.items():
        observed = {}
        for index, policy in enumerate(POLICIES):
            direct = schedule(policy, name, False)
            serialized = schedule(policy, name, True)
            assert serialized == direct
            assert sum(page["status"] == "page" for page in direct["pages"]) == expected[index]
            leaks = direct["content_sent_after_revocation"]
            assert bool(leaks) == (name in ("mandatory-revoked", "optional-revoked")
                                   and policy == "pinned-grant")
            if name in ("mandatory-revoked", "optional-revoked") and policy != "pinned-grant":
                assert direct["fresh_inspection"] == UNAVAILABLE
            observed[policy] = direct
        rows[name] = observed

    relative = str(REFERENCE.relative_to(ROOT))
    archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
    assert REFERENCE.read_bytes() == archived
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "assembly_reference_sha256": hashlib.sha256(archived).hexdigest(), "cases": rows,
    }, indent=2))


if __name__ == "__main__":
    main()
