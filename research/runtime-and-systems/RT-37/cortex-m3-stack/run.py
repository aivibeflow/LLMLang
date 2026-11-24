#!/usr/bin/env python3
"""Measure Cortex-M3 thread-stack and exception-frame depth in the RT-37 fixture."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from stack_model import WINDOW_BYTES, stack_bounds


HERE = Path(__file__).resolve().parent
TIMER = HERE.parent / "cortex-m3-timer"
SPEC = importlib.util.spec_from_file_location("cortex_timer", TIMER / "run.py")
timer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(timer)
closure = timer.closure

PAINT_WORDS = (0xA5A5A5A5, 0x5A5A5A5A)
PROFILES = ("polling", "interrupt", "misaligned_interrupt")


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Expected one assembly hook at {old!r}")
    return source.replace(old, new)


def fixture_startup():
    source = timer.startup_source("timer_interrupt")
    source = replace_once(source, "reset:\n", "reset:\n  bl stack_paint\n")
    report = """  bl stack_watermark
  mov r4, r0
  movs r0, #'@'
  bl uart_byte
  mov r0, r4
  bl output_hex
  movs r0, #'/'
  bl uart_byte
  bl stack_read_handler
  bl output_hex
  movs r0, #'/'
  bl uart_byte
  bl stack_read_padding
  bl output_hex
"""
    return replace_once(source, "  movs r0, #'!'\n", report + "  movs r0, #'!'\n")


def fixture_driver(profile):
    source = (TIMER / "timer.s").read_text(encoding="utf-8")
    if profile == "polling":
        source = ".set POLLING, 1\n" + source
    if profile == "misaligned_interrupt":
        source = replace_once(source, "wait_tick:\n", "wait_tick:\n  push {r4}\n")
        source = replace_once(source, ".endif\n  bx lr\n\n.type timer_interrupt",
                              ".endif\n  pop {r4}\n  bx lr\n\n.type timer_interrupt")
    source = replace_once(source, "  str r3, [r0]\n2:\n",
                          "  str r3, [r0]\n.global armed_wait_begin\narmed_wait_begin:\n2:\n")
    source = replace_once(source, "  beq 2b\n.endif\n",
                          "  beq 2b\n.global armed_wait_end\narmed_wait_end:\n.endif\n")
    sample = """  mrs r0, msp
  ldr r1, =deepest_msp
  ldr r2, [r1]
  cbz r2, 8f
  cmp r0, r2
  bhs 9f
