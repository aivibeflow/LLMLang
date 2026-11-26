#!/usr/bin/env python3
"""Rebuild the native LLMLang declarations from the pinned Linux source tree."""

import argparse
from hashlib import sha256
from pathlib import Path
import re

from catalog import TABLE_HASH, TABLE_PATH, load_catalog
from native_pointer_contracts import RAW_CHAR_POINTERS, refinements


DESTINATION = Path(__file__).resolve().parents[1] / "provider/src/native.llmlang"
KERNEL_DIRECTORIES = ("arch/x86/kernel", "block", "drivers", "fs", "io_uring", "ipc", "kernel", "mm", "net", "security")
DEFINITION = re.compile(r"(?m)^[ \t]*SYSCALL_DEFINE([0-6])\s*\(\s*(\w+)\s*(?:,([^)]*))?\)")
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)

SCALARS = {
    "__kernel_old_time_t": "I64", "__s32": "I32", "__u32": "U32", "__u64": "U64",
    "aio_context_t": "U64", "char": "CChar", "clockid_t": "I32", "gid_t": "U32",
    "int": "I32", "key_serial_t": "I32", "key_t": "I32", "loff_t": "I64",
    "long": "I64", "mqd_t": "I32", "off_t": "I64", "pid_t": "I32",
    "qid_t": "U32", "rwf_t": "I32", "size_t": "Usize", "timer_t": "I32", "u32": "U32",
    "u64": "U64", "uid_t": "U32", "umode_t": "U16", "unsigned": "U32",
    "unsigned char": "U8", "unsigned int": "U32", "unsigned long": "U64", "void": "Void",
    "enum landlock_rule_type": "U32",
}
CAP_POINTERS = {
    "cap_user_data_t": "MutPtr<__user_cap_data_struct>",
    "cap_user_header_t": "MutPtr<__user_cap_header_struct>",
}
POINTEES = {"fd_set", "siginfo_t", "sigset_t", "stack_t"}
SPECIAL = {
    "vfork": ("stackless", "AbiResult", ""),
    "rt_sigreturn": ("restorer", "Never", "; trap()"),
    "uretprobe": ("kernel", "NativeContinuation", ""),
}


def abi_type(c_type):
    base, *pointers = [" ".join(part.split()) for part in c_type.replace("__user", "").split("*")]
    constant = base.startswith("const ")
    base = base.removeprefix("const ")
    if base in CAP_POINTERS:
        return CAP_POINTERS[base]
    if base in SCALARS:
        result = SCALARS[base]
    elif pointers and (base in POINTEES or base.startswith(("struct ", "union "))):
        result = base.split()[-1]
    else:
        raise ValueError(f"unknown native syscall type {c_type}")
    for pointer in pointers:
        if pointer not in {"", "const"}:
            raise ValueError(f"unknown pointer qualification {c_type}")
        result = f"{'ConstPtr' if constant else 'MutPtr'}<{result}>"
        constant = pointer == "const"
    return result


def scan_definitions(source_root, names):
    definitions = {}
    for directory in KERNEL_DIRECTORIES:
        for path in sorted((source_root / directory).rglob("*.c")):
            contents = path.read_text(encoding="utf-8", errors="surrogateescape")
            if "SYSCALL_DEFINE" not in contents:
                continue
            for match in DEFINITION.finditer(COMMENT.sub("", contents)):
                count, name, arguments = match.groups()
                if name not in names:
                    continue
                # Linux x86 selects CONFIG_CLONE_BACKWARDS.
                if name == "clone" and not match.string[:match.start()].rstrip().endswith(
                    "#ifdef CONFIG_CLONE_BACKWARDS"
                ):
                    continue
                items = [" ".join(item.split()) for item in arguments.split(",")] if arguments else []
                if len(items) != 2 * int(count):
                    raise ValueError(f"{path}: wrong arity for {name}")
                signature = tuple(zip(items[::2], items[1::2], strict=True))
                if name in definitions and definitions[name] != signature:
                    raise ValueError(f"{path}: ambiguous native signature for {name}")
                definitions[name] = signature
    if definitions.keys() != names:
        raise ValueError(f"missing native signatures: {', '.join(sorted(names - definitions.keys()))}")
    return definitions


def render(source_root):
    if sha256((source_root / TABLE_PATH).read_bytes()).hexdigest() != TABLE_HASH:
        raise ValueError("source tree's syscall table differs from the pinned Linux table")
    rows = [row for row in load_catalog()["syscalls"] if row["package_status"] != "kernel-no-handler"]
    names = {row["entry_point"].removeprefix("sys_") for row in rows}
    definitions = scan_definitions(source_root, names)
    lines = ["package linux.syscalls.native", ""]
    overrides = refinements()
    raw_char_pointers = set(RAW_CHAR_POINTERS)
    for row in rows:
        name, number = row["name"], row["number"]
        signature = definitions[row["entry_point"].removeprefix("sys_")]
        parameters = []
        for c_type, parameter in signature:
            kind = abi_type(c_type)
            key = (name, parameter)
            override = overrides.pop(key, None)
            if override is not None:
                if not kind.startswith(("ConstPtr<", "MutPtr<")):
                    raise ValueError(f"{name}.{parameter}: pointer contract attached to {kind}")
                kind = override
            elif "CChar>" in kind:
                if key not in raw_char_pointers:
                    raise ValueError(f"{name}.{parameter}: unaudited C char pointer")
                raw_char_pointers.remove(key)
            if name in {"open", "openat"} and parameter == "filename":
                parameter = "path"
            parameters.append((parameter, kind))
        profile, result, suffix = SPECIAL.get(name, ("unsafe", "AbiResult", ""))
        prototype = ", ".join(f"{parameter}: {kind}" for parameter, kind in parameters)
        arguments = ", ".join([str(number), *(parameter for parameter, _ in parameters)])
        lines.extend([f"{profile} fn {name}({prototype}) -> {result} {{", f"    syscall({arguments}){suffix}", "}", ""])
    if overrides or raw_char_pointers:
        stale = ", ".join(f"{name}.{parameter}" for name, parameter in sorted(overrides.keys() | raw_char_pointers))
        raise ValueError(f"stale native pointer contracts: {stale}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("linux_source", type=Path, help="checkout of the pinned Linux revision")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="compare the declarations with the checkout")
    action.add_argument("--write", action="store_true", help="regenerate the declared signatures")
    args = parser.parse_args()
    try:
        content = render(args.linux_source)
        if args.check:
            if DESTINATION.read_text(encoding="utf-8") != content:
                raise ValueError(f"{DESTINATION} differs from the pinned Linux signatures")
        else:
            DESTINATION.write_text(content, encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
