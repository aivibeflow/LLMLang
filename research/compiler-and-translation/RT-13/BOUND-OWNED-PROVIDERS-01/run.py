"""Compare exact owned-result provider binding in C and generated Rust."""
import argparse
from dataclasses import replace
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import get_args

HERE = Path(__file__).resolve().parent
spec = spec_from_file_location("native_abi", HERE.parent / "NATIVE-OWNED-ABI-01" / "run.py")
abi = module_from_spec(spec)
spec.loader.exec_module(abi)
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, make_snapshot

PROVIDERS = ("scripted", "consume-retained")
TIMINGS = get_args(abi.TransferTiming)
SOURCE = abi.RECOVER_SOURCE.replace("destination_alias = d", "destination_alias = a")


def digest(data):
    return sha256(data).hexdigest()


def run_command(args, directory, data=None):
    return subprocess.run(args, cwd=directory, input=data, check=True,
                          text=True, capture_output=True, timeout=90).stdout


def compile_providers(directory):
    original = (HERE.parent / "NATIVE-OWNED-ABI-01" / "provider.c").read_text()
    changed = abi.replace_exact(
        original, "    if (disposition == RETAINED)\n",
        "    if (disposition == RETAINED)\n        disposition = CONSUMED;\n\n    if (disposition == RETAINED)\n",
    )
    artifacts = {}
    for label, source in zip(PROVIDERS, (original, changed), strict=True):
        provider = directory / label
        provider.mkdir()
        (provider / "provider.c").write_text(source, encoding="utf-8")
        run_command(["gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2",
                     "-c", "provider.c", "-o", "provider.o"], provider)
        symbols = run_command(["nm", "-g", "--defined-only", "provider.o"], provider)
        assert sorted(line.split()[-1] for line in symbols.splitlines()) == [
            "rt_acquire", "rt_begin", "rt_finish", "rt_release",
        ]
        artifacts[label] = provider / "provider.o", digest(source.encode())
    return artifacts


def header(caller):
    macros = {
        "FIRST_SOURCE": "abcd".index(caller.workload.first.source),
        "FIRST_DESTINATION": "abcd".index(caller.workload.first.destination),
        "SECOND_SOURCE": "abcd".index(caller.workload.second.source),
        "SECOND_DESTINATION": "abcd".index(caller.workload.second.destination),
        "EARLY_TRANSFER": int(caller.timing == "before_cleanup"),
        "RECOVER_HANDLE": int(dict(caller.actions)["error_with_handle"] == "release_first"),
    }
    assert all(action == "preserve" for group, action in caller.actions if group != "error_with_handle")
    return "".join(f"#define {key} {value}\n" for key, value in macros.items())


def set_disposition(disposition, profile):
    return "consumed_error" if profile == "consume-retained" and disposition == "retained_error" else disposition


def reference(caller, cases, profile):
    observations = []
    for inputs, released in cases:
        mapped = replace(inputs, local_close=set_disposition(inputs.local_close, profile),
                         handle_close=set_disposition(inputs.handle_close, profile))
        outcome = abi.execute(caller, mapped, set_disposition(released, profile))
        observations.extend(f"{abi._encode(outcome)}|{abi.encode_audit(outcome, physical)}"
                            for physical in (False, True))
    return observations


def admit(store, snapshot, contract, artifact):
    payload = store.get(snapshot.mapping["close-provider"]).payload
    return payload["required_contract"] == contract and payload["object_sha256"] == digest(artifact.read_bytes())


def native_rows(directory, provider, encoded, expected):
    commands = {
        "C": ["gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2",
              "caller.c", str(provider), "-o", "caller-c"],
        "Rust": ["rustc", "--edition=2021", "-D", "warnings", "-C", "opt-level=3",
                 "-C", f"link-arg={provider}", "caller.rs", "-o", "caller-rust"],
    }
    result = {}
    for language, command in commands.items():
        run_command(command, directory)
        complete = run_command([f"./caller-{language.lower()}"], directory, encoded)
        values = complete.splitlines()
        for index, (got, want) in enumerate(zip(values, expected, strict=True)):
            if got != want:
                raise AssertionError((language, index, want, got))
        result[language] = {"rows": len(values), "trace_sha256": digest(complete.encode())}
    assert result["C"] == result["Rust"]
    return result


