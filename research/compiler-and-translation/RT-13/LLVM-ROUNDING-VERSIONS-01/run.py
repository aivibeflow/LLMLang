"""Compare LLVM driver versions and the optimization boundary for dynamic signed zero."""
import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "LLVM-DYNAMIC-ROUNDING-01"
TARGET = "x86_64-unknown-linux-gnu"
BASELINE_DIGESTS = {
    "run.py": "4925a4df4c5577ee167bed8df9a347f03a33c8196ff9a6d0b6aabeb664c6bb43",
    "host.c": "4d7d3ca0ff343c7652efdfb04983b78be33ab6257cbadbc2760b015057450cac",
    "evidence.json": "d39e5fd899ed680929b8555816d706e1a20ea03bd6a4853df7c49e03c7f51413",
}
BUILDS = (
    ("19", "Debian clang version 19.1.7 (3+b1)"),
    ("22", "clang version 22.1.4 (https://github.com/llvm/llvm-project 35990504507d79e0b9deb809c8ee5e1b34ceef20)"),
    ("23", "clang version 23.1.1 (https://github.com/llvm/llvm-project 6dfe1677ab8dffbc6ec13d53a1e0215d75147689)"),
)
INLINE = '''
define double @forced_inline() #0 {
  %value = call double @parameterized_fadd(double 1.000000e+00, double -1.000000e+00) #1
  ret double %value
}
define double @retained_call() #0 {
  %value = call double @parameterized_fadd(double 1.000000e+00, double -1.000000e+00) #2
  ret double %value
}

attributes #0 = { strictfp }
attributes #1 = { alwaysinline strictfp }
attributes #2 = { noinline strictfp }
'''
WRAPPERS = ("forced_inline", "retained_call")


def load_baseline(directory):
    spec = spec_from_file_location("rounding", directory / "run.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compile_ir(compiler, command, directory, source, level):
    options = [compiler, "-target", TARGET, "-x", "ir", f"-O{level}", source]
    command([*options, "-c", "-o", "operations.o"], directory)
    command([*options, "-S", "-emit-llvm", "-o", "selected.ll"], directory)
    return (directory / "selected.ll").read_text()


def compile_host(compiler, command, directory, source, output):
    command([compiler, "-target", TARGET, "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2",
             "-I", str(directory), "-c", str(source), "-o", output], directory)


def invoke(profile, linker, command, host):
    command([linker, "-target", TARGET, host, "operations.o", "-lm", "-o", "probe"], profile)
    return command(["./probe"], profile).splitlines()


def check_inline(baseline, directory, compiler, linker, source, level):
    (directory / "with-wrappers.ll").write_text(source, encoding="utf-8")
    optimized = compile_ir(compiler, baseline.command, directory, "with-wrappers.ll", level)
    lines = invoke(directory, linker, baseline.command, "inline_host.o")
    results = {}
    for (mode, wrapper), row in zip(product(baseline.MODES, WRAPPERS), lines, strict=True):
        label, bits, no_flags = row.split()
        assert label == wrapper and no_flags == "1"
        negative = mode == "downward" and wrapper == "retained_call"
        assert bits == baseline.bit_hex((1 << 63) if negative else 0), (mode, wrapper, bits)
        results[f"{mode}/{wrapper}"] = bits
    bodies = {wrapper: baseline.body(optimized, wrapper) for wrapper in WRAPPERS}
    assert "ret double 0.000000e+00" in bodies["forced_inline"]
    assert "call double @parameterized_fadd" in bodies["retained_call"]
    assert ("constrained.fadd" in bodies["forced_inline"]) == (level == 0)
    return {"bits": results, "optimized_bodies": bodies}


def run(directory, baseline_path, compilers):
    received = {name: sha256((baseline_path / name).read_bytes()).hexdigest() for name in BASELINE_DIGESTS}
    if received != BASELINE_DIGESTS:
        raise ValueError("Use the exact archived dynamic rounding fixture")
    expected = json.loads((baseline_path / "evidence.json").read_text(encoding="utf-8"))
    baseline = load_baseline(baseline_path)
    source, header = baseline.generate()
    definitions, attrs = source.rsplit("attributes #0 = { strictfp }", 1)
    assert not attrs.strip()
    rows = {}
    for (label, expected_version), compiler in zip(BUILDS, compilers, strict=True):
        version = baseline.command([compiler, "--version"], directory).splitlines()[0]
        assert version == expected_version, (label, version)
        for level in (0, 3):
            profile = directory / f"{label}-O{level}"
            profile.mkdir()
            (profile / "operations.ll").write_text(source, encoding="utf-8")
            (profile / "operations.h").write_text(header, encoding="utf-8")
            compile_host(compilers[0], baseline.command, profile, baseline_path / "host.c", "baseline_host.o")
            compile_host(compilers[0], baseline.command, profile, HERE / "inline_host.c", "inline_host.o")
            optimized = compile_ir(compiler, baseline.command, profile, "operations.ll", level)
            cancellation = baseline.body(optimized, "strict_exact_cancellation")
            baseline_rows = invoke(profile, compilers[0], baseline.command, "baseline_host.o")
            evaluated = baseline.classify(baseline_rows, cancellation, {})
            assert evaluated["counts"] == expected["profiles"][f"O{level}"]["counts"]
            rows[f"{label}/O{level}"] = {
                "driver": version, "counts": evaluated["counts"], "cancellation_ir": cancellation,
                "full_observation_sha256": sha256(("\n".join(baseline_rows) + "\n").encode()).hexdigest(),
                "inlining": check_inline(baseline, profile, compiler, compilers[0], definitions + INLINE, level),
            }
    return {
        "format": "rt13-llvm-rounding-versions/1", "python": sys.version.split()[0],
        "target": TARGET, "rows_per_route_and_profile": len(baseline.CASES) * len(baseline.MODES) * 2,
        "baseline_inputs_sha256": received,
        "inline_host_sha256": sha256((HERE / "inline_host.c").read_bytes()).hexdigest(),
        "generated_base_ir_sha256": sha256(source.encode()).hexdigest(),
        "generated_inline_ir_sha256": sha256((definitions + INLINE).encode()).hexdigest(),
        "profiles": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang19", default="clang-19")
    parser.add_argument("--clang22", required=True)
    parser.add_argument("--clang23", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline", default=BASELINE, type=Path, help="path to the exact archived dynamic-rounding fixture")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-llvm-rounding-versions-") as scratch:
        data = run(Path(scratch), args.baseline.resolve(), (args.clang19, args.clang22, args.clang23))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
