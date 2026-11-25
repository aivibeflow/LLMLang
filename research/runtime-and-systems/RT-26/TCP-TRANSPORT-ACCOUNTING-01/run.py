#!/usr/bin/env python3
"""Compare Linux TCP socket counters to independently modeled task delivery."""
import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
FIELDS = ("app_sent", "tcp_sent", "tcp_acked", "tcp_arrived", "alias_tcp_arrived",
          "tcp_retransmitted", "queue", "alias_queue",
          "task_a_copied", "task_b_copied", "task_a_consumed", "task_b_consumed")


def call(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, (command, result.stderr)
    return result.stdout


def oracle(first, second, peek, read_a, read_b):
    queue = bytearray()
    sent = 0
    copied, consumed = [0, 0], [0, 0]
    rows = []

    def emit(phase, value=b""):
        counters = (sent, sent, sent, sent, sent, 0, len(queue), len(queue),
                    *copied, *consumed)
        rows.append({"phase": phase, **dict(zip(FIELDS, counters)), "bytes": value.hex() or "-"})

    def add(amount, phase):
        nonlocal sent
        queue.extend(13 + 17 * index - 251 * ((13 + 17 * index) // 251)
                     for index in range(sent, sent + amount))
        sent += amount
        emit(phase)

    def take(amount, reader, consuming, phase):
        observed = bytes(queue[:amount])
        copied[reader] += len(observed)
        if consuming:
            consumed[reader] += len(observed)
            del queue[:len(observed)]
        emit(phase, observed)

    emit("initial")
    add(first, "enqueue-first")
    take(peek, 1, False, "peek-second-reader")
    take(read_a, 0, True, "read-first")
    add(second, "enqueue-second")
    take(read_b, 1, True, "read-second")
    take(peek, 0, False, "peek-first-reader")
    take(len(queue), 0, True, "drain-first")
    return rows


def measure(binary, data, cwd):
    output = call([binary, *map(str, data)], cwd)
    rows = []
    for line in output.splitlines():
        phase, *values, received = line.split("\t")
        assert len(values) == len(FIELDS)
        rows.append({"phase": phase, **dict(zip(FIELDS, map(int, values))), "bytes": received})
    expected = oracle(*data)
    assert rows == expected, (data, rows, expected)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt26-tcp-transport-") as path:
        root = Path(path)
        cases = list(product((8, 21), (9, 31), (2, 12), (3, 7), (2, 6)))
        profiles = {}
        for flags in ("-O0", "-O2"):
            binary = root / ("probe" + flags)
            call(["gcc", "-std=c11", flags, "-Wall", "-Wextra", "-Werror",
                  HERE / "probe.c", "-o", binary], root)
            profiles[flags] = [measure(binary, request, root) for request in cases]
        assert profiles["-O0"] == profiles["-O2"]
        records = []
        for request, rows in zip(cases, profiles["-O0"]):
            final = rows[-1]
            unique = final["task_a_consumed"] + final["task_b_consumed"]
            copied = final["task_a_copied"] + final["task_b_copied"]
            as_distinct_sockets = final["tcp_arrived"] + final["alias_tcp_arrived"]
            assert unique == request[0] + request[1] and copied > unique
            assert as_distinct_sockets == unique * 2 and final["queue"] == 0
            records.append({"inputs": request, "phases": rows, "final_unique_consumed": unique,
                            "extra_copies_from_peek": copied - unique,
                            "overcharge_from_counting_each_descriptor_as_socket": as_distinct_sockets - unique})
        total_bytes = sum(row["final_unique_consumed"] for row in records)
        copied_extras = sum(row["extra_copies_from_peek"] for row in records)
        result = {"source_sha256": sha256((HERE / "probe.c").read_bytes()).hexdigest(),
                  "profiles": list(profiles), "cases": records, "runs": len(records) * len(profiles),
                  "observed_phases": sum(len(row["phases"]) for row in records) * len(profiles),
                  "unique_bytes_per_profile": total_bytes, "extra_copies_per_profile": copied_extras,
                  "compiler": call(["gcc", "--version"], root).splitlines()[0],
                  "kernel": call(["uname", "-r"], root).strip(),
                  "linux_tcp_header_sha256": sha256(Path("/usr/include/linux/tcp.h").read_bytes()).hexdigest(),
                  "libc": call(["getconf", "GNU_LIBC_VERSION"], root).strip()}
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
