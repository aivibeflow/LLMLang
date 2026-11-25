"""Compare exact Dynamic Package requests with a static reference and pinned providers."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
INDEX = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-INDEX-01"
IDENTITY = INDEX.with_name("PACKAGE-IDENTITY-01")
sys.path[:0] = [str(INDEX), str(IDENTITY)]
from content_store import SQLiteContentStore, content_hash
from package_archive import build_archive, verify_archive
from package_identity import PackageFormatError, logical_index_hash, package_content_root, parse_hash, parse_manifest
from package_index import normalize
from package_provider import ProviderError, build_archive_from_snapshot


PAYLOAD = {name: f"fixture object {name}\n".encode() for name in ("app", "kernel", "linux", "documentation")}
HASH = {name: content_hash(value) for name, value in PAYLOAD.items()}
NAME = {key: name for name, key in HASH.items()}
POLICIES = ("roots_only", "closure", "closure_with_optional")
TARGETS = ("linux", "windows")
EDGES = (
    {"edge_id": "kernel", "kind": "required", "target_hash": HASH["kernel"]},
    {"edge_id": "linux", "kind": "required", "target_hash": HASH["linux"], "condition": {"target": "linux"}},
    {"edge_id": "docs", "kind": "optional", "target_hash": HASH["documentation"],
     "condition": {"feature": "docs"}},
)


@dataclass(frozen=True)
class Request:
    roots: tuple[str, ...]
    policy: str
    target: str
    docs: bool

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, dict) or set(raw) != {"roots", "policy", "target", "docs"}:
            raise ValueError("request fields must be explicit")
        roots = raw["roots"]
        if not isinstance(roots, list) or not roots or not all(isinstance(root, str) for root in roots):
            raise ValueError("root references must be exact hashes")
        try:
            for root in roots:
                parse_hash(root)
        except PackageFormatError as exc:
            raise ValueError("root references must be exact hashes") from exc
        if len(set(roots)) != len(roots):
            raise ValueError("duplicate root")
        if raw["policy"] not in POLICIES or raw["target"] not in TARGETS or type(raw["docs"]) is not bool:
            raise ValueError("unsupported dependency or feature profile")
        return cls(tuple(sorted(roots)), raw["policy"], raw["target"], raw["docs"])

    def fingerprint(self):
        return sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def conditions(self):
        return {(HASH["app"], "linux"): self.target == "linux", (HASH["app"], "docs"): self.docs}


def reference(request):
    reached = set(request.roots)
    if HASH["app"] in reached and request.policy != "roots_only":
        reached.add(HASH["kernel"])
        if request.target == "linux":
            reached.add(HASH["linux"])
        if request.policy == "closure_with_optional" and request.docs:
            reached.add(HASH["documentation"])
    typed_edges = [{"source_hash": HASH["app"], **row, "included": row["target_hash"] in reached}
                   for row in EDGES] if HASH["app"] in reached else []
    return normalize({
        "objects": [{"hash": key, "kind": "function", "size": len(PAYLOAD[NAME[key]])} for key in reached],
        "dependencies": typed_edges, "exports": [], "modules": [],
    })


def manifest(request, expected_index):
    placeholder = "sha256:" + "0" * 64
    roots = ", ".join(json.dumps(root) for root in request.roots)
    raw = f'''format = "llmlang.package"
schema_version = 1

[content]
roots = [{roots}]
dependency_policy = "{request.policy}"
content_root = "{placeholder}"

[content.resolution_inputs]
target = "{request.target}"
docs = {str(request.docs).lower()}

[index]
path = "index"
format_version = 1
logical_hash = "{logical_index_hash(expected_index)}"
'''.encode()
    actual = package_content_root(parse_manifest(raw), expected_index)
    return raw.replace(placeholder.encode(), actual.encode())


def provider(path, names, extra=False):
    store = SQLiteContentStore(path)
    for name in names:
        written = store.put_object(PAYLOAD[name], "function", EDGES if name == "app" else ())
        if written != HASH[name]:
            raise ValueError("The persistent object changed identity")
    if extra:
        store.put_object(b"unrelated provider inventory entry\n", "function", ())
    return store


def static_build(path, label, index):
    sources = ((row["hash"], BytesIO(PAYLOAD[NAME[row["hash"]]])) for row in index["objects"])
    build_archive(label, {table: iter(rows) for table, rows in index.items()}, sources, path,
                  max_records_in_memory=2)


def dynamic_build(store, request, label, path, provider_name):
    resolution = parse_manifest(label)["content"].get("resolution_inputs", {})
    if type(resolution.get("docs")) is not bool or resolution != {"target": request.target, "docs": request.docs}:
        raise ProviderError("manifest resolution profile differs from request")
    with store.open_snapshot() as snapshot:
        opaque_id = snapshot.snapshot_id
        build_archive_from_snapshot(request.roots, snapshot, label, path, policy=request.policy,
                                    condition_values=request.conditions(),
                                    max_records_in_memory=2, sqlite_cache_kib=64)
        if snapshot.snapshot_id != opaque_id:
            raise ValueError("Provider changed the active snapshot")
        return {"snapshot_id": opaque_id, "provider": provider_name}


def checked_request(**kwargs):
    return Request.parse({"roots": [HASH["app"]], "policy": "closure",
                          "target": "linux", "docs": False, **kwargs})


def rejected_requests():
    standard = {"roots": [HASH["app"]], "policy": "closure", "target": "linux", "docs": False}
    cases = {
        "nonobject-request": [standard],
        "display-name-root": {**standard, "roots": ["fixture-app"]},
        "malformed-hash-root": {**standard, "roots": ["sha256:xyz"]},
        "duplicate-root": {**standard, "roots": [HASH["app"], HASH["app"]]},
        "empty-roots": {**standard, "roots": []},
        "missing-policy": {key: value for key, value in standard.items() if key != "policy"},
        "unknown-policy": {**standard, "policy": "best-effort"},
        "unknown-target": {**standard, "target": "implicit-host"},
        "nonboolean-feature": {**standard, "docs": 1},
        "delivery-label-in-request": {**standard, "provider_label": "mirror-proxy"},
    }
    rejected = []
    for name, raw in cases.items():
        try:
            Request.parse(raw)
        except ValueError:
            rejected.append(name)
    if rejected != list(cases):
        raise AssertionError(rejected)
    return rejected


def verify(work):
    left = provider(work / "left.sqlite", PAYLOAD)
    right = provider(work / "right.sqlite", reversed(tuple(PAYLOAD)), extra=True)
    incomplete = provider(work / "incomplete.sqlite", ("app", "kernel", "documentation"))
    checked = {}
    for policy, target, docs in product(POLICIES, TARGETS, (False, True)):
        request = checked_request(policy=policy, target=target, docs=docs)
        exact_index = reference(request)
        label = manifest(request, exact_index)
        static = work / "static.llpkg"
        dynamic_left = work / "dynamic-left.llpkg"
        dynamic_right = work / "dynamic-right.llpkg"
        static_build(static, label, exact_index)
        left_delivery = dynamic_build(left, request, label, dynamic_left, "provider-a")
        right_delivery = dynamic_build(right, request, label, dynamic_right, "provider-b")
        if left_delivery["snapshot_id"] == right_delivery["snapshot_id"]:
            raise AssertionError("The provider snapshots were not independent")
        variants = [static, dynamic_left, dynamic_right]
        if not all(verify_archive(path, max_records_in_memory=2) for path in variants):
            raise AssertionError("Produced archive failed its verifier")
        artifacts = {sha256(path.read_bytes()).hexdigest() for path in variants}
        if len(artifacts) != 1:
            raise AssertionError("Equivalent closure produced distinct archives")
        checked[f"{policy}/{target}/{docs}"] = {
            "request_digest": request.fingerprint(),
            "members": sorted(NAME[row["hash"]] for row in exact_index["objects"]),
            "package_root": parse_manifest(label)["content"]["content_root"],
            "three_archive_digests_equal": artifacts.pop(),
        }

    first = checked_request(roots=[HASH["app"], HASH["kernel"]])
    second = checked_request(roots=[HASH["kernel"], HASH["app"]])
    assert first == second and first.fingerprint() == second.fingerprint()
    rejected = rejected_requests()
    for request in (checked_request(), checked_request(target="windows")):
        expected = manifest(request, reference(request))
        output = work / "incomplete.llpkg"
        output.write_bytes(b"prior publication")
        if request.target == "windows":
            dynamic_build(incomplete, request, expected, output, "missing-linux")
            assert verify_archive(output)
        else:
            try:
                dynamic_build(incomplete, request, expected, output, "missing-linux")
            except ProviderError as exc:
                if "missing exact dependency object" not in str(exc):
                    raise
            else:
                raise AssertionError("Incomplete snapshot produced an archive")
            assert output.read_bytes() == b"prior publication"

    actual_profile = checked_request(policy="roots_only")
    stale_profile = checked_request(policy="roots_only", target="windows", docs=True)
    assert reference(actual_profile) == reference(stale_profile)
    stale_label = manifest(stale_profile, reference(stale_profile))
    stale_output = work / "wrong-profile.llpkg"
    with left.open_snapshot() as snapshot:
        build_archive_from_snapshot(actual_profile.roots, snapshot, stale_label, stale_output,
                                    policy=actual_profile.policy, condition_values=actual_profile.conditions())
    assert verify_archive(stale_output)
    try:
        dynamic_build(left, actual_profile, stale_label, work / "refused-profile.llpkg", "provider-a")
    except ProviderError as exc:
        if "resolution profile differs" not in str(exc):
            raise
    else:
        raise AssertionError("A stale manifest resolution profile passed exact admission")

    roots = {item["package_root"] for item in checked.values()}
    assert len(roots) == len(checked)
    watched = (HERE / "run.py", INDEX / "package_archive.py", INDEX / "package_index.py",
               INDEX / "package_provider.py", INDEX / "content_store.py", IDENTITY / "package_identity.py")
    return {
        "sqlite": sqlite3.sqlite_version,
        "request_profiles": len(checked),
        "verified_archives": len(checked) * 3,
        "distinct_logical_roots": len(roots),
        "profiles": checked,
        "rejected_requests": rejected,
        "root_order_canonical": True,
        "absent_active_dependency_refused": True,
        "absent_inactive_dependency_safe": True,
        "prior_publication_preserved": True,
        "underlying_provider_admits_stale_profile_with_equal_closure": True,
        "exact_request_gate_refuses_stale_profile_with_equal_closure": True,
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in watched},
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-dynamic-request-") as temp:
        print(json.dumps(verify(Path(temp)), indent=2))
