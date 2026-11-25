"""Separate linked memory usage, archive stack evidence and conditional deadlines."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent


def response_time(cost, in_flight, period, service):
    if service >= period:
        return None
    response = cost + in_flight
    while True:
        arrivals = (response + period - 1) // period
        following = cost + in_flight + arrivals * service
        if response == following:
            return response
        response = following


def dispatch(cost, in_flight, period, service, horizon):
    pending = 0
    for tick in range(horizon):
        if tick % period == 0:
            pending += service
        if tick < in_flight:
            continue
        if pending:
            pending -= 1
        else:
            cost -= 1
            if cost == 0:
                return tick + 1
    return None


def deadlines():
    outcomes = {"met": 0, "missed": 0, "no_completion": 0}
    false_accept = 0
    max_response = 0
    for cost, in_flight, period, service in product(range(1, 6), range(5), range(2, 8), range(8)):
        calculated = response_time(cost, in_flight, period, service)
        horizon = 2 * period if service >= period else (
            (cost + in_flight + service) * period // (period - service) + 1
        )
        actual = dispatch(cost, in_flight, period, service, horizon)
        assert calculated == actual, (cost, in_flight, period, service)
        if actual is not None:
            max_response = max(actual, max_response)
        for limit in range(1, 17):
            meets = actual is not None and actual <= limit
            key = "no_completion" if actual is None else ("met" if meets else "missed")
            outcomes[key] += 1
            if cost <= limit and not meets:
                false_accept += 1
    return {"scenarios": 1200, "deadline_checks": outcomes,
            "cost_only_false_accepts": false_accept, "max_finite_response_ticks": max_response}


def read(path):
    return json.loads((ROOT / path).read_text())


def elf(name, path, expected):
    header_path = Path(__file__).parent / f"{name}-program-headers.txt"
    output = header_path.read_text()
    image_size = None
    if path is not None:
        image = path.read_bytes()
        image_size = len(image)
        assert sha256(image).hexdigest() == expected
        actual = subprocess.check_output(["readelf", "-lW", path], text=True, timeout=10)
        assert [line.rstrip() for line in actual.splitlines()] == output.splitlines()
    loads = []
    for line in output.splitlines():
        fields = line.split()
        if not fields or fields[0] != "LOAD":
            continue
        offset, address, physical, file_size, memory_size = (int(value, 16) for value in fields[1:6])
        assert file_size <= memory_size
        if image_size is not None:
            assert offset + file_size <= image_size
        loads.append({"address": address, "physical": physical, "file_bytes": file_size,
                      "memory_bytes": memory_size})
    assert loads
    return loads


def arm_layout(loads, memory):
    starts = {name: (int(address, 16), size) for name, (address, size) in memory.items()}
    extents = {name: 0 for name in starts}
    for segment in loads:
        address = segment["address"]
        candidates = [name for name, (start, length) in starts.items()
                      if start <= address and address + segment["memory_bytes"] <= start + length]
        assert len(candidates) == 1, segment
        name = candidates[0]
        extents[name] = max(extents[name], address + segment["memory_bytes"] - starts[name][0])
    return extents


def compose(options):
    manifests = read("MCU-TARGET-MANIFESTS-01/manifests.json")["profiles"]
    arm = read("MCU-GPIO-TIMER-UART-01/stm32-evidence.json")
    esp = read("MCU-GPIO-TIMER-UART-01/esp-evidence.json")
    stm = {name: arm_layout(elf(name, path, arm[name]["elf_sha256"]), manifests[name]["memory"])
           for name, path in (("f1", options.f1), ("f4", options.f4))}
    esp_segments = elf("esp", options.esp, esp["elf_sha256"])
    nested = read("cortex-m3-nested-stack/evidence.json")
    stack = read("cortex-m3-stack/results.json")
    return {
        "stm32_memory_extent_bytes": stm, "esp_load_segments": esp_segments,
        "stack_archives": {
            "fixed_scope": sorted(stack.keys()),
            "nested_scope": sorted(nested.keys()),
            "fixed_sha256": sha256((ROOT / "cortex-m3-stack/results.json").read_bytes()).hexdigest(),
            "nested_sha256": sha256((ROOT / "cortex-m3-nested-stack/evidence.json").read_bytes()).hexdigest(),
        },
        "logical_periodic_deadlines": deadlines(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for target in ("f1", "f4", "esp"):
        parser.add_argument(f"--{target}", type=Path)
    print(json.dumps(compose(parser.parse_args()), indent=2, sort_keys=True))
