"""Compare binding, audit authority and independent source evidence before RT-20 planning."""

import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src import semantic_dependency_index as index
from src.impact_planning import ActionKind, CompletenessStatus, ImpactedArtifact
from src.impact_planning import audit_snapshot_incoming, plan_impact
from src.semantic_graph import canonical_bytes, digest
from tests import test_rt24_merge_tree_gate as tree


SUPPORTED = CompletenessStatus.SUPPORTED_WITHIN_SCOPE
APPROVED = "external-auditor"
UNAPPROVED = "graph-producer"
DOMAIN = "llmlang-rt24-source-audit-fixture/1"


def openssl(*args):
    return subprocess.run(["openssl", *map(str, args)], check=False, capture_output=True, timeout=10)


def checked_openssl(*args):
    result = openssl(*args)
    result.check_returncode()
    return result.stdout


def create_key(directory, authority):
    # Public, reproducible fixture key. These keys authorize nothing outside this harness.
    seed = sha256(("public demonstration key for " + authority).encode()).digest()
    private = directory / f"{authority}.der"
    public = directory / f"{authority}.pem"
    private.write_bytes(bytes.fromhex("302e020100300506032b657004220420") + seed)
    public.write_bytes(checked_openssl("pkey", "-in", private, "-inform", "DER", "-pubout"))
    return private, public


def envelope(evidence, authority):
    return {"format": DOMAIN, "authority": authority, "tree": evidence.tree,
            "inventory": evidence.blob_digest, "claim": asdict(evidence.reverse)}


class Signatures:
    def __init__(self, directory):
        self.payload = directory / "payload.json"
        self.signature = directory / "payload.sig"

    def sign(self, body, private):
        self.payload.write_bytes(canonical_bytes(body))
        return checked_openssl("pkeyutl", "-sign", "-rawin", "-inkey", private,
                               "-keyform", "DER", "-in", self.payload)

    def verify(self, body, signature, public):
        if signature is None:
            return False
        self.payload.write_bytes(canonical_bytes(body))
        self.signature.write_bytes(signature)
        operation = openssl("pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", public,
                            "-in", self.payload, "-sigfile", self.signature)
        return operation.returncode == 0


def compare(inventory, store, snapshot, target, evidence, authority, signature, signatures, grant):
    base_query = index.query_snapshot_incoming(store, snapshot, target, tree.SCOPE)
    checked = index.query_snapshot_incoming(store, snapshot, target, tree.SCOPE, evidence.reverse)
    independent = tree.source_evidence(inventory, store, snapshot, target)
    exact_source = (evidence.tree, evidence.blob_digest) == (inventory.tree, inventory.blob_digest)
    body = envelope(evidence, authority)
    admitted_signature = (
        exact_source and authority == APPROVED and grant is not None
        and evidence.reverse.observation_model_id == tree.SCOPE
        and signatures.verify(body, signature, grant)
    )
    matched_audit = independent == evidence and independent.reverse.status is SUPPORTED

    def feed(permit):
        result = checked if permit else base_query
        audit = audit_snapshot_incoming(result)
        plan = plan_impact(snapshot.root_hash, snapshot.root_hash, DOMAIN,
                           [ImpactedArtifact(target, "implementation", "audit incoming calls")], [audit])
        return {"coverage_admitted": result.completeness_status is SUPPORTED,
                "recorded_calls": sorted(call.call_site_id for call in audit.incoming_call_sites),
                "full_revalidation": any(action.kind is ActionKind.FULL_REVALIDATION
                                         for action in plan.actions)}

    return {"tree": inventory.tree, "root": snapshot.root_hash, "signature_body": body,
            "signature_hex": signature.hex() if signature is not None else None,
            "independent_status": independent.reverse.status.value,
            "independent_discrepancies": independent.reverse.discrepancies,
            "binding_only": feed(True), "authorized_signature": feed(admitted_signature),
            "signature_and_source_recheck": feed(admitted_signature and matched_audit)}


def setup():
    fixture = tree.MergeTreeGateExperiment()
    try:
        fixture.setUp()
        repo = fixture.repo
        second_site = {**fixture.caller["call_sites"][0], "call_site_id": "fallback"}
        caller = {**fixture.caller, "call_sites": [*fixture.caller["call_sites"], second_site]}
        commit = tree.commit(repo, {tree.CALLER: [tree.row("caller", caller)]})
        alternate = tree.commit(repo, {"notes.txt": "different ordinary file\n"})
        return fixture, commit, alternate, fixture.old_hash
    except BaseException:
        fixture.doCleanups()
        raise


