"""Compare content-only and revision-bound Interface Mapping Revision updates."""

from dataclasses import dataclass
from itertools import product
import unittest

from src.semantic_graph import digest


Key = tuple[str, str]  # external namespace and interface name
Target = tuple[str, str]  # exported symbol and exact signature identity
Edit = tuple[Key, Target | None]


class MappingConflict(ValueError):
    pass


@dataclass(frozen=True)
class Revision:
    parents: tuple[str, ...]
    edits: tuple[Edit, ...]
    entries: tuple[tuple[Key, Target], ...]

    @property
    def identity(self):
        return digest(("rt23-mapping-revision/1", self.parents, self.edits, self.entries))


@dataclass(frozen=True)
class Catalog:
    semantic_root: str
    signatures: tuple[tuple[tuple[str, str], str], ...]

    @property
    def identity(self):
        return digest(("rt23-mapping-catalog/1", self.semantic_root, sorted(self.signatures)))


def apply(entries, edits):
    values = dict(entries)
    for key, target in edits:
        if target is None:
            values.pop(key, None)
        else:
            values[key] = target
    return tuple(sorted(values.items()))


def child(base, edits):
    ordered = tuple(sorted(edits.items()))
    return Revision((base.identity,), ordered, apply(base.entries, ordered))


def validate(entries, catalog):
    signatures = dict(catalog.signatures)
    exported = {}
    for (namespace, name), (symbol, signature) in entries:
        key = (namespace, symbol)
        if key in exported:
            raise MappingConflict(f"export {key!r} claimed by {exported[key]!r} and {name!r}")
        if signatures.get(key) != signature:
            raise MappingConflict(f"catalog does not provide exact signature for {key!r}")
        exported[key] = name


@dataclass(frozen=True)
class Candidate:
    inputs: tuple[str, str, str]
    context: str
    revision: Revision

    @property
    def identity(self):
        return digest(("rt23-mapping-merge/1", self.inputs, self.context, self.revision.identity))


def prepare(base, left, right, catalog):
    edits = []
    for tip in (left, right):
        if tip.identity == base.identity:
            edits.append({})
            continue
        if tip.parents != (base.identity,):
            raise MappingConflict("tip does not descend directly from the pinned base")
        rows = dict(tip.edits)
        if child(base, rows) != tip:
            raise MappingConflict("tip entries and edits disagree")
        edits.append(rows)

    ours, theirs = edits
    overlap = ours.keys() & theirs.keys()
    if overlap:
        raise MappingConflict(f"concurrent edits to {sorted(overlap)!r}")

    validate(base.entries, catalog)
    validate(left.entries, catalog)
    validate(right.entries, catalog)
    combined = tuple(sorted((ours | theirs).items()))
    entries = apply(base.entries, combined)
    validate(entries, catalog)
    parents = tuple(sorted({left.identity, right.identity}))
    revision = Revision(parents, combined, entries) if combined else base
    return Candidate((base.identity, left.identity, right.identity), catalog.identity, revision)


@dataclass
class BranchHeads:
    """Represent one serialized CAS step in the experiment, with three guarded inputs."""

    inputs: tuple[str, str, str]
    context: str
    selected: Revision

    def install(self, candidate):
        if self.inputs != candidate.inputs or self.context != candidate.context:
            raise MappingConflict("stale mapping revision or semantic context")
        self.selected = candidate.revision
        self.inputs = (self.inputs[0], self.selected.identity, self.inputs[2])


class InterfaceMappingMergeExperiment(unittest.TestCase):
    def setUp(self):
        self.key = ("api", "entry")
        self.base = Revision((), (), ((self.key, ("f", "sig1")),))
        self.catalog = Catalog("semantic-A", (
            (("api", "f"), "sig1"), (("api", "g"), "sig2"), (("cli", "g"), "sig3"),
        ))

    def test_disjoint_scopes_merge_deterministically(self):
        left = child(self.base, {self.key: ("g", "sig2")})
        right = child(self.base, {("cli", "entry"): ("g", "sig3")})
        merged = prepare(self.base, left, right, self.catalog)
        reversed_merge = prepare(self.base, right, left, self.catalog)
        self.assertEqual(merged.revision, reversed_merge.revision)
        self.assertNotEqual(merged.identity, reversed_merge.identity)
        self.assertEqual(dict(merged.revision.entries), {
            self.key: ("g", "sig2"), ("cli", "entry"): ("g", "sig3"),
        })
        self.assertEqual(prepare(self.base, left, right, self.catalog), merged)

    def test_same_key_requires_review_even_for_equal_value_or_delete(self):
        for ours, theirs in product((None, ("f", "sig1"), ("g", "sig2")), repeat=2):
            with self.subTest(ours=ours, theirs=theirs):
                left = child(self.base, {self.key: ours})
                right = child(self.base, {self.key: theirs})
                with self.assertRaisesRegex(MappingConflict, "concurrent edits"):
                    prepare(self.base, left, right, self.catalog)

    def test_disjoint_keys_can_claim_the_same_export(self):
        left = child(self.base, {("api", "also-this"): ("g", "sig2")})
        right = child(self.base, {("api", "also-that"): ("g", "sig2")})
        prepare(self.base, left, self.base, self.catalog)
        prepare(self.base, self.base, right, self.catalog)
        with self.assertRaisesRegex(MappingConflict, "claimed by"):
            prepare(self.base, left, right, self.catalog)

    def test_incompatible_signature_fails_and_unchanged_retains_base(self):
        left = child(self.base, {self.key: ("g", "sig1")})
        with self.assertRaisesRegex(MappingConflict, "exact signature"):
            prepare(self.base, left, self.base, self.catalog)
        unchanged = prepare(self.base, self.base, self.base, self.catalog)
        self.assertEqual(unchanged.revision, self.base)

    def test_publication_requires_exact_revisions_and_semantic_context(self):
        left = child(self.base, {self.key: ("g", "sig2")})
        right = child(self.base, {("cli", "entry"): ("g", "sig3")})
        candidate = prepare(self.base, left, right, self.catalog)
        heads = BranchHeads(candidate.inputs, candidate.context, left)
        # Return to the same logical entries via two revisions.
        restored = child(child(left, {self.key: None}), {self.key: ("g", "sig2")})
        self.assertEqual(restored.entries, left.entries)
        self.assertNotEqual(restored.identity, left.identity)
        heads.inputs = (self.base.identity, restored.identity, right.identity)
        with self.assertRaisesRegex(MappingConflict, "stale"):
            heads.install(candidate)
        self.assertIs(heads.selected, left)
        with self.assertRaisesRegex(MappingConflict, "pinned base"):
            prepare(self.base, restored, right, self.catalog)

        heads.inputs = candidate.inputs
        next_catalog = Catalog("semantic-B", self.catalog.signatures)
        heads.context = next_catalog.identity
        with self.assertRaisesRegex(MappingConflict, "stale"):
            heads.install(candidate)
        self.assertIs(heads.selected, left)
        rebound = prepare(self.base, left, right, next_catalog)
        self.assertNotEqual(rebound.identity, candidate.identity)
        heads.install(rebound)
        self.assertEqual(heads.selected, rebound.revision)
        with self.assertRaisesRegex(MappingConflict, "stale"):
            heads.install(rebound)

    def test_reported_edits_must_reconstruct_tip_from_base(self):
        missing_edit = Revision((self.base.identity,), (), ())
        with self.assertRaisesRegex(MappingConflict, "entries and edits disagree"):
            prepare(self.base, missing_edit, self.base, self.catalog)


if __name__ == "__main__":
    unittest.main()
