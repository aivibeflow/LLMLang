"""Layered immutable identities for build, deployment, execution, and release.

The module is an experimental model. Mutable channel heads are deliberately
separate from immutable manifests and require compare-and-swap publication.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .semantic_graph import digest

class SnapshotError(ValueError):
    pass

class StaleHeadError(SnapshotError):
    pass

def _require_hash(label: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise SnapshotError(f"{label} must be a 64-character SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SnapshotError(f"{label} must be a 64-character SHA-256 hex digest") from exc

@dataclass(frozen=True)
class BuildSnapshot:
    root_hash: str
    project_root: str
    build_binding_root: str
    target_platform_hash: str
    execution_platform_hash: str
    toolchain_root: str
    dependency_lock_root: str
    build_config_hash: str

@dataclass(frozen=True)
class DeploymentSnapshot:
    root_hash: str
    build_root: str
    runtime_binding_root: str
    runtime_image_hash: str
    deployment_config_hash: str
    infrastructure_root: str

@dataclass(frozen=True)
class ExecutionSnapshot:
    root_hash: str
    deployment_root: str
    request_binding_root: str
    input_root: str
    external_event_root: str
    output_root: str
    deterministic_runtime_root: str

@dataclass(frozen=True)
class ReleaseManifest:
    root_hash: str
    project_root: str
    build_root: str
    deployment_root: str
    parent_release_roots: tuple[str, ...] = ()

def make_build_snapshot(*, project_root: str, build_binding_root: str,
                        target_platform_hash: str, execution_platform_hash: str,
                        toolchain_root: str, dependency_lock_root: str,
                        build_config_hash: str) -> BuildSnapshot:
    fields = locals()
    for name, value in fields.items():
        _require_hash(name, value)
    root = digest({"domain":"llmlang.build-snapshot.v1", **fields})
    return BuildSnapshot(root, project_root, build_binding_root,
                         target_platform_hash, execution_platform_hash,
                         toolchain_root, dependency_lock_root, build_config_hash)

def make_deployment_snapshot(*, build: BuildSnapshot, runtime_binding_root: str,
                             runtime_image_hash: str, deployment_config_hash: str,
                             infrastructure_root: str) -> DeploymentSnapshot:
    for name, value in {
        "runtime_binding_root":runtime_binding_root,
        "runtime_image_hash":runtime_image_hash,
        "deployment_config_hash":deployment_config_hash,
        "infrastructure_root":infrastructure_root,
    }.items():
        _require_hash(name,value)
    fields={"build_root":build.root_hash,
            "runtime_binding_root":runtime_binding_root,
            "runtime_image_hash":runtime_image_hash,
            "deployment_config_hash":deployment_config_hash,
            "infrastructure_root":infrastructure_root}
    root=digest({"domain":"llmlang.deployment-snapshot.v1",**fields})
    return DeploymentSnapshot(root, **fields)

def make_execution_snapshot(*, deployment: DeploymentSnapshot,
                            request_binding_root: str, input_root: str,
                            external_event_root: str, output_root: str,
                            deterministic_runtime_root: str) -> ExecutionSnapshot:
    fields={"deployment_root":deployment.root_hash,
            "request_binding_root":request_binding_root,
            "input_root":input_root,
            "external_event_root":external_event_root,
            "output_root":output_root,
            "deterministic_runtime_root":deterministic_runtime_root}
    for name,value in fields.items(): _require_hash(name,value)
    root=digest({"domain":"llmlang.execution-snapshot.v1",**fields})
    return ExecutionSnapshot(root,**fields)

def make_release_manifest(*, project_root: str, build: BuildSnapshot,
                          deployment: DeploymentSnapshot,
                          parent_release_roots: Iterable[str] = ()) -> ReleaseManifest:
    _require_hash("project_root",project_root)
    if build.project_root != project_root:
        raise SnapshotError("build snapshot belongs to a different project root")
    if deployment.build_root != build.root_hash:
        raise SnapshotError("deployment snapshot belongs to a different build")
    parents=tuple(sorted(set(parent_release_roots)))
    for parent in parents: _require_hash("parent_release_root",parent)
    fields={"project_root":project_root,"build_root":build.root_hash,
            "deployment_root":deployment.root_hash,"parent_release_roots":parents}
    root=digest({"domain":"llmlang.release-manifest.v1",**fields})
    return ReleaseManifest(root,project_root,build.root_hash,deployment.root_hash,parents)

def compare_and_swap_release_head(current_root: str | None,
                                  expected_root: str | None,
                                  new_release_root: str) -> str:
    """Pure model of atomic publication; storage must enforce this CAS atomically."""
    if current_root != expected_root:
        raise StaleHeadError("release channel head changed; re-read and rebase")
    _require_hash("new_release_root",new_release_root)
    return new_release_root
