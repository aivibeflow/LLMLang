"""Check layer-specific library identities against verified package delivery."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import importlib.util
import io
from itertools import product
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
PACKAGE_SOURCE = HERE.parent / "PACKAGE-CONTENT-01" / "check.py"
spec = importlib.util.spec_from_file_location("logical_package", PACKAGE_SOURCE)
PACKAGE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PACKAGE)
from package_identity import canonical, digest


API = {
    "schema": "llmlang.library-spec.fixture/v1",
    "types": {"Quantity": {"representation": "u32", "maximum": 100}},
    "operations": {
        "reserve": {
            "input": "Quantity", "output": "Quantity",
            "preconditions": [{"op": "positive", "arg": "quantity"}],
            "postconditions": [{"op": "equal", "left": "result", "right": "quantity"}],
            "errors": {"Denied": {"state": "unchanged"}},
            "effects": ["ledger-write"],
            "capabilities": ["ledger-write"],
            "state": {"before": "available", "after_success": "reserved"},
            "ownership": {"result": "caller-owned"},
        },
    },
}
DESIGN = {"layout": ["counter", "ledger"]}
IMPLEMENTATION = {"adapter": "fixture-A", "entry": "reserve", "abi": "fixture-abi:1"}
STABLE = "library:inventory"


def layer(kind, data):
    return digest(f"library-{kind}.fixture.v1", data)


def content_record(kind, data):
    raw = canonical({"kind": kind, "record": data})
    return PACKAGE.content_hash(raw), raw


def publish(scratch, label, *, contract=API, design=DESIGN, implementation=IMPLEMENTATION,
            stable=STABLE, metadata="default", second_library=False):
    layers = {"specification": layer("specification", contract)}
    if design is not None:
        layers["design"] = layer("design", design)
    if implementation is not None:
        layers["implementation"] = layer("implementation", implementation)
    library = {"stable_id": stable, "layers": layers}
    materials = [("library", library), ("public-specification", contract)]
    if design is not None:
        materials.append(("design", design))
    if implementation is not None:
        materials.append(("implementation", implementation))
    blobs = {kind: content_record(kind, row) for kind, row in materials}
    first_manifest = blobs["library"][0]
    specification_payload = blobs["public-specification"][0]
    manifests = [first_manifest]
    first_members = [identity for identity, _ in blobs.values()]
    if second_library:
        blobs["second-library"] = content_record("library", {
            "stable_id": "library:reporting", "layers": {"specification": layers["specification"]},
        })
        manifests.append(blobs["second-library"][0])
    index = {
        "objects": [{"hash": identity, "kind": kind, "size": len(raw)}
                    for kind, (identity, raw) in blobs.items()],
        "dependencies": [
            {"source_hash": blobs["library"][0], "edge_id": kind, "kind": "required",
             "target_hash": identity, "included": True}
            for kind, (identity, _) in blobs.items() if kind not in ("library", "second-library")
        ],
        "exports": [{"module_id": stable, "name": "reserve", "object_hash": blobs["public-specification"][0]}],
        "modules": [{"module_id": stable, "members": first_members}],
    }
    if second_library:
        index["dependencies"].append({"source_hash": blobs["second-library"][0],
            "edge_id": "public-specification", "kind": "required",
            "target_hash": specification_payload, "included": True})
        index["exports"].append({"module_id": "library:reporting", "name": "reserve",
                                 "object_hash": specification_payload})
        index["modules"].append({"module_id": "library:reporting",
                                 "members": [blobs["second-library"][0], specification_payload]})
    root, manifest, normalized = PACKAGE.package(index, roots=manifests, label=metadata)
    path = scratch / f"{label}.llpkg"
    streams = ((identity, io.BytesIO(raw)) for identity, raw in sorted(blobs.values()))
    PACKAGE.build_archive(manifest, normalized, streams, path, max_records_in_memory=2)
    assert PACKAGE.verify_archive(path, max_records_in_memory=2)
    return {"package_root": root, "archive": PACKAGE.content_hash(path.read_bytes()),
            "library_id": stable, "layers": layers, "library_count": len(manifests),
            "public_specification_payload": blobs["public-specification"][0]}


def gate(request, package, receipt, dependencies):
    stable, specification, mode = request
    if stable != package["library_id"] or specification != package["layers"]["specification"]:
        return "specification-mismatch"
    if mode == "inspect":
        return "specification-available"
    implementation = package["layers"].get("implementation")
    if implementation is None:
        return "implementation-unavailable"
    if receipt != (stable, specification, implementation, "fixture-abi:1"):
        return "implementation-evidence-unavailable"
    if "ledger-write" not in dependencies:
        return "capability-unavailable"
    return "eligible-for-fixture-execution"


def run(scratch):
    contract = deepcopy(API)
    contract["operations"]["reserve"]["errors"]["Denied"]["state"] = "rolled-back"
    profiles = {
        "base": publish(scratch, "base"),
        "new_carrier": publish(scratch, "new-carrier", metadata="another name"),
        "new_design": publish(scratch, "new-design", design={"layout": ["ledger", "counter"]}),
        "new_implementation": publish(scratch, "new-implementation",
                                      implementation={**IMPLEMENTATION, "adapter": "fixture-B"}),
        "new_contract": publish(scratch, "new-contract", contract=contract),
        "other_library": publish(scratch, "other-library", stable="library:warehouse"),
        "two_libraries": publish(scratch, "two-libraries", second_library=True),
        "spec_only": publish(scratch, "spec-only", design=None, implementation=None),
    }
    base = profiles["base"]
    baseline_spec, baseline_impl = (base["layers"][kind] for kind in ("specification", "implementation"))
    assert profiles["new_carrier"]["archive"] != base["archive"]
    assert profiles["new_carrier"]["package_root"] == base["package_root"]
    for label, row in profiles.items():
        assert (row["package_root"] == base["package_root"]) == (label in ("base", "new_carrier"))
        assert (row["layers"]["specification"] != baseline_spec) == (label == "new_contract")
    assert profiles["new_design"]["layers"]["implementation"] == baseline_impl
    assert profiles["new_implementation"]["layers"]["design"] == base["layers"]["design"]
    assert profiles["two_libraries"]["library_count"] == 2

    observations = Counter()
    for (name, row), mode, receipt_mode, capabilities in product(
        profiles.items(), ("inspect", "execute"), ("current", "base", "absent"), ((), ("ledger-write",))
    ):
        current = (row["library_id"], row["layers"]["specification"],
                   row["layers"].get("implementation"), "fixture-abi:1")
        receipt = {"current": current, "base": (STABLE, baseline_spec, baseline_impl, "fixture-abi:1"),
                   "absent": None}[receipt_mode]
        actual = gate((STABLE, baseline_spec, mode), row, receipt, capabilities)
        if name in ("new_contract", "other_library"):
            expected = "specification-mismatch"
        elif mode == "inspect":
            expected = "specification-available"
        elif name == "spec_only":
            expected = "implementation-unavailable"
        elif receipt_mode == "absent" or (receipt_mode == "base" and name == "new_implementation"):
            expected = "implementation-evidence-unavailable"
        else:
            expected = "eligible-for-fixture-execution" if capabilities else "capability-unavailable"
        assert actual == expected, (name, mode, receipt_mode, actual)
        observations[actual] += 1
    wrong_abi = (STABLE, baseline_spec, baseline_impl, "fixture-abi:2")
    assert gate((STABLE, baseline_spec, "execute"), base, wrong_abi, ("ledger-write",)) == (
        "implementation-evidence-unavailable")
    return {"python": platform.python_version(), "contract": API, "profiles": profiles,
            "observations": observations, "checks": sum(observations.values()),
            "wrong_abi": "implementation-evidence-unavailable",
            "sources": {str(path.relative_to(HERE.parents[1])): sha256(path.read_bytes()).hexdigest()
                        for path in (Path(__file__), PACKAGE_SOURCE,
                                     PACKAGE.IDENTITY / "package_identity.py",
                                     PACKAGE.INDEX / "package_archive.py")}}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="rt12-library-contract-") as tmp:
        print(json.dumps(run(Path(tmp)), sort_keys=True, indent=2))
