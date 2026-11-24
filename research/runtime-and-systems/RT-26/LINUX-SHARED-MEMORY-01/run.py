"""Compare summed RSS and PSS for native shared and copy-on-write mappings."""

import argparse
import json
import mmap
import os
from pathlib import Path
import re
import signal
import subprocess
import sys


HERE = Path(__file__).resolve().parent
MAPPING = "llmlang-rt26-account-fixture"
PAGES = 512
FIELDS = ("Size", "Rss", "Pss", "Shared_Dirty", "Private_Dirty", "Anonymous")
HEADER = re.compile(r"^[0-9a-f]+-[0-9a-f]+ ")
MODES = ("shared", "private")


def smaps(pid):
    selected = False
    matches = 0
    values = {}
    for line in Path(f"/proc/{pid}/smaps").read_text().splitlines():
        if HEADER.match(line):
            selected = f"/memfd:{MAPPING} " in line
            matches += selected
            continue
        if selected:
            key, colon, rest = line.partition(":")
            if colon and key in FIELDS:
                amount, unit = rest.split()
                if unit != "kB":
                    raise AssertionError((key, amount, unit))
                values[key] = int(amount)
    if matches != 1 or values.keys() != set(FIELDS):
        raise AssertionError(("wanted one identifiably scoped mapping", matches, values))
    return values


def expect_byte(fd, expected):
    answer = os.read(fd, 1)
    if answer != expected:
        raise AssertionError((expected, answer))


def sample(parent, child=None):
    participants = [smaps(parent), smaps(child)] if child is not None else [smaps(parent)]
    return {"parent": participants[0], "child": participants[1] if child is not None else None,
            "rss_kib": sum(item["Rss"] for item in participants),
            "pss_kib": sum(item["Pss"] for item in participants)}


def child_step(mapping, offsets, commands, feedback):
    expect_byte(commands, b"T")
    if any(mapping[offset] != 17 for offset in offsets):
        raise AssertionError("Untouched child pages have different fixture values")
    os.write(feedback, b"T")
    expect_byte(commands, b"W")
    for offset in offsets[::2]:
        mapping[offset] = 33
    os.write(feedback, b"W")
    expect_byte(commands, b"E")


def run_case(mode):
    page = mmap.PAGESIZE
    if page != 4096:
        raise ValueError("fixture expects 4 KiB pages")
    length = page * PAGES
    offsets = tuple(range(0, length, page))
    pid = os.getpid()
    descriptor = os.memfd_create(MAPPING, os.MFD_CLOEXEC)
    os.ftruncate(descriptor, length)
    flags = mmap.MAP_SHARED if mode == "shared" else mmap.MAP_PRIVATE
    with mmap.mmap(descriptor, length, flags=flags, prot=mmap.PROT_READ | mmap.PROT_WRITE) as mapping:
        os.close(descriptor)
        mapping.madvise(mmap.MADV_NOHUGEPAGE)
        for offset in offsets:
            mapping[offset] = 17
        before = sample(pid)
        command_read, command_write = os.pipe()
        feedback_read, feedback_write = os.pipe()
        child = os.fork()
        if child == 0:
            os.close(command_write)
            os.close(feedback_read)
            try:
                child_step(mapping, offsets, command_read, feedback_write)
            except Exception as error:
                os.write(2, f"child mapping error: {error}\n".encode())
                os._exit(1)
            os._exit(0)
        os.close(command_read)
        os.close(feedback_write)
        ended = False
        try:
            os.write(command_write, b"T")
            expect_byte(feedback_read, b"T")
            touched = sample(pid, child)
            os.write(command_write, b"W")
            expect_byte(feedback_read, b"W")
            written = sample(pid, child)
            seen = sum(mapping[offset] == 33 for offset in offsets)
            os.write(command_write, b"E")
            _, status = os.waitpid(child, 0)
            ended = True
            if status != 0:
                raise RuntimeError(f"mapping child exited with status {status}")
        finally:
            os.close(command_write)
            os.close(feedback_read)
            if not ended:
                os.kill(child, signal.SIGKILL)
                os.waitpid(child, 0)
        after = sample(pid)
        pages_kib = length // 1024
        expected = pages_kib if mode == "shared" else (pages_kib * 3) // 2
        if tuple((row["rss_kib"], row["pss_kib"]) for row in (before, touched, written, after)) != (
            (pages_kib, pages_kib), (pages_kib * 2, pages_kib), (pages_kib * 2, expected),
            (pages_kib, pages_kib),
        ):
            raise AssertionError((mode, before, touched, written, after))
        if seen != (PAGES // 2 if mode == "shared" else 0):
            raise AssertionError(("shared visibility versus isolated writes", mode, seen))
        return {"prefault": before, "two_readers": touched, "after_half_written": written,
                "after_child_exit": after, "modified_pages_visible_to_parent": seen}


def verify():
    cases = {}
    for mode in MODES:
        child = subprocess.run([sys.executable, "-B", str(HERE / "run.py"), "--case", mode],
                               text=True, capture_output=True, timeout=20)
        if child.returncode:
            raise RuntimeError((mode, child.stdout, child.stderr))
        cases[mode] = json.loads(child.stdout)
    return {"format": "rt26-linux-shared-memory/1", "python": sys.version.split()[0],
            "kernel_release": os.uname().release, "machine": os.uname().machine,
            "page_bytes": mmap.PAGESIZE, "pages_per_mapping": PAGES, "cases": cases}


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("this fixture requires Linux")
    parser = argparse.ArgumentParser(description=__doc__)
    arguments = parser.add_mutually_exclusive_group(required=True)
    arguments.add_argument("--case", choices=MODES)
    arguments.add_argument("--output", type=Path)
    options = parser.parse_args()
    if options.case:
        print(json.dumps(run_case(options.case), sort_keys=True))
    else:
        options.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
