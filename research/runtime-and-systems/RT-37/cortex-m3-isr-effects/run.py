#!/usr/bin/env python3
"""Check ISR effect closure from the linked Cortex-M3 call graph."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
EARLIER = HERE.parent / "cortex-m3-closure"
SPEC = importlib.util.spec_from_file_location("cortex_closure", EARLIER / "run.py")
closure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(closure)

RT04 = HERE.parents[2] / "PROTOTYPES" / "RT-04-01"
STACK = HERE.parent / "cortex-m3-stack"
sys.path[:0] = [str(RT04), str(STACK)]
from rt04_model import check_program
from stack_model import branch_target, instructions, stack_registers


ISR = "timer_interrupt"
ALLOWED = ["mmio.systick.acknowledge"]
PRIMITIVES = {
    "ack_pending": ("e7705273f2bf295560943a58d4fb8c20b1f80b394279332b2f8cd30709dcfab2", ALLOWED[0]),
    "reserve_slice": ("5392b5e5e3cb603c0c412faab449ba280e8563429d2217fc9545ddec4767c30b", "allocation.bump"),
}
CASES = {
    "direct_safe": (0, "ACCEPTED", [ALLOWED[0]], set()),
    "tail_safe": (1, "ACCEPTED", [ALLOWED[0]], set()),
    "transitive_block": (2, "REJECTED", ["irq.block"], {"EFFECT_BOUND_EXCEEDED"}),
    "transitive_allocate": (3, "REJECTED", ["allocation.bump"], {"EFFECT_BOUND_EXCEEDED"}),
    "unknown_indirect": (4, "UNKNOWN", [], {"EFFECT_SUMMARY_UNKNOWN"}),
    "block_and_indirect": (5, "REJECTED", ["irq.block"], {"EFFECT_BOUND_EXCEEDED", "EFFECT_SUMMARY_UNKNOWN"}),
    "stale_primitive": (6, "UNKNOWN", [], {"EFFECT_SUMMARY_UNKNOWN"}),
}


@dataclass(frozen=True)
class Function:
    address: int
    size: int
    digest: str


def image_functions(args, image):
    header = closure.output([args.readelf, "-W", "-S", "-s", image])
    section = re.search(r"\[\s*(\d+)\]\s+\.text\s+PROGBITS\s+([0-9a-f]+)\b", header)
    if section is None:
        raise ValueError("Missing .text section")
    base = int(section[2], 16)
    raw = image.with_suffix(".text.bin")
    closure.output([args.objcopy, "-O", "binary", "-j", ".text", image, raw])
    text = raw.read_bytes()
    functions = {}
    pattern = rf"^\s*\d+:\s+([0-9a-f]+)\s+(\d+)\s+FUNC\s+\w+\s+\w+\s+{section[1]}\s+(\w+)$"
    for address, size, name in re.findall(pattern, header, flags=re.MULTILINE):
        pointer, length = int(address, 16), int(size)
        start = (pointer & ~1) - base
        if not pointer & 1 or start < 0 or not length or start + length > len(text) or name in functions:
            raise ValueError(f"Invalid Thumb function extent for {name}")
        functions[name] = Function(pointer & ~1, length, sha256(text[start:start + length]).hexdigest())
    vector, = struct.unpack_from("<I", image.with_suffix(".vectors.bin").read_bytes(), 15 * 4)
    if vector != (functions[ISR].address | 1):
        raise ValueError("SysTick entry does not select the checked function")
    return functions, hex(vector)


def effect_graph(disassembly, functions):
    code = instructions(disassembly)
    symbols = {fn.address: name for name, fn in functions.items()}
    graph = {}
    for name, fn in functions.items():
        start, end = fn.address, fn.address + fn.size
        local = {}
        effects, targets, missing = set(), set(), set()
        exact = False
        if name in PRIMITIVES:
            identity, effect = PRIMITIVES[name]
            exact = fn.digest == identity
            if exact:
                effects.add(effect)
            else:
                missing.add("primitive-evidence-revision")
        for address, (op, operands) in code.items():
            if not start <= address < end:
                continue
            local[address] = op, operands
            if op == "bl" or op == "b" or re.fullmatch(r"b(?:eq|ne|hs|lo|hi|ls|mi|pl|vs|vc|ge|lt|gt|le)", op):
                try:
                    target = branch_target(operands)
                except ValueError:
                    missing.add(f"unresolved-direct-target@{address:#x}")
                    continue
                if op != "bl" and start <= target < end:
                    continue
                if target in symbols:
                    targets.add(symbols[target])
                else:
                    missing.add(f"branch-without-function-entry@{address:#x}")
            elif op == "blx" or (op == "bx" and operands != "lr"):
                missing.add(f"unresolved-indirect-target@{address:#x}")
            elif op == "wfi":
                effects.add("irq.block")
            elif op in {"push", "pop"}:
                stack_registers(operands)
            elif operands.split(",")[0] in {"sp", "pc", "lr"} and op != "bx":
                missing.add(f"unmodeled-register-control@{address:#x}")
            elif op in {"ldr", "str"} and not exact:
                missing.add(f"unclassified-memory-effect@{address:#x}")
            elif op not in {"bx", "push", "pop", "mov", "movw", "movt", "adds", "ldr", "str", "nop"}:
                missing.add(f"unsupported-opcode:{op}@{address:#x}")
        if start not in local:
            missing.add("missing-entry-instruction")
        if local:
            op, operands = local[max(local)]
            if op not in {"b", "bx"} and not (op == "pop" and "pc" in stack_registers(operands)):
                missing.add("unmodeled-function-fallthrough")
        graph[name] = {"calls": sorted(targets), "effects": sorted(effects), "unresolved": sorted(missing),
                       "sha256": fn.digest}
    return graph


def check(graph):
    functions = {name: {"calls": row["calls"], "effects": row["effects"], "effect_row": "isr"}
                 for name, row in graph.items()}
    functions[ISR]["effect_bound"] = ALLOWED
    complete = [name for name, row in graph.items() if not row["unresolved"]]
    return check_program({"functions": functions, "call_graph_complete": complete}, "B")


def compare(args):
    source = (HERE / "handlers.s").read_text(encoding="utf-8")
    blank = {"calls": [], "effects": [], "unresolved": []}
    supplied = {ISR: {**blank, "calls": ["delegate"]}, "delegate": {**blank, "calls": ["ack_pending"]},
                "ack_pending": {**blank, "effects": ALLOWED}}
    local_status = check({ISR: blank}).status
    supplied_status = check(supplied).status
    if (local_status, supplied_status) != ("ACCEPTED", "ACCEPTED"):
        raise ValueError("The two unchecked graph controls should permit the same declared ISR")
    with TemporaryDirectory(prefix="llmlang-cortex-isr-") as tmp:
        work = Path(tmp)
        records = {}
        for name, (case, expected, effects, diagnostics) in CASES.items():
            assembly = work / f"{name}.s"
            object_code = assembly.with_suffix(".o")
            image = assembly.with_suffix(".elf")
            assembly.write_text(f".set CASE, {case}\n" + source, encoding="utf-8")
            closure.assemble(args.mc, assembly, object_code)
            closure.link(args.lld, image, (object_code,))
            exact = closure.inspect(args, image)
            functions, vector = image_functions(args, image)
            disassembly = closure.output([args.objdump, "-d", "--no-show-raw-insn",
                                          "--triple=thumbv7m-none-eabi", "--section=.text", image])
            graph = effect_graph(disassembly, functions)
            result = check(graph)
            actual = list(dict(result.inferred_effects)[ISR])
            if (result.status, actual, result.codes()) != (expected, effects, diagnostics):
                raise ValueError(f"Unexpected ISR judgment for {name}: {result}")
            records[name] = {"elf_sha256": exact["image_sha256"], "systick_vector": vector,
                             "local_only": local_status, "reused_declared_graph": supplied_status,
                             "linked_graph": result.status, "inferred_isr_effects": actual,
                             "findings": [dict(code=item.code, detail=item.detail) for item in result.findings],
                             "functions": graph}
    inputs = {"handlers.s": HERE / "handlers.s", "run.py": Path(__file__), "memory.ld": EARLIER / "memory.ld",
              "closure-run.py": EARLIER / "run.py", "stack_model.py": STACK / "stack_model.py",
              "rt04_model.py": RT04 / "rt04_model.py"}
    return {"schema": "llmlang-cortex-m3-isr-effects-v1", "isr_allowed_effects": ALLOWED,
            "input_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()},
            "tools": {name: closure.output([getattr(args, name), "--version"]).splitlines()[0].strip()
                      for name in ("mc", "lld", "objdump", "readelf")}, "images": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, command in {
        "mc": "llvm-mc-19", "lld": "ld.lld-19", "readelf": "llvm-readelf-19", "nm": "llvm-nm-19",
        "objcopy": "llvm-objcopy-19", "objdump": "llvm-objdump-19",
    }.items():
        parser.add_argument(f"--{name}", default=command)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(args), indent=2) + "\n", encoding="utf-8")
