"""Compare declaration edges before Lean export and in three importer views."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
PREFIX = "ReceiptFixture."
BRIDGE = "_private.Provider.0.ReceiptFixture.providerBridge"
PREMISE = PREFIX + "environmentPremise"
GOOD = PREFIX + "checkedComposition"
CONDITIONAL = PREFIX + "conditionalComposition"
PROVIDER = PREFIX + "conditionalProvider"
MODULES = ("Inspect", "Provider", "Caller", "ImportedPublic", "ImportedAll", "ImportedLegacy", "OnlyPublic")
OLD_BRIDGE = "private theorem providerBridge (n : Nat) : ReturnsInput n := environmentPremise n"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(work, file, *, build=False, expected_exit=0):
    command = ["lean", "--json"]
    if build:
        command += ["-o", f"{file}.olean"]
    run = subprocess.run([*command, f"{file}.lean"], cwd=work, text=True, capture_output=True,
                         env={**os.environ, "LEAN_PATH": str(work)}, timeout=60)
    if run.returncode != expected_exit:
        raise ValueError(run.stdout + run.stderr)
    messages = [json.loads(line)["data"].strip() for line in run.stdout.splitlines()]
    return {record["subject"]: record for line in messages if line.startswith("RECEIPT ")
            for record in [json.loads(line.removeprefix("RECEIPT "))]}, messages


def compile_case(work, provider_edit=None):
    work.mkdir()
    for module in MODULES:
        source = (HERE / f"{module}.lean").read_text(encoding="utf-8")
        if module == "Provider" and provider_edit:
            require(source.count(OLD_BRIDGE) == 1, "Provider mutation anchor absent")
            source = source.replace(OLD_BRIDGE, provider_edit)
            if "providerRelay" in source:
                source += "\n#inspect_receipt ReceiptFixture.providerRelay\n"
        if module == "ImportedAll" and provider_edit and "providerRelay" in provider_edit:
            source += "\n#inspect_receipt ReceiptFixture.providerRelay\n"
        (work / f"{module}.lean").write_text(source, encoding="utf-8")
    build = {module: invoke(work, module, build=True)[0] for module in MODULES[:3]}
    views = {module: invoke(work, module)[0] for module in MODULES[3:6]}
    _, public_check = invoke(work, "OnlyPublic")
    require(any(GOOD in message for message in public_check), "Public import did not expose the theorem type")
    artifacts = {path.name: sha256(path.read_bytes()).hexdigest()
                 for module in ("Provider", "Caller") for path in work.glob(f"{module}.olean*")}
    return {"build": build, "views": views, "compiled_sha256": artifacts}


def check_baseline(evidence):
    build = evidence["build"]
    public = evidence["views"]["ImportedPublic"]
    complete = evidence["views"]["ImportedAll"]
    legacy = evidence["views"]["ImportedLegacy"]
    require(not public[GOOD]["has_value"] and not public[CONDITIONAL]["has_value"],
            "Public import unexpectedly exposed proof terms")
    require(public[GOOD]["type_constants"] == public[CONDITIONAL]["type_constants"],
            "Two statements should have the same type dependencies")
    require(public[GOOD]["transitive_axioms"] == ["propext"]
            and public[CONDITIONAL]["transitive_axioms"] == [PREMISE],
            "Public export lost the exact axiom summary")
    require(build["Caller"][CONDITIONAL]["value_constants"] == [PROVIDER]
            and not build["Caller"][PROVIDER]["has_value"],
            "Building the caller should see its own body and hide the imported provider body")
    for claim, required in ((CONDITIONAL, PROVIDER), (PROVIDER, BRIDGE), (BRIDGE, PREMISE)):
        require(complete[claim]["value_constants"] == [required] and complete[claim]["has_value"],
                f"Import-all did not expose expected edge {claim} -> {required}")
        from_build = build["Caller"] if claim == CONDITIONAL else build["Provider"]
        require(complete[claim] == from_build[claim], "Reconstructed edge differs from same-module extraction")
    require(all(legacy[name] == complete[name] for name in legacy), "Legacy view differed on shared queried declarations")


def main():
    version = subprocess.check_output(["lean", "--version"], text=True).strip()
    require("version 4.36.0" in version, version)
    with tempfile.TemporaryDirectory(prefix="llmlang-lean-deps-") as directory:
        root = Path(directory)
        base_path = root / "base"
        base = compile_case(base_path)
        check_baseline(base)

        for module in ("Provider", "Caller"):
            path = base_path / f"{module}.olean.private"
            path.rename(base_path / f"{module}.private.saved")
        rejected_without_private = []
        for view in ("OnlyPublic", "ImportedPublic", "ImportedAll"):
            _, errors = invoke(base_path, view, expected_exit=1)
            require(any("Caller.olean.private" in line for line in errors), f"{view} failed for another reason")
            rejected_without_private.append(view)

        extra_hop = ("private theorem providerRelay (n : Nat) : ReturnsInput n := environmentPremise n\n\n"
                     "private theorem providerBridge (n : Nat) : ReturnsInput n := providerRelay n")
        extra = compile_case(root / "extra", extra_hop)
        closed = compile_case(root / "closed", OLD_BRIDGE.replace("environmentPremise n", "checkedProvider n"))
        refactored_public = extra["views"]["ImportedPublic"]
        require(refactored_public == base["views"]["ImportedPublic"], "Extra hop changed public observations")
        changed_bridge = extra["views"]["ImportedAll"][BRIDGE]["value_constants"]
        require(changed_bridge == ["_private.Provider.0.ReceiptFixture.providerRelay"], changed_bridge)
        require(extra["compiled_sha256"]["Provider.olean.private"] != base["compiled_sha256"]["Provider.olean.private"],
                "Private binding failed to distinguish changed proof graph")
        require(extra["compiled_sha256"]["Provider.olean"] == base["compiled_sha256"]["Provider.olean"],
                "Expected public artifact bytes to remain identical")
        require(all(value == extra["compiled_sha256"][path] for path, value in base["compiled_sha256"].items()
                    if path.startswith("Caller.")), "Expected the unchanged caller's files to remain identical")
        require(closed["views"]["ImportedPublic"][CONDITIONAL]["transitive_axioms"] == ["propext"],
                "Discharged proof still reports a foreign premise")
        require(closed["views"]["ImportedPublic"][CONDITIONAL]["type_constants"] == base["views"]["ImportedPublic"][CONDITIONAL]["type_constants"],
                "Changing proof should not change public theorem type")

    controls = {
        "cli_views_rejected_with_private_files_removed": rejected_without_private,
        "extra_private_edge": changed_bridge,
        "extra_hop_public_provider_olean_same": True,
        "extra_hop_private_provider_olean_same": False,
        "extra_hop_all_caller_compiled_files_same": True,
        "discharged_public_composition_axioms": closed["views"]["ImportedPublic"][CONDITIONAL]["transitive_axioms"],
        "proof_statement_constants_unchanged": True,
    }
    inputs = [HERE / f"{module}.lean" for module in MODULES] + [Path(__file__)]
    observed = {"lean": version, "inputs_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in inputs},
                "baseline": base, "extra_private_hop": extra, "discharged": closed, "controls": controls}
    print(json.dumps(observed, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
