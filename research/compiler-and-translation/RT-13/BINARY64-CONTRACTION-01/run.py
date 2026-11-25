"""Compare binary64 split and fused operations against exact rational rounding."""
import argparse
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SIGN = 1 << 63
INFINITY = 0x7FF0000000000000
NAN = 0x7FF8000000000000
MANTISSA = (1 << 52) - 1
JAVAC = ("java", "--module", "jdk.compiler/com.sun.tools.javac.Main")
OPERANDS = (
    0, SIGN, 1, SIGN | 1, 0x000FFFFFFFFFFFFF, 0x0010000000000000,
    0x3FE0000000000000, 0x3FEFFFFFFC000000, 0x3FF0000000000000,
    0x3FF0000002000000, 0xBFF0000000000000, 0x4000000000000000,
    0x7FEFFFFFFFFFFFFF, 0xFFEFFFFFFFFFFFFF, INFINITY, SIGN | INFINITY,
    NAN | 0x42, SIGN | NAN | 0x7, INFINITY | 0x11,
)
WITNESSES = {
    "one-round-versus-two": (0x3FF0000002000000, 0x3FEFFFFFFC000000, 0xBFF0000000000000),
    "overflow-before-cancellation": (0x7FEFFFFFFFFFFFFF, 0x4000000000000000, 0xFFEFFFFFFFFFFFFF),
    "underflow-before-addition": (1, 0x3FE0000000000000, 1),
    "signed-zero": (SIGN, 0x3FF0000000000000, SIGN),
}


def power(exponent):
    return Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)


def kind(bits):
    magnitude = bits & ~SIGN
    if magnitude == INFINITY:
        return "inf"
    if magnitude > INFINITY:
        return "nan"
    return "finite"


def value(bits):
    exponent = ((bits & ~SIGN) >> 52) - 1023
    significand = bits & MANTISSA
    if exponent == -1023:
        exponent = -1022
    else:
        significand += 1 << 52
    return (-1 if bits & SIGN else 1) * significand * power(exponent - 52)


def rounded(number, zero_sign=0):
    if not number:
        return zero_sign
    sign = SIGN if number < 0 else 0
    magnitude = abs(number)
    exponent = magnitude.numerator.bit_length() - magnitude.denominator.bit_length()
    if magnitude < power(exponent):
        exponent -= 1
    quantum = power(max(exponent - 52, -1074))
    scaled = magnitude / quantum
    significand, remainder = divmod(scaled.numerator, scaled.denominator)
    double = 2 * remainder
    significand += double > scaled.denominator or (double == scaled.denominator and significand % 2 == 1)
    if exponent < -1022:
        return sign | significand
    if significand == 1 << 53:
        significand >>= 1
        exponent += 1
    if exponent >= 1024:
        return sign | INFINITY
    return sign | ((exponent + 1023) << 52) | (significand & MANTISSA)


def product_kind(a, b):
    if "nan" in (kind(a), kind(b)):
        return "nan"
    if "inf" in (kind(a), kind(b)):
        return "nan" if ((a & ~SIGN) == 0 or (b & ~SIGN) == 0) else "inf"
    return "finite"


def combine(a, b):
    if "nan" in (kind(a), kind(b)):
        return NAN
    if kind(a) == "inf":
        return NAN if b == (a ^ SIGN) else a
    if kind(b) == "inf":
        return b
    return rounded(value(a) + value(b), SIGN if a == b == SIGN else 0)


def reference(a, b, c):
    state = product_kind(a, b)
    product_sign = (a ^ b) & SIGN
    if state == "nan":
        return NAN, NAN
    if state == "inf":
        result = combine(INFINITY | product_sign, c)
        return result, result
    exact_product = value(a) * value(b)
    split = combine(rounded(exact_product, product_sign), c)
    if kind(c) != "finite":
        return split, c if kind(c) == "inf" else NAN
    zero_sign = SIGN if exact_product == 0 and product_sign and c == SIGN else 0
    return split, rounded(exact_product + value(c), zero_sign)


def canonical(bits):
    return NAN if kind(bits) == "nan" else bits


def fixed(bits):
    return f"{bits:016x}"


def invoke(command, cwd, data=None):
    return subprocess.run(command, cwd=cwd, input=data, capture_output=True,
                          text=True, check=True, timeout=60).stdout


