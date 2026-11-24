#!/usr/bin/env python3
"""Compare SysTick delivery and GPIO isolation in the Cortex-M3 fixture."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import struct
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
CLOSURE = HERE.parent / "cortex-m3-closure"
SPEC = importlib.util.spec_from_file_location("cortex_closure", CLOSURE / "run.py")
closure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(closure)


def startup_source(handler):
    source = (CLOSURE / "startup.s").read_text()
    hooks = {
        ".rept 14\n.word hard_fault\n.endr": f".rept 13\n.word hard_fault\n.endr\n.word {handler}",
        ".type uart_byte,%function": ".global uart_byte\n.type uart_byte,%function",
        ".type output_hex,%function": ".global output_hex\n.type output_hex,%function",
        "  movs r0, #'B'\n": "  bl timer_gpio_init\n  movs r0, #'B'\n",
        "  ldr r1, [r5], #4\n": "  bl wait_tick\n  ldr r1, [r5], #4\n",
        "  mov r4, r0\n  movs r0, #' '\n":
            "  mov r4, r0\n  bl set_probe_pin\n  mov r7, r0\n  movs r0, #' '\n",
        "  bl output_hex\n  b 5b":
            "  bl output_hex\n  movs r0, #'/'\n  bl uart_byte\n  mov r0, r7\n  bl output_hex\n  b 5b",
        "done:\n  movs r0, #'!'":
            "done:\n  ldr r0, =irq_counter\n  ldr r7, [r0]\n  movs r0, #'#'\n  bl uart_byte\n"
            "  mov r0, r7\n  bl output_hex\n  movs r0, #'!'",
    }
    for old, replacement in hooks.items():
        if source.count(old) != 1:
            raise ValueError(f"Upstream startup changed at {old!r}")
        source = source.replace(old, replacement)
    return source


def emit_startup(args, scratch, name, handler):
    source = scratch / f"{name}.s"
    binary = scratch / f"{name}.o"
    source.write_text(startup_source(handler))
    closure.assemble(args.mc, source, binary)
    return binary


def emit_driver(args, scratch, name, *defines):
    source = scratch / f"{name}.s"
    binary = scratch / f"{name}.o"
    contents = (HERE / "timer.s").read_text()
    contents = "".join(f".set {define}, 1\n" for define in defines) + contents
    source.write_text(contents)
    closure.assemble(args.mc, source, binary)
    return binary


def trace_expected(cases, interrupt):
    duty_steps = closure.reference(cases).removeprefix("B ").removesuffix("!").split()
    gpio = [f"{duty}/{(3 if int(duty, 16) else 1):02x}" for duty in duty_steps]
    count = len(cases) if interrupt else 0
    return "B " + " ".join(gpio) + f"#{count:02x}!"


def check_systick_vector(args, image):
    vectors = image.with_suffix(".vectors.bin").read_bytes()
    (vector,) = struct.unpack_from("<I", vectors, 15 * 4)
    symbols = closure.output([args.readelf, "-W", "-s", image])
    match = re.search(r"^\s*\d+:\s+([0-9a-f]+)\s+\d+\s+FUNC\s+GLOBAL.*\btimer_interrupt$",
                      symbols, flags=re.MULTILINE)
    if not match or not vector & 1 or vector != int(match[1], 16):
        raise ValueError(f"Missing or incorrect Thumb SysTick vector for {image.name}")
    return hex(vector)


def compare(args):
    inputs = json.loads((CLOSURE / "inputs.json").read_text())
    names = ("interrupt", "polling")
    with TemporaryDirectory(prefix="llmlang-cortex-timer-") as scratch:
        work = Path(scratch)
        sample_source, sample_object = work / "samples.s", work / "samples.o"
        sample_source.write_text("\n".join(('.section .rodata.fixture,"a",%progbits', '.balign 4',
                                            '.global fixture_begin, fixture_end', 'fixture_begin:',
                                            *(f'.word {sample}, {valid}' for sample, valid in inputs),
                                            'fixture_end:', '')))
        closure.assemble(args.mc, sample_source, sample_object)
        startup = emit_startup(args, work, "startup", "timer_interrupt")
        drivers = {"interrupt": emit_driver(args, work, "irq"),
                   "polling": emit_driver(args, work, "poll", "POLLING")}
        steps = {"llvm": work / "step-llvm.o", "rust": work / "step-rust.o"}
        closure.compile_llvm(args.llc, CLOSURE / "step.ll", steps["llvm"], 2)
        closure.compile_rust(args.rustc, CLOSURE / "step.rs", steps["rust"], 2)

        records = {}
        for name in names:
            for backend, step in steps.items():
                image = work / f"{backend}-{name}.elf"
                closure.link(args.lld, image, (startup, sample_object, drivers[name], step))
                metadata = closure.inspect(args, image)
                vector = check_systick_vector(args, image)
                observed = closure.boot(args.qemu, image)
                if observed != trace_expected(inputs, interrupt=(name == "interrupt")):
                    raise ValueError(f"Unexpected {image.name} trace: {observed!r}")
                records[image.stem] = {**metadata, "systick_vector": vector, "trace": observed}

        wrong_vector = emit_startup(args, work, "wrong-vector", "wrong_interrupt")
        full_write = emit_driver(args, work, "full-write", "UNMASKED")
        clear_extra = emit_driver(args, work, "clear-extra", "FORCE_PENDING")
        leave_extra = emit_driver(args, work, "leave-extra", "FORCE_PENDING", "LEAVE_PENDING")
        interrupt_trace = trace_expected(inputs, interrupt=True)
        extra_trace = interrupt_trace.rsplit("#", 1)[0] + f"#{len(inputs) + 1:02x}!"
        controls = {
            "wrong_systick_vector": (wrong_vector, drivers["interrupt"], "BVX"),
            "write_unmasked_gpio": (startup, full_write, "BG02X"),
            "acknowledge_forced_pending": (startup, clear_extra, interrupt_trace),
            "leave_forced_pending": (startup, leave_extra, extra_trace),
        }
        control_traces = {}
        for label, (boot_object, driver, expected) in controls.items():
            image = work / f"{label}.elf"
            closure.link(args.lld, image, (boot_object, sample_object, driver, steps["llvm"]))
            observed = closure.boot(args.qemu, image)
            if observed != expected:
                raise ValueError(f"Expected {label} to emit {expected!r}, got {observed!r}")
            control_traces[label] = observed

    return {
        "schema": "llmlang-cortex-m3-timer-gpio-v1",
        "machine": "lm3s6965evb",
        "systick_reload": 1999,
        "tools": {name: closure.output([getattr(args, name), "--version"]).splitlines()[0].strip()
                  for name in ("llc", "lld", "rustc", "qemu")},
        "source_sha256": {
            name: sha256(path.read_bytes()).hexdigest()
            for name, path in [(name, CLOSURE / name) for name in ("startup.s", "step.ll", "step.rs",
                                                                  "inputs.json", "memory.ld", "run.py")]
            + [("timer.s", HERE / "timer.s"), ("timer-run.py", Path(__file__))]
        },
        "steps_per_image": len(inputs),
        "images": records,
        "controls": control_traces,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "llc": "llc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19",
        "nm": "llvm-nm-19", "objcopy": "llvm-objcopy-19", "rustc": "rustc", "qemu": "qemu-system-arm",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compare(args)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result['images'])} images, {result['steps_per_image']} timer/GPIO steps per image")
