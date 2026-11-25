"""Exercise the shared integer corpus with interpreted and verified compiled JVM entries."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from lower_java import lower


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "GENERATED-RUST-INTEGERS-01"))
from run import FIXTURE, change, program_source, reference, vectors
from integer_fixture import OPERATIONS, compile_source
from llvm_integer_probe import _STATUS


JAVA = ("-Xmx256m", "-XX:ActiveProcessorCount=2")


def execute(java, args, payload=None):
    result = subprocess.run([java, *JAVA, *map(str, args)], input=payload, capture_output=True, timeout=150)
    if result.returncode:
        raise RuntimeError((args, result.stderr.decode(errors="replace"), result.stdout[:200]))
    return result


def compile_source_code(java, directory, code):
    path = directory / "IntegerProbe.java"
    path.write_text(code, encoding="utf-8")
    execute(java, ("--module", "jdk.compiler/com.sun.tools.javac.Main", "-source", "21", "-target", "21",
                   "-g:none", "-d", directory, path))
    artifacts = {}
    for name in sorted(directory.glob("*.class")):
        raw = name.read_bytes()
        if not raw.startswith(bytes.fromhex("cafebabe00000041")):
            raise ValueError(f"Unexpected class header: {name.name}")
        artifacts[name.name] = {"bytes": len(raw), "sha256": sha256(raw).hexdigest(), "major": 65}
    return artifacts


def observe(java, directory, cases, profile):
    request = b"".join(struct.pack("<4I", index, *values) for index, values in cases)
    if profile == "compiled":
        log = directory / "hotspot.xml"
        flags = ("-Xcomp", "-XX:-TieredCompilation", "-XX:CompileCommand=quiet",
                 "-XX:CompileCommand=compileonly,IntegerProbe::probe*", "-XX:+UnlockDiagnosticVMOptions",
                 "-XX:+LogCompilation", f"-XX:LogFile={log}")
    else:
        flags = ("-Xint",)
    response = execute(java, (*flags, "-cp", directory, "IntegerProbe"), request).stdout
    if len(response) != len(cases) * 20:
        raise ValueError("Malformed JVM observation stream")
    decoded = []
    for status, slot, count, first, second in struct.iter_unpack("<5I", response):
        if count not in (1, 2):
            raise ValueError("Unexpected number of observations")
        decoded.append((_STATUS[status], slot, (first, second)[:count]))
    compiled = set()
    if profile == "compiled":
        for row in ElementTree.parse(log).iter("nmethod"):
            method = row.attrib["method"].split()
            if method[0] == "IntegerProbe" and method[1].startswith("probe"):
                compiled.add(int(method[1].removeprefix("probe")))
    return decoded, compiled


def controls(java, directory):
    cases = (
        ("native_division_overflow", "checked_sdiv", (0x80000000, 0xffffffff, 1),
         "            if (a == Integer.MIN_VALUE && b == -1) return 1;\n", "", {"status", "slot", "events"}),
        ("native_shift_mask", "checked_shl", (7, 32, 1),
         "            if (Integer.compareUnsigned(b, 32) >= 0) return 3;\n", "", {"status", "slot", "events"}),
        ("reverse_callbacks", "checked_sadd", (7, 2, 1), "        trace.emit(a);\n", "", {"events"}),
    )
    result = {}
    for name, operation, values, anchor, replacement, fields in cases:
        program = compile_source(program_source(operation))
        modified = change(lower((program,)), anchor, replacement)
        if name == "reverse_callbacks":
            modified = change(modified, "        trace.emit(value);", "        trace.emit(value);\n        trace.emit(a);")
        compile_source_code(java, directory, modified)
        returns, _ = observe(java, directory, [(0, values)], "interpreted")
        reference_result = reference(program, values)
        changed = {field for field, expected, actual in zip(("status", "slot", "events"), reference_result,
                                                             returns[0], strict=True) if expected != actual}
        if changed != fields:
            raise AssertionError((name, fields, changed))
        result[name] = {"input": values, "expected": reference_result, "actual": returns[0], "changed": sorted(changed)}
    return result


def verify(java):
    runtime = execute(java, ("-version",)).stderr.decode().strip().splitlines()
    compiler = execute(java, ("--module", "jdk.compiler/com.sun.tools.javac.Main", "-version")).stdout.decode().strip()
    if compiler != "javac 21.0.13" or '21.0.13' not in runtime[0]:
        raise ValueError((runtime, compiler))
    programs = tuple(compile_source(program_source(op, left, right))
                     for op, (left, right) in product(OPERATIONS, product("ab", repeat=2)))
    cases = tuple(product(range(len(programs)), vectors()))
    baseline = [reference(programs[i], vector) for i, vector in cases]
    source = lower(programs)
    profiles = {}
    with TemporaryDirectory(prefix="llmlang-java-integer-") as scratch:
        directory = Path(scratch)
        artifacts = compile_source_code(java, directory, source)
        for profile in ("interpreted", "compiled"):
            observed, compiled = observe(java, directory, cases, profile)
            for case, expected, actual in zip(cases, baseline, observed, strict=True):
                if expected != actual:
                    raise AssertionError((case, expected, actual))
            if profile == "compiled" and compiled != set(range(len(programs))):
                raise AssertionError(("missing HotSpot compiled entries", sorted(compiled)))
            profiles[profile] = {"observations": len(observed), "compiled_entries_verified": len(compiled),
                                 "statuses": dict(sorted(Counter(row[0] for row in observed).items()))}
        mutants = controls(java, directory)
    paths = [FIXTURE/"integer_fixture.py", FIXTURE/"llvm_integer_probe.py", HERE/"lower_java.py", HERE/"host.java.in"]
    return {"format": "rt13-java-integers/1", "python": sys.version.split()[0], "compiler": compiler,
            "runtime": runtime, "source_sha256": sha256(source.encode()).hexdigest(),
            "input_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            "programs": len(programs), "vectors": len(cases)//len(programs),
            "profiles": profiles, "artifacts": artifacts, "controls": mutants}


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--java", default="java")
    arguments.add_argument("--output", required=True, type=Path)
    options = arguments.parse_args()
    options.output.write_text(json.dumps(verify(options.java), indent=2, sort_keys=True) + "\n", encoding="utf-8")