def build(directory):
    profiles = {}
    for name, options in (
        ("C-O0-split", ("-O0", "-ffp-contract=off", "-mfma")),
        ("C-O3-split", ("-O3", "-ffp-contract=off", "-mfma")),
        ("C-O3-contract", ("-O3", "-ffp-contract=fast", "-mfma")),
    ):
        executable = directory / name
        assembly = directory / f"{name}.s"
        cflags = ["gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", *options, str(HERE / "probe.c")]
        invoke([*cflags, "-o", str(executable), "-lm"], directory)
        invoke([*cflags, "-S", "-o", str(assembly)], directory)
        body = assembly.read_text().split("multiply_add:", 1)[1].split(".size", 1)[0]
        instructions = sorted(set(re.findall(r"\b(?:v?mulsd|v?addsd|vfmadd[0-9]+sd)\b", body)))
        if name == "C-O3-contract":
            assert any(insn.startswith("vfmadd") for insn in instructions)
        else:
            assert {"vmulsd", "vaddsd"} <= set(instructions) and not any(
                insn.startswith("vfmadd") for insn in instructions)
        profiles[name] = [str(executable)], list(options), instructions

    rust = directory / "rust"
    invoke(["rustc", "--edition=2021", "-D", "warnings", "-C", "opt-level=3", str(HERE / "probe.rs"),
            "-o", str(rust)], directory)
    profiles["Rust-O3"] = [str(rust)], ["-C", "opt-level=3"], None
    invoke([*JAVAC, "-d", str(directory), str(HERE / "Probe.java")], directory)
    profiles["Java-VM"] = ["java", "-cp", str(directory), "Probe"], [], None
    profiles["Java-interpreted"] = ["java", "-Xint", "-cp", str(directory), "Probe"], ["-Xint"], None
    return profiles


def compare(directory):
    gcc = invoke(["gcc", "-dumpfullversion"], directory).strip()
    rust = invoke(["rustc", "--version"], directory).strip()
    java = invoke([*JAVAC, "-version"], directory).strip()
    runtime = subprocess.run(["java", "-version"], cwd=directory, text=True,
                             capture_output=True, check=True, timeout=30).stderr.splitlines()
    assert gcc == "14.2.0" and rust.split()[:2] == ["rustc", "1.85.1"] and java == "javac 21.0.13"
    assert '"21.0.13"' in runtime[0]
    assert re.search(r"\bfma\b", Path("/proc/cpuinfo").read_text())
    triples = tuple(product(OPERANDS, repeat=3))
    expected = tuple(reference(*triple) for triple in triples)
    assert [reference(*value) for value in WITNESSES.values()] == [
        (0, 0xBC90000000000000), (INFINITY, 0x7FEFFFFFFFFFFFFF), (1, 2), (SIGN, SIGN),
    ]
    inputs = "".join(" ".join(map(fixed, triple)) + "\n" for triple in triples)
    rows, all_raw = {}, {}
    for name, (launch, options, instructions) in build(directory).items():
        raw = invoke(launch, directory, inputs)
        outputs = [tuple(int(field, 16) for field in line.split()) for line in raw.splitlines()]
        first_nans, second_nans = set(), set()
        split_bad = 0
        for triple, (separate, fused), (plain, explicit) in zip(triples, expected, outputs, strict=True):
            assert canonical(explicit) == fused, (name, triple, explicit, fused)
            plain_policy = fused if name == "C-O3-contract" else separate
            assert canonical(plain) == plain_policy, (name, triple, plain, plain_policy)
            split_bad += canonical(plain) != separate
            if kind(plain) == "nan":
                first_nans.add(fixed(plain))
            if kind(explicit) == "nan":
                second_nans.add(fixed(explicit))
        rows[name] = {
            "options": options, "expression_instructions": instructions, "rows": len(outputs),
            "plain_mismatches_to_separate_rounding": split_bad, "explicit_mismatches_to_fused_rounding": 0,
            "plain_nan_bits": sorted(first_nans), "fused_nan_bits": sorted(second_nans),
            "raw_output_sha256": sha256(raw.encode()).hexdigest(),
        }
        all_raw[name] = outputs
    nan_differences = [
        position for position, (_, fused) in enumerate(expected)
        if fused == NAN and len({outputs[position][1] for outputs in all_raw.values()}) > 1
    ]
    assert nan_differences
    example = nan_differences[0]
    nan_witness = {
        "input_bits": list(map(fixed, triples[example])),
        "fused_output_bits": {name: fixed(outputs[example][1]) for name, outputs in all_raw.items()},
    }
    witnesses = {}
    for name, inputs_at_edge in WITNESSES.items():
        position = triples.index(inputs_at_edge)
        witnesses[name] = {
            "inputs": list(map(fixed, inputs_at_edge)),
            "expected": list(map(fixed, expected[position])),
            "profile_bits": {profile: list(map(fixed, outputs[position])) for profile, outputs in all_raw.items()},
        }
    split_fused = sum(a != b for a, b in expected)
    assert rows["C-O3-contract"]["plain_mismatches_to_separate_rounding"] == split_fused > 0
    return {"format": "rt13-binary64-contraction/1", "python": sys.version.split()[0],
            "gcc": gcc, "rustc": rust, "java_compiler": java, "java_runtime": runtime,
            "operand_bits": list(map(fixed, OPERANDS)),
            "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ("probe.c", "probe.rs", "Probe.java")},
            "queries": len(triples), "distinct_split_and_fused_rows": split_fused,
            "cross_profile_fused_raw_nan_differences": len(nan_differences),
            "fused_nan_rows": sum(fused == NAN for _, fused in expected),
            "witnesses": witnesses, "raw_nan_witness": nan_witness,
            "results": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-binary64-") as scratch:
        data = compare(Path(scratch))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
