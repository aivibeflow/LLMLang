"""Compare Linux per-process CPU enforcement with an observed group reservation."""

import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
CASES = ("soft_signal", "hard_kill", "locally_admitted_pair")
LOCAL_LIMIT = 1
GROUP_LIMIT_US = 1_000_000
WORK_PER_CHILD_NS = 600_000_000


def cpu_us(usage):
    return round(1_000_000 * usage.ru_utime) + round(1_000_000 * usage.ru_stime)


def wait_child(pid):
    waited, status, usage = os.wait4(pid, 0)
    if waited != pid:
        raise AssertionError("wait4 returned a different child")
    return {"exit": os.waitstatus_to_exitcode(status), "cpu_us": cpu_us(usage)}


def run_limit(case):
    reader, writer = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(reader)

        def soft_signal(_number, _frame):
            os.write(writer, b"cpu limit\n")
            os._exit(23)

        signal.signal(signal.SIGXCPU, soft_signal)
        resource.setrlimit(resource.RLIMIT_CPU, (LOCAL_LIMIT, 2 if case == "soft_signal" else LOCAL_LIMIT))
        while True:
            pass
    os.close(writer)
    child = wait_child(pid)
    notification = os.read(reader, 64)
    os.close(reader)
    wanted = (23, b"cpu limit\n") if case == "soft_signal" else (-signal.SIGKILL, b"")
    if (child["exit"], notification) != wanted:
        raise AssertionError((case, child, notification))
    if not 900_000 <= child["cpu_us"] <= 1_500_000:
        raise AssertionError(("unexpected whole-second limit envelope", case, child))
    return {"exit": child["exit"], "soft_signal_observed": bool(notification),
            "wait4_retained_cpu": child["cpu_us"] > 0}, child


def run_pair():
    starts_read, starts_write = os.pipe()
    before = cpu_us(resource.getrusage(resource.RUSAGE_CHILDREN))
    workers = []
    for _ in range(2):
        pid = os.fork()
        if pid == 0:
            os.close(starts_write)
            resource.setrlimit(resource.RLIMIT_CPU, (LOCAL_LIMIT, 2))
            if os.read(starts_read, 1) != b"S":
                os._exit(2)
            target = time.process_time_ns() + WORK_PER_CHILD_NS
            while time.process_time_ns() < target:
                pass
            os._exit(0)
        workers.append(pid)
    os.close(starts_read)
    os.write(starts_write, b"SS")
    os.close(starts_write)
    children = [wait_child(pid) for pid in workers]
    after = cpu_us(resource.getrusage(resource.RUSAGE_CHILDREN))
    total = sum(child["cpu_us"] for child in children)
    if any(child["exit"] or not 590_000 < child["cpu_us"] < GROUP_LIMIT_US for child in children):
        raise AssertionError(("both workers should fit the per-process limit", children))
    if total <= GROUP_LIMIT_US or abs(total - (after - before)) > 2:
        raise AssertionError(("reaped CPU charge should exceed the proposed group limit", total, after - before))
    return {"both_exited_normally": True, "each_below_own_limit": True, "aggregate_exceeds_group_limit": True,
            "reaped_cpu_agrees_with_wait4_within_us": 2}, {
                "workers": children, "wait4_cpu_sum_us": total, "rusage_children_delta_us": after - before,
            }


def verify():
    outcomes = {}
    samples = {}
    for case in CASES:
        with subprocess.Popen([sys.executable, "-B", str(HERE / "run.py"), "--case", case],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              start_new_session=True) as child:
            try:
                stdout, stderr = child.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
                raise
        if child.returncode:
            raise RuntimeError((case, child.returncode, stdout, stderr))
        outcomes[case], samples[case] = json.loads(stdout)
    return {"format": "rt26-linux-cpu-budget/1", "python": sys.version.split()[0],
            "kernel_release": os.uname().release, "machine": os.uname().machine,
            "per_process_soft_seconds": LOCAL_LIMIT, "pair_target_cpu_ns_each": WORK_PER_CHILD_NS,
            "comparison_group_limit_us": GROUP_LIMIT_US, "cases": outcomes}, samples


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("this fixture checks Linux RLIMIT_CPU")
    parser = argparse.ArgumentParser(description=__doc__)
    choices = parser.add_mutually_exclusive_group(required=True)
    choices.add_argument("--case", choices=CASES)
    choices.add_argument("--output", type=Path)
    parser.add_argument("--raw", type=Path)
    options = parser.parse_args()
    if options.case:
        result = run_pair() if options.case == "locally_admitted_pair" else run_limit(options.case)
        print(json.dumps(result, sort_keys=True))
    else:
        exact, samples = verify()
        options.output.write_text(json.dumps(exact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if options.raw is not None:
            options.raw.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n", encoding="utf-8")
