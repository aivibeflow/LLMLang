"""Audit wide-integer lowering link requirements and checked observations."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
from random import Random
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
MAX_U64 = 2**64 - 1
SENTINEL = 0x6B298E01_F5C374D2
BOUNDARY = (0, 1, 2, 3, 0xFFFF, (1 << 32) - 1, 1 << 32, 1 << 63, MAX_U64 - 1, MAX_U64)


def execute(program, args, work, check=True):
    return subprocess.run([program, *map(str, args)], cwd=work, check=check,
                          text=True, capture_output=True, timeout=60,
                          env={**os.environ, "LC_ALL": "C"})


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def compile_variant(compiler, work, filename, level, wide, silent=False):
    path = work / filename
    execute(compiler, ("-std=gnu17", "-ffreestanding", "-fPIC", "-Wall", "-Wextra", "-Werror",
                       f"-O{level}", f"-DWIDE={int(wide)}", f"-DSILENT_NARROW={int(silent)}",
                       "-c", HERE / "lowering.c", "-o", path), work)
    return path


def imports(nm, work, obj):
    return [line.split()[-1] for line in
            execute(nm, ("--undefined-only", obj), work).stdout.splitlines()]


def link(gcc, work, obj, runtime=None, check=True):
    target = obj.with_suffix(".so")
    inputs = (obj,) if runtime is None else (obj, runtime)
    result = execute(gcc, ("-shared", "-nostdlib", "-Wl,--no-undefined",
                           *inputs, "-o", target), work, check=check)
    return result, target


def linked_needs(readelf, work, path):
    dynamic = execute(readelf, ("--dynamic", path), work).stdout
    return re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic)


def call(path):
    library = ctypes.CDLL(str(path))
    operation = library.quotient
    operation.argtypes = [ctypes.c_uint64] * 3 + [ctypes.POINTER(ctypes.c_uint64)]
    operation.restype = ctypes.c_int32

    def observe(vector):
        slot = ctypes.c_uint64(SENTINEL)
        status = operation(*vector, ctypes.byref(slot))
        return status, slot.value

    return observe


def expected(vector, restricted):
    high, low, divisor = vector
    if divisor == 0:
        return 1, SENTINEL
    if restricted and high:
        return 3, SENTINEL
    quotient = (high * (MAX_U64 + 1) + low) // divisor
    if quotient > MAX_U64:
        return 2, SENTINEL
    return 0, quotient


def vectors():
    random = Random(327)
    return (*product(BOUNDARY, repeat=3), *(
        (random.getrandbits(64), random.getrandbits(64), random.getrandbits(64))
        for _ in range(256)
    ))


def check_observations(path, cases, restricted):
    observe = call(path)
    statuses = Counter()
    traces = sha256()
    for vector in cases:
        actual = observe(vector)
        correct = expected(vector, restricted)
        if actual != correct:
            raise AssertionError((path.name, vector, actual, correct))
        statuses[actual[0]] += 1
        traces.update(bytes([actual[0]]))
        traces.update(actual[1].to_bytes(8, "little"))
    return dict(sorted(statuses.items())), traces.hexdigest()


def verify(args):
    cases = vectors()
    profiles = {}
    negative = {}
    with TemporaryDirectory(prefix="llmlang-wide-division-") as temp:
        work = Path(temp)
        runtime = Path(execute(args.gcc, ("-print-libgcc-file-name",), work).stdout.strip())
        if not runtime.is_file():
            raise ValueError("The GCC runtime archive is missing")
        compilers = {"gcc": args.gcc, "clang": args.clang}
        versions = {name: execute(binary, ("--version",), work).stdout.splitlines()[0]
                    for name, binary in compilers.items()}
        for name, compiler in compilers.items():
            for level in (0, 3):
                label = f"{name}-O{level}"
                for wide in (False, True):
                    route = "wide" if wide else "restricted"
                    obj = compile_variant(compiler, work, f"{label}-{route}.o", level, wide)
                    external = imports(args.nm, work, obj)
                    if external != (["__udivti3"] if wide else []):
                        raise ValueError((label, route, external))
                    result, artifact = link(args.gcc, work, obj, check=False)
                    bare_link = result.returncode == 0
                    if wide:
                        if bare_link or "__udivti3" not in result.stderr:
                            raise ValueError((label, "wide runtime dependency was not diagnosed", result))
                        _, artifact = link(args.gcc, work, obj, runtime)
                    elif not bare_link:
                        raise ValueError((label, "restricted native link failed", result.stderr))
                    needed = linked_needs(args.readelf, work, artifact)
                    if needed or imports(args.nm, work, artifact):
                        raise ValueError((label, route, "linked artifact has unresolved imports", needed))
                    statuses, traces = check_observations(artifact, cases, restricted=not wide)
                    profiles[f"{label}-{route}"] = {
                        "object_sha256": digest(obj), "object_imports": external,
                        "link_without_runtime": bare_link, "runtime_archive_linked": wide,
                        "artifact_sha256": digest(artifact), "elf_needed": needed,
                        "status_counts": statuses, "trace_sha256": traces,
                    }
        altered = compile_variant(args.gcc, work, "silent-narrowing.o", 3, wide=False, silent=True)
        _, library = link(args.gcc, work, altered)
        witness = (1, 2, 8)
        actual = call(library)(witness)
        normal = expected(witness, restricted=False)
        restricted = expected(witness, restricted=True)
        if actual == restricted or actual == normal:
            raise AssertionError("The silent narrowing control failed to distinguish the contracts")
        negative = {"vector": witness, "silent_narrowing": actual, "wide": normal,
                    "restricted": restricted}
        linker = execute(args.gcc, ("-print-prog-name=ld",), work).stdout.strip()
        return {
            "compilers": versions,
            "linker": execute(linker, ("--version",), work).stdout.splitlines()[0],
            "link_driver_target": execute(args.gcc, ("-dumpmachine",), work).stdout.strip(),
            "runtime_archive": {"file": runtime.name, "sha256": digest(runtime)},
            "source_sha256": {name: digest(HERE / name) for name in ("lowering.c", "run.py")},
            "vectors_per_route": len(cases),
            "profiles": profiles,
            "negative_control": negative,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--nm", default="nm")
    parser.add_argument("--readelf", default="readelf")
    print(json.dumps(verify(parser.parse_args()), indent=2))


if __name__ == "__main__":
    main()
