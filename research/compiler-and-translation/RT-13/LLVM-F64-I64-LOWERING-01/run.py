"""Compare exact LLVM binary64-to-I64 lowerings and refinement tool coverage."""

import argparse
import ctypes
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
LOWERINGS = HERE / "lowerings.ll"
NATIVE = (HERE.parents[2] / "semantic-representation" / "RT-05"
          / "F64-I64-CONVERSION-01" / "evidence.json")
MATCHING = ("bits_branch", "ordered_branch", "ordered_select")
SAFE = (*MATCHING, "guarded_saturate", "saturate")
TARGETS = (*SAFE[1:], "inclusive_upper", "unmasked_value")
CATEGORIES = {"range": 1, "nonfinite": 2}
UPPER = "43e0000000000000"
LOWER = "c3e0000000000000"
POSITIVE_OVERFLOW = "43e0000000000001"
NAN = "7ff8000000000000"


def execute(*args, data=None, check=True):
    return subprocess.run(list(map(str, args)), input=data, check=check, text=True,
                          capture_output=True, timeout=150)


def signed(word):
    bits = int(word, 16)
    return bits - (1 << 64) if bits >= (1 << 63) else bits


def expected_result(row, route):
    if route == "saturate":
        return (0, int(row["rust_saturate"][1:]))
    observed = row["checked_trunc"]
    return (0, int(observed[1:])) if observed.startswith("v") else (CATEGORIES[observed], 0)


def native_wrappers():
    for name in SAFE:
        yield f"""
define i64 @probe_{name}(i64 %word, i32 %which) {{
  %x = bitcast i64 %word to double
  %r = call {{ i32, i64 }} @{name}(double %x)
  %tag = extractvalue {{ i32, i64 }} %r, 0
  %value = extractvalue {{ i32, i64 }} %r, 1
  %tag64 = zext i32 %tag to i64
  %tag_requested = icmp eq i32 %which, 0
  %observed = select i1 %tag_requested, i64 %tag64, i64 %value
  ret i64 %observed
}}
"""


def observe_native(args, directory, ir, rows):
    inputs = directory / "native.ll"
    inputs.write_text(ir + "".join(native_wrappers()), encoding="utf-8")
    profiles = {}
    for level in (0, 3):
        path = directory / f"lowerings-O{level}.so"
        execute(args.clang, "-x", "ir", "-shared", "-fPIC", f"-O{level}", inputs, "-o", path)
        library = ctypes.CDLL(str(path))
        results = {}
        for name in SAFE:
            probe = getattr(library, f"probe_{name}")
            probe.argtypes = (ctypes.c_uint64, ctypes.c_int32)
            probe.restype = ctypes.c_int64
            observed = [[probe(int(row["input"], 16), lane) for lane in (0, 1)] for row in rows]
            for row, result in zip(rows, observed, strict=True):
                assert tuple(result) == expected_result(row, name), (name, row, result)
            results[name] = [{
                "input": row["input"], "tag": result[0], "value": str(result[1]),
            } for row, result in zip(rows, observed, strict=True)]
        profiles[f"O{level}"] = results
    assert profiles["O0"] == profiles["O3"]
    return profiles["O0"]


def vellvm_module(ir, route, observations):
    tests = [ir]
    for lane, width in enumerate((32, 64)):
        name = f"probe_{lane}"
        tests.append(f"""
define i{width} @{name}(i64 %word) {{
  %x = bitcast i64 %word to double
  %r = call {{ i32, i64 }} @{route}(double %x)
  %output = extractvalue {{ i32, i64 }} %r, {lane}
  ret i{width} %output
}}
""")
        for source, output in observations:
            expected = output[lane]
            tests.append(f"; ASSERT EQ: i{width} {expected} = call i{width} @{name}(i64 {signed(source)})\n")
    return "".join(tests)


def vellvm_result(command, directory, module):
    run = execute(*command, "-op", directory, "-test-file", module, check=False)
    match = re.search(r"^Passed: (\d+)/(\d+)\s+Failed: (\d+)/(\d+)$", run.stdout, re.MULTILINE)
    if match is None:
        raise ValueError((command, run.returncode, run.stdout, run.stderr))
    passed, total, failed, count = map(int, match.groups())
    assert passed + failed == total == count
    unsupported = run.stdout.count("ERROR: Uninterpreted Call:")
    return {"passed": passed, "failed": failed, "exit": run.returncode, "uninterpreted_calls": unsupported}


def observe_vellvm(args, directory, ir, rows):
    controls = {
        "inclusive_upper": [(UPPER, (0, "poison")), (LOWER, (0, -(1 << 63)))],
        "unmasked_value": [(POSITIVE_OVERFLOW, (1, "poison")), (NAN, (2, "poison"))],
        "guarded_saturate": [(LOWER, (0, -(1 << 63)))],
        "saturate": [(UPPER, (0, (1 << 63) - 1))],
    }
    all_observations = {route: [(row["input"], expected_result(row, route)) for row in rows] for route in MATCHING} | controls
    observations = {}
    for route, cases in all_observations.items():
        module = directory / f"vellvm-{route}.ll"
        module.write_text(vellvm_module(ir, route, cases), encoding="utf-8")
        execute(args.assembler, module, "-o", directory / "vellvm-input.bc")
        native = vellvm_result([args.vellvm], directory, module)
        byte = vellvm_result([args.ocamlrun, args.bytecode], directory, module)
        assert native == byte, (route, native, byte)
        failed = 0
        if route in ("saturate", "guarded_saturate"):
            # Both projection calls evaluate the unsupported intrinsic.
            failed = 2
        assert native == {"passed": 2 * len(cases) - failed, "failed": failed,
                          "exit": int(bool(failed)), "uninterpreted_calls": failed}, (route, native)
        observations[route] = {"inputs": len(cases), "per_extraction": native,
                               "assertion_module_sha256": sha256(module.read_bytes()).hexdigest()}
        if route in controls:
            observations[route]["controls"] = [{"input": word, "tag": tag, "value": str(value)}
                                               for word, (tag, value) in cases]
    return observations


