"""Compare verifier-admitted LLVM floating-point flags against exact binary64 observations."""
import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from itertools import product
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
spec = spec_from_file_location("binary64", HERE.parent / "BINARY64-CONTRACTION-01" / "run.py")
numeric = module_from_spec(spec)
spec.loader.exec_module(numeric)

FUNCTIONS = (
    "split_expression", "permit_contract", "exact_fma", "signed_zero",
    "ignore_zero_sign", "inspect_nan", "assume_no_nan",
)


def function_body(text, name, *, assembly=False):
    pattern = (rf"(?m)^{name}:.*?^\s*\.size\s+{name}," if assembly
               else rf"(?m)^define[^\n]*@{name}\([^\n]*?\{{(.*?)^\}}")
    match = re.search(pattern, text, re.S)
    if match is None:
        raise ValueError(f"Cannot locate function {name}")
    return match[0] if assembly else match[1].strip()


def check_profile(directory, clang, assembler, optimizer, compiler, level, triples, split_fused, stdin):
    source = HERE / "operations.ll"
    bitcode = directory / "operations.bc"
    optimized = directory / "selected.ll"
    assembly = directory / "selected.s"
    objects = directory / "selected.o"
    executable = directory / "selected"
    numeric.invoke([assembler, str(source), "-o", str(bitcode)], directory)
    numeric.invoke([optimizer, "-passes=verify", "-disable-output", str(bitcode)], directory)
    numeric.invoke([optimizer, f"-passes=default<O{level}>", "-S", str(bitcode), "-o", str(optimized)],
                   directory)
    numeric.invoke([optimizer, "-passes=verify", "-disable-output", str(optimized)], directory)
    backend = [compiler, f"-O{level}", "-mattr=+fma", str(optimized)]
    numeric.invoke([*backend, "-filetype=asm", "-o", str(assembly)], directory)
    numeric.invoke([*backend, "-filetype=obj", "-o", str(objects)], directory)
    numeric.invoke([clang, "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", str(HERE / "host.c"),
                    str(objects), "-lm", "-o", str(executable)], directory)
    text = numeric.invoke([str(executable)], directory, stdin).splitlines()
    instructions = {}
    code = assembly.read_text()
    for name in FUNCTIONS:
        body = function_body(code, name, assembly=True)
        instructions[name] = sorted(set(re.findall(r"\b(?:v?mulsd|v?addsd|vfmadd[0-9]+sd|v?ucomisd)\b", body)))
    assert not any(insn.startswith("vfmadd") for insn in instructions["split_expression"])
    assert any(insn.startswith("vfmadd") for insn in instructions["exact_fma"])

    contracted_rows = 0
    signed_zero_changes = 0
    excluded_nan_rows = 0
    zero_witness = None
    contraction_witness = None
    contract_is_fused = any(insn.startswith("vfmadd") for insn in instructions["permit_contract"])
    for triple, (split, fused), row in zip(triples, split_fused, text, strict=True):
        a, _, _ = triple
        plain, contract, explicit, exact_zero, relax_zero, normal_class, restricted_class = row.split()
        current = tuple(map(numeric.canonical, (int(bits, 16) for bits in (
            plain, contract, explicit, exact_zero, relax_zero,
        ))))
        expected_zero = numeric.combine(a, 0)
        assert current[:4] == (split, fused if contract_is_fused else split, fused, expected_zero)
        if current[4] != expected_zero:
            assert a == numeric.SIGN and current[4] == numeric.SIGN
            signed_zero_changes += 1
            if zero_witness is None:
                zero_witness = {"input": numeric.fixed(a), "strict": numeric.fixed(current[3]),
                                "nsz": numeric.fixed(current[4])}
        if current[1] != split:
            contracted_rows += 1
            if contraction_witness is None:
                contraction_witness = {
                    "inputs": list(map(numeric.fixed, triple)),
                    "split": numeric.fixed(current[0]), "contract": numeric.fixed(current[1]),
                }
        expected_class = int(numeric.kind(a) == "nan")
        assert int(normal_class) == expected_class
        assert int(restricted_class) == (-1 if expected_class else 0)
        excluded_nan_rows += expected_class
    ir = optimized.read_text()
    if level == 3:
        assert "ret i32 0" in function_body(ir, "assume_no_nan")
        assert "ret double %a" in function_body(ir, "ignore_zero_sign")
        assert "fadd double" in function_body(ir, "signed_zero")
        assert contract_is_fused and contracted_rows > 0 and signed_zero_changes > 0
    return {
        "rows": len(text), "contract_is_fused": contract_is_fused, "contract_differences_from_split": contracted_rows,
        "nsz_differences_from_signed_zero": signed_zero_changes, "nnan_inputs_excluded": excluded_nan_rows,
        "exact_expression_disagreements": 0, "exact_fma_disagreements": 0, "instructions": instructions,
        "zero_witness": zero_witness, "contraction_witness": contraction_witness,
        "optimized_nsz_ir": function_body(ir, "ignore_zero_sign"),
        "optimized_nnan_ir": function_body(ir, "assume_no_nan"),
        "raw_rows_sha256": sha256(("\n".join(text) + "\n").encode()).hexdigest(),
    }


def run(directory, clang, assembler, optimizer, compiler):
    tools = {"clang": clang, "llvm-as": assembler, "opt": optimizer, "llc": compiler}
    versions = {}
    for name, command in tools.items():
        lines = numeric.invoke([command, "--version"], directory).strip().splitlines()
        version = next(line.strip() for line in lines if "version" in line)
        assert "19.1.7" in version, (name, version)
        versions[name] = version
    assert re.search(r"\bfma\b", Path("/proc/cpuinfo").read_text())
    triples = tuple(product(numeric.OPERANDS, repeat=3))
    reference = tuple(numeric.reference(*triple) for triple in triples)
    stdin = "".join(" ".join(map(numeric.fixed, triple)) + "\n" for triple in triples)
    result = {}
    for level in (0, 3):
        scratch = directory / f"O{level}"
        scratch.mkdir()
        result[f"O{level}"] = check_profile(scratch, clang, assembler, optimizer, compiler, level,
                                            triples, reference, stdin)
    sources = (HERE / "operations.ll", HERE / "host.c", HERE.parent / "BINARY64-CONTRACTION-01/run.py")
    return {
        "format": "rt13-llvm-fp-flags/1", "python": sys.version.split()[0], "versions": versions,
        "rows_per_profile": len(triples),
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
        "input_sha256": sha256(stdin.encode()).hexdigest(), "profiles": result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--asm", default="llvm-as")
    parser.add_argument("--opt", default="opt")
    parser.add_argument("--llc", default="llc")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-llvm-fp-flags-") as root:
        result = run(Path(root), args.clang, args.asm, args.opt, args.llc)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
