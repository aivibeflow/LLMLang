"""Admit exact compiled Lean claims using signature, subject, theorem and axiom checks."""
import argparse
from dataclasses import replace
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calls = load("generated_calls", HERE.parent / "GENERATED-CALL-01" / "run.py")
audit = load("audit_signatures", HERE.parents[2] / "toolchain-and-collaboration" / "RT-24" / "AUDIT-AUTHORITY-01" / "run.py")

AUTHORITY = "fixture-lean-proof-publisher"
OTHER = "fixture-untrusted-proof-publisher"
MODULES = ("CallCore", "Caller", "Provider", "Closed")
BINDINGS = ("root", "caller", "provider", "provider_contract", "caller_contract", "reference", "binding")
ALLOWED_AXIOMS = {"propext"}


def fixture_graphs():
    trace = {"provider": calls.ORDER, "forward": (("argument", "first", "last"),), "quiet": ((),)}
    base = replace(calls.dispatch_program(), contracts=trace)
    base = calls.replace_body(base, "late", 'op("provider", emit("argument", n))')
    alternate = replace(base, bindings={"provider": "alternate"})
    return calls.subject(calls.compile_program(base), "late"), calls.subject(calls.compile_program(alternate), "late")


def compile_bundle(directory, entry, variant):
    directory.mkdir()
    closure = calls.closed_source(entry)
    original = """theorem closedClaim : conforms declared (caller actualProvider) :=
  conditional actualProvider providerChecked"""
    assert closure.count(original) == 1
    if variant == "wrong-theorem":
        closure = closure.replace(original, "theorem closedClaim : True := True.intro")
    elif variant == "foreign-axiom":
        closure = closure.replace(original, """axiom foreignAssertion : conforms declared (caller actualProvider)
theorem closedClaim : conforms declared (caller actualProvider) := foreignAssertion""")
    elif variant == "different-bundle":
        closure += "\ndef closedModuleMarker : Nat := 13\n"
    sources = {"CallCore": (calls.HERE / "CallCore.lean").read_text(encoding="utf-8"),
               "Caller": calls.caller_source(entry), "Provider": calls.provider_source(entry), "Closed": closure}
    for key, text in sources.items():
        (directory / f"{key}.lean").write_text(text, encoding="utf-8")
        calls.run_lean(directory, key, "-o", f"{key}.olean")
    return directory


def bundle(directory):
    return {path.name: sha256(path.read_bytes()).hexdigest() for module in MODULES
            for path in sorted(directory.glob(f"{module}.olean*"))}


def invoke(directory, filename, text):
    (directory / filename).write_text(text, encoding="utf-8")
    result = subprocess.run([*calls.LEAN, filename], cwd=directory, capture_output=True,
                            text=True, env={**os.environ, "LEAN_PATH": str(directory)}, timeout=45)
    return result.returncode, result.stdout.strip().splitlines()


def inspect_declaration(directory):
    prefix = "import Closed\nopen LLMLang.GeneratedCall\n"
    status, lines = invoke(directory, "InspectClaim.lean", prefix + "#check closedClaim\n#print axioms closedClaim\n")
    assert status == 0 and lines[0].startswith("closedClaim :"), lines
    summary = lines[-1]
    if summary.endswith("does not depend on any axioms"):
        axioms = []
    else:
        assert summary.startswith("'closedClaim' depends on axioms: ["), lines
        axioms = summary.split("[", 1)[1].removesuffix("]").split(", ")
    return axioms


def expected_type(directory, requested):
    body = f"""import Closed
open LLMLang.GeneratedCall
example : conforms {calls.lean_list(requested["caller_allowed"])} (caller actualProvider) :=
  closedClaim
"""
    status, lines = invoke(directory, "CheckType.lean", body)
    if status:
        assert any("Type mismatch" in line or "type mismatch" in line for line in lines), lines
    return status == 0


def expected_constants(directory, requested):
    checks = {
        "scopeRoot": requested["root"],
        "callerIdentity": requested["caller"],
        "providerIdentity": requested["provider"],
        "assumptionsIdentity": requested["provider_contract"],
        "claimIdentity": requested["caller_contract"],
        "callReference": requested["reference"],
        "selectedReference": requested["binding"] or requested["reference"],
    }
    text = "import Closed\n" + "".join(f'example : {key} = "{value}" := by rfl\n' for key, value in checks.items())
    status, lines = invoke(directory, "CheckContext.lean", text)
    if status:
        assert any("rfl" in line for line in lines), lines
    return status == 0


def subject(entry):
    return {name: entry[name] for name in BINDINGS}


