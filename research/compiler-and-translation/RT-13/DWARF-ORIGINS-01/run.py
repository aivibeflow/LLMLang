"""Check source origins for linked callback instructions in the checked-add probe."""

import argparse
import ast
import ctypes
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
RT13 = HERE.parent
sys.path.insert(0, str(RT13 / "GENERATED-RUST-INTEGERS-01"))
from lower_rust import lower as lower_rust
from integer_fixture import SOURCE, compile_source, evaluate
from llvm_integer_probe import CPU, TRIPLE, _EMIT, _STATUS, _entry, lower as lower_llvm


SOURCE_FILE = "/llmlang/source/checked_add.fixture"
RUST_FILE = "/llmlang/generated/probe.rs"
SENTINEL = 0xabad1234
VECTORS = ((3, 1, 1), (0x7fffffff, 1, 1), (7, 5, 0), (4, 3, 2))


def execute(*arguments, stdin=None):
    result = subprocess.run(list(map(str, arguments)), input=stdin, capture_output=True,
                            text=True, timeout=60)
    if result.returncode or result.stderr:
        raise ValueError(f"Tool failed: {arguments!r}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def origins(source):
    function, = ast.parse(source).body
    return {("entry_emit" if node.value.args[0].id == "a" else "result_emit"): node.lineno
            for node in function.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and node.value.func.id == "emit"}


def source_line(text, exact):
    lines = [index for index, line in enumerate(text.splitlines(), 1) if line.strip() == exact]
    line, = lines
    return line


def add_llvm_debug(ir, sites):
    lines = []
    for line in ir.splitlines():
        if line.startswith("define i32 @probe_0("):
            line = line.replace(") {", ") !dbg !4 {")
        elif line.strip() == "call void %emit(i32 %a)":
            line += ", !dbg !10"
        elif line.strip() == "call void %emit(i32 %value)":
            line += ", !dbg !11"
        elif line.strip() == "ret i32 1":
            line += ", !dbg !12"
        lines.append(line)
    metadata = f'''
!llvm.dbg.cu = !{{!0}}
!llvm.module.flags = !{{!8, !9}}
!0 = distinct !DICompileUnit(language: DW_LANG_C, file: !1, producer: "LLMLang fixture", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug)
!1 = !DIFile(filename: "checked_add.fixture", directory: "/llmlang/source")
!2 = !DISubroutineType(types: !3)
!3 = !{{}}
!4 = distinct !DISubprogram(name: "probe_0", scope: !1, file: !1, line: 1, type: !2, scopeLine: 1, spFlags: DISPFlagDefinition, unit: !0)
!8 = !{{i32 2, !"Dwarf Version", i32 4}}
!9 = !{{i32 2, !"Debug Info Version", i32 3}}
!10 = !DILocation(line: {sites["entry_emit"]}, column: 5, scope: !4)
!11 = !DILocation(line: {sites["result_emit"]}, column: 5, scope: !4)
!12 = !DILocation(line: 4, column: 9, scope: !4)
'''
    return "\n".join(lines) + "\n" + metadata


def llvm_object(work, ir, level, name):
    opt = work / f"{name}.ll"
    obj = opt.with_suffix(".o")
    execute("opt-19", f"-passes=verify,default<O{level}>,verify", "-S", "-o", opt, "-", stdin=ir)
    execute("llc-19", f"-mtriple={TRIPLE}", f"-mcpu={CPU}", f"-O={level}", "-relocation-model=pic",
            "-filetype=obj", opt, "-o", obj)
    return obj


def rust_object(work, rust, level):
    path = work / "probe.rs"
    path.write_text(rust, encoding="utf-8")
    obj = work / f"rust-{level}.o"
    execute("rustc", "--target", TRIPLE, "--edition", "2021", "--crate-type", "lib",
            "--crate-name", "llmlang_probe_debug", "--emit", "obj", "-D", "warnings",
            "-C", "panic=abort", "-C", "debug-assertions=no", "-C", "debuginfo=2",
            "-C", f"opt-level={level}", "-C", f"target-cpu={CPU}", "-C", "relocation-model=pic",
            "--remap-path-prefix", f"{work}=/llmlang/generated", path, "-o", obj)
    return obj


def link(obj):
    lib = obj.with_suffix(".so")
    execute("gcc", "-shared", "-Wl,--no-undefined", "-Wl,--build-id=none", "-o", lib, obj)
    return lib


def callback_pcs(lib):
    dis = execute("llvm-objdump-19", "--disassemble-symbols=probe_0", "--no-show-raw-insn", lib)
    return re.findall(r"^\s*([0-9a-f]+):\s+callq?\s+\*", dis, re.MULTILINE)


def line_at(lib, address):
    raw = execute("llvm-addr2line-19", "-e", lib, "0x" + address).strip()
    source, line = raw.rsplit(":", maxsplit=1)
    return source, int(line)


def check_dwarf(lib):
    text = execute("llvm-dwarfdump-19", "--verify", lib)
    if "No errors." not in text:
        raise ValueError(text)


def replay_native(lib, program):
    binary = ctypes.CDLL(str(lib))
    entry = _entry(binary, 0)
    for a, b, enabled in VECTORS:
        slot = ctypes.c_uint32(SENTINEL)
        events = []
        result = _STATUS[entry(a, b, enabled, _EMIT(events.append), ctypes.byref(slot))]
        expected = evaluate(program, a, b, bool(enabled))
        if (result, slot.value, tuple(events)) != (
                expected.status, SENTINEL if expected.value is None else expected.value, expected.events):
            raise AssertionError(f"Native replay mismatch for {lib.name}")


def profile(lib, expected_file, mapping=None):
    check_dwarf(lib)
    addresses = callback_pcs(lib)
    if len(addresses) != 2:
        raise ValueError(f"Did not find exactly two indirect callbacks in {lib.name}: {addresses}")
    result = []
    for address in addresses:
        name, line = line_at(lib, address)
        if name != expected_file:
            raise ValueError(f"Unexpected location at {address}: {name}:{line}")
        result.append({"pc": address, "debug_line": line, "source_line": mapping.get(line) if mapping else line})
    return result


def text_hash(lib):
    target = lib.with_suffix(".text")
    execute("llvm-objcopy-19", f"--dump-section=.text={target}", lib, lib.with_suffix(".section-copy"))
    return sha256(target.read_bytes()).hexdigest()


def main():
    source = SOURCE.replace("operation", "checked_sadd")
    program = compile_source(source)
    syntax_origins = origins(source)
    expected = [syntax_origins["entry_emit"], syntax_origins["result_emit"]]
    ir = add_llvm_debug(lower_llvm((program,)), syntax_origins)
    rust = lower_rust((program,))
    sidecar = {source_line(rust, "emit(a);"): expected[0], source_line(rust, "emit(value);"): expected[1]}
    profiles = {}
    with TemporaryDirectory(prefix="llmlang-dwarf-") as directory:
        work = Path(directory)
        for level in (0, 3):
            for name, obj, filename, mapping in (
                ("llvm", llvm_object(work, ir, level, f"llvm-{level}"), SOURCE_FILE, None),
                ("rust", rust_object(work, rust, level), RUST_FILE, sidecar),
            ):
                lib = link(obj)
                replay_native(lib, program)
                records = profile(lib, filename, mapping)
                profiles[f"{name}_O{level}"] = {"callbacks": records, "text_sha256": text_hash(lib)}
                if [row["source_line"] for row in records] != expected:
                    raise AssertionError(f"Callback source mismatch in {name} O{level}: {records}")

        marker = "call void %emit(i32 %a), !dbg !10"
        if ir.count(marker) != 1:
            raise ValueError("Missing unique metadata mutation point")
        mutant = ir.replace(marker, "call void %emit(i32 %a), !dbg !11")
        corrupted = link(llvm_object(work, mutant, 3, "wrong-origin"))
        replay_native(corrupted, program)
        wrong_llvm = profile(corrupted, SOURCE_FILE)
        wrong_map = {line: expected[1] for line in sidecar}
        wrong_rust = profile(work / "rust-3.so", RUST_FILE, wrong_map)
        same_code = text_hash(corrupted) == profiles["llvm_O3"]["text_sha256"]
        if not same_code or any([row["source_line"] for row in records] == expected
                                for records in (wrong_llvm, wrong_rust)):
            raise AssertionError("Debug provenance mutation was not distinguished at the same code boundary")
    llvm_version = execute("opt-19", "--version").splitlines()[0]
    rust_version = execute("rustc", "--version").strip()
    if "19.1.7" not in llvm_version or "1.85.1" not in rust_version:
        raise ValueError(f"Unexpected toolchain: {llvm_version}, {rust_version}")
    return {
        "tools": {"llvm": llvm_version, "rustc": rust_version,
                  "gcc": execute("gcc", "--version").splitlines()[0]},
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_file": SOURCE_FILE, "rust_generated_file": RUST_FILE, "expected_origin_lines": expected,
        "source_sha256": sha256(source.encode()).hexdigest(), "llvm_ir_sha256": sha256(ir.encode()).hexdigest(),
        "rust_source_sha256": sha256(rust.encode()).hexdigest(), "rust_sidecar": sidecar,
        "profiles": profiles, "runtime_vectors_per_profile": len(VECTORS),
        "controls": {"llvm_wrong_location": wrong_llvm, "rust_wrong_sidecar": wrong_rust,
                     "llvm_code_unchanged": same_code},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(main(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
