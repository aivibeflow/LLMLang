#!/usr/bin/env python3
"""Compare native action, artifact, implementation, and evidence identities."""

from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ENV = {"LC_ALL": "C", "PATH": "/usr/bin:/bin"}
ABIS = {"sysv": 0, "ms": 1}
MASK = (1 << 64) - 1
INPUTS = (
    (0, 0, 0), (1, 2, 3), (MASK, 1, 0), (0, MASK, MASK),
    (MASK, MASK, MASK), (1 << 63, 1 << 32, 17), (17, 23, 31), (99, 35, 1 << 40),
)
CONTRACT = {"arguments": ["u64", "u64", "u64"], "result": ["u64", "u64"],
            "specification": ["first + salt + 1 modulo 2^64", "second xor salt"]}
ABI_SHAPE = {"symbol": "step", "record_size": 16, "field_offsets": [0, 8], "alignment": 8}


def key(domain, data):
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def file_digest(path):
    return sha256(path.read_bytes()).hexdigest()


def execute(args, directory, *, source=None):
    return subprocess.run(
        args, cwd=directory, input=source, env=ENV, capture_output=True, check=True,
        text=True, timeout=30,
    ).stdout


def observed_toolchain(directory):
    names = {
        "gcc": shutil.which("gcc", path=ENV["PATH"]),
        **{tool: execute(["gcc", f"-print-prog-name={tool}"], directory).strip()
           for tool in ("cc1", "as", "ld", "collect2")},
    }
    result = {}
    for tool, name in names.items():
        path = shutil.which(name, path=ENV["PATH"])
        result[tool] = {"sha256": file_digest(Path(path))}
        if tool in {"gcc", "as", "ld"}:
            result[tool]["version"] = execute([path, "--version"], directory).splitlines()[0]
    return result


def build(directory, sources, toolchain, abi, *, provider=None, marker=None):
    provider_build = provider is not None
    source = "provider.c" if provider_build else "caller.c"
    name = "provider.so" if provider_build else "caller"
    profile = f"provider-{abi}-{provider}" if provider_build else f"caller-{abi}-{marker}"
    work = directory / profile
    work.mkdir()
    for input_name in ("entry.h", source):
        shutil.copyfile(HERE / input_name, work / input_name)
    define = f"-DPROVIDER_DELTA={provider}" if provider_build else f"-DUNUSED_MARKER={marker}"
    args = ["gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", "-march=x86-64",
            f"-DTARGET_ABI={ABIS[abi]}", define, source]
    args += ["-shared", "-fPIC"] if provider_build else ["-ldl"]
    args += ["-o", name]
    action = {
        "argv": args, "inputs": {name: sources[name] for name in ("entry.h", source)},
        "environment": ENV, "toolchain": toolchain,
    }
    execute(args, work)
    binary = work / name
    return {"file": binary.relative_to(directory).as_posix(), "sha256": file_digest(binary), "action": action,
            "action_key": key("native-build-action/1", action)}


def loader_dependencies(directory, caller):
    output = execute(["ldd", caller["file"]], directory)
    names = ("libc.so.6", "ld-linux-x86-64.so.2")
    libraries = {}
    for name in names:
        matches = re.findall(rf"(/[^\s]*?/{re.escape(name)})(?=\s|$)", output)
        if len(matches) != 1:
            raise ValueError(f"Expected one resolved {name}: {output}")
        libraries[name] = file_digest(Path(matches[0]))
    return libraries


def native_rows(directory, caller, provider):
    source = "".join(f"{first} {second} {salt}\n" for first, second, salt in INPUTS)
    output = execute([f"./{caller['file']}", f"./{provider['file']}"], directory, source=source)
    return [list(map(int, line.split())) for line in output.splitlines()]


