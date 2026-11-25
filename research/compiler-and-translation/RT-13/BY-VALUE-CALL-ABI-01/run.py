#!/usr/bin/env python3
"""Compare exact calling conventions for the same native by-value record type."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ABIS = ("sysv64", "win64")
LEVELS = (0, 3)
LANGUAGES = ("c", "rust")
ROUTES = ("direct", "bridge")
VALUES = ((0, 1, 4294967297, 2**64 - 1),
          (0, 2, 1099511627779, 2**64 - 1),
          (0, 3, 2**63 - 1, 2**64 - 1))
MAX_MASK = 2**64 - 1


def run_command(arguments, directory, text=False):
    return subprocess.check_output(arguments, cwd=directory, timeout=30, text=text)


def checksum(data):
    return sha256(data).hexdigest()


def expected():
    return [[(x + (y ^ salt)) & MAX_MASK, (y + 3 * salt + 5 * x) & MAX_MASK]
            for x, y, salt in product(*VALUES)]


def build_provider(directory, style, level):
    provider = directory / f"provider-{style}-{level}.o"
    run_command(["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{level}",
                 f"-DCALL_STYLE={style}", "-c", str(HERE / "provider.c"), "-o", str(provider)], directory)
    disassembly = run_command(["objdump", "-d", "--disassemble=transform_record", str(provider)],
                              directory, text=True)
    begin = disassembly.index("<transform_record>:")
    operations = disassembly[begin:].strip().splitlines()[1:]
    assert operations and re.search(r"\bret\b", operations[-1])
    registers = {register for line in operations for register in re.findall(r"%([a-z0-9]+)", line)}
    expected_inputs = {"rdi", "rsi", "rdx"} if style == 0 else {"rcx", "rdx", "r8"}
    assert expected_inputs <= registers
    return provider, {
        "abi": ABIS[style], "provider_optimization": level, "sha256": checksum(provider.read_bytes()),
        "known_input_registers_observed": sorted(expected_inputs), "symbol": "transform_record",
        "disassembly": [line.strip() for line in operations],
    }


def build_consumer(directory, provider, style, level, language, route):
    executable = directory / "consumer"
    if language == "c":
        arguments = ["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{level}",
                     f"-DCALL_STYLE={style}", f"-DUSE_BRIDGE={int(route == 'bridge')}",
                     str(HERE / "caller.c"), str(provider), "-o", str(executable)]
    else:
        arguments = ["rustc", "--edition=2021", "-Dwarnings", "-C", f"opt-level={level}",
                     "-C", f"link-arg={provider}", str(HERE / "caller.rs"), "-o", str(executable)]
        if route == "bridge":
            arguments.extend(["--cfg", "bridge"])
        elif style == 1:
            arguments.extend(["--cfg", "win"])
    run_command(arguments, directory)
    output = run_command([str(executable)], directory, text=True)
    executable.unlink()
    rows = [json.loads(line) for line in output.splitlines()]
    return rows[0], rows[1:]


def run(directory):
    assert run_command(["cc", "-dumpmachine"], directory, text=True).strip() == "x86_64-linux-gnu"
    oracle = expected()
    native = []
    artifacts = []
    proposals = []
    for style, provider_level in product(range(len(ABIS)), LEVELS):
        provider, proof_identity = build_provider(directory, style, provider_level)
        artifacts.append(proof_identity)
        for consumer_abi in ABIS:
            matches = consumer_abi == ABIS[style]
            proposals.append({"provider_sha256": proof_identity["sha256"], "consumer_abi": consumer_abi,
                              "symbol_type_gate": True, "explicit_direct_gate": matches,
                              "fixed_bridge_gate": True, "mismatched_direct_call_executed": False})
        for language, consumer_level, route in product(LANGUAGES, LEVELS, ROUTES):
            shape_and_abi, results = build_consumer(directory, provider, style, consumer_level, language, route)
            assert shape_and_abi == [16, 8, 0, 8, style]
            assert results == oracle
            native.append({"provider": proof_identity["sha256"], "provider_abi": ABIS[style],
                           "provider_optimization": provider_level, "caller": language,
                           "caller_optimization": consumer_level, "route": route,
                           "physical_shape_and_abi": shape_and_abi, "vectors": results})
    assert len({row["sha256"] for row in artifacts}) == len(artifacts)
    totals = Counter(row["route"] for row in native)
    return {
        "schema": "llmlang-rt13-by-value-call-abi/1", "python": platform.python_version(),
        "cc": run_command(["cc", "--version"], directory, text=True).splitlines()[0],
        "rustc": run_command(["rustc", "-Vv"], directory, text=True).splitlines(),
        "objdump": run_command(["objdump", "--version"], directory, text=True).splitlines()[0],
        "source_sha256": {name: checksum((HERE / name).read_bytes())
                          for name in ("provider.h", "provider.c", "caller.c", "caller.rs", "run.py")},
        "inputs": VALUES, "vectors_per_run": len(oracle), "native_runs": len(native),
        "native_route_runs": dict(totals), "native_observations": sum(len(row["vectors"]) for row in native),
        "direct_proposals": len(proposals),
        "symbol_type_false_admissions": sum(not row["explicit_direct_gate"] for row in proposals),
        "checked_direct_admissions": sum(row["explicit_direct_gate"] for row in proposals),
        "checked_bridge_admissions": sum(row["fixed_bridge_gate"] for row in proposals),
        "providers": artifacts, "proposals": proposals, "native": native,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt13-byvalue-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("native")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "native": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
