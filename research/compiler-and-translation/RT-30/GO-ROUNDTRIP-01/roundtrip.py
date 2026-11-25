"""Import and re-export the checked wrapping Go fixture with native differential checks."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RT13 = HERE.parents[1] / "RT-13" / "GENERATED-GO-INTEGERS-01"
sys.path.insert(0, str(RT13))
from run import FIXTURE, GO_SHA256, GO_VERSION, build, emit_project, reference, run, source, standalone, vectors
from lower_go import lower, registry
from integer_fixture import WRAPPING, compile_source


OPERATORS = {"wrap_add": "+", "wrap_sub": "-", "wrap_mul": "*"}


def recognize(importer, path, source_text):
    path.write_text(source_text, encoding="utf-8")
    return json.loads(run(importer, path))


def program_from_result(result):
    if result["status"] != "accepted":
        raise ValueError(result)
    return compile_source(source(result["operation"], *result["operands"]))


def original_source(index, operation, left, right):
    template = (HERE / "original.go.in").read_text(encoding="utf-8")
    for name, value in (("NAME", f"original{index}"), ("LEFT", left),
                        ("RIGHT", right), ("OP", OPERATORS[operation])):
        template = template.replace(f"@{name}@", value)
    return template


def emit_original(directory, inputs):
    emit_project(directory, inputs[0], "standalone", len(inputs))
    (directory / "registry.go").write_text(registry(len(inputs)).replace("    kernel", "    original"),
                                           encoding="utf-8")
    for index, code in enumerate(inputs[1:], start=1):
        (directory / f"kernel_{index}.go").write_text(code, encoding="utf-8")


def control_results(importer, scratch):
    baseline = original_source(0, "wrap_add", "a", "b")
    controls = {
        "malformed": (baseline.replace("enabled != 0", "enabled ! 0"), "parse-error"),
        "ill-typed": (baseline.replace("a + b", "a + true"), "type-error"),
        "different-inventory": (baseline + "\nfunc other() {}\n", "unsupported-inventory"),
        "build-constraint": ("//go:build excluded\n\n" + baseline, "unsupported-directive"),
        "compiler-directive": (baseline.replace("func original0", "//go:noinline\nfunc original0"),
                               "unsupported-directive"),
        "signed-schema": (baseline.replace("uint32", "int32"), "unsupported-shape"),
        "different-operation": (baseline.replace("a + b", "a & b"), "unsupported-shape"),
        "narrower-branch": (baseline.replace("enabled != 0", "enabled == 1"), "unsupported-shape"),
        "different-initial-event": (baseline.replace("emit(a);", "emit(b);"), "unsupported-shape"),
        "different-slot-effect-order":
            (baseline.replace("emit(value); *out = value", "*out = value; emit(value)"), "unsupported-shape"),
    }
    results = {}
    for name, (mutation, expected) in controls.items():
        actual = recognize(importer, scratch / "control.go", mutation)
        if actual != {"status": expected}:
            raise AssertionError((name, expected, actual))
        results[name] = actual["status"]
    return results


def native_controls(args, work):
    directory = work / "negative-native"
    original_add = original_source(0, "wrap_add", "a", "b")
    cases = {
        "narrower-branch": (original_add.replace("enabled != 0", "enabled == 1"), (7, 2, 2),
                            {"slot", "events"}),
        "different-initial-event": (
            original_add.replace("original0", "original1").replace("emit(a);", "emit(b);"),
            (7, 2, 1), {"events"},
        ),
    }
    emit_original(directory, tuple(fixture for fixture, _, _ in cases.values()))
    executable = build(args, directory, "standalone")
    indexed = tuple((index, vector) for index, (_, vector, _) in enumerate(cases.values()))
    observed = tuple(standalone(executable, indexed))
    add = compile_source(source("wrap_add"))
    witness = {}
    fields = ("status", "slot", "events")
    for (name, (_, vector, changes)), actual in zip(cases.items(), observed, strict=True):
        expected = reference(add, vector)
        changed = {field for field, before, after in zip(fields, expected, actual, strict=True)
                   if before != after}
        if changed != changes:
            raise AssertionError((name, changes, changed))
        witness[name] = {"input": vector, "expected": expected, "actual": actual,
                         "changed": sorted(changed)}
    return witness


def observations(executable, cases, expected):
    counts = Counter()
    for case, wanted, actual in zip(cases, expected, standalone(executable, cases), strict=True):
        if actual != wanted:
            raise AssertionError((case, wanted, actual))
        counts[actual[0]] += 1
    return {"observations": sum(counts.values()), "statuses": dict(sorted(counts.items())),
            "binary_sha256": sha256(executable.read_bytes()).hexdigest()}


def verify(args, work):
    version = run(args.go, "version").decode().strip()
    if version != GO_VERSION:
        raise ValueError((version, GO_VERSION))

    source_root = work / "importer"
    source_root.mkdir()
    (source_root / "go.mod").write_text("module llmlang.local/goimport\n\ngo 1.27\n", encoding="utf-8")
    shutil.copyfile(HERE / "import.go", source_root / "main.go")
    importer = build(args, source_root, "standalone")

    expected_ir = tuple(compile_source(source(operation, left, right))
                        for operation, (left, right) in product(WRAPPING, product("ab", repeat=2)))
    originals = tuple(original_source(index, term.operation, *term.operands)
                      for index, term in enumerate(expected_ir))
    imported = tuple(program_from_result(recognize(importer, work / "candidate.go", code))
                     for code in originals)
    if imported != expected_ir:
        raise AssertionError("Initial import changed the operation or operand order")
    reimported = tuple(program_from_result(recognize(importer, work / "candidate.go", lower((term,))))
                       for term in imported)
    if reimported != imported:
        raise AssertionError("Go re-export and re-import changed the bounded program")

    original = work / "original"
    exported = work / "exported"
    emit_original(original, originals)
    generated = lower(imported)
    emit_project(exported, generated, "standalone", len(imported))
    indexed = tuple(product(range(len(expected_ir)), vectors()))
    expected = tuple(reference(expected_ir[index], case) for index, case in indexed)
    files = [*sorted(HERE.glob("*.py")), HERE / "import.go", HERE / "original.go.in",
             RT13 / "host.go", RT13 / "lower_go.py", RT13 / "run.py",
             FIXTURE / "integer_fixture.py", FIXTURE / "llvm_integer_probe.py"]
    return {
        "go": version,
        "go_release_archive_sha256": GO_SHA256,
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in files},
        "approved_programs": [{"operation": term.operation, "operands": term.operands}
                              for term in imported],
        "successful_reimports": len(reimported),
        "negative": control_results(importer, work),
        "negative_native": native_controls(args, work),
        "native_comparison": {
            "original_go": observations(build(args, original, "standalone"), indexed, expected),
            "reexported_go": observations(build(args, exported, "standalone"), indexed, expected),
        },
        "input_go_sha256": sha256("".join(originals).encode()).hexdigest(),
        "output_go_sha256": sha256(generated.encode()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", default="go")
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--cache", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-go-roundtrip-") as directory:
        print(json.dumps(verify(args, Path(directory)), indent=2))


if __name__ == "__main__":
    main()