def verify_alive(args, module_args):
    run = execute(args.alive, "--disable-poison-input", "--disable-undef-input",
                  *module_args, check=False)
    assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)
    if "Transformation seems to be correct!" in run.stdout:
        return {"verdict": "refines"}
    if "Unknown libcall: @llvm.fptosi.sat.i64.f64" in run.stdout or "Unknown libcall: @llvm.fptosi.sat.i64.f64" in run.stderr:
        return {"verdict": "unsupported", "reason": "unknown saturating conversion intrinsic"}
    if "Target is more poisonous than source" in run.stdout:
        example = re.search(r"^double %x = #x([0-9a-f]{16})", run.stdout, re.MULTILINE)
        if not example:
            raise ValueError(run.stdout)
        return {"verdict": "refuted", "reason": "target more poisonous", "input": example[1]}
    raise ValueError((source_name, target_name, run.returncode, run.stdout, run.stderr))


def extract(args, module, name, destination):
    extracted = execute(args.extractor, f"--func={name}", "-S", "-o", "-",
                        data=module.read_text(encoding="utf-8")).stdout
    before, identifier = "@" + name + "(", "@comparison_subject("
    assert extracted.count(before) == 1
    destination.write_text(extracted.replace(before, identifier), encoding="utf-8")
    return {"file": destination, "sha256": sha256(destination.read_bytes()).hexdigest()}


def optimized_modules(args, directory, ir):
    modules = {}
    for level in (0, 3):
        raw = execute(args.optimizer, f"-passes=default<O{level}>", "-S", "-o", "-", data=ir).stdout
        module = directory / f"optimized-O{level}.ll"
        module.write_text(raw, encoding="utf-8")
        execute(args.optimizer, "-passes=verify", "-disable-output", module)
        modules[f"O{level}"] = module
    return modules


def compare(args):
    assert platform.system() == "Linux" and platform.machine() == "x86_64"
    archive = json.loads(NATIVE.read_text(encoding="utf-8"))
    assert archive["schema"] == "llmlang-rt05-f64-i64-conversion/1" and archive["inputs"] == 216
    rows = archive["observations"]
    ir = LOWERINGS.read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="llmlang-llvm-f64-i64-") as scratch:
        directory = Path(scratch)
        execute(args.assembler, LOWERINGS, "-o", directory / "original.bc")
        original = {route: verify_alive(args, ("--src-fn=bits_branch", f"--tgt-fn={route}", LOWERINGS))
                    for route in TARGETS}
        assert original["inclusive_upper"]["input"] == UPPER
        assert original["unmasked_value"]["verdict"] == "refuted"
        assert all(original[route]["verdict"] == "refines" for route in MATCHING[1:])
        assert all(original[route]["verdict"] == "unsupported" for route in ("saturate", "guarded_saturate"))
        optimized = {}
        reference = extract(args, LOWERINGS, "bits_branch", directory / "reference.ll")
        for name, module in optimized_modules(args, directory, ir).items():
            verdicts = {}
            for route in MATCHING:
                target = extract(args, module, route, directory / f"{name}-{route}.ll")
                verdict = verify_alive(args, (reference["file"], target["file"]))
                assert verdict["verdict"] == "refines", (name, route, verdict)
                verdicts[route] = verdict | {"projected_ir_sha256": target["sha256"]}
            optimized[name] = {"ir_sha256": sha256(module.read_bytes()).hexdigest(), "verdicts": verdicts}
        native = observe_native(args, directory, ir, rows)
        vellvm = observe_vellvm(args, directory, ir, rows)
    mismatches = {route: sum(x != y for x, y in zip(native["bits_branch"], observed, strict=True))
                  for route, observed in native.items()}
    tools = {"python": platform.python_version(),
             "llvm": execute(args.optimizer, "--version").stdout.splitlines()[1].strip(),
             "clang": execute(args.clang, "--version").stdout.splitlines()[0],
             "ocaml": execute(args.ocamlrun, "-version").stdout.strip()}
    binaries = {name: sha256(path.read_bytes()).hexdigest() for name, path in vars(args).items()}
    return {"schema": "llmlang-rt13-llvm-f64-i64/1", "tools": tools, "binary_sha256": binaries,
            "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in (NATIVE, LOWERINGS, Path(__file__))},
            "inputs": len(rows), "native_configurations": ["x86-64 O0", "x86-64 O3"],
            "native_mismatches": mismatches, "original_refinement": original,
            "reference_ir_sha256": reference["sha256"], "optimized_refinement": optimized, "vellvm": vellvm, "native_observations": native}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for tool in ("assembler", "optimizer", "extractor", "clang", "alive", "vellvm", "ocamlrun", "bytecode"):
        parser.add_argument(f"--{tool}", type=Path, required=True)
    result = compare(parser.parse_args())
    vectors = result.pop("native_observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "native_observations": {')
    for index, (policy, rows) in enumerate(vectors.items()):
        print(f'    "{policy}": [')
        print(",\n".join("      " + json.dumps(row, separators=(",", ":")) for row in rows))
        print("    ]" + ("," if index + 1 < len(vectors) else ""))
    print("  }\n}")
