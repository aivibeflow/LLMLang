"""Compare ordinary and constrained LLVM IR against dynamic binary64 observations."""
import argparse
from hashlib import sha256
from itertools import product
import json
import re
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SIG = 1 << 63
INF = 0x7FF0000000000000
QNAN = 0x7FF8000000000000
ONE = 0x3FF0000000000000
TWO = 0x4000000000000000
HALF = 0x3FE0000000000000
HALF_ULP_AT_ONE = 0x3CA0000000000000
LARGEST = INF - 1
MODES = ("nearest", "upward", "downward", "toward-zero")
ROUTES = ("plain", "strict", "parameterized")
# Each expected tuple follows the four modes. Flags describe the operation itself.
CASES = {
    "halfway_positive": ("fadd", ONE, HALF_ULP_AT_ONE, (ONE, ONE + 1, ONE, ONE), 16),
    "halfway_negative": ("fadd", SIG | ONE, SIG | HALF_ULP_AT_ONE,
                         (SIG | ONE, SIG | ONE, SIG | (ONE + 1), SIG | ONE), 16),
    "overflow_positive": ("fmul", LARGEST, TWO, (INF, INF, LARGEST, LARGEST), 4 | 16),
    "overflow_negative": ("fmul", SIG | LARGEST, TWO,
                          (SIG | INF, SIG | LARGEST, SIG | INF, SIG | LARGEST), 4 | 16),
    "subnormal_positive": ("fmul", 1, HALF, (0, 1, 0, 0), 8 | 16),
    "subnormal_negative": ("fmul", SIG | 1, HALF, (SIG, SIG, SIG | 1, SIG), 8 | 16),
    "divide_by_zero": ("fdiv", ONE, 0, (INF,) * 4, 2),
    "invalid_division": ("fdiv", 0, 0, (QNAN,) * 4, 1),
    "exact_addition": ("fadd", ONE, ONE, (TWO,) * 4, 0),
    "exact_cancellation": ("fadd", ONE, SIG | ONE, (0, 0, SIG, 0), 0),
}


def bit_hex(bits):
    return f"{bits:016x}"


def canonical(bits):
    return QNAN if (bits & ~SIG) > INF else bits


def command(args, directory):
    return subprocess.run(args, cwd=directory, check=True, text=True, capture_output=True, timeout=45).stdout


def generate():
    declarations = [
        f"declare double @llvm.experimental.constrained.{operator}.f64(double, double, metadata, metadata)"
        for operator in ("fadd", "fmul", "fdiv")
    ]
    ir = ['target triple = "x86_64-unknown-linux-gnu"', *declarations, ""]
    header = []
    for operator in ("fadd", "fmul", "fdiv"):
        ir.extend((
            f"define double @parameterized_{operator}(double %a, double %b) #0 {{",
            f"  %value = call double @llvm.experimental.constrained.{operator}.f64(double %a,"
            ' double %b, metadata !"round.dynamic", metadata !"fpexcept.strict") #0',
            "  ret double %value", "}", "",
        ))
        header.append(f"double parameterized_{operator}(double, double);")
    for name, (operator, left, right, _, _) in CASES.items():
        a, b = f"0x{left:016X}", f"0x{right:016X}"
        ir.extend((
            f"define double @plain_{name}() {{",
            f"  %value = {operator} double {a}, {b}", "  ret double %value", "}", "",
            f"define double @strict_{name}() #0 {{",
            f"  %value = call double @llvm.experimental.constrained.{operator}.f64(double {a},"
            f' double {b}, metadata !"round.dynamic", metadata !"fpexcept.strict") #0',
            "  ret double %value", "}", "",
        ))
        header.extend(f"double {route}_{name}(void);" for route in ("plain", "strict"))
    ir += ["attributes #0 = { strictfp }", ""]
    header += ["", "static const struct operation_pair cases[] = {"]
    header.extend(
        f'    {{"{name}", plain_{name}, strict_{name}, parameterized_{op},'
        f' UINT64_C(0x{left:016x}), UINT64_C(0x{right:016x})}},'
        for name, (op, left, right, _, _) in CASES.items()
    )
    header += ["};", ""]
    return "\n".join(ir), "\n".join(header)


def body(ir, function):
    match = re.search(rf"(?m)^define[^\n]*@{function}\([^\n]*?\{{(.*?)^\}}", ir, re.S)
    if not match:
        raise ValueError(function)
    return match[1].strip()


