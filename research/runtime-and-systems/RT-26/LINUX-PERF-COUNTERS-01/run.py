"""Record Linux perf_event_open availability without modifying host policy."""

import argparse
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent


def checked(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, check=True, timeout=20).stdout


def measure(compiler):
    version = checked([compiler, "--version"]).splitlines()[0]
    source = HERE / "probe.c"
    with TemporaryDirectory(prefix="llmlang-perf-") as work:
        program = Path(work) / "probe"
        checked([compiler, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(program)])
        lines = checked([str(program)]).splitlines()
    events = {}
    data = {}
    native_samples = {}
    for row in lines:
        event, error, count, enabled, running = row.split(",")
        if event == "fallback":
            data = {"cpu_ns": int(error), "minor_faults": int(count), "voluntary_context_switches": int(enabled),
                    "involuntary_context_switches": int(running)}
            continue
        if int(error):
            events[event] = {"status": "unavailable", "errno": errno.errorcode[int(error)]}
        else:
            value, enabled_ns, running_ns = map(int, (count, enabled, running))
            if not 0 <= running_ns <= enabled_ns:
                raise AssertionError((event, enabled_ns, running_ns))
            events[event] = {"status": "sampled" if running_ns else "not_scheduled"}
            native_samples[event] = {"value": value, "enabled_ns": enabled_ns, "running_ns": running_ns}
    if len(events) != 5 or data["cpu_ns"] < 20_000_000 or data["minor_faults"] < 64:
        raise AssertionError((data, events))
    policy = Path("/proc/sys/kernel/perf_event_paranoid").read_text().strip()
    return {
        "format": "rt26-linux-perf-counters/1", "python": sys.version.split()[0],
        "kernel_release": os.uname().release, "architecture": os.uname().machine,
        "compiler": version, "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "observed_perf_event_paranoid": int(policy), "self_user_space_events": events,
        "fallback": {"thread_cpu_at_least_20ms": True, "minor_faults_at_least_64": True,
                     "context_switch_counters_observed": True},
    }, {"fallback": data, "native_samples": native_samples}


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("this fixture checks native Linux counter access")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw", type=Path)
    options = parser.parse_args()
    evidence, sample = measure(options.cc)
    options.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if options.raw is not None:
        options.raw.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