8:
  str r0, [r1]
  ldr r2, [r0, #28]  // xPSR in the basic exception frame
  ubfx r2, r2, #9, #1
  ldr r1, =stacked_padding
  str r2, [r1]
9:
"""
    return replace_once(source, "timer_interrupt:\n", "timer_interrupt:\n" + sample)


def assemble_source(args, work, name, text):
    source, obj = work / f"{name}.s", work / f"{name}.o"
    source.write_text(text, encoding="utf-8")
    closure.assemble(args.mc, source, obj)
    return obj


def setup(args, work, cases):
    startup = assemble_source(args, work, "stack-startup", fixture_startup())
    rows = [f".word {sample}, {valid}" for sample, valid in cases]
    samples = assemble_source(args, work, "samples", "\n".join((
        '.section .rodata.fixture,"a",%progbits', '.balign 4', '.global fixture_begin, fixture_end',
        'fixture_begin:', *rows, 'fixture_end:', '',
    )))
    steps = {"llvm": work / "step-llvm.o", "rust": work / "step-rust.o"}
    closure.compile_llvm(args.llc, timer.CLOSURE / "step.ll", steps["llvm"], 2)
    closure.compile_rust(args.rustc, timer.CLOSURE / "step.rs", steps["rust"], 2)
    probes = {}
    for paint in PAINT_WORDS:
        source = (HERE / "stack_probe.s").read_text(encoding="utf-8")
        defines = f".set PAINT_WORD, {paint}\n.set STACK_WINDOW, {WINDOW_BYTES}\n"
        probes[paint] = assemble_source(args, work, f"paint-{paint:08x}", defines + source)
    drivers = {name: assemble_source(args, work, name, fixture_driver(name)) for name in PROFILES}
    return startup, samples, steps, probes, drivers


def observe(args, image, cases, profile):
    trace = closure.boot(args.qemu, image)
    expected = timer.trace_expected(cases, interrupt=(profile != "polling")).removesuffix("!")
    match = re.fullmatch(re.escape(expected) + r"@([0-9a-f]{2})/([0-9a-f]{2})/(0[01])!", trace)
    if match is None:
        raise ValueError(f"Unexpected observation for {image.name}: {trace!r}")
    return {"stack_watermark_bytes": int(match[1], 16), "stack_top_to_handler_msp_bytes": int(match[2], 16),
            "stacked_xpsr_alignment_bit": int(match[3], 16), "trace": trace}


def compare(args):
    cases = json.loads((timer.CLOSURE / "inputs.json").read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="llmlang-cortex-stack-") as tmp:
        work = Path(tmp)
        startup, samples, steps, probes, drivers = setup(args, work, cases)
        records = {}
        for name, driver in drivers.items():
            for backend, step in steps.items():
                for paint, stack_probe in probes.items():
                    image = work / f"{backend}-{name}-{paint:08x}.elf"
                    closure.link(args.lld, image, (startup, samples, driver, step, stack_probe))
                    metadata = closure.inspect(args, image)
                    vector = timer.check_systick_vector(args, image)
                    initial_stack = int(metadata["initial_stack"], 16)
                    ram_end = max(load["virtual"] + load["memory_bytes"] for load in metadata["loads"]
                                  if 0x20000000 <= load["virtual"] < initial_stack)
                    if initial_stack % 8 or ram_end > initial_stack - WINDOW_BYTES:
                        raise ValueError(f"Unaligned or overlapping stack interval for {image.name}")
                    disassembly = closure.output([args.objdump, "-d", "--no-show-raw-insn",
                                                  "--triple=thumbv7m-none-eabi", "--section=.text", image])
                    symbols = closure.output([args.nm, "--defined-only", "--numeric-sort", image])
                    bounds = stack_bounds(disassembly, symbols, interrupt=(name != "polling"))
                    observed = observe(args, image, cases, name)
                    expected = (bounds["armed_phase_bound"], bounds["entry_msp_depth"], int(bounds["padding"] != 0))
                    measured = (observed["stack_watermark_bytes"], observed["stack_top_to_handler_msp_bytes"],
                                observed["stacked_xpsr_alignment_bit"])
                    if measured != expected:
                        raise ValueError(f"Stack audit disagrees for {image.name}: {measured} vs. {expected}")
                    # Falsify an alignment-blind predictor and the resulting 36-byte budget.
                    if name == "misaligned_interrupt" and not (
                        bounds["entry_msp_depth"] - bounds["padding"] == 36 < measured[0]
                    ):
                        raise ValueError(f"The missing-padding control did not discriminate for {image.name}")
                    exact = {key: metadata[key] for key in ("image_sha256", "initial_stack", "reset_vector",
                                                           "static_ram_bytes", "flash_extent_bytes")}
                    records[image.stem] = {**exact, "systick_vector": vector, "static_ram_end": hex(ram_end),
                                           "static_stack_model": bounds, **observed}
    inputs = [*[(filename, timer.CLOSURE / filename) for filename in
                ("startup.s", "step.ll", "step.rs", "inputs.json", "memory.ld")],
              ("closure-run.py", timer.CLOSURE / "run.py"), ("timer-run.py", TIMER / "run.py"),
              ("timer.s", TIMER / "timer.s"), ("stack-run.py", Path(__file__)),
              ("stack_probe.s", HERE / "stack_probe.s"), ("stack_model.py", HERE / "stack_model.py")]
    return {"schema": "llmlang-cortex-m3-stack-v1", "machine": "lm3s6965evb",
            "paint_window_bytes": WINDOW_BYTES, "steps_per_image": len(cases),
            "source_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in inputs},
            "tools": {name: closure.output([getattr(args, name), "--version"]).splitlines()[0].strip()
                      for name in ("objdump", "llc", "lld", "rustc", "qemu")},
            "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "llc": "llc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "objdump": "llvm-objdump-19",
        "rustc": "rustc", "qemu": "qemu-system-arm",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(args), indent=2) + "\n", encoding="utf-8")
