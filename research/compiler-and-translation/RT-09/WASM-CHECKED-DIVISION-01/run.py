"""Audit guarded Wasm lowering and exact capability and evidence outcomes."""

import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent


def run(*command, expect_failure=False):
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    if expect_failure:
        assert result.returncode != 0, command
        return result.stderr
    result.check_returncode()
    assert not result.stderr, result.stderr
    return result.stdout.strip()


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Scope:
    source: str
    module: str
    engine: str
    capability_profile: str
    observation: str
    binding: str | None
    restriction: str | None


def decide(scope, declared, required, observed, approval):
    if any(declared.get(feature) is False for feature in required):
        return "unsupported"
    if any(declared.get(feature) is not True for feature in required):
        return "unverified"
    exact_scope, evidence = observed
    if exact_scope != scope or evidence["wrong"]:
        return "unverified"
    if scope.restriction is not None:
        return "restricted" if approval == scope else "unverified"
    if scope.binding is not None:
        return "runtime-supported"
    return "exact-under-assumptions"


def collect(args, temporary):
    source = HERE / "source.json"
    modules = {}
    for route in ("pure", "guarded", "raw", "reversed"):
        wat = temporary / f"{route}.wat"
        artifact = wat.with_suffix(".wasm")
        wat.write_text(run(sys.executable, HERE / "lower.py", source, route) + "\n", encoding="utf-8")
        run("wat2wasm", wat, "-o", artifact)
        run("wasm-validate", artifact)
        rejected = run("wasm-validate", "--disable-multi-value", artifact, expect_failure=True)
        assert "multiple results" in rejected or "multi-value" in rejected, rejected
        shape = run("wasm-objdump", "-d", artifact)
        assert "i32.div_s" in shape
        assert shape.count("if") == (0 if route == "raw" else 2)
        modules[route] = artifact

    routes = (
        ("pure", "pure", "none"),
        ("guarded", "full", "intended"),
        ("guarded", "full", "wrong"),
        ("guarded", "full", "missing"),
        ("raw", "full", "intended"),
        ("raw", "restricted", "intended"),
        ("raw", "restricted-zero-only", "intended"),
        ("reversed", "full", "intended"),
    )
    results = {}
    for engine_path in args.node:
        engine = run(engine_path, "--version")
        observations = {}
        for module, mode, binding in routes:
            key = "/".join((module, mode, binding))
            observations[key] = json.loads(
                run(engine_path, HERE / "check.mjs", modules[module], mode, binding)
            )
        pure = observations["pure/pure/none"]
        guarded = observations["guarded/full/intended"]
        restricted = observations["raw/restricted/intended"]
        unsafe_restriction = observations["raw/restricted-zero-only/intended"]
        raw = observations["raw/full/intended"]
        reversed_effects = observations["reversed/full/intended"]
        wrong = observations["guarded/full/wrong"]
        missing = observations["guarded/full/missing"]
        assert pure["wrong"] == guarded["wrong"] == restricted["wrong"] == 0
        assert pure["cases"] == guarded["cases"] == 71**2
        assert raw["wrong"] == raw["traps"] == raw["wrong_trace"] == restricted["rejected_domain"] == 72
        assert reversed_effects["wrong"] == wrong["wrong"] == guarded["cases"]
        assert reversed_effects["wrong_result"] == wrong["wrong_result"] == 0
        assert unsafe_restriction["wrong"] == unsafe_restriction["traps"] == unsafe_restriction["wrong_domain"] == 1
        assert missing["binding"] == "refused"

        source_hash = digest(source)
        runtime_identity = digest(HERE / "check.mjs") + "#intended"
        scope_pure = Scope(
            source_hash, digest(modules["pure"]), engine, "node-core-multivalue-v1",
            "status-value", None, None,
        )
        scope_guarded = replace(
            scope_pure, module=digest(modules["guarded"]),
            observation="status-value-ordered-host-audit", binding=runtime_identity,
        )
        scope_restricted = replace(
            scope_guarded, module=digest(modules["raw"]),
            restriction="y!=0 and (x,y)!=(I32_MIN,-1)",
        )
        common = {"division": True, "multi-value": True}
        hosted = {**common, "host.audit": True}
        pure_requires = ("division", "multi-value")
        hosted_requires = (*pure_requires, "host.audit")
        precise = (scope_guarded, guarded)
        decisions = {}
        for title, scope, features, required, receipt, approval, expected in (
            ("pure profile", scope_pure, common, pure_requires, (scope_pure, pure), None, "exact-under-assumptions"),
            ("exact provider", scope_guarded, hosted, hosted_requires, precise, None, "runtime-supported"),
            ("accepted exact restriction", scope_restricted, hosted, hosted_requires, (scope_restricted, restricted), scope_restricted, "restricted"),
            ("wrong domain guard", scope_restricted, hosted, hosted_requires, (scope_restricted, unsafe_restriction), scope_restricted, "unverified"),
            ("unapproved restriction", scope_restricted, hosted, hosted_requires, (scope_restricted, restricted), None, "unverified"),
            ("old restriction approval", scope_restricted, hosted, hosted_requires, (scope_restricted, restricted), scope_guarded, "unverified"),
            ("missing import capability", scope_guarded, {**common, "host.audit": False}, hosted_requires, precise, None, "unsupported"),
            ("unknown import capability", scope_guarded, common, hosted_requires, precise, None, "unverified"),
            ("validator without multi-value", scope_guarded, {**hosted, "multi-value": False}, hosted_requires, precise, None, "unsupported"),
            ("old executable receipt", replace(scope_guarded, module=digest(modules["raw"])), hosted, hosted_requires, precise, None, "unverified"),
            ("different provider receipt", replace(scope_guarded, binding="different"), hosted, hosted_requires, precise, None, "unverified"),
            ("wrong trace with exact metadata", scope_guarded, hosted, hosted_requires, (scope_guarded, wrong), None, "unverified"),
        ):
            actual = decide(scope, features, required, receipt, approval)
            assert actual == expected, title
            decisions[title] = actual
        results[engine] = {
            "checks": observations,
            "decision_controls": decisions,
            "scopes": [asdict(scope) for scope in (scope_pure, scope_guarded, scope_restricted)],
        }

    node_versions = sorted(results)
    assert {v.split(".")[0] for v in node_versions} == {"v22", "v24"}
    assert results[node_versions[0]]["checks"] == results[node_versions[1]]["checks"]
    return {
        "tools": {"wabt": run("wat2wasm", "--version"), "node": node_versions},
        "validator_profiles": {"default": "admitted", "disable-multi-value": "rejected"},
        "modules": {route: digest(path) for route, path in modules.items()},
        "source_files": {
            name: digest(HERE / name) for name in ("source.json", "lower.py", "check.mjs", "run.py")
        },
        "engines": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt09-wasm-div-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
