"""Reconcile real versioned zlib releases with one checked local Rust mirror."""

import argparse
import ctypes as c
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile


HERE = Path(__file__).resolve().parent
RELEASES = {
    "1.2.13": "1525952a0a567581792613a9723333d7f8cc20b87a81f920fb8bc7e3f2251428",
    "1.3.1": "17e88863f3600672ab49182f217281b6fc4d3c762bde361935e436a95214d05c",
    "1.3.2": "b99a0b86c0ba9360ec7e78c4f1e43b1cbdf1e6936c8fa0f6835c0cd694a495a1",
}
LENGTHS = (0, 1, 2, 15, 16, 17, 31, 255, 1024, 5551, 5552, 5553, 12000)
SEEDS = (0, 1, 0x00120042, 0xfff0fff0)
TAGS = (0, 11, 127, 255)
FIELDS = ("kind", "name", "opcode", "value", "castKind", "type", "valueCategory", "isArrow",
          "referencedDecl", "isPostfix")


def run(*args, cwd=None):
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1764000000"}
    observed = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=45)
    assert observed.returncode == 0, (args[0], observed.stderr)
    return observed.stdout.strip()


def digest(data):
    return sha256(data).hexdigest()


def filehash(path):
    return digest(path.read_bytes())


def identifier(payload):
    return digest(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def canonical(node):
    normalized = {key: node[key] for key in FIELDS if key in node}
    if "type" in normalized:
        t = normalized["type"]
        normalized["type"] = t.get("desugaredQualType", t.get("qualType"))
    if "referencedDecl" in normalized:
        source = normalized["referencedDecl"]
        normalized["referencedDecl"] = {k: source[k] for k in ("kind", "name") if k in source}
    if "inner" in node:
        normalized["inner"] = [canonical(child) for child in node["inner"]]
    return normalized


def import_occurrence(clang, source):
    data = json.loads(run(clang, "-std=c17", "-Wno-deprecated-non-prototype", "-fsyntax-only",
                          "-Xclang", "-ast-dump=json", "adler32.c", cwd=source))
    executable_decls = [
        n for n in data["inner"]
        if n.get("name") == "adler32_z" and n.get("kind") == "FunctionDecl"
        and any(child.get("kind") == "CompoundStmt" for child in n.get("inner", []))
    ]
    assert len(executable_decls) == 1
    declaration = executable_decls[0]
    executable = [node for node in declaration["inner"] if node["kind"] == "CompoundStmt"][0]
    parameters = [canonical(node) for node in declaration["inner"] if node["kind"] == "ParmVarDecl"]
    assert len(parameters) == 3
    old_syntax = bool(re.search(r"(?m)^uLong ZEXPORT adler32_z\(adler, buf, len\)$",
                                (source / "adler32.c").read_text(encoding="utf-8")))
    return {
        "operation": declaration["name"], "parameters": parameters,
        "function_type": declaration["type"]["qualType"],
        "body_semantic_projection": identifier(canonical(executable)),
        "syntax": "K&R" if old_syntax else "prototype",
        "source_file_sha256": filehash(source / "adler32.c"),
    }


def observe(operation, inputs):
    rows = []
    for seed, length, salt in inputs:
        if length is None:
            rows.append([operation(seed, None, 0), None])
            continue
        data = bytes((index * 73 + salt) % 256 for index in range(length))
        whole = operation(seed, data, length)
        state = seed
        for offset, stop in ((0, length // 3), (length // 3, length // 2), (length // 2, length)):
            chunk = data[offset:stop]
            state = operation(state, chunk, len(chunk))
        rows.append([whole, state])
    return rows


def reference(inputs):
    rows = []
    for seed, length, salt in inputs:
        if length is None:
            rows.append([1, None])
            continue
        a, b = seed % 65536, seed // 65536
        data = [(index * 73 + salt) & 255 for index in range(length)]
        sum_a = (a + sum(data)) % 65521
        sum_b = (b + len(data) * a + sum((len(data) - index) * value
                                       for index, value in enumerate(data))) % 65521
        answer = (sum_b << 16) | sum_a
        rows.append([answer, answer])
    return rows


def native_library(path, symbol):
    library = c.CDLL(str(path))
    function = getattr(library, symbol)
    function.argtypes = [c.c_uint64, c.c_char_p, c.c_size_t]
    function.restype = c.c_uint64
    return function


@dataclass(frozen=True)
class Binding:
    release: str
    upstream_material: str
    native_provider: str
    mirror_artifact: str
    abi: str
    observation: str


def change_store(path, binding):
    staged = path.with_suffix(".pending")
    staged.write_text(json.dumps(asdict(binding), sort_keys=True), encoding="utf-8")
    staged.replace(path)
    return json.loads(path.read_text(encoding="utf-8"))


def decide(request, receipt, checked, observed):
    if receipt != request:
        return "stale-receipt"
    if not checked:
        return "unknown"
    return "admitted" if observed else "divergent"


def collect(args, work):
    assets = {}
    inputs = list(product(SEEDS, LENGTHS, TAGS)) + [(seed, None, 0) for seed in SEEDS]
    expected = reference(inputs)
    for release, archive_hash in RELEASES.items():
        source = args.inputs / f"zlib-{release}"
        archive = args.inputs / f"zlib-{release}.tar.gz"
        assert filehash(archive) == archive_hash
        # Read build dependencies from the real release's preprocessing closure.
        rule = run(args.cc, "-std=c17", "-MM", "adler32.c", cwd=source)
        dependencies = sorted(set(rule.replace("\\\n", " ").split()[1:]))
        assert {"adler32.c", "zconf.h", "zlib.h", "zutil.h"} <= set(dependencies)
        material = {name: filehash(source / name) for name in dependencies}
        with tarfile.open(archive, "r:gz") as snapshot:
            for name, expected_hash in material.items():
                member = snapshot.extractfile(f"zlib-{release}/{name}")
                assert member is not None and digest(member.read()) == expected_hash, name
        profile = import_occurrence(args.clang, source)
        generated = work / f"upstream-{release}.so"
        run(args.cc, "-std=c17", "-fPIC", "-O2", "-shared", "-Wl,--no-undefined",
            f"-ffile-prefix-map={source}=/upstream", "adler32.c", "-o", generated, cwd=source)
        observed = observe(native_library(generated, "adler32_z"), inputs)
        assert observed == expected
        assets[release] = {
            "archive_sha256": archive_hash, "transitive_release_inputs": material,
            "typed_source": profile, "native_sha256": filehash(generated), "trace_sha256": identifier(observed),
        }

    mirrors = {}
    for mode, extra in (("preserving", []), ("alternate_modulus", ["--cfg", "faulty"])):
        artifact = work / f"mirror-{mode}.so"
        run(args.rustc, "--edition=2021", "--crate-name=rt28_mirror", "--crate-type=cdylib",
            "-Copt-level=2", "--remap-path-prefix", f"{HERE}=/fixture", *extra, HERE / "mirror.rs",
            "-o", artifact)
        observed = observe(native_library(artifact, "mirror"), inputs)
        mismatches = sum(a != b for a, b in zip(observed, expected))
        assert (mismatches > 0) == bool(extra)
        mirrors[mode] = {"artifact_sha256": filehash(artifact), "trace_sha256": identifier(observed),
                         "mismatches": mismatches}

    revisions = list(assets)
    assert [assets[name]["typed_source"]["syntax"] for name in revisions] == ["K&R", "prototype", "prototype"]
    projections = [assets[name]["typed_source"]["body_semantic_projection"] for name in revisions]
    selected = mirrors["preserving"]["artifact_sha256"]
    bindings = {
        release: Binding(release, identifier(asset["transitive_release_inputs"]), asset["native_sha256"],
                         selected, "LP64 adler32_z unsigned-long pointer size_t", identifier(expected))
        for release, asset in assets.items()
    }
    previous, middle, latest = [bindings[name] for name in revisions]
    staged = work / "selected.json"
    assert change_store(staged, previous)["release"] == previous.release
    rollback_receipt = previous
    results = {
        "original": decide(previous, rollback_receipt, True, True),
        "middle_with_old_receipt": decide(middle, rollback_receipt, True, True),
        "latest_without_native_observations": decide(latest, latest, False, True),
        "latest_exact": decide(latest, latest, True, True),
    }
    assert results == {
        "original": "admitted", "middle_with_old_receipt": "stale-receipt",
        "latest_without_native_observations": "unknown", "latest_exact": "admitted",
    }
    assert change_store(staged, latest)["release"] == latest.release
    fault = replace(latest, mirror_artifact=mirrors["alternate_modulus"]["artifact_sha256"])
    assert decide(fault, fault, True, False) == "divergent"
    assert json.loads(staged.read_text())["mirror_artifact"] == selected
    assert decide(previous, rollback_receipt, True, True) == "admitted"
    assert change_store(staged, previous) == asdict(rollback_receipt)
    results.update({"altered_mirror": "divergent", "rollback": "restored exact original binding"})
    return {
        "upstream": assets, "mirror": mirrors, "binding_controls": results,
        "bindings": {name: asdict(value) for name, value in bindings.items()},
        "body_projection_unique_count": len(set(projections)),
        "cases_per_provider": len(inputs),
        "observation_shape": "exact full checksum and independently chunked continuation",
        "toolchain": {
            name: run(getattr(args, name), "--version").splitlines()[0] for name in ("cc", "clang", "rustc")
        },
        "fixture_sha256": {path.name: filehash(path) for path in (HERE / "mirror.rs", Path(__file__))},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, tool in (("cc", "gcc"), ("clang", "clang"), ("rustc", "rustc")):
        parser.add_argument(f"--{name}", default=tool)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt28-zlib-mirror-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
