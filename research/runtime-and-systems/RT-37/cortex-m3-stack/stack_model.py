"""Analyze stack and return links in the admitted Cortex-M3 fixture disassembly."""

from collections import defaultdict, deque
import re


WINDOW_BYTES = 128
BASIC_FRAME_BYTES = 32
EXCEPTION_RETURN = -1
PASS_THROUGH = frozenset((
    "add", "addhs", "addlo", "adds", "and", "cmp", "cpsie", "dsb", "isb", "it", "ite", "ldr",
    "lsrs", "mov", "moveq", "movhi", "movhs", "movlo", "movne", "movs", "movw", "mrs", "orr",
    "str", "sub", "subs", "tst", "ubfx", "wfi",
))
BRANCH_CONDITIONS = "eq|ne|hs|lo|hi|ls|cs|cc|mi|pl|vs|vc|ge|lt|gt|le"


def instructions(disassembly):
    result = {}
    for line in disassembly.splitlines():
        match = re.fullmatch(r"\s+([0-9a-f]+):\s*(.*)", line)
        if match is None:
            continue
        address = int(match[1], 16)
        operation, _, arguments = match[2].partition("@")[0].strip().expandtabs().partition(" ")
        if re.search(r"\s\.(?:word|short|byte|long)\s", match[2]):
            operation, arguments = "data", ""
        result[address] = operation.removesuffix(".w").removesuffix(".n"), arguments.strip()
    return result


def symbol_addresses(nm_output):
    addresses = {}
    for row in nm_output.splitlines():
        match = re.fullmatch(r"([0-9a-f]+)\s+[Tt]\s+(\S+)", row)
        if match:
            addresses[match[2]] = int(match[1], 16)
    return addresses


def branch_target(operands):
    match = re.search(r"\b0x([0-9a-f]+)\s+<[^>]+>$", operands)
    if match is None:
        raise ValueError(f"Unsupported indirect or undecoded branch {operands!r}")
    return int(match[1], 16)


def stack_registers(operands):
    match = re.fullmatch(r"\{((?:r(?:[0-9]|1[0-2])|lr|pc)(?:, (?:r(?:[0-9]|1[0-2])|lr|pc))*)\}", operands)
    if match is None:
        raise ValueError(f"Unsupported stack register list {operands!r}")
    return match[1].split(", ")


def depths_from(code, entry, *, handler=False):
    next_address = dict(zip(code, list(code)[1:]))
    pending = deque([(entry, (), EXCEPTION_RETURN if handler else None, ())])
    visited = set()
    depths = defaultdict(set)
    while pending:
        state = pending.popleft()
        if state in visited:
            continue
        visited.add(state)
        address, returns, lr, stack = state
        if address not in code or len(stack) * 4 > WINDOW_BYTES or len(returns) > 16:
            raise ValueError(f"Outside the admitted code, stack or call depth at {address:#x}")
        depths[address].add(4 * len(stack))
        op, args = code[address]
        following = next_address.get(address, address + 2)

        def schedule(pc, *, chain=returns, link=lr, words=stack):
            pending.append((pc, chain, link, words))

        def finish(destination, words):
            if returns:
                expected_pc, saved_stack = returns[-1]
                if destination != expected_pc or words != saved_stack:
                    raise ValueError(f"Unbalanced return or unexpected link at {address:#x}")
                schedule(expected_pc, chain=returns[:-1], words=words)
            elif not handler or destination != EXCEPTION_RETURN or words:
                raise ValueError(f"Unexpected root return at {address:#x}")

        if op == "bl":
            schedule(branch_target(args), chain=(*returns, (following, stack)), link=following)
        elif op == "b":
            schedule(branch_target(args))
        elif op in {"cbz", "cbnz"} or re.fullmatch(rf"b(?:{BRANCH_CONDITIONS})", op):
            schedule(branch_target(args))
            schedule(following)
        elif args == "lr" and (op == "bx" or re.fullmatch(rf"bx(?:{BRANCH_CONDITIONS})", op)):
            finish(lr, stack)
            if op != "bx":
                schedule(following)
        elif op == "push":
            registers = stack_registers(args)
            if "pc" in registers:
                raise ValueError(f"Unexpected PC save at {address:#x}")
            schedule(following, words=tuple(lr if register == "lr" else None for register in registers) + stack)
        elif op == "pop":
            registers = stack_registers(args)
            if len(registers) > len(stack) or "lr" in registers:
                raise ValueError(f"Unexpected stack restore at {address:#x}")
            words = stack[len(registers):]
            if "pc" in registers:
                finish(stack[registers.index("pc")], words)
            else:
                schedule(following, words=words)
        elif op in PASS_THROUGH and not re.search(r"\b(?:sp|lr)\b", args) and args.split(",")[0] != "pc":
            schedule(following)
        else:
            raise ValueError(f"Unsupported stack/control instruction at {address:#x}: {op} {args}")
    return depths


def stack_bounds(disassembly, nm_output, interrupt):
    code = instructions(disassembly)
    addresses = symbol_addresses(nm_output)
    thread = depths_from(code, addresses["reset"])
    thread_depths = {depth for per_pc in thread.values() for depth in per_pc}
    software = max(thread_depths)
    if not interrupt:
        return {"thread_max": software, "interrupt_local_max": 0, "any_phase_bound": software,
                "armed_phase_bound": software, "entry_msp_depth": 0, "padding": 0}

    handler = depths_from(code, addresses["timer_interrupt"], handler=True)
    handler_depth = max(max(per_pc) for per_pc in handler.values())
    begin, end = (addresses[name] for name in ("armed_wait_begin", "armed_wait_end"))
    armed_depths = {depth for pc, values in thread.items() if begin <= pc < end for depth in values}
    if len(armed_depths) != 1:
        raise ValueError("Expected a single software depth throughout the armed interval")
    (armed_depth,) = armed_depths
    padding = armed_depth % 8
    entry_depth = armed_depth + BASIC_FRAME_BYTES + padding
    max_any_exception = max(depth + BASIC_FRAME_BYTES + depth % 8 for depth in thread_depths)
    return {"thread_max": software, "interrupt_local_max": handler_depth,
            "any_phase_bound": max(software, max_any_exception + handler_depth),
            "armed_phase_bound": max(software, entry_depth + handler_depth),
            "entry_msp_depth": entry_depth, "padding": padding}
