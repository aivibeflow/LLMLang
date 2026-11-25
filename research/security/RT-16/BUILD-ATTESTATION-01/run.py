"""Compare repeatable native artifacts with signed, scoped build attestations."""

import argparse
import ctypes
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
DEFAULT_EPOCH = 1_700_000_000
BASE_FLAGS = ("-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", "-fPIC", "-shared")
CANONICAL_MAP = "-ffile-prefix-map={checkout}=/fixture"
POLICY = "build-attestation-v1"


@dataclass(frozen=True)
class Build:
    source: bytes
    epoch: int = DEFAULT_EPOCH
    canonicalize_path: bool = True
    extra_flag: str = ""


@dataclass(frozen=True)
class Statement:
    payload: bytes
    signature: bytes


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return sha256(value).hexdigest()


def execute(args, directory, *, check=True, environment=None):
    return subprocess.run(args, cwd=directory, check=check, text=True, capture_output=True,
                          timeout=60, env={**os.environ, "LC_ALL": "C", **(environment or {})})


def toolchain(args, work):
    compiler = Path(shutil.which(args.cc) or args.cc).resolve()
    ld_name = execute([str(compiler), "-print-prog-name=ld"], work).stdout.strip()
    linker = Path(shutil.which(ld_name) or ld_name).resolve()
    return {
        "compiler_version": execute([str(compiler), "--version"], work).stdout.splitlines()[0],
        "compiler_sha256": digest(compiler.read_bytes()),
        "linker_version": execute([str(linker), "--version"], work).stdout.splitlines()[0],
        "linker_sha256": digest(linker.read_bytes()),
        "target": execute([str(compiler), "-dumpmachine"], work).stdout.strip(),
    }


def build(args, work, label, recipe, tools):
    directory = work / label
    directory.mkdir()
    source = directory / "probe.c"
    source.write_bytes(recipe.source)
    artifact = directory / "probe.so"
    flags = list(BASE_FLAGS)
    if recipe.canonicalize_path:
        flags.append(CANONICAL_MAP)
    if recipe.extra_flag:
        flags.append(recipe.extra_flag)
    native_flags = [flag.replace("{checkout}", str(directory)) for flag in flags]
    execute([args.cc, *native_flags, str(source), "-o", str(artifact)], directory,
            environment={"SOURCE_DATE_EPOCH": str(recipe.epoch)})
    library = ctypes.CDLL(str(artifact))
    for operation in ("fixture_filename", "fixture_timestamp"):
        function = getattr(library, operation)
        function.restype = ctypes.c_char_p
        function.argtypes = []
    file = library.fixture_filename().decode("ascii")
    display = "/fixture/probe.c" if recipe.canonicalize_path else str(source)
    stamp = library.fixture_timestamp().decode("ascii")
    wanted_time = datetime.fromtimestamp(recipe.epoch, timezone.utc).strftime("%b %e %Y %H:%M:%S")
    if (file, stamp) != (display, wanted_time):
        raise ValueError((label, file, stamp))
    predicate = {
        "recipe": digest(canonical({"toolchain": tools, "flags": flags, "locale": "C",
                                     "source_date_epoch": recipe.epoch,
                                     "path_binding": "/fixture" if recipe.canonicalize_path else str(directory),
                                     "source_sha256": digest(recipe.source)})),
        "source_sha256": digest(recipe.source),
        "subject_sha256": digest(artifact.read_bytes()),
        "policy": POLICY,
    }
    return predicate, {"path": "mapped" if recipe.canonicalize_path else "physical",
                       "timestamp": stamp, "value": library.fixture_value()}


def keys(openssl, work, builder):
    private = work / f"{builder}.key"
    public = work / f"{builder}.pub"
    execute([openssl, "genpkey", "-algorithm", "Ed25519", "-out", str(private)], work)
    execute([openssl, "pkey", "-in", str(private), "-pubout", "-out", str(public)], work)
    return private, public


def sign(openssl, work, key, payload):
    claim = work / "claim.json"
    signature = work / "claim.sig"
    raw = canonical(payload)
    claim.write_bytes(raw)
    execute([openssl, "pkeyutl", "-sign", "-rawin", "-inkey", str(key),
             "-in", str(claim), "-out", str(signature)], work)
    return Statement(raw, signature.read_bytes())


def verify(openssl, work, authorities, statement, expected):
    payload = json.loads(statement.payload)
    authority = authorities.get(payload["builder"])
    if authority is None:
        return False, False
    claim = work / "verified.json"
    signature = work / "verified.sig"
    claim.write_bytes(statement.payload)
    signature.write_bytes(statement.signature)
    verified = execute([openssl, "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(authority),
                        "-in", str(claim), "-sigfile", str(signature)], work, check=False).returncode == 0
    subject = verified and payload["predicate"].get("subject_sha256") == expected["subject_sha256"]
    exact = subject and payload["predicate"] == expected
    return subject, exact


