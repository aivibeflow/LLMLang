"""Compare Linux descriptor closure with cooperative cancellation of one outstanding read."""

import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
from queue import Queue
import select
import subprocess
import sys
import threading
import time


HERE = Path(__file__).resolve().parent
READ = 0
POLL = (7, 271)
RESERVED = 4
CASES = ("close_reuse_reader", "close_last_writer", "data_only", "cancel_only",
         "both_ready_cancel_first", "both_ready_data_first")


def await_syscall(tid, numbers, descriptor=None):
    allowed = {numbers} if isinstance(numbers, int) else set(numbers)
    path = Path(f"/proc/self/task/{tid}/syscall")
    expiration = time.monotonic() + 5
    while time.monotonic() < expiration:
        try:
            fields = path.read_text().split()
        except FileNotFoundError:
            break
        if fields and fields[0] != "running" and int(fields[0]) in allowed:
            if descriptor is None or int(fields[1], 0) == descriptor:
                return int(fields[0])
        time.sleep(0.001)
    raise AssertionError(f"Worker did not enter expected syscall {sorted(allowed)}")


def join(thread, answers):
    thread.join(timeout=5)
    if thread.is_alive():
        raise TimeoutError("Outstanding read did not reach terminal settlement")
    return answers.get(timeout=1)


def blocked_read(mode):
    data_read, data_write = os.pipe()
    reuse_read, reuse_write = os.pipe()
    entered, answers = Queue(), Queue()

    def worker():
        entered.put(threading.get_native_id())
        answer = os.read(data_read, RESERVED)
        answers.put(answer.decode("ascii"))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    tid = entered.get(timeout=5)
    await_syscall(tid, READ, data_read)
    result = {"confirmed_initial_read": True, "reserved_before_terminal": RESERVED}
    if mode == "close_reuse_reader":
        os.close(data_read)
        try:
            fcntl.fcntl(data_read, fcntl.F_GETFD)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise
        else:
            raise AssertionError("The descriptor table entry should be closed")
        result["descriptor_closed"] = True
        await_syscall(tid, READ, data_read)
        os.dup2(reuse_read, data_read)
        os.write(reuse_write, b"new!")
        await_syscall(tid, READ, data_read)
        if not answers.empty():
            raise AssertionError("Closing and reusing the descriptor altered the outstanding read")
        result["still_blocked_after_close_and_reuse"] = True
        os.write(data_write, b"old!")
        expected = "old!"
    else:
        os.close(data_write)
        expected = ""
    actual = join(thread, answers)
    if actual != expected:
        raise AssertionError((mode, expected, actual))
    result.update(outcome="data" if actual else "eof", bytes_read=actual,
                  spent=len(actual), released=RESERVED - len(actual))
    if mode == "close_reuse_reader":
        if os.read(data_read, RESERVED) != b"new!":
            raise AssertionError("Outstanding read consumed bytes from the replacement descriptor")
        result["replacement_bytes_untouched"] = True
    return result


def cooperative(mode):
    data_read, data_write = os.pipe2(os.O_NONBLOCK)
    cancel = os.eventfd(0, os.EFD_CLOEXEC | os.EFD_NONBLOCK)
    entered, answers = Queue(), Queue()
    begin = threading.Event()

    def worker():
        poller = select.poll()
        poller.register(data_read, select.POLLIN)
        poller.register(cancel, select.POLLIN)
        entered.put(threading.get_native_id())
        if not begin.wait(timeout=5):
            raise TimeoutError("Cooperative worker did not start")
        ready = {descriptor for descriptor, event in poller.poll(5000) if event & select.POLLIN}
        priority = (data_read, cancel) if mode == "both_ready_data_first" else (cancel, data_read)
        chosen = next(candidate for candidate in priority if candidate in ready)
        if chosen == cancel:
            os.eventfd_read(cancel)
            record = ("cancelled", "")
        else:
            record = ("data", os.read(data_read, RESERVED).decode("ascii"))
        answers.put((record, set(ready)))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    tid = entered.get(timeout=5)
    both = mode.startswith("both_")
    if not both:
        begin.set()
        await_syscall(tid, POLL)
    if mode != "cancel_only":
        os.write(data_write, b"data")
    if mode != "data_only":
        os.eventfd_write(cancel, 1)
    begin.set()
    (outcome, actual), observed = join(thread, answers)

    def pending():
        poller = select.poll()
        poller.register(data_read, select.POLLIN)
        poller.register(cancel, select.POLLIN)
        return {descriptor for descriptor, event in poller.poll(0) if event & select.POLLIN}

    wanted = {
        "data_only": ({data_read}, "data", set()),
        "cancel_only": ({cancel}, "cancelled", set()),
        "both_ready_cancel_first": ({data_read, cancel}, "cancelled", {data_read}),
        "both_ready_data_first": ({data_read, cancel}, "data", {cancel}),
    }[mode]
    remaining = pending()
    if (observed, outcome, remaining) != wanted:
        raise AssertionError((mode, wanted, observed, outcome, remaining))
    labels = {data_read: "data", cancel: "cancel"}
    return {"confirmed_blocking_poll": not both, "ready": sorted(labels[item] for item in observed),
            "outcome": outcome, "bytes_read": actual, "pending": sorted(labels[item] for item in remaining),
            "reserved_before_terminal": RESERVED, "spent": len(actual), "released": RESERVED - len(actual)}


def parent():
    results = {}
    for case in CASES:
        run = subprocess.run([sys.executable, "-B", str(HERE / "run.py"), "--case", case],
                             capture_output=True, text=True, check=False, timeout=15)
        if run.returncode:
            raise RuntimeError((case, run.stdout, run.stderr))
        results[case] = json.loads(run.stdout)
    return {"format": "rt26-linux-io-cancel/1", "python": sys.version.split()[0],
            "architecture": os.uname().machine, "kernel_release": os.uname().release, "cases": results}


if __name__ == "__main__":
    if sys.platform != "linux" or os.uname().machine != "x86_64":
        raise SystemExit("this fixture checks Linux x86-64 syscalls")
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--case", choices=CASES)
    mode.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.case:
        operation = blocked_read if args.case.startswith("close_") else cooperative
        print(json.dumps(operation(args.case), sort_keys=True))
    else:
        args.output.write_text(json.dumps(parent(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
