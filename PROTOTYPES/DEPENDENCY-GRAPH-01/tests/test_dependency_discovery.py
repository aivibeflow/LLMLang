import unittest
from src.dependency_discovery import (
    AuditStatus, DependencyMeaning, DependencyObservation, DiscoveryError,
    EvidenceSource, audit_dependencies, discover_candidates,
)

class DependencyDiscoveryTests(unittest.TestCase):
    def obs(self, h, source=EvidenceSource.DYNAMIC, scope="build-x", tool="trace-v1"):
        return DependencyObservation("artifact-A",h,source,tool,scope,f"evidence-{h}-{source.value}")

    def test_static_and_dynamic_evidence_are_preserved(self):
        rows=[self.obs("config",EvidenceSource.STATIC),self.obs("config",EvidenceSource.DYNAMIC)]
        found=discover_candidates("artifact-A","build-x",rows,{"config":DependencyMeaning.CONFIGURATION})
        self.assertEqual(set(found[0].sources),{EvidenceSource.STATIC,EvidenceSource.DYNAMIC})
        self.assertEqual(len(found[0].evidence_digests),2)

    def test_static_observation_alone_is_not_semantic_edge(self):
        audit=audit_dependencies("artifact-A","build-x",set(),[self.obs("possible",EvidenceSource.STATIC)],{})
        self.assertEqual(audit.status,AuditStatus.REVIEW_REQUIRED)
        self.assertEqual(audit.semantic_dependencies,())

    def test_dynamic_observation_alone_is_not_semantic_edge(self):
        audit=audit_dependencies("artifact-A","build-x",set(),[self.obs("runtime-read")],{})
        self.assertEqual(audit.status,AuditStatus.REVIEW_REQUIRED)

    def test_missing_classified_semantic_dependency_is_gap(self):
        audit=audit_dependencies("artifact-A","build-x",{"declared"},[self.obs("hidden")],
            {"hidden":DependencyMeaning.SEMANTIC_INPUT})
        self.assertEqual(audit.status,AuditStatus.GAP_FOUND)
        self.assertEqual(audit.missing_dependencies,("hidden",))

    def test_declared_dependency_is_supported_within_scope(self):
        audit=audit_dependencies("artifact-A","build-x",{"config"},[self.obs("config")],
            {"config":DependencyMeaning.CONFIGURATION})
        self.assertEqual(audit.status,AuditStatus.SUPPORTED_WITHIN_SCOPE)

    def test_provenance_only_is_not_hash_relevant(self):
        audit=audit_dependencies("artifact-A","build-x",set(),[self.obs("author")],
            {"author":DependencyMeaning.PROVENANCE_ONLY})
        self.assertEqual(audit.status,AuditStatus.SUPPORTED_WITHIN_SCOPE)
        self.assertEqual(audit.semantic_dependencies,())

    def test_incidental_access_is_not_hash_relevant(self):
        audit=audit_dependencies("artifact-A","build-x",set(),[self.obs("telemetry")],
            {"telemetry":DependencyMeaning.INCIDENTAL_ACCESS})
        self.assertEqual(audit.status,AuditStatus.SUPPORTED_WITHIN_SCOPE)

    def test_unknown_candidate_requires_review(self):
        audit=audit_dependencies("artifact-A","build-x",set(),[self.obs("maybe")],{})
        self.assertEqual(audit.status,AuditStatus.REVIEW_REQUIRED)
        self.assertEqual(audit.unresolved_candidates,("maybe",))

    def test_empty_evidence_is_not_checked(self):
        audit=audit_dependencies("artifact-A","build-x",set(),[],{})
        self.assertEqual(audit.status,AuditStatus.NOT_CHECKED)

    def test_wrong_artifact_or_scope_is_rejected(self):
        row=DependencyObservation("other","input",EvidenceSource.DYNAMIC,"trace-v1","build-x","e1")
        with self.assertRaises(DiscoveryError):
            discover_candidates("artifact-A","build-x",[row],{})

    def test_classification_without_observation_is_rejected(self):
        with self.assertRaises(DiscoveryError):
            discover_candidates("artifact-A","build-x",[],{"phantom":DependencyMeaning.SEMANTIC_INPUT})

    def test_evidence_digest_changes_when_classification_changes(self):
        row=self.obs("input")
        a=audit_dependencies("artifact-A","build-x",{"input"},[row],{"input":DependencyMeaning.SEMANTIC_INPUT})
        b=audit_dependencies("artifact-A","build-x",{"input"},[row],{"input":DependencyMeaning.INCIDENTAL_ACCESS})
        self.assertNotEqual(a.evidence_digest,b.evidence_digest)

    def test_evidence_digest_changes_when_tool_changes(self):
        a=audit_dependencies("artifact-A","build-x",{"input"},[self.obs("input",tool="v1")],
            {"input":DependencyMeaning.SEMANTIC_INPUT})
        b=audit_dependencies("artifact-A","build-x",{"input"},[self.obs("input",tool="v2")],
            {"input":DependencyMeaning.SEMANTIC_INPUT})
        self.assertNotEqual(a.evidence_digest,b.evidence_digest)

if __name__=="__main__":
    unittest.main()
