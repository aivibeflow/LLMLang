"""Bind one interface mapping revision to semantic and physical Git state."""

from dataclasses import asdict, dataclass
import unittest

from src.semantic_graph import canonical_bytes
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt23_interface_mapping_merge as mappings
from tests import test_rt24_merge_tree_gate as tree


MAPPING = "interface-mapping.json"


class UnpublishableMapping(ValueError):
    pass


@dataclass(frozen=True)
class MappingApproval:
    commit: recovery.Prepared
    catalog: mappings.Catalog
    candidate: mappings.Candidate


def export_mapping(catalog, candidate):
    return canonical_bytes({
        "format": "rt23-interface-mapping-fixture/1",
        "catalog": catalog.identity,
        "semantic_root": catalog.semantic_root,
        "mapping": candidate.revision.identity,
        "revision": asdict(candidate.revision),
        "inputs": candidate.inputs,
    }) + b"\n"


def publish(repo, approved):
    prepared, catalog, candidate = approved.commit, approved.catalog, approved.candidate
    inventory = tree.read_inventory(repo, prepared.candidate)
    _, snapshot = tree.import_closed(inventory)
    if snapshot.root_hash != catalog.semantic_root or candidate.context != catalog.identity:
        raise UnpublishableMapping("mapping catalog is stale for the semantic snapshot")
    descriptor = tree.git(repo, "ls-tree", prepared.candidate, "--", MAPPING)
    if not descriptor.startswith(b"100644 blob "):
        raise UnpublishableMapping("mapping artifact must be a regular source blob")
    exported = tree.git(repo, "show", f"{prepared.candidate}:{MAPPING}")
    if exported != export_mapping(catalog, candidate):
        raise UnpublishableMapping("mapping artifact differs from the prepared revision")
    mappings.validate(candidate.revision.entries, catalog)
    return recovery.publish(repo, prepared)


class MappingTreePublicationExperiment(unittest.TestCase):
    setUp = tree.MergeTreeGateExperiment.setUp

    def fixture(self):
        tree.git(self.repo, "branch", "-m", "main")
        tree.git(self.repo, "switch", "--quiet", "--detach", self.base)
        semantic_change = tree.commit(self.repo, {
            tree.CALLEE: [tree.row("callee", self.new)],
            "notes.txt": "approved ordinary change\n",
        })
        changed = tree.read_inventory(self.repo, semantic_change)
        _, snapshot = tree.import_closed(changed)
        catalog = mappings.Catalog(snapshot.root_hash, (
            (("api", "write"), "sig-api"), (("cli", "write"), "sig-cli"),
        ))
        base = mappings.Revision((), (), ())
        left = mappings.child(base, {("api", "entry"): ("write", "sig-api")})
        right = mappings.child(base, {("cli", "entry"): ("write", "sig-cli")})
        candidate = mappings.prepare(base, left, right, catalog)
        return catalog, candidate

    def prepare_commit(self, catalog, candidate, files):
        materialized = tree.commit(self.repo, files)
        inventory = tree.read_inventory(self.repo, materialized)
        _, snapshot = tree.import_closed(inventory)
        commit = recovery.commit_object(self.repo, inventory.tree, (self.base,), "bound mapping fixture")
        prepared = recovery.Prepared("mapping-publication", inventory.tree, snapshot.root_hash,
                                     (self.base,), commit)
        return MappingApproval(prepared, catalog, candidate)

    def test_exact_mapping_and_semantic_state_publish_once(self):
        catalog, candidate = self.fixture()
        artifact = export_mapping(catalog, candidate)
        approval = self.prepare_commit(catalog, candidate, {MAPPING: artifact.decode()})
        self.assertEqual(publish(self.repo, approval), "published")
        self.assertEqual(publish(self.repo, approval), "published")
        commit = approval.commit.candidate
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), commit)
        self.assertEqual(recovery.ref(self.repo, approval.commit.receipt), commit)
        self.assertEqual(tree.git(self.repo, "show", f"{commit}:{MAPPING}"), artifact)
        self.assertEqual(tree.git(self.repo, "show", f"{commit}:notes.txt"),
                         b"approved ordinary change\n")

    def test_mapping_revision_cannot_change_at_the_same_semantic_root(self):
        catalog, candidate = self.fixture()
        artifact = export_mapping(catalog, candidate).decode().replace("sig-cli", "other")
        approval = self.prepare_commit(catalog, candidate, {MAPPING: artifact})
        self.assertEqual(approval.commit.semantic_root, catalog.semantic_root)
        with self.assertRaisesRegex(UnpublishableMapping, "prepared revision"):
            publish(self.repo, approval)
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), self.base)
        self.assertIsNone(recovery.ref(self.repo, approval.commit.receipt))

    def test_mapping_cannot_cross_a_snapshot_change_with_equal_signatures(self):
        catalog, candidate = self.fixture()
        artifact = export_mapping(catalog, candidate)
        approval = self.prepare_commit(catalog, candidate, {
            MAPPING: artifact.decode(), tree.CALLEE: [tree.row("callee", self.old)],
        })
        self.assertNotEqual(approval.commit.semantic_root, catalog.semantic_root)
        self.assertEqual(tree.git(self.repo, "show", f"{approval.commit.candidate}:{MAPPING}"),
                         artifact)
        with self.assertRaisesRegex(UnpublishableMapping, "catalog is stale"):
            publish(self.repo, approval)
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), self.base)
        self.assertIsNone(recovery.ref(self.repo, approval.commit.receipt))

    def test_missing_mapping_artifact_blocks_publication(self):
        catalog, candidate = self.fixture()
        approval = self.prepare_commit(catalog, candidate, {"notes.txt": "another file\n"})
        with self.assertRaisesRegex(UnpublishableMapping, "regular source blob"):
            publish(self.repo, approval)
        self.assertEqual(recovery.ref(self.repo, recovery.BRANCH), self.base)
        self.assertIsNone(recovery.ref(self.repo, approval.commit.receipt))