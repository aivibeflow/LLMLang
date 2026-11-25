"""Check native JIT callback traversal and separately resolve the call-site PC."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
HOST = (
    "return_value", "callback_count", "saw_generated_frame", "reached_host_caller",
    "libgcc_fde_found", "dladdr_symbol_found", "call_site_offset",
)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def run(*command):
    process = subprocess.run(command, text=True, capture_output=True, check=True, timeout=30)
    check(not process.stderr, process.stderr)
    return process.stdout.strip()


def parse_host(line, traverses):
    label, *fields = line.split()
    check(label == "host" and len(fields) == len(HOST), line)
    values = list(map(int, fields))
    check(values[:-1] == [35, 1, 1, int(traverses), int(traverses), 0], line)
    return dict(zip(HOST, values))


def compare_orc(args, scratch):
    text = (HERE / "jit.ll").read_text()
    check(text.count("nounwind uwtable") == text.count("line: 4, column: 20") == 1, "mutant anchors")
    cases = (
        ("original", text, True, 4),
        ("without_uwtable", text.replace("nounwind uwtable", "nounwind"), False, 4),
        ("wrong_origin", text.replace("line: 4, column: 20", "line: 5, column: 20"), True, 5),
    )
    results = {}
    for name, ir, traverses, expected_line in cases:
        input_path = scratch / f"{name}.ll"
        object_path = scratch / f"{name}.o"
        code_path = scratch / f"{name}.text"
        input_path.write_text(ir)
        host = parse_host(run(args.orc, input_path, object_path), traverses)
        sections = run("llvm-readelf-19", "-SW", object_path)
        check(bool(re.search(r"\s\.eh_frame\s", sections)) == traverses, sections)
        check(bool(re.search(r"\s\.debug_line\s", sections)), sections)
        check("No errors." in run("llvm-dwarfdump-19", "--verify", object_path), name)
        listing = run("llvm-nm-19", "--print-size", object_path).splitlines()
        address, size, kind, symbol = next(line.split() for line in listing if line.endswith(" T jit_step"))
        check(kind == "T" and symbol == "jit_step", listing)
        offset = host["call_site_offset"]
        check(0 <= offset < int(size, 16), host)
        pc = int(address, 16) + offset
        [location] = json.loads(run("llvm-symbolizer-19", "--output-style=JSON", f"--obj={object_path}", hex(pc)))
        [symbolized] = location["Symbol"]
        origin = {key: symbolized[key] for key in ("FileName", "FunctionName", "Line", "Column")}
        check(origin == {"FileName": "/llmlang/rt13/source.c", "FunctionName": "jit_step",
                         "Line": expected_line, "Column": 20}, origin)
        run("llvm-objcopy-19", f"--dump-section=.text={code_path}", object_path)
        results[name] = {"host": host, "offline_dwarf_origin": origin, "accepted_origin": expected_line == 4,
                         "object_size": object_path.stat().st_size,
                         "text_sha256": sha256(code_path.read_bytes()).hexdigest(),
                         "object_sha256": sha256(object_path.read_bytes()).hexdigest()}
    check(len({item["text_sha256"] for item in results.values()}) == 1, "text changed across ORC controls")
    return results


def compare_cranelift(executable):
    results = {}
    variants = (("true", "unregistered"), ("false", "unregistered"), ("true", "registered"))
    for level, (emit, register) in product(("none", "speed"), variants):
        observed = run(executable, level, emit, register).splitlines()
        records = [line for line in observed if line.startswith("source ")]
        check(len(observed) == len(records) + 3, observed)
        compiled, after, host = (line for line in observed if not line.startswith("source "))
        label, info_present, operations, size = compiled.split()
        check(label == "compiled" and info_present == "1", compiled)
        count = int(operations)
        check((count > 0 if emit == "true" else count == 0) and int(size) > 0, compiled)
        check(after == "after 0", after)
        host = parse_host(host, register == "registered")
        spans = [list(map(int, line.split()[1:])) for line in records]
        matches = [source for begin, end, source in spans if begin <= host["call_site_offset"] < end]
        check(matches == [4], spans)
        results[f"{level}-{emit}-{register}"] = {
            "host": host, "unwind_info_object_available": bool(int(info_present)),
            "unwind_operations": count, "code_size": int(size), "source_spans": spans,
            "internal_source_line": matches[0], "fde_found_after_deregistration": False,
        }
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cranelift", required=True, type=Path)
    parser.add_argument("--orc", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    check((HERE / "source.c").read_text().splitlines()[3].strip() == "u32 observed = callback(input);",
          "source callback line changed")
    with tempfile.TemporaryDirectory(prefix="llmlang-jit-unwind-") as temp:
        sources = ("observer.h", "observer.c", "source.c", "jit.ll", "orc.cpp",
                   "Cargo.toml", "Cargo.lock", "src/main.rs", "run.py")
        evidence = {
            "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in sources},
            "tools": {"llvm": run("llvm-config-19", "--version"), "rustc": run("rustc", "--version"),
                      "gcc": run("cc", "-dumpfullversion"), "glibc": run("getconf", "GNU_LIBC_VERSION")},
            "profiles": {"orc": compare_orc(args, Path(temp)), "cranelift": compare_cranelift(args.cranelift)},
        }
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
