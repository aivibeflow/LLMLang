#!/usr/bin/env python3
"""Observe where early and staged ownership transfers satisfy caller contracts."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import get_args

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "RT-04-01"
sys.path.insert(0, str(PROTOTYPE))

from rt04_return_disposition import Disposition, TransferTiming  # noqa: E402
from rt04_rust_owned_probe import _encode, generate  # noqa: E402
from rt04_shared_owned_handlers import PRESERVE_SOURCE, compile_caller, execute  # noqa: E402
from rt04_shared_owned_workload import Inputs  # noqa: E402

ALIASES = (("a", "b", "c", "d"), ("a", "b", "a", "b"))
RELEASE = "ok"


def domain():
    dispositions = get_args(Disposition)
    return [
        Inputs(identities, wants, local, handle)
        for identities, wants, local, handle in product(ALIASES, (False, True), dispositions, dispositions)
    ]


def input_csv(cases):
    return "".join(
        ",".join((*case.identities, str(int(case.wants_value)), case.local_close, case.handle_close, RELEASE))
        + "\n"
        for case in cases
    )


def checked_outputs(compiler, cases, timing, directory):
    generated = generate(PRESERVE_SOURCE, timing)
    source = directory / "provider.rs"
    source.write_text(generated, encoding="utf-8")
    binary = directory / "provider"
    caller = compile_caller(PRESERVE_SOURCE, timing)
    expected = [_encode(execute(caller, inputs, RELEASE)) for inputs in cases]
    for level in ("0", "3"):
        subprocess.run(
            [compiler, "--edition=2021", "-D", "warnings", "-C", f"opt-level={level}",
             str(source), "-o", str(binary)], check=True, timeout=60,
        )
        actual = subprocess.check_output([str(binary)], input=input_csv(cases), text=True, timeout=60).splitlines()
        if actual != expected:
            raise ValueError(f"Native trace mismatch for {timing} at O{level}")
    return actual, sha256(generated.encode()).hexdigest()


def contract_observation(raw):
    tag, _, _, _, cleanup, second, _, forwarded = raw.split("|")
    return {
        "tag": tag, "cleanup_reported": bool(cleanup), "second": second,
        "owned_handle_forwarded": "handle,owned" in forwarded.split(";"),
    }


def compare(compiler):
    version = subprocess.check_output([compiler, "--version"], text=True).strip()
    if not version.startswith("rustc 1.85.1 "):
        raise ValueError(f"Expected pinned rustc 1.85.1, got {version}")
    cases = domain()
    outputs = {}
    source_ids = {}
    with TemporaryDirectory(prefix="llmlang-owned-transfer-") as tmp:
        for timing in get_args(TransferTiming):
            outputs[timing], source_ids[timing] = checked_outputs(compiler, cases, timing, Path(tmp))

    results = []
    for index, case in enumerate(cases):
        if not case.wants_value or case.local_close == "ok":
            continue
        early = contract_observation(outputs["before_cleanup"][index])
        staged = contract_observation(outputs["after_cleanup"][index])
        if not early["cleanup_reported"] or not staged["cleanup_reported"]:
            raise ValueError("Cleanup-failure input failed to observe its cleanup error")
        if not early["owned_handle_forwarded"] or staged["owned_handle_forwarded"]:
            raise ValueError("Unexpected outcome for the owned-return contract pair")
        results.append({
            "identities": case.identities, "wants_value": case.wants_value,
            "local_close": case.local_close, "handle_close": case.handle_close,
            "early": early, "staged": staged,
            "early_raw_trace": outputs["before_cleanup"][index],
            "staged_raw_trace": outputs["after_cleanup"][index],
        })
    overlap = [row for row in results if row["identities"] == ALIASES[1]]
    return {
        "schema": "llmlang-owned-transfer-discriminator-v1",
        "python": sys.version,
        "rustc": subprocess.check_output([compiler, "-vV"], text=True).strip(),
        "source_sha256": {
            file.name: sha256(file.read_bytes()).hexdigest()
            for file in (Path(__file__), PROTOTYPE / "rt04_owned_probe.rs",
                         PROTOTYPE / "rt04_rust_owned_probe.py", PROTOTYPE / "rt04_shared_owned_handlers.py",
                         PROTOTYPE / "rt04_shared_owned_workload.py")
        },
        "source_fixture_sha256": sha256(PRESERVE_SOURCE.encode()).hexdigest(),
        "generated_rust_sha256": source_ids,
        "inputs_per_timing": len(cases),
        "native_trace_comparisons": len(cases) * len(outputs) * 2,
        "cleanup_failure_pairs": len(results),
        "error_only_indistinguishable_pairs": sum(
            row["early"]["cleanup_reported"] == row["staged"]["cleanup_reported"] for row in results
        ),
        "overlapping_second_call_outcomes": {
            timing: dict(Counter(row[timing]["second"] for row in overlap))
            for timing in ("early", "staged")
        },
        "observations": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = compare(args.rustc)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: data[name] for name in (
        "native_trace_comparisons", "cleanup_failure_pairs", "error_only_indistinguishable_pairs",
        "overlapping_second_call_outcomes",
    )}, indent=2))
