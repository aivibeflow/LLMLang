#!/usr/bin/env python3
"""Replay native async cancellation and explicit cleanup with an independent resource oracle."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SCOPES = tuple(product(range(4), range(3), range(4), range(2)))


def oracle(polls, failure, diagnostics, explicit):
    acquisitions = []
    outcome = "cancelled"
    held = []
    if polls:
        if failure == 1:
            acquisitions.append("acquire-failed:A")
            outcome = "acquire:A"
        else:
            acquisitions.append("acquire:A")
            held.append(("A", 1))
            if polls >= 2:
                if failure == 2:
                    acquisitions.append("acquire-failed:B")
                    outcome = "acquire:B"
                else:
                    acquisitions.append("acquire:B")
                    held.append(("B", 2))
                    if polls >= 3:
                        outcome = "completed"
    explicitly_closed = explicit and outcome != "cancelled"
    events = acquisitions.copy()
    reported = []
    for name, bit in reversed(held):
        mode = "close" if explicitly_closed else "drop"
        status = "diagnostic" if diagnostics & bit else "ok"
        if explicitly_closed and status == "diagnostic":
            reported.append(name)
        events.append(f"{mode}:{name}:{status}")
    response = "cancelled" if outcome == "cancelled" else f"{outcome}/{','.join(reported)}"
    return response, events


def experiment(root):
    rustc = os.environ.get("RUSTC", "rustc")
    outcomes = {}
    for optimization in (0, 2):
        binary = root / f"app-{optimization}"
        subprocess.run(
            [rustc, "--edition=2021", "-Dwarnings", "-C", f"opt-level={optimization}",
             str(HERE / "ownership.rs"), "-o", str(binary)],
            check=True, capture_output=True,
        )
        native = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
        assert not native.stderr
        counts = Counter()
        diagnostics = Counter()
        conditions = []
        for scope, line in zip(SCOPES, native.stdout.splitlines(), strict=True):
            header, result, listed = line.split(" | ", 2)
            assert tuple(map(int, header.split())) == scope
            expected_result, events = oracle(*scope)
            observed = listed.split(",") if listed else []
            assert (result, observed) == (expected_result, events)
            disposition = result.split("/")[0]
            counts[disposition] += 1
            failure_events = [event for event in observed if event.endswith(":diagnostic")]
            diagnostics["cleanup_diagnostics"] += len(failure_events)
            diagnostics["explicitly_reported"] += sum(event.startswith("close:") for event in failure_events)
            diagnostics["drop_only"] += sum(event.startswith("drop:") for event in failure_events)
            if result == "completed/B,A":
                conditions.append({"scope": scope, "result": result, "trace": observed})
        assert conditions and diagnostics["drop_only"] and diagnostics["explicitly_reported"]
        outcomes[optimization] = {
            "scopes": len(SCOPES), "dispositions": dict(counts), "diagnostics": dict(diagnostics),
            "two_failures": conditions, "stdout_sha256": sha256(native.stdout.encode()).hexdigest(),
        }
    assert outcomes[0] == outcomes[2]
    return {"format": "async-resource-cancellation-01", "rust": subprocess.check_output(
        [rustc, "--version"], text=True).strip(), "outcomes": outcomes}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-async-cancellation-") as work:
        evidence = experiment(Path(work))
    raw = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(raw, encoding="utf-8")
    else:
        print(raw, end="")
