"""RT-24 experiment with closed source inventories in temporary Git trees."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from src.candidate_graph_audit import audit_candidate_snapshot_graph
from src.impact_planning import (
    ActionKind, CompletenessStatus, ImpactedArtifact, audit_snapshot_incoming, plan_impact,
)
from src.semantic_dependency_index import (
    ReverseLookupEvidence, SnapshotIncomingResult, audit_snapshot_incoming_independently,
    publish_declaration, query_snapshot_incoming, validate_declaration,
)
from src.semantic_graph import ContentStore, Snapshot, canonical_bytes, digest, make_snapshot
from tests.test_candidate_graph_audit import declaration


MANIFEST = "program/manifest.json"
CONTRACT = "program/contract.json"
CALLEE = "program/callee.json"
CALLER = "program/caller.json"
SCOPE = "rt24-fixture-explicit-calls/1"


class InventoryError(ValueError):
    """The tree does not establish the fixture source inventory."""


class GraphImportError(ValueError):
    """The declared source does not reconstruct a closed graph."""


@dataclass(frozen=True)
class Inventory:
    tree: str
    blob_digest: str
    declarations: dict[str, dict]


@dataclass(frozen=True)
class SourceEvidence:
    tree: str
    blob_digest: str
    reverse: ReverseLookupEvidence


def git(repo: Path, *args: str) -> bytes:
    environment = {
        **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    }
    return subprocess.run(
        ["git", "-c", "user.name=RT-24 fixture", "-c", "user.email=fixture@example.invalid",
         *args], cwd=repo, env=environment, capture_output=True, check=True, timeout=30,
    ).stdout


def _unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise InventoryError("duplicate JSON object key")
    return fields


def read_inventory(repo: Path, revision: str) -> Inventory:
    """Read tracked blobs under the reserved fixture directory at one Git tree."""
    tree = git(repo, "rev-parse", f"{revision}^{{tree}}").decode("ascii").strip()
    blobs = {}
    entries = git(repo, "ls-tree", "-rz", "--full-tree", tree, "--", "program/")
    for entry in entries.split(b"\0")[:-1]:
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        if (mode, kind) != ("100644", "blob"):
            raise InventoryError("fixture source paths require ordinary nonexecutable blobs")
        blobs[name.decode("utf-8")] = oid

    def read(path):
        try:
            return json.loads(git(repo, "cat-file", "blob", blobs[path]), object_pairs_hook=_unique_fields)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise InventoryError(f"invalid JSON source: {path}") from exc

    if MANIFEST not in blobs:
        raise InventoryError("missing source manifest")
    manifest = read(MANIFEST)
    if (not isinstance(manifest, dict) or set(manifest) != {"version", "sources"}
            or type(manifest["version"]) is not int or manifest["version"] != 1):
        raise InventoryError("unsupported source manifest")
    sources = manifest["sources"]
    if (not isinstance(sources, list) or not sources or any(not isinstance(path, str) for path in sources)
            or len(set(sources)) != len(sources)):
        raise InventoryError("source manifest requires a nonempty list of unique paths")
    if set(sources) != blobs.keys() - {MANIFEST}:
        raise InventoryError("manifest and tracked source inventory differ")

    rows = {}
    for path in sorted(sources):
        file_rows = read(path)
        if not isinstance(file_rows, list):
            raise InventoryError(f"expected declaration rows at {path}")
        for row in file_rows:
            if (not isinstance(row, dict) or set(row) != {"slot", "declaration"}
                    or not isinstance(row["slot"], str) or not row["slot"]):
                raise InventoryError(f"invalid source row at {path}")
            if row["slot"] in rows:
                raise InventoryError(f"duplicate source slot: {row['slot']}")
            rows[row["slot"]] = row["declaration"]
    return Inventory(tree, digest(sorted(blobs.items())), rows)


def publish_rows(rows: dict[str, dict], store: ContentStore) -> Snapshot:
    """Publish the exact acyclic fixture declarations, retrying forward references."""
    selections = {}
    pending = dict(rows)
    while pending:
        missing = {}
        for slot, value in sorted(pending.items()):
            try:
                selections[slot] = publish_declaration(store, value)
            except KeyError as exc:
                missing[slot] = exc.args[0]
        if len(missing) == len(pending):
            raise GraphImportError(f"unavailable exact targets: {sorted(missing.items())}")
        pending = {slot: pending[slot] for slot in missing}
    return make_snapshot(selections)


def import_closed(inventory: Inventory) -> tuple[ContentStore, Snapshot]:
    store = ContentStore()
    snapshot = publish_rows(inventory.declarations, store)
    audit = audit_candidate_snapshot_graph(store, snapshot)
    if not audit.valid:
        raise GraphImportError(f"invalid graph: {audit.errors}")
    return store, snapshot


def source_evidence(inventory: Inventory, store: ContentStore, snapshot: Snapshot,
                    target: str) -> SourceEvidence:
    if store.get(target).kind not in {"function", "operation"}:
        raise GraphImportError("the fixture source audit covers callable targets")
    query = query_snapshot_incoming(store, snapshot, target, SCOPE)
    payload_audit = audit_snapshot_incoming_independently(store, snapshot, query)
    expected = {
        (slot, f"{site['call_site_id']}/{row['target_id']}", row["condition"], row["required_contract_hash"])
        for slot, value in inventory.declarations.items()
        for site in value.get("call_sites", ())
        for row in site["targets"]
        if row["target_hash"] == target
    }
    projected = {
        (slot, edge.edge_id, edge.condition, edge.required_contract_hash)
        for slot, address in snapshot.selections
        for edge in query.edges
        if edge.source_hash == address and edge.relation == "calls"
    }
    discrepancies = set(payload_audit.discrepancies)
    discrepancies.update(f"source-call-missing:{slot}/{edge}" for slot, edge, _, _ in expected - projected)
    discrepancies.update(f"source-call-unexpected:{slot}/{edge}" for slot, edge, _, _ in projected - expected)
    selected = snapshot.mapping
    source_slots, snapshot_slots = inventory.declarations.keys(), selected.keys()
    discrepancies.update(f"source-slot-missing:{slot}" for slot in source_slots - snapshot_slots)
    discrepancies.update(f"source-slot-unexpected:{slot}" for slot in snapshot_slots - source_slots)
    for slot in source_slots & snapshot_slots:
        declared = canonical_bytes(validate_declaration(inventory.declarations[slot]))
        stored = canonical_bytes(store.get(selected[slot]).payload)
        if declared != stored:
            discrepancies.add(f"source-value-mismatch:{slot}")
    findings = tuple(sorted(discrepancies))
    identity = digest({
        "model": SCOPE, "tree": inventory.tree, "inventory": inventory.blob_digest,
        "query": payload_audit.evidence_id, "findings": findings,
    })
    reverse = replace(payload_audit, evidence_id=f"source-audit:{identity}", observation_model_id=SCOPE,
                      status=CompletenessStatus.GAP_FOUND if findings else CompletenessStatus.SUPPORTED_WITHIN_SCOPE,
                      discrepancies=findings)
    return SourceEvidence(inventory.tree, inventory.blob_digest, reverse)


def checked_source_query(inventory: Inventory, store: ContentStore, snapshot: Snapshot,
                         evidence: SourceEvidence) -> SnapshotIncomingResult:
    if (evidence.tree, evidence.blob_digest) != (inventory.tree, inventory.blob_digest):
        raise InventoryError("source evidence is bound to a different Git tree or inventory")
    return query_snapshot_incoming(store, snapshot, evidence.reverse.target_hash, SCOPE, evidence.reverse)


def manifest(*sources: str) -> dict:
    return {"version": 1, "sources": list(sources)}


def row(slot: str, value: dict) -> dict:
    return {"slot": slot, "declaration": value}


def commit(repo: Path, files: dict) -> str:
    for name, content in files.items():
        path = repo / name
        if content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = content if isinstance(content, str) else json.dumps(content, indent=2) + "\n"
            path.write_text(data, encoding="utf-8")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "fixture state")
    return git(repo, "rev-parse", "HEAD").decode("ascii").strip()


class MergeTreeGateExperiment(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="rt24-merge-tree-")
        self.addCleanup(directory.cleanup)
        self.repo = Path(directory.name)
        git(self.repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1")
        store = ContentStore()
        contract = declaration("contract", "contract:score", {"result": "Int"})
        self.contract_hash = publish_declaration(store, contract)
        self.old = declaration("function", "function:score", {"offset": 1}, references=[{
            "reference_id": "provides", "relation": "provides_contract", "target_hash": self.contract_hash,
            "target_kind": "contract",
        }])
        self.old_hash = publish_declaration(store, self.old)
        self.new = {**self.old, "content": {"offset": 2}}
        self.caller = declaration("function", "function:entry", call_sites=[{
            "call_site_id": "invoke", "targets": [{
                "target_id": "direct", "target_hash": self.old_hash,
                "required_contract_hash": self.contract_hash, "condition": "entry-active",
            }],
        }])
        self.base = commit(self.repo, {
            MANIFEST: manifest(CONTRACT, CALLEE, CALLER), CONTRACT: [row("contract", contract)],
            CALLEE: [row("callee", self.old)], CALLER: [], "notes.txt": "original\n",
        })

    def merge(self, *, retain_old: bool) -> Inventory:
        git(self.repo, "switch", "--quiet", "-c", "ours", self.base)
        providers = [row("callee", self.new)]
        if retain_old:
            providers.append(row("callee.old", self.old))
        ours = commit(self.repo, {CALLEE: providers})
        git(self.repo, "switch", "--quiet", "-c", "theirs", self.base)
        theirs = commit(self.repo, {CALLER: [row("caller", self.caller)]})
        self.assertEqual(git(self.repo, "merge-base", ours, theirs).decode().strip(), self.base)
        for revision in (self.base, ours, theirs):
            import_closed(read_inventory(self.repo, revision))
        tree = git(self.repo, "merge-tree", "--write-tree", "--no-messages", ours, theirs).decode().strip()
        self.assertEqual(git(self.repo, "rev-parse", "HEAD").decode().strip(), theirs)
        self.assertEqual(git(self.repo, "status", "--porcelain"), b"")
        return read_inventory(self.repo, tree)

    def test_clean_git_merge_can_be_invalid_and_warm_store_masks_the_missing_target(self):
        merged = self.merge(retain_old=False)
        with self.assertRaisesRegex(GraphImportError, self.old_hash):
            import_closed(merged)
        warm, _ = import_closed(read_inventory(self.repo, self.base))
        snapshot = publish_rows(merged.declarations, warm)
        audit = audit_candidate_snapshot_graph(warm, snapshot)
        self.assertTrue(audit.valid, audit.errors)
        self.assertEqual(set(audit.reachable_hashes) - set(snapshot.mapping.values()), {self.old_hash})

    def test_explicitly_retaining_the_old_version_reconstructs_the_exact_call(self):
        merged = self.merge(retain_old=True)
        store, snapshot = import_closed(merged)
        self.assertEqual(snapshot.mapping["callee.old"], self.old_hash)
        self.assertNotEqual(snapshot.mapping["callee"], self.old_hash)
        evidence = source_evidence(merged, store, snapshot, self.old_hash)
        query = checked_source_query(merged, store, snapshot, evidence)
        self.assertEqual(query.completeness_status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        audit = audit_snapshot_incoming(query)
        (call,) = audit.incoming_call_sites
        self.assertEqual((call.caller_hash, call.call_site_id, call.target_id, call.target_hash,
                          call.condition, call.required_contract_hash),
                         (snapshot.mapping["caller"], "invoke", "direct", self.old_hash,
                          "entry-active", self.contract_hash))

    def test_source_comparison_detects_an_omission_shared_by_index_and_payload_audit(self):
        merged = self.merge(retain_old=True)
        omitted = dict(merged.declarations)
        del omitted["caller"]
        store = ContentStore()
        snapshot = publish_rows(omitted, store)
        query = query_snapshot_incoming(store, snapshot, self.old_hash, SCOPE)
        payload_only = audit_snapshot_incoming_independently(store, snapshot, query)
        self.assertEqual(payload_only.status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        self.assertEqual(query.edges, ())
        evidence = source_evidence(merged, store, snapshot, self.old_hash)
        checked = checked_source_query(merged, store, snapshot, evidence)
        self.assertEqual(checked.completeness_status, CompletenessStatus.GAP_FOUND)
        self.assertEqual(checked.discrepancies, ("source-call-missing:caller/invoke/direct", "source-slot-missing:caller"))

        def planned(result):
            plan = plan_impact(snapshot.root_hash, "proposed-next-snapshot", "rt24-fixture",
                               [ImpactedArtifact(self.old_hash, "implementation", "callee changed")],
                               [audit_snapshot_incoming(result)])
            return {action.kind for action in plan.actions}

        payload_query = query_snapshot_incoming(store, snapshot, self.old_hash, SCOPE, payload_only)
        self.assertNotIn(ActionKind.FULL_REVALIDATION, planned(payload_query))
        self.assertTrue({ActionKind.HUMAN_REVIEW, ActionKind.FULL_REVALIDATION} <= planned(checked))

    def test_duplicate_value_preserves_two_source_slots_in_the_completeness_comparison(self):
        revision = commit(self.repo, {CALLER: [row("caller", self.caller), row("caller.copy", self.caller)]})
        inventory = read_inventory(self.repo, revision)
        store, snapshot = import_closed(inventory)
        self.assertEqual(snapshot.mapping["caller"], snapshot.mapping["caller.copy"])
        evidence = source_evidence(inventory, store, snapshot, self.old_hash)
        query = checked_source_query(inventory, store, snapshot, evidence)
        self.assertEqual(query.completeness_status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        self.assertEqual(len(query.edges), 1)
        partial = make_snapshot({slot: addr for slot, addr in snapshot.selections if slot != "caller.copy"})
        missing = source_evidence(inventory, store, partial, self.old_hash)
        self.assertEqual(evidence.reverse.edge_set_digest, missing.reverse.edge_set_digest)
        self.assertEqual(missing.reverse.discrepancies, (
            "source-call-missing:caller.copy/invoke/direct", "source-slot-missing:caller.copy",
        ))
        replay = checked_source_query(inventory, store, partial, evidence)
        self.assertEqual(replay.completeness_status, CompletenessStatus.UNKNOWN)

    def test_wrong_value_in_a_known_slot_is_detected_even_with_the_same_reverse_edges(self):
        merged = self.merge(retain_old=True)
        store, snapshot = import_closed(merged)
        wrong = make_snapshot({**snapshot.mapping, "callee": self.old_hash})
        original = source_evidence(merged, store, snapshot, self.old_hash)
        altered = source_evidence(merged, store, wrong, self.old_hash)
        self.assertEqual(original.reverse.edge_set_digest, altered.reverse.edge_set_digest)
        self.assertEqual(altered.reverse.status, CompletenessStatus.GAP_FOUND)
        self.assertEqual(altered.reverse.discrepancies, ("source-value-mismatch:callee",))

    def test_inventory_disagreement_cannot_be_interpreted_as_deletion(self):
        cases = (
            {CALLER: None},
            {MANIFEST: manifest(CONTRACT, CALLEE)},
            {MANIFEST: {"version": 2, "sources": [CONTRACT, CALLEE, CALLER]}},
        )
        for files in cases:
            with self.subTest(paths=tuple(files)):
                git(self.repo, "switch", "--quiet", "--detach", self.base)
                revision = commit(self.repo, files)
                with self.assertRaisesRegex(InventoryError, "inventory differ|unsupported source manifest"):
                    read_inventory(self.repo, revision)

    def test_clone_reconstruction_and_evidence_replay_at_same_semantics_different_tree(self):
        original = commit(self.repo, {CALLER: [row("caller", self.caller)]})
        source = read_inventory(self.repo, original)
        store, baseline = import_closed(source)
        original_evidence = source_evidence(source, store, baseline, self.old_hash)
        moved_path = "program/relocated.json"
        moved = commit(self.repo, {
            CALLER: None, moved_path: json.dumps([row("caller", self.caller)], separators=(",", ":")),
            MANIFEST: manifest(moved_path, CALLEE, CONTRACT), "notes.txt": "changed independently\n",
        })
        with TemporaryDirectory(prefix="rt24-clone-") as clone_path:
            clone = Path(clone_path)
            git(clone, "clone", "--quiet", "--no-local", str(self.repo), ".")
            relocated = read_inventory(clone, moved)
            clone_store, snapshot = import_closed(relocated)
        self.assertEqual(snapshot, baseline)
        self.assertNotEqual(relocated.tree, source.tree)
        self.assertNotEqual(relocated.blob_digest, source.blob_digest)
        plain_replay = query_snapshot_incoming(clone_store, snapshot, self.old_hash, SCOPE, original_evidence.reverse)
        self.assertEqual(plain_replay.completeness_status, CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
        with self.assertRaisesRegex(InventoryError, "different Git tree or inventory"):
            checked_source_query(relocated, clone_store, snapshot, original_evidence)
        fresh = source_evidence(relocated, clone_store, snapshot, self.old_hash)
        self.assertEqual(checked_source_query(relocated, clone_store, snapshot, fresh).completeness_status,
                         CompletenessStatus.SUPPORTED_WITHIN_SCOPE)


if __name__ == "__main__":
    unittest.main()
