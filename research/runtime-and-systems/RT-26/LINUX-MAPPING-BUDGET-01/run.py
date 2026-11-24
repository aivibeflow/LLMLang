"""Distinguish reserved address space and resident pages on native Linux."""

import argparse
import ctypes
import errno
import json
import mmap
import os
from pathlib import Path
import platform
import resource
import selectors
import subprocess
import sys
from contextlib import ExitStack


MIB = 1024**2
ADDRESS_ALLOWANCE = 8 * MIB
FIRST_LENGTH = 6 * MIB
SECOND_LENGTH = 4 * MIB
PAGE = os.sysconf("SC_PAGE_SIZE")
LIBC = ctypes.CDLL(None, use_errno=True)
MINCORE = LIBC.mincore
MINCORE.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte))
MINCORE.restype = ctypes.c_int


def equal(actual, expected):
    if actual != expected:
        raise AssertionError(f"{actual!r} != {expected!r}")
    return actual


def virtual_size():
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmSize:"):
            _, length, units = line.split()
            equal(units, "kB")
            return int(length) * 1024
    raise ValueError("Missing VmSize from procfs")


def set_address_limit():
    limit = virtual_size() + ADDRESS_ALLOWANCE
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if any(bound != resource.RLIM_INFINITY and limit > bound for bound in (soft, hard)):
        raise ValueError("The inherited limit is below the fixture's initial allowance")
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def mapping(length):
    region = mmap.mmap(-1, length, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                       prot=mmap.PROT_READ | mmap.PROT_WRITE)
    region.madvise(mmap.MADV_NOHUGEPAGE)
    return region


def pages(region):
    length = len(region)
    equal(length % PAGE, 0)
    address = ctypes.addressof(ctypes.c_char.from_buffer(region))
    sample = (ctypes.c_ubyte * (length // PAGE))()
    if MINCORE(address, length, sample):
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return sum(value & 1 for value in sample)


def denied():
    try:
        region = mapping(SECOND_LENGTH)
    except OSError as error:
        return equal(errno.errorcode[error.errno], "ENOMEM")
    region.close()
    raise AssertionError("Address limit admitted both mappings")


def single():
    set_address_limit()
    with mapping(FIRST_LENGTH) as first:
        cold = equal(pages(first), 0)
        for index in range(0, FIRST_LENGTH, PAGE * 2):
            first[index] = 1
        touched = equal(pages(first), FIRST_LENGTH // PAGE // 2)
        while_some_resident = denied()
        first.madvise(mmap.MADV_DONTNEED)
        discarded = equal(pages(first), 0)
        after_discard = denied()
        equal(first[0], 0)
    with mapping(SECOND_LENGTH) as second:
        allocated_after_unmap = equal(len(second), SECOND_LENGTH)
        second_cold = equal(pages(second), 0)

    return {"first_mapping_bytes": FIRST_LENGTH, "initial_resident_pages": cold,
            "touched_resident_pages": touched, "discarded_resident_pages": discarded,
            "second_with_partial_residency": while_some_resident,
            "second_after_discard": after_discard, "second_after_first_unmap_bytes": allocated_after_unmap,
            "second_initial_resident_pages": second_cold, "discarded_content_read_zero": True}


def hold():
    set_address_limit()
    with mapping(FIRST_LENGTH) as region:
        print(json.dumps({"mapped_bytes": len(region), "resident_pages": equal(pages(region), 0)}), flush=True)
        equal(sys.stdin.readline(), "release\n")


def command(mode):
    return [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", mode]


def pair():
    with ExitStack() as cleanup:
        processes = [cleanup.enter_context(subprocess.Popen(
            command("hold"), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )) for _ in range(2)]
        for process in processes:
            cleanup.callback(lambda p: p.kill() if p.poll() is None else None, process)
        reserved = []
        for process in processes:
            with selectors.DefaultSelector() as ready:
                ready.register(process.stdout, selectors.EVENT_READ)
                if not ready.select(timeout=10):
                    raise TimeoutError("Child did not reach its mapping barrier")
            reserved.append(json.loads(process.stdout.readline()))
        equal([process.poll() for process in processes], [None, None])
        shared_total = equal(sum(row["mapped_bytes"] for row in reserved), 2 * FIRST_LENGTH)
        for process in processes:
            _, errors = process.communicate("release\n", timeout=10)
            equal((process.returncode, errors), (0, ""))
    return {"simultaneous_holders": reserved, "combined_virtual_bytes": shared_total,
            "over_hypothetical_group_allowance_bytes": shared_total - ADDRESS_ALLOWANCE}


def replay():
    if platform.system() != "Linux" or not hasattr(mmap, "MADV_NOHUGEPAGE"):
        raise ValueError("This fixture requires Linux anonymous mappings and MADV_NOHUGEPAGE")
    result = subprocess.run(command("single"), capture_output=True, text=True, check=True, timeout=10)
    equal(result.stderr, "")
    return {"kernel": platform.release(), "python": platform.python_version(), "page_bytes": PAGE,
            "allowance_above_process_baseline_bytes": ADDRESS_ALLOWANCE,
            "single": json.loads(result.stdout), "pair": pair()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("single", "hold"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker == "single":
        print(json.dumps(single(), sort_keys=True))
    elif args.worker == "hold":
        hold()
    elif args.output:
        args.output.write_text(json.dumps(replay(), sort_keys=True, indent=2) + "\n")
    else:
        parser.error("Use --output for the main replay")