def verify(directory):
    repo_fixture, commit, alternate, target = setup()
    try:
        repo = repo_fixture.repo
        inventory = tree.read_inventory(repo, commit)
        other_tree = tree.read_inventory(repo, alternate)
        store, snapshot = tree.import_closed(inventory)
        if other_tree.tree == inventory.tree or tree.import_closed(other_tree)[1] != snapshot:
            raise AssertionError("Ordinary-file control must only change the physical tree")
        honest = tree.source_evidence(inventory, store, snapshot, target)
        projection = index.build_snapshot_dependency_index(store, snapshot)
        direct = projection.incoming(target)
        if {edge.edge_id for edge in direct} != {"invoke/direct", "fallback/direct"}:
            raise AssertionError("Expected two exact incoming calls")
        incomplete = replace(projection, edges=tuple(edge for edge in projection.edges if edge not in direct))
        auditor_private, auditor_public = create_key(directory, APPROVED)
        producer_private, producer_public = create_key(directory, UNAPPROVED)
        signatures = Signatures(directory)
        good = signatures.sign(envelope(honest, APPROVED), auditor_private)

        def check(evidence=honest, identity=APPROVED, signature=good, grant=auditor_public,
                  on_tree=inventory):
            return compare(on_tree, store, snapshot, target, evidence, identity, signature,
                           signatures, grant)

        altered = replace(honest, reverse=replace(honest.reverse, assumptions=("different assumptions",)))
        mismatch_model = replace(honest, reverse=replace(honest.reverse, observation_model_id="wrong/1"))
        other_signature = signatures.sign(envelope(honest, UNAPPROVED), producer_private)
        wrong_key_signature = signatures.sign(envelope(honest, APPROVED), producer_private)
        if not signatures.verify(envelope(honest, UNAPPROVED), other_signature, producer_public):
            raise AssertionError("The different authority must produce a valid signature")
        cases = {
            "honest": check(),
            "unsigned": check(signature=None),
            "outside_role": check(identity=UNAPPROVED, signature=other_signature),
            "wrong_key": check(signature=wrong_key_signature),
            "grant_withdrawn": check(grant=None),
            "changed_assumptions": check(evidence=altered),
            "wrong_model_signed": check(evidence=mismatch_model,
                signature=signatures.sign(envelope(mismatch_model, APPROVED), auditor_private)),
            "stale_tree_same_root": check(on_tree=other_tree),
        }
        with patch.object(index, "build_snapshot_dependency_index", return_value=incomplete):
            finding = tree.source_evidence(inventory, store, snapshot, target)
            false_claim = replace(finding, reverse=replace(
                finding.reverse, evidence_id="fixture:" + digest({"projected": [], "status": "supported"}),
                status=SUPPORTED, discrepancies=(),
            ))
            signed_finding = signatures.sign(envelope(finding, APPROVED), auditor_private)
            signed_falsehood = signatures.sign(envelope(false_claim, APPROVED), auditor_private)
            cases["stale_edge_set"] = check()
            cases["signed_missing_calls_finding"] = check(evidence=finding, signature=signed_finding)
            cases["unsigned_false_claim"] = check(evidence=false_claim, signature=None)
            cases["authorized_false_claim"] = check(evidence=false_claim, signature=signed_falsehood)

        expected = {
            "honest": (True, True, True),
            "unsigned": (True, False, False),
            "outside_role": (True, False, False),
            "wrong_key": (True, False, False),
            "grant_withdrawn": (True, False, False),
            "changed_assumptions": (True, False, False),
            "wrong_model_signed": (True, False, False),
            "stale_tree_same_root": (True, False, False),
            "stale_edge_set": (False, False, False),
            "signed_missing_calls_finding": (False, False, False),
            "unsigned_false_claim": (True, False, False),
            "authorized_false_claim": (True, True, False),
        }
        policies = ("binding_only", "authorized_signature", "signature_and_source_recheck")
        for label, case in cases.items():
            actual = tuple(case[policy]["coverage_admitted"] for policy in policies)
            if actual != expected[label]:
                raise AssertionError((label, expected[label], actual))
        falsehood = cases["authorized_false_claim"]
        if falsehood["authorized_signature"]["full_revalidation"]:
            raise AssertionError("A falsely empty call set should expose the unsafe planner path")
        if not falsehood["signature_and_source_recheck"]["full_revalidation"]:
            raise AssertionError("Require full revalidation when the scope check fails")
        if cases["honest"]["signature_and_source_recheck"]["recorded_calls"] != ["fallback", "invoke"]:
            raise AssertionError("The honest audit must pass both exact call sites to RT-20")
        return {"format": DOMAIN, "python": sys.version.split()[0],
                "git": tree.git(repo, "--version").decode().strip(),
                "openssl": checked_openssl("version").decode().strip(),
                "approved_public_key": auditor_public.read_text(),
                "other_public_key": producer_public.read_text(), "cases": cases}
    finally:
        repo_fixture.doCleanups()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-audit-authority-") as scratch:
        ledger = verify(Path(scratch))
    arguments.output.write_text(json.dumps(ledger, sort_keys=True, indent=2) + "\n", encoding="utf-8")
