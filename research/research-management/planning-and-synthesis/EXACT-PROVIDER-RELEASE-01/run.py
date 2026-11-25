"""Exercise exact COR-13 native release transitions and local admission controls."""

import argparse
from dataclasses import replace
import importlib.util
from itertools import product
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import get_args

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
REPO = RESEARCH.parent
BASE = "685c3a13ef600ce76bfe9d36446b970cc7c6c3da"
PROVIDER_MODULE = RESEARCH / "compiler-and-translation/RT-13/BOUND-OWNED-PROVIDERS-01/run.py"
CACHE_MODULE = RESEARCH / "toolchain-and-collaboration/RT-11/SIGNED-REBUILD-ADMISSION-01/run.py"
ROUTES = {
    "c": ["gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2",
          "caller.c", "provider.o", "-o", "release"],
    "rust": ["rustc", "--edition=2021", "-D", "warnings", "-C", "opt-level=3",
             "-C", "link-arg=provider.o", "caller.rs", "-o", "release"],
}
SCOPE = "ordered-result-effects-ownership-and-descriptor-audit/v1"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


provider = load("release_provider_fixture", PROVIDER_MODULE)
cache = load("release_cache_fixture", CACHE_MODULE)


def key(value):
    return cache.digest(cache.encoded(value))


def output(args):
    return subprocess.check_output(args, text=True).strip()


def pin_sources():
    paths = [
        PROVIDER_MODULE, PROVIDER_MODULE.with_name("caller.c"),
        PROVIDER_MODULE.parent.parent / "NATIVE-OWNED-ABI-01/run.py",
        PROVIDER_MODULE.parent.parent / "NATIVE-OWNED-ABI-01/provider.c",
        CACHE_MODULE,
    ]
    for module in sys.modules.copy().values():
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(RESEARCH / "PROTOTYPES") and path.suffix == ".py":
                paths.append(path)
    result = {}
    for path in sorted(set(paths)):
        relative = str(path.relative_to(REPO))
        git = ["git", "-C", str(REPO)]
        blob = output([*git, "rev-parse", f"{BASE}:{relative}"])
        if blob != output([*git, "hash-object", relative]):
            raise ValueError(f"Changed fixture input: {relative}")
        result[relative] = blob
    return result


def configure(directory, caller, timing):
    directory.mkdir()
    (directory / "fixture.h").write_text(provider.header(caller))
    (directory / "caller.c").write_bytes(PROVIDER_MODULE.with_name("caller.c").read_bytes())
    (directory / "caller.rs").write_text(provider.abi.generate_linked(provider.SOURCE, timing))
    return provider.compile_providers(directory)


def build(directory, label, route, artifacts, inputs, expected, rustc):
    artifact, source_hash = artifacts[label]
    shutil.copyfile(artifact, directory / "provider.o")
    command = ROUTES[route]
    program = str(rustc) if route == "rust" else command[0]
    cache.run([program, *command[1:]], directory)
    binary = (directory / "release").read_bytes()
    observed = subprocess.run(
        ["./release"], cwd=directory, env=cache.ENV, input=inputs, capture_output=True,
        check=True, timeout=60
    ).stdout
    if observed != expected:
        raise ValueError(f"Native observations differ for {label}/{route}")
    return binary, {
        "provider_object": cache.digest(artifact.read_bytes()), "provider_source": source_hash,
        "source_caller": cache.digest(provider.SOURCE.encode()),
        "route_sources": {name: cache.digest((directory / name).read_bytes())
                          for name in (("caller.c", "fixture.h") if route == "c" else ("caller.rs",))},
        "command": command, "trace": cache.digest(observed),
    }


def statement(signers, request, binary):
    return signers.sign({
        "scheme": "native-cache-attestation/1", "action": request.key,
        "closure": request.closure, "workspace": request.workspace,
        "generation": request.policy_generation, "artifact": cache.digest(binary), "issuer": "alice",
    })


