import unittest
from src.execution import (
    SnapshotError, StaleHeadError, compare_and_swap_release_head,
    make_build_snapshot, make_deployment_snapshot, make_execution_snapshot,
    make_release_manifest,
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

def deployment(b, runtime_binding="runtime-prod", image="runtime-v1"):
    return make_deployment_snapshot(
        build=b, runtime_binding_root=h(runtime_binding),
        runtime_image_hash=h(image), deployment_config_hash=h("deploy-config"),
        infrastructure_root=h("infra-prod"),
    )

class LayeredSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.project=make_snapshot({"module":h("module-v1")}).root_hash

    def test_runtime_binding_change_does_not_change_project_or_build(self):
        b=build(self.project)
        prod=deployment(b,"runtime-prod")
        staging=deployment(b,"runtime-staging")
        self.assertEqual(b.project_root,self.project)
        self.assertEqual(prod.build_root,staging.build_root)
        self.assertNotEqual(prod.root_hash,staging.root_hash)

    def test_build_toolchain_change_does_not_change_project(self):
        a=build(self.project,toolchain="clang-1")
        b=build(self.project,toolchain="clang-2")
        self.assertEqual(a.project_root,b.project_root)
        self.assertNotEqual(a.root_hash,b.root_hash)

    def test_two_deployments_can_share_same_project_and_build(self):
        b=build(self.project)
        prod=deployment(b,"prod")
        test=deployment(b,"test")
        rp=make_release_manifest(project_root=self.project,build=b,deployment=prod)
        rt=make_release_manifest(project_root=self.project,build=b,deployment=test)
        self.assertEqual(rp.project_root,rt.project_root)
        self.assertEqual(rp.build_root,rt.build_root)
        self.assertNotEqual(rp.root_hash,rt.root_hash)

    def test_release_manifest_rejects_crossed_project_or_build(self):
        b1=build(self.project)
        b2=build(h("other-project"))
        d1=deployment(b1)
        with self.assertRaisesRegex(SnapshotError,"different project"):
            make_release_manifest(project_root=h("other-project"),build=b1,deployment=d1)
        d2=deployment(b2)
        with self.assertRaisesRegex(SnapshotError,"different build"):
            make_release_manifest(project_root=self.project,build=b1,deployment=d2)

    def test_execution_identity_pins_request_bindings_inputs_and_effects(self):
        b=build(self.project); d=deployment(b)
        common=dict(deployment=d,request_binding_root=h("request-bindings"),
                    input_root=h("inputs"),external_event_root=h("io-transcript"),
                    output_root=h("outputs"),deterministic_runtime_root=h("runtime"))
        a=make_execution_snapshot(**common)
        changed=make_execution_snapshot(**{**common,"external_event_root":h("different-io")})
        self.assertNotEqual(a.root_hash,changed.root_hash)

    def test_execution_identity_changes_when_deployment_changes(self):
        b=build(self.project); d1=deployment(b,"prod")
        d2=deployment(b,"canary")
        args=dict(request_binding_root=h("request"),input_root=h("input"),
                  external_event_root=h("events"),output_root=h("output"),
                  deterministic_runtime_root=h("runtime"))
        self.assertNotEqual(make_execution_snapshot(deployment=d1,**args).root_hash,
                            make_execution_snapshot(deployment=d2,**args).root_hash)

    def test_channel_compare_and_swap_accepts_current_head(self):
        old=h("release-1"); new=h("release-2")
        self.assertEqual(compare_and_swap_release_head(old,old,new),new)

    def test_channel_compare_and_swap_rejects_stale_writer(self):
        with self.assertRaises(StaleHeadError):
            compare_and_swap_release_head(h("head-now"),h("head-observed"),h("new-release"))

    def test_invalid_digest_rejected(self):
        with self.assertRaises(SnapshotError):
            make_build_snapshot(project_root="not-a-hash",build_binding_root=h("b"),
                target_platform_hash=h("t"),execution_platform_hash=h("e"),
                toolchain_root=h("tc"),dependency_lock_root=h("d"),build_config_hash=h("c"))

if __name__=="__main__": unittest.main()