def signed_receipt(publisher, key, entry, files, version, service):
    claim = {"format": "rt32-compiled-claim/1", "publisher": publisher, "toolchain": version,
             "subject": subject(entry), "theorem": "closedClaim", "compiled": files}
    return claim, service.sign(claim, key)


def verify(directory):
    base, rebound = fixture_graphs()
    base_artifact = compile_bundle(directory / "base", base, "good")
    rebound_artifact = compile_bundle(directory / "rebound", rebound, "good")
    wrong_artifact = compile_bundle(directory / "wrong-theorem", base, "wrong-theorem")
    axiom_artifact = compile_bundle(directory / "foreign-axiom", base, "foreign-axiom")
    other_artifact = compile_bundle(directory / "different-bundle", base, "different-bundle")
    private, trusted = audit.create_key(directory, AUTHORITY)
    second_key, second_public = audit.create_key(directory, OTHER)
    service = audit.Signatures(directory)
    version = subprocess.check_output([*calls.LEAN, "--version"], text=True).strip()

    base_receipt = signed_receipt(AUTHORITY, private, base, bundle(base_artifact), version, service)
    rebound_receipt = signed_receipt(AUTHORITY, private, rebound, bundle(rebound_artifact), version, service)
    wrong_receipt = signed_receipt(AUTHORITY, private, base, bundle(wrong_artifact), version, service)
    axiom_receipt = signed_receipt(AUTHORITY, private, base, bundle(axiom_artifact), version, service)
    incorrect_scope = signed_receipt(AUTHORITY, private, base, bundle(rebound_artifact), version, service)
    second_receipt = signed_receipt(OTHER, second_key, base, bundle(base_artifact), version, service)
    stale_toolchain = signed_receipt(AUTHORITY, private, base, bundle(base_artifact), "fixture-previous-toolchain", service)
    assert service.verify(*second_receipt, second_public)
    assert bundle(base_artifact)["Closed.olean"] != bundle(other_artifact)["Closed.olean"]

    cases = (
        ("base", base_artifact, base, base_receipt, "closed"),
        ("rebound", rebound_artifact, rebound, rebound_receipt, "closed"),
        ("wrong-theorem", wrong_artifact, base, wrong_receipt, "claim-mismatch"),
        ("foreign-axiom", axiom_artifact, base, axiom_receipt, "axiom-policy"),
        ("old-proof-for-rebound", base_artifact, rebound, base_receipt, "receipt-subject"),
        ("signed-wrong-compiled-context", rebound_artifact, base, incorrect_scope, "compiled-context"),
        ("different-bundle", other_artifact, base, base_receipt, "bundle-mismatch"),
        ("untrusted-issuer", base_artifact, base, second_receipt, "issuer-or-signature"),
        ("missing-signature", base_artifact, base, (base_receipt[0], None), "issuer-or-signature"),
        ("changed-toolchain", base_artifact, base, stale_toolchain, "toolchain-mismatch"),
    )
    observations = {}
    checked = {}
    for label, artifact, requested, (receipt, signature), expected in cases:
        cache_key = (artifact.name, requested["root"])
        if cache_key not in checked:
            checked[cache_key] = (inspect_declaration(artifact), expected_type(artifact, requested),
                                  expected_constants(artifact, requested))
        axioms, type_matches, context_matches = checked[cache_key]
        trusted_signer = receipt["publisher"] == AUTHORITY and service.verify(receipt, signature, trusted)
        target_matches = receipt["subject"] == subject(requested)
        bytes_match = receipt["compiled"] == bundle(artifact)
        version_match = receipt["toolchain"] == version
        allowed = set(axioms) <= ALLOWED_AXIOMS
        conditions = {
            "issuer-or-signature": trusted_signer, "receipt-subject": target_matches,
            "bundle-mismatch": bytes_match, "toolchain-mismatch": version_match, "claim-mismatch": type_matches,
            "axiom-policy": allowed, "compiled-context": context_matches,
        }
        disposition = next((reason for reason, passed in conditions.items() if not passed), "closed")
        assert disposition == expected, (label, conditions)
        observations[label] = {
            "request": subject(requested), "receipt": receipt, "signature": signature.hex() if signature else None,
            "conditions": conditions, "axioms": axioms, "full_admission": disposition,
            "signature_bundle_admission": trusted_signer and target_matches and bytes_match and version_match,
            "type_axiom_admission": type_matches and allowed,
        }
    return {"format": "rt32-compiled-proof-admission/1", "lean": version, "python": sys.version.split()[0],
            "openssl": audit.checked_openssl("version").decode().strip(), "cases": observations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt32-compiled-proof-admission-") as temporary:
        data = verify(Path(temporary))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
