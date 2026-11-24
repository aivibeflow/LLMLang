#!/usr/bin/env python3
"""Compare fixed slots and a checked bump cursor within the same Cortex-M3 arena."""

import argparse
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
CLOSURE = HERE.parent / "cortex-m3-closure"
SPEC = importlib.util.spec_from_file_location("cortex_closure", CLOSURE / "run.py")
closure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(closure)
FAILED = 0xFFFFFFFF
CAPACITY = 64

NAMED = {
    "small_packing": (0, ((4, 1),) * 17),
    "large_requests": (0, ((32, 8), (17, 1), (16, 1), (1, 1))),
    "alignment_gaps": (0, ((3, 1), (4, 8), (1, 16), (16, 16), (15, 1), (1, 1), (1, 1))),
    "invalid_requests": (0, ((16, 16), (FAILED, 1), (4, 0), (4, 3), (4, 32), (0, 1), (48, 16), (1, 1))),
}


def scenarios():
    values = product((0, 1, 15, 16, 31, 48, 63, 64, 65, FAILED), (0, 1, 4, 16, 17, 64, 65, FAILED),
                     (0, 1, 2, 3, 4, 8, 16, 32))
    return {**NAMED, **{f"boundary-{index}": (cursor, ((size, alignment),))
                       for index, (cursor, size, alignment) in enumerate(values)}}


