import unittest
from src.execution import (
    SnapshotError, StaleHeadError, compare_and_swap_release_head,
    make_build_snapshot, make_build_artifact, make_deployment_snapshot,
    make_execution_snapshot, make_release_manifest,
)
from src.semantic_graph import digest, make_snapshot

def h(label): return digest({"fixture":label})

def build(project, build_binding="build-bind-A", toolchain="toolchain-A"):
    return make_build_snapshot(
        project_root=project, build_binding_root=h(build_binding),
        target_platform_hash=h("target-linux"), execution_platform_hash=h("exec-linux"),
        toolchain_root=h(toolchain), dependency_lock_root=h("deps-v1"),
        build_config_hash=h("build-config"),
    )

def artifact(b, output="binary-A"):
    return make_build_artifact(build=b,artifact_hash=h(output),
        provenance_root=h("provenance-"+output),builder_identity_hash=h("builder-1"))

def deployment(b,a,runtime_binding="runtime-prod",image="runtime-v1"):
    return make_deployment_snapshot(
        build=b,artifact=a,runtime_binding_root=h(runtime_binding),
        runtime_image_hash=h(image),deployment_config_hash=h("deploy-config"),
        infrastructure_root=h("infra-prod"),
    )

class LayeredSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.project=make_snapshot({"module":h("module-v1")}).root_hash

    def test_runtime_binding_change_does_not_change_project_or_build(self):
        b=build(self.project); a=artifact(b)
        prod=deployment(b,a,"runtime-prod")
        staging=deployment(b,a,"runtime-staging")
        self.assertEqual(b.project_root,self.project)
        self.assertEqual(prod.build_root,staging.build_root)
        self.assertNotEqual(prod.root_hash,staging.root_hash)

    def test_build_toolchain_change_does_not_change_project(self):
        a=build(self.project,toolchain="clang-1")
        b=build(self.project,toolchain="clang-2")
        self.assertEqual(a.project_root,b.project_root)
        self.assertNotEqual(a.root_hash,b.root_hash)

    def test_same_build_inputs_can_produce_distinct_artifact_records(self):
        b=build(self.project)
        a1=artifact(b,"binary-1"); a2=artifact(b,"binary-2")
        self.assertEqual(a1.build_root,a2.build_root)
        self.assertNotEqual(a1.root_hash,a2.root_hash)
        self.assertNotEqual(a1.artifact_hash,a2.artifact_hash)

    def test_two_deployments_can_share_project_and_build(self):
        b=build(self.project); a=artifact(b)
        prod=deployment(b,a,"prod"); test=deployment(b,a,"test")
        rp=make_release_manifest(project_root=self.project,build=b,artifact=a,deployment=prod)
        rt=make_release_manifest(project_root=self.project,build=b,artifact=a,deployment=test)
        self.assertEqual(rp.project_root,rt.project_root)
        self.assertEqual(rp.build_root,rt.build_root)
        self.assertNotEqual(rp.root_hash,rt.root_hash)

    def test_release_rejects_crossed_project_build_or_artifact(self):
        b1=build(self.project); a1=artifact(b1); d1=deployment(b1,a1)
        b2=build(h("other-project")); a2=artifact(b2); d2=deployment(b2,a2)
        with self.assertRaisesRegex(SnapshotError,"different project"):
            make_release_manifest(project_root=h("other-project"),build=b1,artifact=a1,deployment=d1)
        with self.assertRaisesRegex(SnapshotError,"different build"):
            make_release_manifest(project_root=self.project,build=b1,artifact=a2,deployment=d1)
        with self.assertRaisesRegex(SnapshotError,"different build"):
            make_deployment_snapshot(build=b1,artifact=a2,runtime_binding_root=h("r"),
                runtime_image_hash=h("i"),deployment_config_hash=h("d"),infrastructure_root=h("infra"))

    def test_execution_identity_pins_request_bindings_inputs_and_effects(self):
        b=build(self.project); a=artifact(b); d=deployment(b,a)
        common=dict(deployment=d,request_binding_root=h("request-bindings"),
                    input_root=h("inputs"),external_event_root=h("io-transcript"),
                    output_root=h("outputs"),deterministic_runtime_root=h("runtime"))
        x=make_execution_snapshot(**common)
        y=make_execution_snapshot(**{**common,"external_event_root":h("different-io")})
        self.assertNotEqual(x.root_hash,y.root_hash)

    def test_execution_identity_changes_when_deployment_changes(self):
        b=build(self.project); a=artifact(b)
        d1=deployment(b,a,"prod"); d2=deployment(b,a,"canary")
        args=dict(request_binding_root=h("request"),input_root=h("input"),
                  external_event_root=h("events"),output_root=h("output"),
                  deterministic_runtime_root=h("runtime"))
        self.assertNotEqual(make_execution_snapshot(deployment=d1,**args).root_hash,
                            make_execution_snapshot(deployment=d2,**args).root_hash)

    def test_channel_cas_accepts_current_head_and_rejects_stale_writer(self):
        old=h("release-1"); new=h("release-2")
        self.assertEqual(compare_and_swap_release_head(old,old,new),new)
        with self.assertRaises(StaleHeadError):
            compare_and_swap_release_head(h("head-now"),h("head-observed"),h("new-release"))

    def test_invalid_digest_rejected(self):
        with self.assertRaises(SnapshotError):
            build("not-a-hash")

if __name__=="__main__": unittest.main()
