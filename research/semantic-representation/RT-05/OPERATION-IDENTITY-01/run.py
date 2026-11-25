#!/usr/bin/env python3
"""Audit candidate operation, body and binding identities for an effectful contract."""

from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
CONTEXTS = {"wrap": 0, "saturate": 1}
PROVIDERS = ("stay", "advance", "parity", "mixed", "reordered")
INPUTS = tuple(range(256))
TRACE_CODES = {
    ("read", "commit"): "S",
    ("read", "advance", "commit"): "A",
    ("commit", "read"): "R",
}
CONTRACT = {
    "signature": {"input": "u8", "output": "u8"},
    "allowed": [
        ("x", ("read", "commit")),
        ("advance(x)", ("read", "advance", "commit")),
    ],
    "trace_interpretation": "exact ordered event sequence",
}


def digest(value):
    return sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")).hexdigest()


def file_digest(path):
    return sha256(path.read_bytes()).hexdigest()


def execute(args, directory, *, source=None):
    return subprocess.run(args, cwd=directory, env=ENV, input=source, check=True,
                          capture_output=True, text=True, timeout=30).stdout


def relation(value, context):
    advanced = min(value + 1, 255) if context == "saturate" else (value + 1) % 256
    return ((value, ("read", "commit")), (advanced, ("read", "advance", "commit")))


def run_provider(directory, context, provider, allowed):
    args = ["gcc", "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror",
            f"-DSATURATE={CONTEXTS[context]}", f"-DPROVIDER={PROVIDERS.index(provider)}",
            "provider.c", "-o", "provider"]
    execute(args, directory)
    data = execute(["./provider"], directory, source="".join(f"{value}\n" for value in INPUTS))
    observations = []
    for line in data.splitlines():
        value, trace = line.split()
        observations.append((int(value), tuple(trace.split(","))))
    member = tuple(actual in options for actual, options in zip(observations, allowed, strict=True))
    marginal = tuple(
        actual[0] in {first[0], second[0]} and actual[1] in {first[1], second[1]}
        for actual, (first, second) in zip(observations, allowed, strict=True)
    )
    op_hash = digest(("contract-operation/1", CONTRACT, context))
    binary = file_digest(directory / "provider")
    body = digest(("native-provider/1", binary, "stdio-effect-observation/1"))
    return {
        "context": context, "provider": provider, "build": args,
        "binary_sha256": binary,
        "op_hash": op_hash, "implementation_hash": body,
        "body_qualified_op_hash": digest(("body-operation/1", op_hash, body)),
        "binding_hash": digest(("binding/1", op_hash, body)),
        "member_count": sum(member), "marginal_count": sum(marginal),
        "wrong_marginal_admissions": sum(not full and projected
                                         for full, projected in zip(member, marginal, strict=True)),
        "first_refused_input": next((x for x, valid in enumerate(member) if not valid), None),
        "observations": observations,
    }


def results():
    with TemporaryDirectory(prefix="llmlang-contract-address-") as temp:
        directory = Path(temp)
        shutil.copyfile(HERE / "provider.c", directory / "provider.c")
        version = execute(["gcc", "--version"], directory).splitlines()[0]
        rows = [
            run_provider(directory, context, provider, tuple(relation(x, context) for x in INPUTS))
            for context in CONTEXTS for provider in PROVIDERS
        ]
    accepted = [row for row in rows if row["member_count"] == len(INPUTS)]
    if {row["provider"] for row in accepted} != {"stay", "advance", "parity"} or len(accepted) != 6:
        raise AssertionError("Expected exactly three conforming providers per context")
    counters = [
        {
            "context": a["context"], "left": a["provider"], "right": b["provider"],
            "same_contract_key": a["op_hash"] == b["op_hash"],
            "same_binding": a["binding_hash"] == b["binding_hash"],
            "different_input_count": sum(left != right for left, right in
                                         zip(a["observations"], b["observations"], strict=True)),
        }
        for a, b in combinations(accepted, 2) if a["context"] == b["context"]
    ]
    pair = [row for row in accepted if row["provider"] == "advance"]
    boundary = {
        "shared_context_free_key": digest(("contract-operation/1", CONTRACT)),
        "input": 255, "wrap_observation": pair[0]["observations"][255],
        "saturate_observation": pair[1]["observations"][255],
        "distinct_contextual_keys": pair[0]["op_hash"] != pair[1]["op_hash"],
    }
    for row in rows:
        observations = row.pop("observations")
        row["result_bytes_hex"] = bytes(value for value, _ in observations).hex()
        row["trace_codes"] = "".join(TRACE_CODES[trace] for _, trace in observations)
    return {
        "schema": "llmlang-operation-identity/1",
        "host": {"python": platform.python_version(), "system": platform.system(),
                 "architecture": platform.machine(), "kernel": platform.release(),
                 "libc": platform.libc_ver()},
        "gcc": version, "gcc_sha256": file_digest(Path(shutil.which("gcc", path=ENV["PATH"]))),
        "sources_sha256": {name: file_digest(HERE / name) for name in ("provider.c", "run.py", "Contract.lean")},
        "contract": CONTRACT, "input_range_inclusive": [INPUTS[0], INPUTS[-1]],
        "trace_codebook": {code: events for events, code in TRACE_CODES.items()}, "rows": rows,
        "scope_boundary": boundary, "same_contract_distinct_providers": counters,
    }


if __name__ == "__main__":
    print(json.dumps(results(), separators=(",", ":"), indent=2))