def measure(args, work):
    tools = toolchain(args, work)
    baseline = Build((HERE / "probe.c").read_bytes())
    fixtures = {
        "reference-a": baseline,
        "independent-checkout-b": baseline,
        "comment-only": replace(baseline, source=baseline.source.replace(b"original comment", b"modified comment")),
        "unused-flag": replace(baseline, extra_flag="-DFIXTURE_UNUSED=1"),
        "physical-checkout-path-a": replace(baseline, canonicalize_path=False),
        "physical-checkout-path-b": replace(baseline, canonicalize_path=False),
        "new-epoch": replace(baseline, epoch=DEFAULT_EPOCH + 60),
        "changed-output": replace(baseline, source=baseline.source.replace(b"return 42", b"return 43")),
    }
    actual = {name: build(args, work, name, recipe, tools) for name, recipe in fixtures.items()}
    expected = actual["reference-a"][0]
    physical_a = actual["physical-checkout-path-a"][0]
    physical_b = actual["physical-checkout-path-b"][0]
    if (physical_a["subject_sha256"] == physical_b["subject_sha256"]
            or physical_a["recipe"] == physical_b["recipe"]):
        raise AssertionError("The physical paths must remain distinct inputs and observations")
    reproducibility = {}
    for label, (predicate, observations) in actual.items():
        same = predicate["subject_sha256"] == expected["subject_sha256"]
        if same != (label in {"reference-a", "independent-checkout-b", "comment-only", "unused-flag"}):
            raise AssertionError((label, "unexpected artifact correspondence"))
        if (predicate["recipe"] == expected["recipe"]) != (label in {"reference-a", "independent-checkout-b"}):
            raise AssertionError((label, "unexpected recipe correspondence"))
        if observations["value"] != (43 if label == "changed-output" else 42):
            raise AssertionError((label, observations))
        reproducibility[label] = {"same_artifact": same, "same_recipe": predicate["recipe"] == expected["recipe"],
                                  "observations": observations}
        if not label.startswith("physical-checkout-path-"):
            reproducibility[label]["selected_artifact_sha256"] = predicate["subject_sha256"]

    signer_a, public_a = keys(args.openssl, work, "builder-a")
    signer_b, public_b = keys(args.openssl, work, "builder-b")
    outsider, _ = keys(args.openssl, work, "outsider")
    trusted = {"builder-a": public_a, "builder-b": public_b}
    reference_payload = {"builder": "builder-a", "predicate": expected}
    reference = sign(args.openssl, work, signer_a, reference_payload)
    checks = {
        "reference-a": (reference, (True, True)),
        "independent-builder-b": (
            sign(args.openssl, work, signer_b,
                 {"builder": "builder-b", "predicate": actual["independent-checkout-b"][0]}), (True, True)),
        "identical-artifact-different-source": (
            sign(args.openssl, work, signer_a,
                 {"builder": "builder-a", "predicate": actual["comment-only"][0]}), (True, False)),
        "identical-artifact-different-flags": (
            sign(args.openssl, work, signer_a,
                 {"builder": "builder-a", "predicate": actual["unused-flag"][0]}), (True, False)),
        "wrong-policy": (
            sign(args.openssl, work, signer_a,
                 {"builder": "builder-a", "predicate": {**expected, "policy": "older-policy"}}), (True, False)),
        "subject-only": (
            sign(args.openssl, work, signer_a, {"builder": "builder-a",
                 "predicate": {"subject_sha256": expected["subject_sha256"]}}), (True, False)),
        "changed-artifact": (
            sign(args.openssl, work, signer_a,
                 {"builder": "builder-a", "predicate": actual["changed-output"][0]}), (False, False)),
        "untrusted-builder": (
            sign(args.openssl, work, outsider, {"builder": "outsider", "predicate": expected}), (False, False)),
        "signature-by-wrong-builder": (
            sign(args.openssl, work, outsider, reference_payload), (False, False)),
        "tampered-signed-predicate": (
            replace(reference, payload=canonical(
                {"builder": "builder-a", "predicate": {**expected, "policy": "modified-after-signing"}}
            )), (False, False)),
    }
    admissions = {}
    for name, (statement, intended) in checks.items():
        got = verify(args.openssl, work, trusted, statement, expected)
        if got != intended:
            raise AssertionError((name, intended, got))
        admissions[name] = {"signed_subject_only": got[0], "exact_signed_predicate": got[1]}
    return {
        "toolchain": tools,
        "openssl": execute([args.openssl, "version"], work).stdout.strip(),
        "trusted_profile": expected,
        "native_reproducibility": reproducibility,
        "admissions": admissions,
        "sources": {name: digest((HERE / name).read_bytes()) for name in ("probe.c", "run.py")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--openssl", default="openssl")
    options = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-build-attestation-") as directory:
        print(json.dumps(measure(options, Path(directory)), indent=2))
