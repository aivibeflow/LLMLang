"""Check emitted CPython code against the shared checked integer corpus."""

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

from lower_python import lower


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "GENERATED-RUST-INTEGERS-01"))
from run import FIXTURE, change, program_source, reference, vectors
from integer_fixture import OPERATIONS, compile_source
from llvm_integer_probe import _STATUS


PROFILES = {"normal": (), "optimized": ("-O",)}


def observe(python, directory, source, request, profile):
    path = directory / "generated.py"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run([python, "-I", *PROFILES[profile], str(HERE / "host.py"), path],
                            input=request, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError((profile, result.stderr.decode(), result.stdout[:100]))
    metadata = json.loads(result.stderr)
    if metadata["optimization"] != len(PROFILES[profile]):
        raise ValueError((profile, metadata))
    decoded = []
    for status, slot, count, first, second in struct.iter_unpack("<5I", result.stdout):
        if count not in (1, 2):
            raise ValueError(f"Unexpected event count: {count}")
        decoded.append((_STATUS[status], slot, (first, second)[:count]))
    metadata["response_sha256"] = sha256(result.stdout).hexdigest()
    return decoded, metadata


def controls(python, directory):
    wrong_floor = (("value = signed_divmod(signed(a), signed(b))[0]",
                    "value = signed(a) // signed(b)"),)
    wrong_remainder = (("value = signed_divmod(signed(a), signed(b))[1]",
                        "value = signed(a) % signed(b)"),)
    assertion_guard = (("        if b >= 32:\n            return 3",
                        "        try:\n            assert b < 32\n"
                        "        except AssertionError:\n            return 3"),)
    controls = (
        ("floor_instead_of_truncation", "checked_sdiv", (0xfffffff9, 2, 1), wrong_floor,
         {"slot", "events"}, "normal"),
        ("divisor_sign_instead_of_dividend", "checked_srem", (0xfffffff9, 2, 1), wrong_remainder,
         {"slot", "events"}, "normal"),
        ("assert_guard_in_normal_profile", "checked_shl", (7, 32, 1), assertion_guard,
         set(), "normal"),
        ("assert_guard_in_optimized_profile", "checked_shl", (7, 32, 1), assertion_guard,
         {"status", "slot", "events"}, "optimized"),
        ("reverse_effects", "checked_sadd", (7, 2, 1),
         (("    emit(a)\n", ""), ("    emit(value)", "    emit(value)\n    emit(a)")),
         {"events"}, "normal"),
    )
    result = {}
    for name, operation, vector, mutations, fields, profile in controls:
        program = compile_source(program_source(operation))
        source = lower((program,))
        for anchor, replacement in mutations:
            source = change(source, anchor, replacement)
        (actual,), _ = observe(python, directory, source, struct.pack("<4I", 0, *vector), profile)
        expected = reference(program, vector)
        changed = {field for field, old, new in
                   zip(("status", "slot", "events"), expected, actual, strict=True) if old != new}
        if fields != changed:
            raise AssertionError((name, fields, changed))
        result[name] = {"profile": profile, "input": vector, "expected": expected,
                        "actual": actual, "changed": sorted(changed)}
    return result


def verify(python):
    runtime = subprocess.check_output(
        [python, "-I", "-c",
         "import json, platform; print(json.dumps([platform.python_implementation(),"
         " platform.python_version(), platform.system(), platform.machine()]))"],
        text=True, timeout=10,
    )
    programs = tuple(compile_source(program_source(op, left, right))
                     for op, (left, right) in product(OPERATIONS, product("ab", repeat=2)))
    cases = tuple(product(range(len(programs)), vectors()))
    reference_results = tuple(reference(programs[index], vector) for index, vector in cases)
    request = b"".join(struct.pack("<4I", index, *vector) for index, vector in cases)
    source = lower(programs)
    profiles = {}
    with TemporaryDirectory(prefix="llmlang-python-integer-") as scratch:
        directory = Path(scratch)
        for profile in PROFILES:
            observed, metadata = observe(python, directory, source, request, profile)
            if metadata["entries"] != len(programs):
                raise AssertionError((profile, "entry count mismatch"))
            for case, wanted, actual in zip(cases, reference_results, observed, strict=True):
                if actual != wanted:
                    raise AssertionError((profile, case, wanted, actual))
            profiles[profile] = {**metadata, "observations": len(observed),
                                 "statuses": dict(sorted(Counter(row[0] for row in observed).items()))}
        negative = controls(python, directory)
    return {
        "runtime": json.loads(runtime),
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in
                          (HERE / "host.py", HERE / "lower_python.py", HERE / "run.py",
                           FIXTURE / "integer_fixture.py", FIXTURE / "llvm_integer_probe.py",
                           HERE.parent / "GENERATED-RUST-INTEGERS-01" / "run.py")},
        "generated_source_sha256": sha256(source.encode("utf-8")).hexdigest(),
        "request_sha256": sha256(request).hexdigest(),
        "profiles": profiles,
        "controls": negative,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    print(json.dumps(verify(args.python), indent=2))


if __name__ == "__main__":
    main()