def publish(db, signers, request, signed, store, rebuilt, verification, expected_evidence, parent):
    # BEGIN IMMEDIATE fences the publication and policy generation on this database.
    db.execute("BEGIN IMMEDIATE")
    try:
        generation, allowed, current = db.execute(
            "SELECT generation, allowed, current FROM state"
        ).fetchone()
        if not allowed or generation != request.policy_generation:
            return "authority-refused"
        status, result = cache.admit(request, [signed], signers, store, rebuilt, complete=True)
        if status != "exact-hit":
            return status
        address, = result
        evidence_context = tuple(verification.get(field) for field in
                                 ("action", "closure", "projection", "artifact"))
        if verification != expected_evidence or evidence_context != (
            request.key, request.closure, SCOPE, address
        ):
            return "evidence-refused"
        if current != parent:
            return "parent-refused"
        db.execute("UPDATE state SET current = ?", (address,))
        db.execute("INSERT INTO history VALUES (?, ?, ?)", (current, address, generation))
        db.commit()
        return "published"
    finally:
        if db.in_transaction:
            db.rollback()


def transitions(root, route, profiles):
    policy_db = root / f"{route}.sqlite"
    sign_root = root / route
    sign_root.mkdir()
    signers = cache.Signers(sign_root)
    db = sqlite3.connect(policy_db)
    db.executescript(
        "CREATE TABLE state(generation INTEGER, allowed INTEGER, current TEXT); "
        "CREATE TABLE history(parent TEXT, artifact TEXT, generation INTEGER); "
        "INSERT INTO state VALUES (1, 1, NULL);"
    )
    first, second = [profiles[label] for label in provider.PROVIDERS]
    step_results = {}

    def attempt(name, expect, target, parent=None, *, request=None, signed=None,
                supplied=None, verification=None, rebuilt=None):
        request = target["request"] if request is None else request
        signed = statement(signers, request, target["binary"]) if signed is None else signed
        before = db.execute("SELECT current FROM state").fetchone()[0]
        address = target["evidence"]["artifact"]
        result = publish(
            db, signers, request, signed,
            {address: target["binary"] if supplied is None else supplied},
            target["rebuilt"] if rebuilt is None else rebuilt,
            target["evidence"] if verification is None else verification,
            target["evidence"], parent,
        )
        intended = address if expect == "published" else before
        actual = db.execute("SELECT current FROM state").fetchone()[0]
        if (result, actual) != (expect, intended):
            raise ValueError((route, name, result, actual, expect, intended))
        step_results[name] = {"verdict": result, "selected_after": actual}

    old_address = first["evidence"]["artifact"]
    new_address = second["evidence"]["artifact"]
    initial_signature = statement(signers, first["request"], first["binary"])
    attempt("initial_release", "published", first)
    attempt("stale_signed_cache", "no-attestation", second, old_address, signed=initial_signature)
    attempt("stale_trace", "evidence-refused", second, old_address, verification=first["evidence"])
    attempt("narrow_projection", "evidence-refused", second, old_address,
            verification=dict(second["evidence"], projection="scalar"))
    without_artifact = dict(second["evidence"])
    del without_artifact["artifact"]
    attempt("missing_artifact_in_evidence", "evidence-refused", second, old_address,
            verification=without_artifact)
    attempt("missing_descriptor_audit", "evidence-refused", second, old_address,
            verification=dict(second["evidence"], trace=key("scalar-only-control")))
    attempt("old_payload_under_new_address", "payload-refused", second, old_address, supplied=first["binary"])
    attempt("independent_rebuild_disagrees", "rebuild-disagrees", second, old_address, rebuilt=first["rebuilt"])
    attempt("signed_request_with_unbound_action", "evidence-refused", second, old_address,
            request=replace(second["request"], key=key("wrong-action")))
    attempt("stale_parent", "parent-refused", second, new_address)
    attempt("exact_replacement", "published", second, old_address)
    db.execute("UPDATE state SET generation = 2, allowed = 0")
    db.commit()
    revoked_request = replace(first["request"], policy_generation=2)
    attempt("revoked_publisher", "authority-refused", first, new_address, request=revoked_request)
    db.close()
    db = sqlite3.connect(policy_db)
    db.execute("UPDATE state SET generation = 3, allowed = 1")
    db.commit()
    fresh_request = replace(first["request"], policy_generation=3)
    attempt("historical_signature_after_reauthorize", "no-attestation", first, new_address,
            request=fresh_request, signed=initial_signature)
    attempt("exact_rollback_reauthorized", "published", first, new_address, request=fresh_request)
    history = db.execute("SELECT * FROM history ORDER BY rowid").fetchall()
    db.close()
    assert history == [(None, old_address, 1), (old_address, new_address, 1), (new_address, old_address, 3)]
    return {"attempts": step_results, "history": history}


