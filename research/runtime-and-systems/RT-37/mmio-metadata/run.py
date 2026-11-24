#!/usr/bin/env python3
"""Compare layout, direction and protocol admission for pinned MMIO metadata."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from xml.etree import ElementTree

from lxml import etree


PINS = {
    "ARMCM3.svd": "cd91b8682b2e9f2ec632ad2f9f7bc403d0b58f8cc695efd524f31f11ee937e8d",
    "CMSIS-SVD.xsd": "48456961947060a71d75144a74f3a081c32ad2cba7a68dcb7a4603a77d10fb65",
    "TM4C123GH6PM.svd": "562d122ffd2f99e7c6aec073384fdca261fef0f89424ec9dd70174de46837faa",
    "core_cm3.h": "c9937781259a8897adf514445441c68570087d6a72a558d8a4afe75cdb62dbd2",
    "armv7m_nvic.c": "ab05395824767017605b33b9bfdf55ef9bf70b72972cee92e9a414dfe2e7795d",
    "armv7m_systick.c": "e2baf1ceef50315020157b588fbca0ae6c8c79be040f4edc8a4d156c7aed1834",
    "pl061.c": "9629fcbb69b77d85c7dd65d156587354921b7559faffaf797c05f908a61b4c59",
    "stellaris.c": "eba34705bf82331cac36fcd97b4517c9d1f8b12cf0273ae2ec02d6a70ac04acc",
}

BOARD = "qemu-lm3s6965evb"
VENDOR = "TM4C123GH6PM"
HERE = Path(__file__).resolve().parent
READS = {"read", "consume", "observe_pend", "modify"}
WRITES = {"write", "modify", "reset", "set_pending", "clear_pending", "masked_write", "clear_irq"}


@dataclass(frozen=True)
class Request:
    label: str
    device: str
    register: str
    operation: str
    value: int = 0
    mask: int = 0
    width: int = 32
    cap: str = "controller"


def pinned_inputs(directory):
    data = {}
    for name, expected in PINS.items():
        contents = (directory / name).read_bytes()
        if sha256(contents).hexdigest() != expected:
            raise ValueError(f"Pinned source bytes changed: {name}")
        data[name] = contents
    return data


def effective(node, ancestors, name):
    return next((text for candidate in (node, *ancestors) if (text := candidate.findtext(name)) is not None),
                None)


def gpio_layout(document, peripheral_name, register_name):
    peripherals = {one.findtext("name"): one for one in document.findall("./peripherals/peripheral")}
    peripheral = peripherals[peripheral_name]
    parent = peripheral.get("derivedFrom")
    inherited = peripherals[parent] if parent else peripheral
    if parent and (inherited.get("derivedFrom") or peripheral.find("registers") is not None):
        raise ValueError("Outside the single-level derived-peripheral profile")
    register, = [one for one in inherited.findall("./registers/register") if one.findtext("name") == register_name]
    if register.get("derivedFrom") or register.find("dim") is not None:
        raise ValueError("Outside the scalar register profile")
    ancestors = (peripheral, inherited, document)
    offset = int(register.findtext("addressOffset"), 0)
    fields = [{"name": node.findtext("name"), "bits": node.findtext("bitRange"),
               "access": effective(node, (register, *ancestors), "access"),
               "readAction": node.findtext("readAction"), "modifiedWriteValues": node.findtext("modifiedWriteValues")}
              for node in register.findall("./fields/field")]
    return {
        "address": hex(int(peripheral.findtext("baseAddress"), 0) + offset),
        "width": int(effective(register, ancestors, "size"), 0),
        "access": effective(register, ancestors, "access"), "derivedFrom": parent,
        "readAction": register.findtext("readAction"), "modifiedWriteValues": register.findtext("modifiedWriteValues"),
        "fields": fields,
    }


def core_layout(header):
    source = header.decode("utf-8")
    system = int(re.search(r"#define SCS_BASE\s+\((0x[0-9A-F]+)UL\)", source)[1], 0)
    layout = {}
    for group, registers in (("SysTick", ("CTRL", "LOAD", "VAL", "CALIB")), ("SCB", ("ICSR",))):
        base = re.search(rf"#define {group}_BASE\s+\(SCS_BASE \+\s*(0x[0-9A-F]+)UL\)", source)
        declaration = re.search(rf"typedef struct\s*\{{([^{{}}]+)\}}\s*{group}_Type;", source)[1]
        for name in registers:
            match = re.search(rf"(__IOM|__IM)\s+uint32_t {name};\s*/\*!< Offset: (0x[0-9A-F]+)", declaration)
            access = "read-write" if match[1] == "__IOM" else "read-only"
            layout[f"{group}.{name}"] = {"address": hex(system + int(base[1], 0) + int(match[2], 0)),
                                        "width": 32, "access": access, "readAction": None,
                                        "modifiedWriteValues": None}
    masks = {label: 1 << int(re.search(rf"#define {label}_Pos\s+(\d+)U\b", source)[1])
             for label in ("SysTick_CTRL_COUNTFLAG", "SCB_ICSR_PENDSTSET", "SCB_ICSR_PENDSTCLR")}
    return layout, masks


def layout_verdict(request, layout, *, directions):
    if layout is None:
        return "unknown"
    if request.width != layout["width"]:
        return "deny"
    if not directions:
        return "allow"
    access = layout["access"]
    if access is None:
        return "unknown"
    if (request.operation in READS and access == "write-only"
            or request.operation in WRITES and access == "read-only"):
        return "deny"
    return "allow"


def protocol_verdict(request, emulator_gpio, core, masks):
    if request.device != BOARD:
        return "unknown", None
    register = request.register
    if register not in core and register not in {"GPIOF.DATA", "GPIOF.ICR"}:
        return "unknown", None
    if request.width != 32 or request.cap != "controller":
        return "deny", None
    address = int(core[register]["address"], 0) if register in core else emulator_gpio
    operation, value, mask = request.operation, request.value, request.mask
    match register, operation:
        case ("SysTick.CTRL", "consume") | ("SysTick.CALIB" | "SysTick.VAL" | "SysTick.LOAD", "read"):
            return "allow", {"volatile_load": hex(address)}
        case "SysTick.CTRL", "write" if 0 <= value <= 7:
            return "allow", {"volatile_store": [hex(address), value]}
        case "SysTick.LOAD", "write" if 0 <= value <= 0xFFFFFF:
            return "allow", {"volatile_store": [hex(address), value]}
        case "SysTick.VAL", "reset" if value == 0:
            return "allow", {"volatile_store": [hex(address), value]}
        case "SCB.ICSR", "observe_pend":
            return "allow", {"volatile_load": hex(address), "mask": masks["SCB_ICSR_PENDSTSET"]}
        case "SCB.ICSR", "set_pending" if value == masks["SCB_ICSR_PENDSTSET"]:
            return "allow", {"volatile_store": [hex(address), value]}
        case "SCB.ICSR", "clear_pending" if value == masks["SCB_ICSR_PENDSTCLR"]:
            return "allow", {"volatile_store": [hex(address), value]}
        case "GPIOF.DATA", "read":
            return "allow", {"volatile_load": hex(address + 0x3FC)}
        case "GPIOF.DATA", "masked_write" if 0 < mask <= 3 and value >= 0 and value & ~mask == 0:
            return "allow", {"volatile_store": [hex(address + 4 * mask), value]}
        case "GPIOF.ICR", "clear_irq" if 0 < value <= 3:
            return "allow", {"volatile_store": [hex(address + 0x41C), value]}
    return "deny", None


def evidence(data):
    anchors = {
        "armv7m_systick.c": ("val = s->control;\n        s->control &= ~SYSTICK_COUNTFLAG;",
                             "value & 7;", "value & 0xffffff", "Writing any value clears SYST_CVR to zero",
                             ".valid.min_access_size = 4", ".valid.max_access_size = 4"),
        "armv7m_nvic.c": ("if (value & (1 << 26)) {\n            armv7m_nvic_set_pending(s, ARMV7M_EXCP_SYSTICK",
                          "} else if (value & (1 << 25)) {\n            armv7m_nvic_clear_pending(s, ARMV7M_EXCP_SYSTICK"),
        "pl061.c": ("r = s->data & (offset >> 2);", "mask = (offset >> 2) & s->dir;",
                    "s->data = (s->data & ~mask) | (value & mask);", "s->istate &= ~value;"),
        "stellaris.c": ('sysbus_create_simple("pl061_luminary", gpio_addr[i]', "0x40024000, 0x40025000, 0x40026000"),
    }
    for path, patterns in anchors.items():
        if any(pattern.encode() not in data[path] for pattern in patterns):
            raise ValueError(f"An emulator behavior anchor changed in {path}")
    schema = ElementTree.fromstring(data["CMSIS-SVD.xsd"])
    attributes = {node.get("name") for node in schema.iter("{http://www.w3.org/2001/XMLSchema}element")}
    if not {"readAction", "modifiedWriteValues"} <= attributes:
        raise ValueError("Expected both behavior annotations in the pinned XSD")
    reference_path = HERE.parent / "cortex-m3-timer" / "results.json"
    reference_bytes = reference_path.read_bytes()
    controls = json.loads(reference_bytes)["controls"]
    if (controls["write_unmasked_gpio"] != "BG02X" or not controls["acknowledge_forced_pending"].endswith("#0e!")
            or not controls["leave_forced_pending"].endswith("#0f!")):
        raise ValueError("The earlier exact timer/GPIO discriminators changed")
    return {"emulator_behavior_anchors": sum(map(len, anchors.values())),
            "prior_timer_ledger_sha256": sha256(reference_bytes).hexdigest(),
            "prior_timer_controls": controls, "pin_1_alias_write": "0x40025008"}


def cases():
    specs = (
        ("observe_countflag", "SysTick.CTRL", "consume", "allow", {}),
        ("pretend_countflag_is_pure", "SysTick.CTRL", "read", "deny", {}),
        ("systick_control_rw", "SysTick.CTRL", "modify", "deny", {"value": 2}),
        ("systick_control_store", "SysTick.CTRL", "write", "allow", {"value": 7}),
        ("systick_control_reserved_bit", "SysTick.CTRL", "write", "deny", {"value": 8}),
        ("systick_control_flag_write", "SysTick.CTRL", "write", "deny", {"value": 1 << 16}),
        ("systick_control_wrong_width", "SysTick.CTRL", "consume", "deny", {"width": 16}),
        ("systick_control_no_capability", "SysTick.CTRL", "consume", "deny", {"cap": "none"}),
        ("systick_reload_end_of_range", "SysTick.LOAD", "write", "allow", {"value": 0xFFFFFF}),
        ("systick_reload_out_of_range", "SysTick.LOAD", "write", "deny", {"value": 0x1000000}),
        ("systick_reload_read", "SysTick.LOAD", "read", "allow", {}),
        ("systick_value_read", "SysTick.VAL", "read", "allow", {}),
        ("systick_value_store", "SysTick.VAL", "write", "deny", {"value": 9}),
        ("systick_value_reset", "SysTick.VAL", "reset", "allow", {}),
        ("systick_calibration_read", "SysTick.CALIB", "read", "allow", {}),
        ("systick_calibration_write", "SysTick.CALIB", "write", "deny", {"value": 1}),
        ("pending_status_read", "SCB.ICSR", "observe_pend", "allow", {}),
        ("pending_set_command", "SCB.ICSR", "set_pending", "allow", {"value": 1 << 26}),
        ("pending_clear_command", "SCB.ICSR", "clear_pending", "allow", {"value": 1 << 25}),
        ("pending_clear_zero", "SCB.ICSR", "clear_pending", "deny", {}),
        ("pending_clear_echoes_set", "SCB.ICSR", "clear_pending", "deny", {"value": 3 << 25}),
        ("pending_clear_rmw", "SCB.ICSR", "modify", "deny", {"value": 1 << 25}),
        ("gpio_read_full_alias", "GPIOF.DATA", "read", "allow", {}),
        ("gpio_pin1_set", "GPIOF.DATA", "masked_write", "allow", {"mask": 2, "value": 2}),
        ("gpio_pin1_clear", "GPIOF.DATA", "masked_write", "allow", {"mask": 2}),
        ("gpio_preserve_neighbor", "GPIOF.DATA", "masked_write", "deny", {"mask": 2, "value": 3}),
        ("gpio_unmasked_write", "GPIOF.DATA", "write", "deny", {"value": 2}),
        ("gpio_clear_rmw", "GPIOF.ICR", "modify", "deny", {"value": 2}),
        ("gpio_clear_literal_mask", "GPIOF.ICR", "clear_irq", "allow", {"value": 2}),
        ("unsupported_dma", "DMA.CH0", "write", "unknown", {"value": 1}),
    )
    board = [(Request(label, BOARD, register, op, **options), expected)
             for label, register, op, expected, options in specs]
    vendor = [(Request("exact_device_missing_" + op, VENDOR, register, op, value=2), "unknown")
              for register, op in (("GPIOF.DATA", "write"), ("GPIOF.ICR", "read"), ("GPIOF.ICR", "clear_irq"))]
    return board + vendor


def schema_comparison(data):
    schema = etree.XMLSchema(etree.fromstring(data["CMSIS-SVD.xsd"]))
    core_valid = schema.validate(etree.fromstring(data["ARMCM3.svd"]))
    core_error = schema.error_log.last_error
    vendor_valid = schema.validate(etree.fromstring(data["TM4C123GH6PM.svd"]))
    if core_valid or core_error is None or "Expected is ( peripherals )" not in core_error.message or not vendor_valid:
        raise ValueError("The pinned documents did not retain their XSD validation outcomes")
    return {"lxml_version": ".".join(map(str, etree.LXML_VERSION[:3])),
            "ARMCM3": {"valid": core_valid, "reason": "missing peripherals"},
            "TM4C123GH6PM": {"valid": vendor_valid}}


def compare(directory):
    data = pinned_inputs(directory)
    core_svd = ElementTree.fromstring(data["ARMCM3.svd"])
    vendor_svd = ElementTree.fromstring(data["TM4C123GH6PM.svd"])
    vendor = {f"{name}.{reg}": gpio_layout(vendor_svd, name, reg)
              for name, reg in (("GPIOF", "DATA"), ("GPIOF", "DIR"), ("GPIOF", "ICR"), ("GPIOF_AHB", "DATA"))}
    core, masks = core_layout(data["core_cm3.h"])
    anchors = evidence(data)
    emulator_gpio = 0x40025000
    gpio = {"GPIOF.DATA": {"address": hex(emulator_gpio + 0x3FC), "width": 32, "access": "read-write"},
            "GPIOF.ICR": {"address": hex(emulator_gpio + 0x41C), "width": 32, "access": "write-only"}}
    expected_layout = ("0x400253fc", "0x40025400", "0x4002541c")
    if tuple(vendor[f"GPIOF.{name}"]["address"] for name in ("DATA", "DIR", "ICR")) != expected_layout:
        raise ValueError("The derived APB address did not match the independent offset oracle")

    counts = {name: Counter() for name in ("width_only", "direction_only", "protocol")}
    records = {}
    for request, expected in cases():
        layout = (vendor if request.device == VENDOR else {**core, **gpio}).get(request.register)
        protocol, command = protocol_verdict(request, emulator_gpio, core, masks)
        verdicts = {"width_only": layout_verdict(request, layout, directions=False),
                    "direction_only": layout_verdict(request, layout, directions=True), "protocol": protocol}
        if protocol != expected:
            raise ValueError(f"Unexpected {request.label} result: {protocol} vs. {expected}")
        for name, verdict in verdicts.items():
            counts[name][verdict] += 1
            counts[name]["false_admissions"] += int(verdict == "allow" and expected != "allow")
        records[request.label] = {**verdicts, "command": command}

    if records["gpio_pin1_set"]["command"] != {"volatile_store": [anchors["pin_1_alias_write"], 2]}:
        raise ValueError("The typed GPIO encoding did not match the independent alias address")
    return {"schema": "llmlang-rt37-mmio-metadata-v1", "input_sha256": PINS,
            "core_svd": {"schema_version": core_svd.get("schemaVersion"),
                         "peripherals": len(core_svd.findall("./peripherals/peripheral"))},
            "vendor_svd": {"schema_version": vendor_svd.get("schemaVersion"), "registers": vendor},
            "xsd_validation": schema_comparison(data),
            "core_header": {"registers": core, "masks": masks}, "evidence": anchors,
            "case_count": len(records), "totals": counts, "observations": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(args.inputs), indent=2) + "\n", encoding="utf-8")
