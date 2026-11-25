"""Separate coroutine dispatch CPU from a thread clock spanning an await."""

import argparse
import asyncio
from collections import defaultdict
import json
import os
from pathlib import Path
import resource
import sys
import threading
import time


STEP_NS = 20_000_000
SIBLING_NS = 60_000_000


def burn(duration):
    start = time.thread_time_ns()
    now = start
    while now - start < duration:
        now = time.thread_time_ns()
    return now - start


async def suspended_reader(label, shared, spans, reference):
    start = time.thread_time_ns()
    reference[label] += burn(STEP_NS)
    shared["waiting"].set()
    try:
        await shared["finish"].wait()
    finally:
        reference[label] += burn(STEP_NS)
        spans[label] = time.thread_time_ns() - start
        shared["cleanup"].append(label)


async def active_sibling(label, shared, spans, reference, cancel):
    start = time.thread_time_ns()
    if not shared["waiting"].is_set():
        raise AssertionError("The reader must reach its suspension first")
    reference[label] += burn(SIBLING_NS)
    if cancel:
        shared["reader"].cancel()
    else:
        shared["finish"].set()
    spans[label] = time.thread_time_ns() - start


async def tasks(cancel):
    admitted = {}
    spans = {}
    reference = defaultdict(int)
    charged = defaultdict(int)
    events = []
    segments = []
    threads = set()
    monitored = {suspended_reader.__code__, active_sibling.__code__}

    def profile(frame, event, _message):
        if frame.f_code not in monitored or event not in ("call", "return"):
            return
        now = time.thread_time_ns()
        label = frame.f_locals["label"]
        if event == "call":
            if admitted:
                raise AssertionError("Two fixture frames execute simultaneously on one thread")
            admitted[frame] = now
            events.append((label, "enter"))
        else:
            elapsed = now - admitted.pop(frame)
            charged[label] += elapsed
            segments.append((label, elapsed))
            events.append((label, "leave"))
        threads.add(threading.get_native_id())
    shared = {"waiting": asyncio.Event(), "finish": asyncio.Event(), "cleanup": []}
    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        first = asyncio.create_task(suspended_reader("reader", shared, spans, reference))
        shared["reader"] = first
        second = asyncio.create_task(active_sibling("worker", shared, spans, reference, cancel))
        settled = await asyncio.gather(first, second, return_exceptions=True)
    finally:
        sys.setprofile(previous)
    expected = [
        ("reader", "enter"), ("reader", "leave"), ("worker", "enter"),
        ("worker", "leave"), ("reader", "enter"), ("reader", "leave"),
    ]
    if events != expected or admitted or shared["cleanup"] != ["reader"] or len(threads) != 1:
        raise AssertionError((events, admitted, shared["cleanup"], threads))
    for (label, elapsed), (wanted, work) in zip(
        segments, (("reader", STEP_NS), ("worker", SIBLING_NS), ("reader", STEP_NS)), strict=True,
    ):
        if label != wanted or elapsed < work:
            raise AssertionError(("dispatch window omitted fixture work", label, elapsed, work))
    wants_cancelled = isinstance(settled[0], asyncio.CancelledError)
    if wants_cancelled != cancel or settled[1] is not None or (not cancel and settled[0] is not None):
        raise AssertionError(settled)
    return {
        "profile_events": events, "terminal": "cancelled" if wants_cancelled else "finished",
        "measures": {"spanning": spans, "profiled": dict(charged), "explicit_work": dict(reference),
                     "dispatch_segments": segments},
    }


def run_case(cancel):
    r0 = resource.getrusage(resource.RUSAGE_THREAD)
    total_before = time.thread_time_ns()
    outcome = asyncio.run(tasks(cancel))
    total = time.thread_time_ns() - total_before
    r1 = resource.getrusage(resource.RUSAGE_THREAD)
    methods = outcome["measures"]
    if sum(methods["profiled"].values()) > total:
        raise AssertionError("Disjoint coroutine CPU must be bounded by thread CPU")
    if methods["spanning"]["reader"] < methods["profiled"]["reader"] + SIBLING_NS - 1_000_000:
        raise AssertionError("The spanning clock failed to include the sibling's CPU")
    if sum(methods["spanning"].values()) < total + 30_000_000:
        raise AssertionError("Overlapping spans should double-charge part of the thread CPU")
    for task, known in methods["explicit_work"].items():
        if not known <= methods["profiled"][task] <= known + 10_000_000:
            raise AssertionError((task, known, methods["profiled"][task]))
    return {
        "terminal": outcome["terminal"], "profile_events": outcome["profile_events"],
        "cleanup_cpu_in_reader_dispatch": True, "spanning_charge_exceeds_thread_cpu": True,
        "dispatch_charge_bounded_by_thread_cpu": True,
        "independent_work_lower_bound_met": True,
    }, {
        "thread_cpu_ns": total, "thread_voluntary_context_switches": r1.ru_nvcsw - r0.ru_nvcsw,
        "thread_involuntary_context_switches": r1.ru_nivcsw - r0.ru_nivcsw, **methods,
    }


def verify():
    evidence = {}
    samples = {}
    for case, cancelled in (("normal", False), ("cancel", True)):
        evidence[case], samples[case] = run_case(cancelled)
    return {
        "format": "rt26-coroutine-cpu-attribution/1", "python": sys.version.split()[0],
        "kernel_release": os.uname().release, "architecture": os.uname().machine,
        "reader_step_cpu_ns": STEP_NS, "worker_cpu_ns": SIBLING_NS, "cases": evidence,
    }, samples


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("this fixture uses Linux thread CPU and getrusage")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw", type=Path)
    options = parser.parse_args()
    result, sample = verify()
    options.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if options.raw is not None:
        options.raw.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