def experiment(root, rustc):
    pinned = pin_sources()
    executables = {name: Path(shutil.which(name, path=cache.ENV["PATH"]))
                   for name in ("gcc", "ld", "openssl")}
    executables["rustc"] = rustc
    tools = {name: {"version": output([str(path), "--version"]).splitlines()[0],
                    "sha256": cache.digest(path.read_bytes())}
             for name, path in executables.items()}
    abi = provider.abi
    roles = (*product("abc", repeat=4), ("a", "b", "c", "d"))
    dispositions = get_args(abi.Disposition)
    cases = [(abi.Inputs(ids, wants, local, handle), cleanup)
             for ids, wants, local, handle, cleanup in product(
                 roles, (False, True), dispositions, dispositions, dispositions)]
    inputs = "".join(abi.encode_input(*case, physical)
                     for case in cases for physical in (False, True)).encode()
    timing = "before_cleanup"
    caller = abi.compile_caller(provider.SOURCE, timing)
    workspace = "local-cor13-release"
    compiler_host = {"machine": platform.machine(), "kernel": platform.release(),
                     "libc": output(["getconf", "GNU_LIBC_VERSION"])}
    trees = {name: configure(root / name, caller, timing) for name in ("primary", "rebuild")}
    outcomes = {}
    references = {label: provider.reference(caller, cases, label) for label in provider.PROVIDERS}
    for route in ROUTES:
        profiles = {}
        for label, traces in references.items():
            expected = ("\n".join(traces) + "\n").encode()
            binary, closure = build(root / "primary", label, route, trees["primary"], inputs, expected, rustc)
            rebuilt, repeated = build(root / "rebuild", label, route, trees["rebuild"], inputs, expected, rustc)
            if binary != rebuilt or closure != repeated:
                raise ValueError(f"Different clean rebuild {route}/{label}")
            observed_trace = closure.pop("trace")
            identity = key({"route": route, "tools": tools, "host": compiler_host,
                            "environment": cache.ENV, "closure": closure})
            request = cache.Request(identity, key(closure), workspace, 1, frozenset({"alice"}))
            evidence = {"action": identity, "closure": request.closure, "projection": SCOPE,
                        "inputs": cache.digest(inputs), "trace": observed_trace,
                        "artifact": cache.digest(binary)}
            profiles[label] = {"binary": binary, "rebuilt": rebuilt, "request": request,
                               "evidence": evidence, "declared_closure": closure}
        outcomes[route] = transitions(root, route, profiles) | {
            "profiles": {label: {"evidence": match["evidence"], "declared_closure": match["declared_closure"]}
                         for label, match in profiles.items()}
        }

    old, new = references.values()
    assert len(old) == len(new) == 20992
    assert sum(left != right for left, right in zip(old, new, strict=True)) == 5720
    return {"format": "scoped-provider-release/1", "base": BASE, "inputs": pinned,
            "tools": tools, "host": compiler_host, "build_environment": cache.ENV,
            "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "rows_per_execution": len(old), "native_executions_total": 8,
            "replacement_changed_rows_per_route": 5720, "outcomes": outcomes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rustc", type=Path, help="direct toolchain rustc executable")
    args = parser.parse_args()
    rustc = args.rustc
    if rustc is None:
        rustc = Path(output(["rustc", "--print", "sysroot"])) / "bin/rustc"
    with TemporaryDirectory(prefix="provider-release-") as work:
        result = experiment(Path(work), rustc.resolve())
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