def check_model(directory):
    model = HERE / "Disposition.lean"
    version = run_command(["lean", "--version"], directory).strip()
    assert version.startswith("Lean (version 4.36.0,")
    axioms = run_command(["lean", str(model)], directory).splitlines()
    assert axioms == [
        "'decode_preserves_obligation' depends on axioms: [propext]",
        "'distinct_bindings_change_retained_request' depends on axioms: [propext]",
    ]
    return {"version": version, "model_sha256": digest(model.read_bytes()), "axiom_report": axioms}


def check(directory):
    model = check_model(directory)
    gcc = abi.tool_banner("gcc")
    rustc = abi.tool_banner("rustc")
    assert abi.checked_run(["gcc", "-dumpfullversion"]).strip() == "14.2.0"
    assert rustc.split()[:2] == ["rustc", "1.85.1"]
    roles = (*product("abc", repeat=4), ("a", "b", "c", "d"))
    outcomes = get_args(abi.Disposition)
    cases = [(abi.Inputs(ids, wants, local, handle), caller)
             for ids, wants, local, handle, caller in product(roles, (False, True), outcomes, outcomes, outcomes)]
    encoded = "".join(abi.encode_input(*case, physical) for case in cases for physical in (False, True))
    artifacts = compile_providers(directory)
    (directory / "caller.c").write_bytes((HERE / "caller.c").read_bytes())
    store = ContentStore()
    contract = store.put("rt13-close-contract", {"abi": "disposition:u32, usable_token:u32",
                         "cases": outcomes, "scope": "sequential fixture role provider"})
    provider_values = {
        label: store.put("rt13-close-provider", {"required_contract": contract,
                         "source_sha256": source_sha, "object_sha256": digest(path.read_bytes())})
        for label, (path, source_sha) in artifacts.items()
    }

    results = {}
    for timing in TIMINGS:
        caller = abi.compile_caller(SOURCE, timing)
        fixture_header = header(caller)
        generated = abi.generate_linked(SOURCE, timing)
        (directory / "fixture.h").write_text(fixture_header, encoding="utf-8")
        (directory / "caller.rs").write_text(generated, encoding="utf-8")
        caller_value = store.put("rt13-caller-source", {"source_sha256": digest(SOURCE.encode()),
                                 "required_contract": contract, "transfer": timing})
        snapshots = {label: make_snapshot({"caller": caller_value, "close-provider": address,
                                           "required-contract": contract})
                     for label, address in provider_values.items()}
        observations = {}
        for label in PROVIDERS:
            artifact, _ = artifacts[label]
            bound = snapshots[label]
            assert admit(store, bound, contract, artifact)
            other, = set(PROVIDERS) - {label}
            assert not admit(store, bound, contract, artifacts[other][0])
            expected = reference(caller, cases, label)
            observations[label] = expected
            result = native_rows(directory, artifact, encoded, expected)
            results[f"{timing}/{label}"] = {
                "semantic_root": bound.root_hash, "caller_source_value": caller_value,
                "provider_value": provider_values[label],
                "generated_rust_sha256": digest(generated.encode()),
                "compiled_c_configuration_sha256": digest(fixture_header.encode()),
                "native": result, "substituted_object_rejected": True,
            }
        original, replacement = (observations[label] for label in PROVIDERS)
        differences = 0
        language_changes = 0
        audit_changes = 0
        for old, new in zip(original, replacement, strict=True):
            if old != new:
                differences += 1
                old_trace, old_audit = old.rsplit("|", 1)
                new_trace, new_audit = new.rsplit("|", 1)
                language_changes += old_trace != new_trace
                audit_changes += old_audit != new_audit
        assert differences > 0 and language_changes > 0 and audit_changes > 0
        assert len({snapshot.root_hash for snapshot in snapshots.values()}) == 2
        results[f"{timing}/rebind"] = {
            "same_caller_source_and_contract": True,
            "different_exact_roots": True,
            "incorrect_cached_rows_with_caller_and_contract_key": differences,
            "language_trace_changes": language_changes,
            "physical_audit_changes": audit_changes,
            "total_rows_per_provider": len(original),
        }

    return {"format": "rt13-bound-owned-providers/1", "python": sys.version.split()[0],
            "gcc": gcc, "rustc": rustc, "lean_model": model,
            "contract": contract, "input_rows_sha256": digest(encoded.encode()),
            "c_caller_sha256": digest((HERE / "caller.c").read_bytes()),
            "providers": {label: store.get(value).payload for label, value in provider_values.items()},
            "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-bound-owned-providers-") as scratch:
        evidence = check(Path(scratch))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
