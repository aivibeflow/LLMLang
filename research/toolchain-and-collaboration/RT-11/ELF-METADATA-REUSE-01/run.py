#!/usr/bin/env python3
"""Compare loaded bytes, raw artifacts and self-observation after ELF edits."""

from hashlib import sha256
from itertools import combinations
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
PROGRAM = struct.Struct("<IIQQQQQQ")
SECTION = struct.Struct("<IIQQQQIIQQ")
PAYLOADS = tuple(f"documentation-tag={i:02}\n".encode() for i in range(6))


def elf(data):
    identification, *fields = HEADER.unpack_from(data)
    if identification[:6] != b"\x7fELF\x02\x01" or fields[1] != 62:
        raise AssertionError("Expected little-endian x86-64 ELF")
    phoff, shoff = fields[4:6]
    phent, phnum, shent, shnum, strings = fields[-5:]
    if phent != PROGRAM.size or shent != SECTION.size:
        raise AssertionError("Unexpected ELF entry size")
    segments = []
    for index in range(phnum):
        header = PROGRAM.unpack_from(data, phoff + phent * index)
        if header[0] != 1:
            continue
        _, _, offset, _, _, length, _, _ = header
        segments.append((header, sha256(data[offset:offset + length]).hexdigest()))
    sections = [SECTION.unpack_from(data, shoff + shent * index) for index in range(shnum)]
    string_offset, string_size = sections[strings][4:6]
    strings = data[string_offset:string_offset + string_size]
    match = []
    for name_offset, _, flags, _, offset, size, *_ in sections:
        name = strings[name_offset:strings.index(b"\x00", name_offset)]
        if name == b".note.llmlang":
            match.append((flags, data[offset:offset + size]))
    if len(match) != 1 or match[0][0] & 2:
        raise AssertionError("Expected one non-allocated metadata section")
    return segments, match[0][1]


def fnv(data):
    state = 14695981039346656037
    for byte in data:
        state = ((state ^ byte) * 1099511628211) % (1 << 64)
    return f"{state:016x}"


def command(directory, *args):
    return subprocess.check_output(args, cwd=directory, text=True)


def compare():
    cc = os.environ.get("CC", "gcc")
    objcopy = os.environ.get("OBJCOPY", "objcopy")
    reports = {}
    with tempfile.TemporaryDirectory() as work:
        directory = Path(work)
        (directory / "probe.c").write_bytes((HERE / "probe.c").read_bytes())
        for optimization in ("O0", "O2"):
            command(directory, cc, f"-{optimization}", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "probe.c", "-o", "base")
            identities = []
            for i, payload in enumerate(PAYLOADS):
                (directory / "note").write_bytes(payload)
                name = f"fixture-{i}"
                command(directory, objcopy, "--add-section", ".note.llmlang=note",
                        "--set-section-flags", ".note.llmlang=readonly,contents", "base", name)
                target = directory / name
                data = target.read_bytes()
                load, note = elf(data)
                normal = [int(value) for value in command(directory, str(target)).splitlines()]
                reported = command(directory, str(target), "--self").strip()
                if note != payload or normal != [n + 2 for n in range(-4, 5)] or reported != fnv(data):
                    raise AssertionError((name, normal, reported))
                identities.append({
                    "artifact": sha256(data).hexdigest(),
                    "load_segments": load,
                    "metadata": sha256(note).hexdigest(),
                    "normal": normal,
                    "self_inspection": reported,
                })
            pair_checks = 0
            for left, right in combinations(identities, 2):
                if not (left["load_segments"] == right["load_segments"]
                        and left["normal"] == right["normal"]
                        and left["artifact"] != right["artifact"]
                        and left["metadata"] != right["metadata"]
                        and left["self_inspection"] != right["self_inspection"]):
                    raise AssertionError((left, right))
                pair_checks += 1
            reports[optimization] = {"profiles": identities, "pairs_compared": pair_checks,
                                     "normal_observations": len(identities) * 9}
    tools = {name: subprocess.check_output([exe, "--version"], text=True).splitlines()[0]
             for name, exe in (("gcc", cc), ("objcopy", objcopy))}
    return reports, tools


if __name__ == "__main__":
    rows, versions = compare()
    print(json.dumps({
        "schema": "llmlang-elf-metadata-reuse/1", "python": platform.python_version(),
        "tools": versions,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "probe.c")},
        "results": rows,
    }, indent=2))
