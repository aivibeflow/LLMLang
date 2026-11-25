#!/usr/bin/env python3
"""Compare cancellation and settlement against scripted native worker schedules."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
POLICIES = ("guarded", "admission_only", "early_terminal")
SCENARIOS = {
    "completed": (0, ("s0", "s1", "w0", "w1", "f1", "f0"), ("ok", "ok"), ("A", "B")),
    "cancel_before_start": (0, ("c0", "s0", "s1", "w1", "f0", "f1"), ("cancelled", "ok"), ("", "B")),
    "cancel_before_write": (0, ("s0", "s1", "c0", "w0", "w1", "f0", "f1"),
                            ("cancelled", "ok"), ("", "B")),
    "cancel_after_write": (0, ("s0", "w0", "c0", "s1", "w1", "f0", "f1"),
                           ("ok", "ok"), ("A", "B")),
    "cancel_after_error": (1, ("s0", "s1", "w0", "c0", "w1", "f0", "f1"),
                           ("io_failure", "ok"), ("", "B")),
    "cancel_before_error": (2, ("s1", "s0", "c1", "w1", "w0", "f1", "f0"),
                            ("ok", "cancelled"), ("A", "")),
    "repeat_cancellation": (0, ("s0", "s1", "c0", "c0", "w0", "w1", "f0", "c0", "f1", "f0"),
                            ("cancelled", "ok"), ("", "B")),
    "two_failures": (3, ("s0", "s1", "w0", "w1", "f0", "f1"),
                     ("io_failure", "io_failure"), ("", "")),
}
COMMANDS = {"s": "start", "w": "write", "c": "cancel", "f": "settle"}


def request(short):
    kind = COMMANDS[short[0]]
    task = int(short[1])
    sender = 1 - task if kind == "cancel" else task
    return sender, task, kind


def exercise(directory, command, policy, name):
    mask, steps, expected_status, expected_effects = SCENARIOS[name]
    directory.mkdir()
    for task in range(2):
        (directory / f"job-{task}").write_bytes(b"")
    script = [request(item) for item in steps]
    wire = "\n".join(" ".join(map(str, step)) for step in script) + "\n"
    result = subprocess.run([*command, str(directory), policy, str(mask)], input=wire,
                            text=True, capture_output=True, check=True, timeout=15)
    assert result.stderr == ""
    lines = result.stdout.splitlines()
    assert len(lines) == len(script) + 1 and lines[-1].startswith("final ")
    final = lines[-1].split()[1:]
    data = [(directory / f"job-{task}").read_text() for task in range(2)]
    active, revoked = [False, False], [False, False]
    counts = Counter()
    events = []
    for line, (sender, task, kind) in zip(lines[:-1], script, strict=True):
        prefix, actor, slot, event, handles, released = line.split()
        assert (prefix, int(actor), int(slot)) == ("step", sender, task)
        assert len(handles) == 2 and released in {"0", "1"}
        if event == "started":
            assert not active[task]
            active[task] = True
            counts["acquisitions"] += 1
        if released == "1":
            assert active[task] and kind == "settle"
            active[task] = False
            counts["confirmed_releases"] += 1
        assert handles == "".join(str(int(owned)) for owned in active)
        if event in {"requested", "early_cancelled"}:
            revoked[task] = True
        if event in {"written", "write_failed"} and revoked[task]:
            counts["write_attempts_after_revocation"] += 1
        if event == "early_cancelled" and active[task]:
            counts["early_terminal_live_handle"] += 1
        events.append({"actor": sender, "task": task, "command": kind, "event": event,
                       "open_handles": handles, "released": released == "1"})
    assert not any(active) and counts["confirmed_releases"] == counts["acquisitions"]
    counts["wrong_outcomes"] = sum(left != right for left, right in zip(final, expected_status, strict=True))
    counts["wrong_effects"] = sum(left != right for left, right in zip(data, expected_effects, strict=True))
    return {"case": name, "policy": policy, "expected": [expected_status, expected_effects],
            "observed": [final, data], "events": events, "counts": dict(counts)}


def run(directory):
    routes = {"python": [sys.executable, "-B", str(HERE / "worker.py")]}
    for level in (0, 3):
        output = directory / f"rust-{level}"
        subprocess.run(["rustc", "--edition=2021", "-Dwarnings", "-C", f"opt-level={level}",
                        str(HERE / "worker.rs"), "-o", str(output)], check=True, timeout=30)
        routes[f"rust_O{level}"] = [str(output)]
    checks = []
    for name, policy in product(SCENARIOS, POLICIES):
        results = [exercise(directory / f"{name}-{policy}-{backend}", command, policy, name)
                   for backend, command in routes.items()]
        assert all(result == results[0] for result in results)
        checks.append(results[0])
    metrics = {}
    categories = ("acquisitions", "confirmed_releases", "write_attempts_after_revocation",
                  "early_terminal_live_handle", "wrong_outcomes", "wrong_effects")
    for policy in POLICIES:
        chosen = [row["counts"] for row in checks if row["policy"] == policy]
        metrics[policy] = {field: sum(row.get(field, 0) for row in chosen) for field in categories}
    assert all(metrics["guarded"][field] == 0 for field in categories[2:])
    assert metrics["admission_only"]["write_attempts_after_revocation"] > 0
    assert metrics["early_terminal"]["early_terminal_live_handle"] > 0
    return {
        "schema": "llmlang-rt01-resource-worker/1", "python": platform.python_version(),
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True).splitlines(),
        "linux": platform.release(),
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                          for path in (HERE / "worker.py", HERE / "worker.rs", Path(__file__))},
        "scenarios": len(SCENARIOS), "configurations": list(routes), "native_runs": len(checks) * len(routes),
        "native_steps": sum(len(row["events"]) for row in checks) * len(routes),
        "metrics_per_host_configuration": metrics, "observations": checks,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt01-resource-worker-") as temporary:
        result = run(Path(temporary))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
