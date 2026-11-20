import hashlib
import io
import os
import tempfile
import unittest

from package_archive import verify_archive
from package_identity import logical_index_hash, package_content_root, parse_manifest
from package_index import normalize
from package_provider import ProviderError, build_archive_from_snapshot

H1 = "sha256:" + hashlib.sha256(b"root").hexdigest()
H2 = "sha256:" + hashlib.sha256(b"dep").hexdigest()
H3 = "sha256:" + hashlib.sha256(b"optional").hexdigest()


class Snapshot:
    def __init__(self):
        self.snapshot_id = "snapshot-1"
        self.objects = {
            H1: {"hash": H1, "kind": "function", "size": 4},
            H2: {"hash": H2, "kind": "function", "size": 3},
            H3: {"hash": H3, "kind": "type", "size": 8},
        }
        self.edges = {
            H1: [
                {"edge_id": "required", "kind": "required", "target_hash": H2},
                {"edge_id": "optional", "kind": "optional", "target_hash": H3},
            ],
            H2: [{"edge_id": "cycle", "kind": "required", "target_hash": H1}],
            H3: [],
        }

    def get_object(self, content_hash):
        return self.objects[content_hash]

    def get_dependencies(self, source_hash):
        return self.edges[source_hash]

    def open_object(self, content_hash):
        return io.BytesIO({H1: b"root", H2: b"dep", H3: b"optional"}[content_hash])


def expected_index(snapshot, policy):
    included = {H1}
    if policy in {"closure", "closure_with_optional"}:
        included.add(H2)
    if policy == "closure_with_optional":
        included.add(H3)
    deps = []
    for source in sorted(included):
        for edge in snapshot.edges[source]:
            row = {
                "source_hash": source, "edge_id": edge["edge_id"], "kind": edge["kind"],
                "target_hash": edge["target_hash"], "included": edge["target_hash"] in included,
            }
            if "condition" in edge:
                row["condition"] = edge["condition"]
            deps.append(row)
    return normalize({
        "objects": [snapshot.objects[h] for h in sorted(included)],
        "dependencies": deps, "exports": [], "modules": [],
    })


def make_manifest(index, policy):
    raw = f'''format = "llmlang.package"
schema_version = 1

[package]
name = "provider-test"

[content]
roots = ["{H1}"]
dependency_policy = "{policy}"
content_root = "sha256:{'0' * 64}"

[index]
path = "index"
format_version = 1
logical_hash = "{logical_index_hash(index)}"
'''.encode()
    model = parse_manifest(raw)
    root = package_content_root(model, index)
    return raw.replace(("sha256:" + "0" * 64).encode(), root.encode())


class ProviderArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "provider.llpkg")

    def tearDown(self):
        self.temp.cleanup()

    def test_all_dependency_policies_build_verified_archives(self):
        for policy in ("closure", "roots_only", "closure_with_optional"):
            with self.subTest(policy=policy):
                snapshot = Snapshot()
                index = expected_index(snapshot, policy)
                manifest = make_manifest(index, policy)
                build_archive_from_snapshot([H1], snapshot, manifest, self.path,
                                            policy=policy, max_records_in_memory=1)
                self.assertTrue(verify_archive(self.path, max_records_in_memory=1))

    def test_manifest_roots_and_policy_must_match_request(self):
        snapshot = Snapshot()
        manifest = make_manifest(expected_index(snapshot, "closure"), "closure")
        with self.assertRaisesRegex(ProviderError, "roots differ"):
            build_archive_from_snapshot([H2], snapshot, manifest, self.path)
        with self.assertRaisesRegex(ProviderError, "policy differs"):
            build_archive_from_snapshot([H1], snapshot, manifest, self.path, policy="roots_only")

    def test_missing_exact_transitive_object_fails(self):
        snapshot = Snapshot()
        del snapshot.objects[H2]
        manifest = make_manifest(expected_index(Snapshot(), "closure"), "closure")
        with self.assertRaisesRegex(ProviderError, "missing exact dependency object"):
            build_archive_from_snapshot([H1], snapshot, manifest, self.path)

    def test_hash_substitution_fails(self):
        snapshot = Snapshot()
        snapshot.objects[H2] = {"hash": H1, "kind": "function", "size": 3}
        manifest = make_manifest(expected_index(Snapshot(), "closure"), "closure")
        with self.assertRaisesRegex(ProviderError, "different hash"):
            build_archive_from_snapshot([H1], snapshot, manifest, self.path)

    def test_payload_hash_is_verified_by_archive_writer(self):
        class BadPayloadSnapshot(Snapshot):
            def open_object(self, content_hash):
                return io.BytesIO(b"evil")
        snapshot = BadPayloadSnapshot()
        manifest = make_manifest(expected_index(snapshot, "closure"), "closure")
        with self.assertRaisesRegex(ProviderError, "Content Hash mismatch"):
            build_archive_from_snapshot([H1], snapshot, manifest, self.path)

    def test_snapshot_change_does_not_publish_archive(self):
        class ChangingSnapshot(Snapshot):
            def open_object(self, content_hash):
                self.snapshot_id = "snapshot-2"
                return super().open_object(content_hash)
        snapshot = ChangingSnapshot()
        manifest = make_manifest(expected_index(snapshot, "closure"), "closure")
        with self.assertRaisesRegex(ProviderError, "snapshot changed"):
            build_archive_from_snapshot([H1], snapshot, manifest, self.path)
        self.assertFalse(os.path.exists(self.path))

    def test_conditional_required_edge_requires_explicit_selection(self):
        snapshot = Snapshot()
        snapshot.edges[H1][0]["condition"] = {"feature": "extra"}
        manifest = make_manifest(expected_index(Snapshot(), "closure"), "closure")
        with self.assertRaisesRegex(ProviderError, "explicit boolean selection"):
            build_archive_from_snapshot([H1], snapshot, manifest, self.path)

    def test_optional_conditional_edge_is_not_evaluated_by_required_only_policy(self):
        snapshot = Snapshot()
        snapshot.edges[H1][1]["condition"] = {"feature": "optional"}
        manifest = make_manifest(expected_index(snapshot, "closure"), "closure")
        build_archive_from_snapshot([H1], snapshot, manifest, self.path, policy="closure")
        self.assertTrue(verify_archive(self.path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
