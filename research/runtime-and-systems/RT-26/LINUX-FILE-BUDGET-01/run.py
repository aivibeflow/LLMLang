"""Compare actual Linux file size enforcement with a shared reservation ledger."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import errno
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory


CAP = 4096


def worker(cap, mode, writes):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
    disposition = signal.SIG_DFL if mode == "default-signal" else signal.SIG_IGN
    signal.signal(signal.SIGXFSZ, disposition)
    if mode == "crash-before":
        os._exit(71)

    operations = {}
    for path, requested in writes:
        written = []
        completed = 0
        length_error = None
        with path.open("xb", buffering=0) as file:
            while completed < requested:
                try:
                    count = file.write(b"a" * (requested - completed))
                except OSError as error:
                    if error.errno != errno.EFBIG:
                        raise
                    length_error = "EFBIG"
                    break
                if not count:
                    raise ValueError("Unexpected zero-length write")
                written.append(count)
                completed += count
            file.flush()
        operations[path.name] = {"writes": written, "error": length_error}
    if mode == "crash-after":
        os._exit(72)
    print(json.dumps(operations, sort_keys=True))
    return 0


def size(path):
    return path.stat().st_size if path.exists() else 0


def run_child(cap, mode, writes):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(cap), mode]
    for path, requested in writes:
        command.extend((str(path), str(requested)))
    process = subprocess.run(command, text=True, capture_output=True, timeout=10)
    if process.stderr:
        raise ValueError(process.stderr)
    return {
        "status": process.returncode,
        "reported": json.loads(process.stdout) if process.stdout else None,
        "file_sizes": {path.name: size(path) for path, _ in writes},
    }


class Ledger:
    """One task group's pending capacity and live file lengths."""

    def __init__(self, limit):
        self.limit = limit
        self.pending = {}
        self.live = {}

    def reserve(self, path, amount):
        if path in self.pending or path in self.live or path.exists():
            raise ValueError("Expected a fresh tracked file")
        if self.total() + amount > self.limit:
            return False
        self.pending[path] = amount
        return True

    def settle(self, path):
        actual = size(path)
        if actual > self.pending[path]:
            raise ValueError("Child exceeded its assigned file reservation")
        del self.pending[path]
        if path.exists():
            self.live[path] = actual

    def remove(self, path):
        if path.stat().st_size != self.live[path]:
            raise ValueError("Tracked file changed outside the fixture boundary")
        path.unlink()
        del self.live[path]

    def total(self):
        return sum(self.live.values()) + sum(self.pending.values())

    def state(self):
        return {"pending": sum(self.pending.values()), "live": sum(self.live.values()),
                "remaining": self.limit - self.total()}


def check(value, expected):
    if value != expected:
        raise AssertionError(f"Observed {value!r}, expected {expected!r}")
    return value


def local_caps(work):
    sequence = run_child(CAP, "normal", [(work / "limited", 6144)])
    check(sequence, {"status": 0, "reported": {"limited": {"writes": [CAP], "error": "EFBIG"}},
                     "file_sizes": {"limited": CAP}})
    terminated = run_child(CAP, "default-signal", [(work / "terminated", 6144)])
    check(terminated, {"status": -int(signal.SIGXFSZ), "reported": None, "file_sizes": {"terminated": CAP}})

    split = run_child(CAP, "normal", [(work / "split-a", 3072), (work / "split-b", 3072)])
    check(split["status"], 0)
    check(split["file_sizes"], {"split-a": 3072, "split-b": 3072})

    # Both client checks observe the same empty group before either starts its write.
    split_check = [3072 <= CAP, 3072 <= CAP]
    with ThreadPoolExecutor(max_workers=2) as worker_pool:
        children = list(worker_pool.map(lambda name: run_child(CAP, "normal", [(work / name, 3072)]),
                                        ("separate-a", "separate-b")))
    check([child["status"] for child in children], [0, 0])
    total = sum(length for child in children for length in child["file_sizes"].values())
    check(total, 6144)
    return {"single_file_error": sequence, "single_file_signal": terminated,
            "one_process_two_files_bytes": sum(split["file_sizes"].values()),
            "two_workers_two_files_bytes": total, "split_runtime_checks_accepted": split_check,
            "root_overshoot_bytes": total - CAP}


def brokered(work):
    ledger = Ledger(CAP)
    alpha, beta = work / "alpha", work / "beta"
    check(ledger.reserve(alpha, 3072), True)
    check(ledger.reserve(beta, 3072), False)
    reserved = check(ledger.state(), {"pending": 3072, "live": 0, "remaining": 1024})
    child = run_child(3072, "normal", [(alpha, 3072)])
    check(child["status"], 0)
    ledger.settle(alpha)
    live = check(ledger.state(), {"pending": 0, "live": 3072, "remaining": 1024})
    check(ledger.reserve(beta, 3072), False)
    ledger.remove(alpha)
    check(ledger.reserve(beta, 3072), True)
    child = run_child(3072, "normal", [(beta, 3072)])
    check(child["status"], 0)
    ledger.settle(beta)
    after = check(ledger.state(), live)
    ledger.remove(beta)
    return {"reservation": reserved, "settled": live, "retry_after_unlink": after,
            "fully_released": check(ledger.state(), {"pending": 0, "live": 0, "remaining": CAP})}


def failures(work):
    ledger = Ledger(CAP)
    records = {}
    for mode, requested, exit_code, actual in (
        ("crash-before", 2048, 71, 0),
        ("crash-after", 1536, 72, 1536),
        ("writes-over-reservation", 3072, 0, 2048),
    ):
        path = work / mode
        check(ledger.reserve(path, 2048), True)
        child = run_child(2048, "normal" if exit_code == 0 else mode, [(path, requested)])
        check(child["status"], exit_code)
        check(child["file_sizes"][path.name], actual)
        if not exit_code:
            check(child["reported"][path.name]["error"], "EFBIG")
        ledger.settle(path)
        records[mode] = {"child": child,
                         "settlement": check(ledger.state(), {"pending": 0, "live": actual,
                                                              "remaining": CAP - actual})}
        if path in ledger.live:
            ledger.remove(path)
        check(ledger.total(), 0)
    return records


def replay():
    if platform.system() != "Linux":
        raise ValueError("This fixture requires Linux")
    with TemporaryDirectory(prefix="llmlang-file-budget-") as directory:
        work = Path(directory)
        return {"limit_bytes": CAP, "os": platform.system(), "kernel": platform.release(),
                "python": platform.python_version(), "local_caps": local_caps(work),
                "brokered": brokered(work), "failed_processes": failures(work)}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        cap, mode = sys.argv[2:4]
        writes = [(Path(path), int(requested))
                  for path, requested in zip(sys.argv[4::2], sys.argv[5::2], strict=True)]
        sys.exit(worker(int(cap), mode, writes))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