def profile(directory, tools, source, header, level):
    directory.mkdir()
    original = directory / "operations.ll"
    original.write_text(source, encoding="utf-8")
    (directory / "operations.h").write_text(header, encoding="utf-8")
    command([tools["as"], str(original), "-o", "before.bc"], directory)
    command([tools["opt"], "-passes=verify", "-disable-output", "before.bc"], directory)
    command([tools["opt"], f"-passes=default<O{level}>", "-S", "before.bc", "-o", "after.ll"], directory)
    command([tools["opt"], "-passes=verify", "-disable-output", "after.ll"], directory)
    command([tools["llc"], f"-O{level}", "-filetype=obj", "after.ll", "-o", "operations.o"], directory)
    command([tools["cc"], "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", "-I", str(directory),
             str(HERE / "host.c"), "operations.o", "-lm", "-o", "probe"], directory)
    output = command(["./probe"], directory)
    ir = (directory / "after.ll").read_text()
    assert "metadata !\"round.dynamic\", metadata !\"fpexcept.strict\"" in ir
    control = body(ir, "strict_exact_cancellation")
    assert "llvm.experimental.constrained.fadd" in body(ir, "parameterized_fadd")
    fold_controls = {}
    if level == 3:
        for pass_name in ("early-cse", "instcombine"):
            command([tools["opt"], f"-passes={pass_name}", "-S", "before.bc", "-o", "isolated.ll"], directory)
            fold_controls[pass_name] = body((directory / "isolated.ll").read_text(), "strict_exact_cancellation")
            assert "ret double 0.000000e+00" in fold_controls[pass_name]
        assert "constrained.fadd" in fold_controls["early-cse"]
        assert "constrained.fadd" not in fold_controls["instcombine"]
        assert "ret double 1.000000e+00" in body(ir, "plain_halfway_positive")
        assert "ret double 0.000000e+00" in control and "constrained" not in control
    else:
        assert "llvm.experimental.constrained.fadd" in control
    return output.splitlines(), control, fold_controls


def classify(lines, strict_cancellation_ir, isolated_fold_controls):
    ledger = {}
    counts = {route: dict.fromkeys(("value_mismatches", "flag_mismatches", "seed_dropped"), 0)
              for route in ROUTES}
    work = product(CASES, enumerate(MODES), (0, 1), ROUTES)
    for (name, (mode_index, mode), seed, route), entry in zip(work, lines, strict=True):
        label, observed_route, observed_seed, raw, flags = entry.split()
        assert (name, route, seed) == (label, observed_route, int(observed_seed))
        expected_bits = CASES[name][3][mode_index]
        expected_flags = CASES[name][4] | seed
        value_diff = canonical(int(raw, 16)) != expected_bits
        flags_diff = int(flags, 16) != expected_flags
        counts[route]["value_mismatches"] += value_diff
        counts[route]["flag_mismatches"] += flags_diff
        counts[route]["seed_dropped"] += seed == 1 and int(flags, 16) & 1 == 0
        if route == "parameterized":
            assert not value_diff and not flags_diff, (name, mode, seed, entry)
        if route == "strict" and (value_diff or flags_diff):
            assert name == "exact_cancellation" and mode == "downward" and not flags_diff and raw == "0000000000000000"
        ledger[f"{name}/{mode}/{seed}/{route}"] = {
            "raw_bits": raw, "flags": int(flags, 16), "reference_bits": bit_hex(expected_bits),
            "reference_flags": expected_flags,
        }
    return {"counts": counts, "strict_cancellation_optimized_ir": strict_cancellation_ir,
            "isolated_fold_controls": isolated_fold_controls, "observations": ledger}


def run(directory, tools):
    versions = {}
    for name, executable in tools.items():
        lines = command([executable, "--version"], directory).splitlines()
        version = next(line.strip() for line in lines if "version" in line)
        assert "19.1.7" in version, (name, version)
        versions[name] = version
    ir, header = generate()
    profiles = {
        f"O{level}": classify(*profile(directory / f"O{level}", tools, ir, header, level))
        for level in (0, 3)
    }
    assert profiles["O3"]["counts"]["plain"]["value_mismatches"] > 0
    assert profiles["O3"]["counts"]["plain"]["flag_mismatches"] > 0
    assert profiles["O3"]["counts"]["strict"]["value_mismatches"] == 2
    assert all(not count["seed_dropped"] for row in profiles.values() for count in row["counts"].values())
    return {
        "format": "rt13-llvm-dynamic-rounding/1", "python": sys.version.split()[0], "versions": versions,
        "rows_per_route_and_profile": len(CASES) * len(MODES) * 2, "profiles": profiles,
        "source_sha256": {"generated_ir": sha256(ir.encode()).hexdigest(),
                          "generated_header": sha256(header.encode()).hexdigest(),
                          "host_c": sha256((HERE / "host.c").read_bytes()).hexdigest()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--opt", default="opt")
    args = parser.parse_args()
    tools = {"cc": "clang", "as": "llvm-as", "opt": args.opt, "llc": "llc"}
    with TemporaryDirectory(prefix="llmlang-llvm-dynamic-rounding-") as scratch:
        result = run(Path(scratch), tools)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
