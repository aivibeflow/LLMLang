"""Verify safe local cross-workspace proof cache reuse and exact envelope migration."""
import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations
import json
import os
from pathlib import Path
import re
import runpy
from stat import S_ISREG
from subprocess import run
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PIN = "c0196a202f648f8c62125591611324044f855caf"
DEFINITION = ROOT / "research/formal-verification/RT-32/LEAN-ARTIFACT-REPLAY-01/Defs.lean"
SIGNED = ROOT / "research/toolchain-and-collaboration/RT-11/SIGNED-REBUILD-ADMISSION-01/run.py"
SIGNERS = runpy.run_path(str(SIGNED))
DIGEST = re.compile(r"[a-f0-9]{64}")
LABELS = re.compile(r"[a-z][a-z0-9/-]*")
ROLES = {"import-source": "Defs.lean", "claim-type": "Claim.txt"}
CLAIM = b"forall n : Nat, CacheTrial.step n = n\n"
TERM = b"fun n => Eq.refl (CacheTrial.step n)"
MAX_RECEIPT = 4096
MAX_EVIDENCE = 1024
MAX_SOURCE = 4096
PROFILE = "lean-term/simple-forall-v1"
BRANCH = "research/all"


def digest(value):
    return sha256(value).hexdigest()


def strict_dict(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("unexpected object fields")
    return value


def label(value):
    if not isinstance(value, str) or not LABELS.fullmatch(value):
        raise ValueError("invalid label")
    return value


def exact_digest(value):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ValueError("invalid digest")
    return value


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


@dataclass(frozen=True)
class Request:
    project: str
    profile: str
    roles: tuple[tuple[str, str], ...]
    checker: str
    artifact: str
    issuer: str
    epoch: int


def decode(raw):
    if len(raw) > MAX_RECEIPT:
        raise ValueError("oversize receipt")
    try:
        outer = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (RecursionError, UnicodeDecodeError) as error:
        raise ValueError("invalid receipt encoding") from error
    if not isinstance(outer, dict) or type(outer.get("version")) is not int:
        raise ValueError("invalid version")
    if outer["version"] == 1:
        data = strict_dict(outer, ("version", "project", "profile", "inputs", "checker", "artifact", "issuer", "epoch"))
        if not isinstance(data["inputs"], list):
            raise ValueError("invalid v1 inventory")
        entries = []
        for item in data["inputs"]:
            strict_dict(item, ("role", "sha256"))
            if not isinstance(item["role"], str):
                raise ValueError("invalid input role")
            entries.append((item["role"], item["sha256"]))
        roles = unique(entries)
    elif outer["version"] == 2:
        strict_dict(outer, ("version", "subject", "scope", "result", "issuer", "epoch"))
        subject = strict_dict(outer["subject"], ("project", "profile", "branch"))
        if subject["branch"] != BRANCH:
            raise ValueError("invalid branch")
        scope = strict_dict(outer["scope"], ("deps",))
        result = strict_dict(outer["result"], ("checker", "artifact"))
        data = {**outer, **subject, **result}
        roles = scope["deps"]
    else:
        raise ValueError("unsupported version")
    strict_dict(roles, ROLES)
    if type(data["epoch"]) is not int or data["epoch"] < 0:
        raise ValueError("invalid epoch")
    return Request(label(data["project"]), label(data["profile"]),
                   tuple(sorted((role, exact_digest(address)) for role, address in roles.items())),
                   exact_digest(data["checker"]), exact_digest(data["artifact"]),
                   label(data["issuer"]), data["epoch"])


def v1(request, roles):
    return {
        "version": 1, "project": request.project, "profile": request.profile,
        "inputs": [{"role": role, "sha256": address} for role, address in roles],
        "checker": request.checker, "artifact": request.artifact,
        "issuer": request.issuer, "epoch": request.epoch,
    }


def v2(request):
    return {
        "version": 2, "subject": {"project": request.project, "profile": request.profile, "branch": BRANCH},
        "scope": {"deps": dict(request.roles)}, "result": {"checker": request.checker, "artifact": request.artifact},
        "issuer": request.issuer, "epoch": request.epoch,
    }


def git(directory, *args):
    environment = {
        "PATH": os.environ["PATH"], "LC_ALL": "C", "GIT_AUTHOR_NAME": "Research fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Research fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid", "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    process = run(["git", *args], cwd=directory, env=environment, capture_output=True, check=True, timeout=12)
    return process.stdout.strip()


def create(directory):
    directory.mkdir()
    git(directory, "init", "--quiet", "--initial-branch", BRANCH, "--object-format=sha1")
    (directory / "Defs.lean").write_bytes(DEFINITION.read_bytes())
    (directory / "Claim.txt").write_bytes(CLAIM)
    (directory / "Notes.md").write_text("# Unrelated notes\n")
    git(directory, "add", "Defs.lean", "Claim.txt", "Notes.md")
    git(directory, "commit", "--quiet", "-m", "Add exact source fixture")


def read_worktree(directory):
    if git(directory, "branch", "--show-current").decode() != BRANCH:
        raise ValueError("wrong worktree branch")
    captured = {}
    for role, source in ROLES.items():
        path = directory / source
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source_file:
            if not S_ISREG(os.fstat(source_file.fileno()).st_mode):
                raise ValueError("non-regular source")
            data = source_file.read(MAX_SOURCE + 1)
            if len(data) > MAX_SOURCE:
                raise ValueError("oversize source")
            captured[role] = data
    return captured


def scope(captured):
    return tuple(sorted((role, digest(data)) for role, data in captured.items()))


def replay_lean(lean, captured, artifact, work):
    # Only the closed specimen's source profiles and proof term reach the Lean process.
    approved_source = DEFINITION.read_bytes()
    source = captured["import-source"]
    if (artifact != TERM or captured["claim-type"] != CLAIM
            or source not in {approved_source, approved_source.replace(b"n + 0", b"n + 1")}):
        return False
    env = {**os.environ, "LEAN_PATH": str(work), "LC_ALL": "C"}
    (work / "Defs.lean").write_bytes(source)
    (work / "Check.lean").write_bytes(
        b"import Defs\ntheorem replayed : "
        + b"\xe2\x88\x80 n : Nat, CacheTrial.step n = n := " + artifact + b"\n#print axioms replayed\n"
    )
    for args in (("-o", "Defs.olean", "Defs.lean"), ("Check.lean",)):
        result = run([lean, "-DwarningAsError=true", *args], cwd=work, env=env, capture_output=True, timeout=12)
        if result.returncode:
            return False
    return result.stdout.strip() == b"'replayed' does not depend on any axioms"


def approve(signed, directory, project, expected_checker, issuer, epoch, signer, cas, lean):
    try:
        request = decode(signed.message)
    except ValueError:
        return "receipt-refused"
    if request.issuer != issuer or not signer.verify(signed, issuer):
        return "signature-refused"
    if (request.project, request.profile, request.checker, request.epoch) != (
        project, PROFILE, expected_checker, epoch,
    ):
        return "authority-or-checker-refused"
    try:
        captured = read_worktree(directory)
    except (ValueError, OSError):
        return "worktree-source-refused"
    if request.roles != scope(captured):
        return "source-scope-refused"
    data = cas.get(request.artifact)
    if data is None or len(data) > MAX_EVIDENCE or digest(data) != request.artifact:
        return "cas-refused"
    with TemporaryDirectory() as temp:
        if not replay_lean(lean, captured, data, Path(temp)):
            return "checker-refused"
    return "checked"


def experiment(root, lean):
    origin, project_b = root / "origin", root / "project-b"
    create(origin)
    create(project_b)
    metadata, dirty = root / "metadata", root / "dirty"
    for work in (metadata, dirty):
        git(root, "clone", "--quiet", "--no-hardlinks", "--branch", BRANCH, origin, work)
    original_head = git(origin, "rev-parse", "HEAD").decode()
    assert git(project_b, "rev-parse", "HEAD").decode() == original_head
    assert git(metadata, "rev-parse", "HEAD").decode() == original_head

    signers = root / "signers"
    signers.mkdir()
    signer = SIGNERS["Signers"](signers)
    version = run([lean, "--version"], check=True, capture_output=True).stdout.decode().strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    runtime = lean.parent.parent / "lib/lean"
    checker = digest(SIGNERS["encoded"]([version, *(digest(path.read_bytes()) for path in
                     (lean, runtime / "libleanshared.so", runtime / "Init.olean"))]))
    template = Request("project-a", PROFILE, scope(read_worktree(origin)), checker, digest(TERM), "alice", 4)
    verified = signer.sign(v2(template))
    cas = {template.artifact: TERM}

    def decision(signed, tree=origin, project="project-a", issuer="alice",
                 epoch=4, executable=checker, content=cas):
        return approve(signed, tree, project, executable, issuer, epoch, signer, content, lean)

    checks = {"origin": decision(verified), "unchanged-clone": decision(verified, metadata)}
    (metadata / "Notes.md").write_text("# Edited unrelated notes\n")
    git(metadata, "add", "Notes.md")
    git(metadata, "commit", "--quiet", "-m", "Revise unrelated notes")
    assert git(metadata, "rev-parse", "HEAD").decode() != original_head
    checks["clone-changed-only-notes"] = decision(verified, metadata)
    checks["foreign-project-same-commit"] = decision(verified, project_b, project="project-b", issuer="alice")
    assigned = replace(template, project="project-b", issuer="bob")
    checks["foreign-project-new-exact-authority"] = decision(
        signer.sign(v2(assigned)), project_b, project="project-b", issuer="bob")

    (dirty / "Defs.lean").write_bytes(DEFINITION.read_bytes().replace(b"n + 0", b"n + 1"))
    assert git(dirty, "rev-parse", "HEAD").decode() == original_head
    checks["dirty-relevant-source-with-same-head"] = decision(verified, dirty)
    fresh_source = replace(template, roles=scope(read_worktree(dirty)))
    checks["fresh-signed-different-semantics"] = decision(signer.sign(v2(fresh_source)), dirty)
    (dirty / "Defs.lean").unlink()
    (dirty / "Defs.lean").symlink_to(origin / "Defs.lean")
    checks["source-symlink"] = decision(verified, dirty)

    old = signer.sign(v1(template, template.roles))
    assert decision(old) == "checked"
    migrated = {SIGNERS["encoded"](v2(decode(signer.sign(v1(template, order)).message)))
                for order in permutations(template.roles)}
    assert migrated == {verified.message} and old.message != verified.message
    checks["migrated-same-evidence-fresh-signature"] = decision(signer.sign(v2(decode(old.message))))
    checks["reused-v1-signature-over-v2"] = decision(replace(old, message=verified.message))
    checks["missing-cas"] = decision(verified, content={})
    checks["corrupt-cas"] = decision(verified, content={template.artifact: b"altered"})
    checks["other-checker"] = decision(verified, executable="0" * 64)
    checks["stale-epoch"] = decision(verified, epoch=5)
    checks["unexpected-signer"] = decision(signer.sign(v2(replace(template, issuer="visitor"))))
    alternative = b"unapproved term"
    signed_hash = replace(template, artifact=digest(alternative))
    checks["signed-but-unsupported-artifact"] = decision(
        signer.sign(v2(signed_hash)), content={signed_hash.artifact: alternative})

    for label_name, wire in {
        "oversize": b" " * (MAX_RECEIPT + 1),
        "unrecognized-version": SIGNERS["encoded"]({**v2(template), "version": 3}),
        "floating-version": SIGNERS["encoded"]({**v2(template), "version": 2.0}),
        "extra-field": SIGNERS["encoded"]({**v2(template), "untrusted_path": "../Defs.lean"}),
        "duplicate-key": verified.message.replace(b'"version":2', b'"version":2,"version":2'),
        "missing-dependency": SIGNERS["encoded"](v1(template, template.roles[:1])),
        "invalid-artifact-hash": SIGNERS["encoded"](v2(replace(template, artifact="00"))),
        "invalid-utf8": b"\xff",
    }.items():
        checks[label_name] = decision(replace(verified, message=wire))
        assert checks[label_name] == "receipt-refused"

    assert {name for name, value in checks.items() if value == "checked"} == {
        "origin", "unchanged-clone", "clone-changed-only-notes",
        "foreign-project-new-exact-authority", "migrated-same-evidence-fresh-signature",
    }
    assert checks["foreign-project-same-commit"] == "authority-or-checker-refused"
    assert checks["source-symlink"] == "worktree-source-refused"
    assert checks["dirty-relevant-source-with-same-head"] == "source-scope-refused"
    assert checks["fresh-signed-different-semantics"] == "checker-refused"
    assert checks["reused-v1-signature-over-v2"] == "signature-refused"
    assert checks["signed-but-unsupported-artifact"] == "checker-refused"
    return {"result": checks, "same_git_commit_across_projects": True, "git_commit": original_head,
            "lean": version, "checker": checker, "migrated_exact_payload_sha256": template.artifact,
            "canonical_v1_orders": len(tuple(permutations(template.roles))), "branch": BRANCH}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pins = {}
    for source in (DEFINITION, SIGNED):
        location = source.relative_to(ROOT).as_posix()
        archived = run(["git", "show", f"{PIN}:{location}"], cwd=ROOT,
                       capture_output=True, check=True).stdout
        assert archived == source.read_bytes()
        pins[location] = digest(archived)
    with TemporaryDirectory() as directory:
        result = experiment(Path(directory), args.lean.resolve(strict=True))
    args.output.write_text(json.dumps({"basis": PIN, "source_hashes": pins, **result},
                                     sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