def independent_reservation(kind, cursor, size, alignment):
    if alignment not in (1, 2, 4, 8, 16) or not 1 <= size <= CAPACITY:
        return FAILED, cursor
    if kind == "fixed":
        if cursor in range(0, CAPACITY, 16) and size <= 16:
            return cursor, cursor + 16
        return FAILED, cursor
    if cursor <= CAPACITY:
        # Compute round-up in unbounded integer arithmetic, independently of the IR mask.
        start = ((cursor + alignment - 1) // alignment) * alignment
        if start + size <= CAPACITY:
            return start, start + size
    return FAILED, cursor


def expected_trace(kind, cases):
    pieces = ["B"]
    observations = {}
    for name, (cursor, requests) in cases.items():
        pieces.append("|")
        results = []
        for size, alignment in requests:
            offset, cursor = independent_reservation(kind, cursor, size, alignment)
            pieces.append(f"{offset:08x}{cursor:08x}")
            results.append([offset, cursor])
        observations[name] = results
    return "".join([*pieces, "!"]), observations


def fixture_rows(args, work, name, cases):
    source = work / f"{name}.s"
    line = ['.section .rodata.reserve,"a",%progbits', '.balign 4', '.global request_begin, request_end',
            'request_begin:']
    for cursor, requests in cases.values():
        line.append(f".word 0, {cursor}, 0")
        line.extend(f".word 1, {size}, {alignment}" for size, alignment in requests)
    source.write_text("\n".join([*line, "request_end:", ""]), encoding="utf-8")
    obj = source.with_suffix(".o")
    closure.assemble(args.mc, source, obj)
    return obj


def startup(args, work, kind):
    source = work / f"startup-{kind}.s"
    text = (HERE / "startup.s").read_text(encoding="utf-8")
    if text.count("bl reserve_request") != 1:
        raise ValueError("Expected one exact allocator call site")
    source.write_text(text.replace("bl reserve_request", f"bl reserve_{kind}"), encoding="utf-8")
    obj = source.with_suffix(".o")
    closure.assemble(args.mc, source, obj)
    return obj


def emit_llvm(args, work, name, source):
    compiled_ir = closure.run([args.opt, "-passes=verify,default<O2>,verify", "-S", "-o", "-", "-"],
                              input=source, check=True).stdout
    path = work / f"{name}.ll"
    path.write_text(compiled_ir, encoding="utf-8")
    obj = path.with_suffix(".o")
    closure.compile_llvm(args.llc, path, obj, 2)
    return obj


def check_layout(args, image):
    exact = closure.inspect(args, image)
    output = closure.output([args.nm, "--defined-only", image])
    addresses = {name: int(address, 16) for address, name in
                 re.findall(r"^([0-9a-f]+)\s+[Bb]\s+(arena|arena_end|cursor)$", output, flags=re.MULTILINE)}
    if (addresses["arena"] % CAPACITY or addresses["arena_end"] - addresses["arena"] != CAPACITY
            or addresses["cursor"] != addresses["arena_end"] or exact["static_ram_bytes"] != CAPACITY + 4):
        raise ValueError(f"Unexpected SRAM layout for {image.name}: {addresses}")
    symbols = closure.output([args.readelf, "-W", "-s", image])
    [(size, routine)] = re.findall(r"\b([1-9][0-9]*)\s+FUNC\s+\w+\s+\w+\s+\d+\s+(reserve_(?:fixed|bump))$",
                                   symbols, flags=re.MULTILINE)
    return {**{name: exact[name] for name in ("image_sha256", "flash_extent_bytes", "static_ram_bytes")},
            "arena": {name: hex(address) for name, address in addresses.items()},
            "linked_reservation_routine": routine, "reservation_routine_bytes": int(size)}


def compare(args):
    cases = scenarios()
    records = {}
    with TemporaryDirectory(prefix="llmlang-cortex-allocator-") as tmp:
        work = Path(tmp)
        samples = fixture_rows(args, work, "samples", cases)
        starts = {kind: startup(args, work, kind) for kind in ("fixed", "bump")}
        llvm = (HERE / "reserve.ll").read_text(encoding="utf-8")
        objects = {"llvm": emit_llvm(args, work, "reserve", llvm), "rust": work / "reserve-rust.o"}
        closure.compile_rust(args.rustc, HERE / "reserve.rs", objects["rust"], 2)
        for kind, start in starts.items():
            expected, operations = expected_trace(kind, cases)
            for backend, obj in objects.items():
                name = f"{backend}-{kind}"
                image = work / f"{name}.elf"
                closure.link(args.lld, image, (start, samples, obj))
                metadata = check_layout(args, image)
                observed = closure.boot(args.qemu, image)
                if observed != expected:
                    raise ValueError(f"Unexpected allocator trace in {name}: "
                                     f"{sha256(observed.encode()).hexdigest()} != {sha256(expected.encode()).hexdigest()}")
                records[name] = {**metadata, "trace_sha256": sha256(observed.encode()).hexdigest(),
                                 "accepted": sum(offset != FAILED for values in operations.values()
                                                 for offset, _ in values),
                                 "named": {case: {"accepted": sum(offset != FAILED for offset, _ in operations[case]),
                                                   "last_cursor": operations[case][-1][1]} for case in NAMED}}

        guard = "%size_ok = and i1 %nonempty, %within_capacity"
        if llvm.count(guard) != 1:
            raise ValueError("Expected one exact bump size guard")
        bad = emit_llvm(args, work, "wrap-control", llvm.replace(guard, "%size_ok = or i1 %nonempty, false"))
        wrap_case = {"overflow": (16, ((FAILED, 1),))}
        wrap_samples = fixture_rows(args, work, "overflow-sample", wrap_case)
        wrap_image = work / "missed-size-guard.elf"
        closure.link(args.lld, wrap_image, (starts["bump"], wrap_samples, bad))
        exact = check_layout(args, wrap_image)
        observed = closure.boot(args.qemu, wrap_image)
        expected, _ = expected_trace("bump", wrap_case)
        if expected != "B|ffffffff00000010!" or observed != "B|000000100000000f!":
            raise ValueError(f"The missing-size-guard control did not expose wraparound: {observed!r}")
        control = {**exact, "expected": expected, "observed": observed}

    paths = {name: HERE / name for name in ("reserve.rs", "reserve.ll", "startup.s", "run.py")}
    paths.update({"closure-run.py": CLOSURE / "run.py", "memory.ld": CLOSURE / "memory.ld"})
    return {"schema": "llmlang-cortex-m3-bounded-allocator-v1", "machine": "lm3s6965evb",
            "case_count": len(cases), "requests_per_image": sum(len(rows) for _, rows in cases.values()),
            "source_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
            "tools": {name: closure.output([getattr(args, name), "--version"]).splitlines()[0].strip()
                      for name in ("opt", "llc", "lld", "rustc", "qemu")},
            "images": records, "control": control}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "llc": "llc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "opt": "opt-19", "rustc": "rustc", "qemu": "qemu-system-arm",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(args), indent=2) + "\n", encoding="utf-8")
