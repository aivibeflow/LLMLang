"""Observe distinct GPIO edge and NVIC pending acknowledgments through QEMU qtest."""

import argparse
from contextlib import contextmanager
from hashlib import file_digest
from itertools import product
import json
import os
import platform
from pathlib import Path
import select
import subprocess
import sys
from tempfile import TemporaryFile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REVISION = "3ed06f02"
PORTS = {"A": (0x40004000, 1, 0, 0x01), "F": (0x40025000, 6, 30, 0x20)}
PENDING_SET = 0xE000E200
PENDING_CLEAR = 0xE000E280
ARGUMENTS = ("-machine", "lm3s6965evb", "-display", "none", "-serial", "none", "-monitor",
             "none", "-S", "-qtest", "stdio", "-qtest-log", os.devnull)


class GPIO:
    def __init__(self, process, port):
        self.process = process
        self.base, device, irq, self.clock = PORTS[port]
        self.device = f"/machine/unattached/device[{device}]"
        self.line = 1 << irq

    def send(self, *items):
        command = " ".join(map(str, items))
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        ready, _, _ = select.select([self.process.stdout], [], [], 5)
        if not ready:
            raise TimeoutError(f"QEMU did not reply to {command}")
        response = self.process.stdout.readline().split()
        if not response or response[0] != "OK":
            raise RuntimeError(f"QEMU refused {command}: {response}")
        return int(response[1], 16) if len(response) > 1 else None

    def write(self, offset, value):
        self.send("writel", hex(self.base + offset), hex(value))

    def pin(self, pin, level):
        self.send("set_irq_in", self.device, "unnamed-gpio-in", pin, level)

    def nvic_clear(self):
        self.send("writel", hex(PENDING_CLEAR), hex(self.line))

    def observe(self):
        raw = self.send("readl", hex(self.base + 0x414))
        masked = self.send("readl", hex(self.base + 0x418))
        pending = self.send("readl", hex(PENDING_SET))
        return raw, masked, int(bool(pending & self.line))

    def initial_edges(self, ordered_pins):
        self.send("writel", "0x400fe108", hex(self.clock))
        for offset, value in ((0x400, 0), (0x51C, 3), (0x404, 0), (0x408, 0), (0x40C, 3), (0x410, 3)):
            self.write(offset, value)
        for pin in ordered_pins:
            self.pin(pin, 0)
        assert self.observe() == (0, 0, 0)
        for pin in ordered_pins:
            self.pin(pin, 1)
        assert self.observe() == (3, 3, 1)


@contextmanager
def device(qemu, port):
    with TemporaryFile(mode="w+t") as diagnostics:
        process = subprocess.Popen([qemu, *ARGUMENTS], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=diagnostics, text=True, bufsize=1)
        try:
            yield GPIO(process, port)
        except Exception as error:
            diagnostics.seek(0)
            raise RuntimeError(f"QEMU port {port} failed: {error}\n{diagnostics.read()}") from error
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


def exercise(qemu, port, selected_pin, policy):
    selected = 1 << selected_pin
    peer = 3 ^ selected
    phases = {}
    with device(qemu, port) as gpio:
        gpio.initial_edges((selected_pin, 1 - selected_pin))

        def expect(name, desired):
            actual = gpio.observe()
            if actual != desired:
                raise ValueError((port, policy, name, actual, desired))
            phases[name] = actual

        expect("initial_two_edges", (3, 3, 1))
        if policy == "selected_then_peer":
            gpio.write(0x41C, selected)
            expect("selected_edge_acknowledged", (peer, peer, 1))
            gpio.nvic_clear()
            expect("attempted_controller_clear_high_line", (peer, peer, 1))
            gpio.write(0x41C, peer)
            expect("peripheral_idle_controller_still_pending", (0, 0, 1))
            gpio.nvic_clear()
            expect("controller_cleared_after_gpio", (0, 0, 0))
            gpio.pin(selected_pin, 1)
            expect("unchanged_high_input", (0, 0, 0))
            gpio.pin(selected_pin, 0)
            gpio.pin(selected_pin, 1)
            expect("fresh_rising_edge", (selected, selected, 1))
        elif policy == "controller_only":
            gpio.nvic_clear()
            expect("controller_only_keeps_latches", (3, 3, 1))
        elif policy == "mask_without_clear":
            gpio.write(0x410, 0)
            expect("port_masked_with_raw_edges", (3, 0, 1))
            gpio.nvic_clear()
            expect("controller_clear_with_masked_sources", (3, 0, 0))
            gpio.write(0x410, selected)
            expect("unmask_reasserts_latched_edge", (3, selected, 1))
        else:
            gpio.write(0x41C, 0)
            expect("write_zero_keeps_latches", (3, 3, 1))
            gpio.write(0x41C, 3)
            expect("wider_mask_also_clears_peer", (0, 0, 1))
            gpio.nvic_clear()
            expect("controller_clear_after_wider_mask", (0, 0, 0))
    return phases


def audit(qemu):
    policies = ("selected_then_peer", "controller_only", "mask_without_clear", "zero_and_wide_mask")
    rows = {f"{port}/{pin}/{policy}": exercise(qemu, port, pin, policy)
            for port, pin, policy in product(PORTS, (0, 1), policies)}
    report = "research/runtime-and-systems/RT-37/RT-37-LM3S6965-PART-REGISTER-2026-11-25.md"
    git = ["git", "-C", str(REPO)]
    revision = subprocess.check_output([*git, "rev-parse", REVISION], text=True).strip()
    blob = subprocess.check_output([*git, "rev-parse", f"{revision}:{report}"], text=True).strip()
    with qemu.open("rb") as source:
        digest = file_digest(source, "sha256").hexdigest()
    return {
        "reference_revision": revision, "manual_reconciliation_blob": blob, "python": sys.version.split()[0],
        "host": {"machine": platform.machine(), "kernel": platform.release()},
        "qemu": subprocess.check_output([qemu, "--version"], text=True).splitlines()[0],
        "qemu_sha256": digest, "qemu_arguments": ARGUMENTS,
        "ports": {name: {"base": hex(base), "irq": irq, "qom_device_index": index}
                  for name, (base, index, irq, _) in PORTS.items()},
        "tuple": ["gpio_raw", "gpio_masked", "nvic_pending_for_port"],
        "profiles": len(rows), "observations": sum(len(phases) for phases in rows.values()), "traces": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.qemu.resolve(strict=True))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