def profile_observations(directory, sources, toolchain, host):
    operation = key("abstract-operation/1", CONTRACT)
    expected = [[(first + salt + 1) & MASK, second ^ salt] for first, second, salt in INPUTS]
    callers, providers, rows = {}, {}, []
    for abi in ABIS:
        for marker in (0, 1):
            callers[(abi, marker)] = build(directory, sources, toolchain, abi, marker=marker)
        for delta in (1, 2):
            providers[(abi, delta)] = build(directory, sources, toolchain, abi, provider=delta)
        target = {"architecture": "x86_64", "format": "ELF", "call_abi": abi}
        for marker in (0, 1):
            caller = callers[(abi, marker)]
            libraries = loader_dependencies(directory, caller)
            for delta in (1, 2):
                provider = providers[(abi, delta)]
                implementation = {
                    "caller_sha256": caller["sha256"], "provider_sha256": provider["sha256"],
                    "target": target, "external_entry": ABI_SHAPE,
                    "runtime_libraries_sha256": libraries,
                }
                observed = native_rows(directory, caller, provider)
                if observed != [[(first + salt + delta) & MASK, second ^ salt]
                                for first, second, salt in INPUTS]:
                    raise AssertionError(f"Unexpected observations for {abi=}, {delta=}, {marker=}")
                impl_key = key("native-implementation/1", implementation)
                receipt = {
                    "operation": operation, "implementation": impl_key,
                    "host": host, "vectors": key("input-vectors/1", INPUTS),
                    "checker": sources["run.py"], "expected": expected, "observed": observed,
                }
                rows.append({
                    "abi": abi, "delta": delta, "marker": marker,
                    "caller_build_action": caller["action_key"], "provider_build_action": provider["action_key"],
                    "caller_only_key": key("caller-bytes", caller["sha256"]),
                    "closed_implementation": implementation, "implementation_key": impl_key,
                    "fixture_evidence_key": key("fixture-evidence/1", receipt),
                    "observed": observed,
                    "contract_mismatch_vectors": sum(a != b for a, b in zip(expected, observed, strict=True)),
                })
    return callers, providers, rows, operation


def results():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("This fixture requires a Linux x86-64 host")
    sources = {name: file_digest(HERE / name) for name in ("caller.c", "provider.c", "entry.h", "run.py")}
    host = {"system": platform.system(), "architecture": platform.machine(), "kernel": platform.release(),
            "libc": platform.libc_ver(), "python": platform.python_version()}
    with TemporaryDirectory(prefix="llmlang-native-identity-") as temp:
        directory = Path(temp)
        toolchain = observed_toolchain(directory)
        callers, providers, rows, operation = profile_observations(directory, sources, toolchain, host)

    abi_admissions = [
        {"required": caller, "provider": provider, "shape_admitted": True,
         "exact_abi_admitted": caller == provider}
        for caller in ABIS for provider in ABIS
    ]
    pairs = list(combinations(rows, 2))
    collapsed = {
        field: sum(a[field] == b[field] and a["observed"] != b["observed"] for a, b in pairs)
        for field in ("caller_only_key", "implementation_key", "fixture_evidence_key")
    }
    marker_pairs = [(a, b) for a, b in pairs if a["abi"] == b["abi"] and a["delta"] == b["delta"]]
    if len(marker_pairs) != 4 or any(
        a["marker"] == b["marker"] or a["caller_build_action"] == b["caller_build_action"]
        or a["implementation_key"] != b["implementation_key"]
        or a["fixture_evidence_key"] != b["fixture_evidence_key"]
        for a, b in marker_pairs
    ):
        raise AssertionError("Expected distinct build recipes and the same resolved implementation")
    return {
        "schema": "llmlang-native-implementation-identity/1", "sources_sha256": sources,
        "host": host, "tools": toolchain, "contract": CONTRACT, "abstract_operation_key": operation,
        "inputs": INPUTS, "callers": list(callers.values()), "providers": list(providers.values()),
        "rows": rows, "native_rows": len(rows) * len(INPUTS), "distinct_marker_recipe_pairs": len(marker_pairs),
        "pairs_with_same_key_and_distinct_observations": collapsed, "abi_admissions": abi_admissions,
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
