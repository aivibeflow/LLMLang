"""Validate typed C/C++ wrapping import and narrow cross-target re-export."""

import argparse
from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
import os
import struct
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CORPUS = HERE.parents[1] / "RT-13" / "GENERATED-GO-INTEGERS-01"
sys.path.insert(0, str(CORPUS))
from run import FIXTURE, SENTINEL, reference, source, vectors
from integer_fixture import WRAPPING, compile_source
from llvm_integer_probe import _EMIT, _STATUS, _entry


LANGUAGES = {"c": ("c", "c17"), "cpp": ("c++", "c++20")}
OPERATORS = {"wrap_add": "+", "wrap_sub": "-", "wrap_mul": "*"}
NONSEMANTIC_AST_KEYS = frozenset({"id", "loc", "range"})
STATUS = {
    "accepted": "accepted",
    "directive": "unsupported-preprocessing",
    "syntax": "compiler-rejected",
    "inventory": "unsupported-inventory",
    "shape": "unsupported-shape",
}


def invoke(clang, args, directory, *, payload=None, check=True):
    return subprocess.run([clang, *map(str, args)], cwd=directory, input=payload, text=True,
                          capture_output=True, check=check, timeout=60,
                          env={**os.environ, "LC_ALL": "C"})


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def flags(profile):
    language, standard = LANGUAGES[profile]
    return ["-x", language, f"-std={standard}", "-Wall", "-Wextra", "-Werror"]


def emit(profile, function, operation, operands):
    left, right = operands
    binary = OPERATORS[operation]
    body = f"""unsigned {function}(unsigned a, unsigned b, unsigned enabled,
                    void (*emit)(unsigned), unsigned *out) {{
    emit(a);
    unsigned value = b;
    if (enabled != 0u) {{
        value = {left} {binary} {right};
    }}
    emit(value);
    *out = value;
    return 0u;
}}
"""
    return body if profile == "c" else 'extern "C" {\n' + body + '}\n'


def original(profile, function, program):
    text = (HERE / "original.c.in").read_text(encoding="utf-8")
    replacements = {
        "OPEN": 'extern "C" {' if profile == "cpp" else "",
        "CLOSE": "}" if profile == "cpp" else "",
        "FUNCTION": function,
        "LEFT": program.operands[0],
        "RIGHT": program.operands[1],
        "OP": OPERATORS[program.operation],
    }
    for name, value in replacements.items():
        text = text.replace(f"@{name}@", value)
    return text


def normalized(node):
    if isinstance(node, list):
        return [normalized(item) for item in node]
    if isinstance(node, dict):
        return {key: normalized(value) for key, value in node.items()
                if key not in NONSEMANTIC_AST_KEYS}
    return node


def parse(clang, directory, profile, text):
    # This source-only profile has no preprocessing or escaped lines.
    if any(marker in text for marker in ("#", "%:", "??=", "\\")):
        return STATUS["directive"], None
    execution = invoke(clang, (*flags(profile), "-fsyntax-only", "-Xclang",
                              "-ast-dump=json", "-"), directory, payload=text, check=False)
    if execution.returncode:
        return STATUS["syntax"], None
    declarations = [node for node in json.loads(execution.stdout)["inner"] if not node.get("isImplicit")]
    if profile == "cpp":
        if (len(declarations) != 1 or declarations[0].get("kind") != "LinkageSpecDecl"
                or declarations[0].get("language") != "C"):
            return STATUS["inventory"], None
        declarations = declarations[0]["inner"]
    if len(declarations) != 1 or declarations[0].get("kind") != "FunctionDecl":
        return STATUS["inventory"], None
    declaration = normalized(declarations[0])
    declaration["name"] = declaration["mangledName"] = "normalized"
    return STATUS["accepted"], declaration


def recognize(clang, directory, profile, text, templates):
    status, declaration = parse(clang, directory, profile, text)
    if status != STATUS["accepted"]:
        return status, None
    for candidate, template in templates.items():
        if declaration == template:
            return STATUS["accepted"], candidate
    return STATUS["shape"], None


def make_templates(clang, directory, profiles, programs):
    templates = {}
    for profile in profiles:
        candidates = {}
        for term in programs:
            status, tree = parse(clang, directory, profile, emit(profile, "reference", term.operation, term.operands))
            if status != STATUS["accepted"]:
                raise AssertionError((profile, term, status))
            candidates[term] = tree
        templates[profile] = candidates
    return templates


def negative_controls(clang, directory, profiles, program, templates):
    cases = {}
    for profile in profiles:
        baseline = original(profile, "original", program)
        altered = {
            "directive": ("#define OMITTED 1\n" + baseline, "directive"),
            "syntax": (baseline.replace("enabled != 0u", "enabled ! 0u"), "syntax"),
            "inventory": (baseline + "\nunsigned unwanted;\n", "inventory"),
            "wider-type": (baseline.replace("unsigned", "unsigned long"), "shape"),
            "signed-arithmetic": (baseline.replace("unsigned", "int").replace("0u", "0"), "shape"),
            "arithmetic-mode": (baseline.replace("a + b", "a ^ b"), "shape"),
            "slot-write-order": (baseline.replace("  emit(value);\n  *out=value;", "  *out=value;\n  emit(value);"),
                                 "shape"),
            "callback-source": (baseline.replace("emit(a);", "emit(b);"), "shape"),
        }
        if profile == "cpp":
            altered["unadapted-cpp-linkage"] = (baseline.replace('extern "C" {', "").strip().removesuffix("}"),
                                              "inventory")
        result = {}
        for case, (source_text, expected) in altered.items():
            actual = recognize(clang, directory, profile, source_text, templates[profile])
            if actual != (STATUS[expected], None):
                raise AssertionError((profile, case, expected, actual))
            result[case] = actual[0]
        cases[profile] = result
    return cases


def compile_and_compare(clang, directory, label, profile, statements, args, oracle, opt):
    source_file = directory / (label + ".source")
    source_file.write_text("\n".join(statements), encoding="utf-8")
    library = directory / f"{label}-O{opt}.so"
    invoke(clang, (*flags(profile), f"-O{opt}", "-fPIC", "-shared", "-nostdlib",
                   "-Wl,--no-undefined", source_file, "-o", library), directory)
    loaded = ctypes.CDLL(str(library))
    digest_observations = sha256()
    counts = Counter()
    entries = [_entry(loaded, index) for index in range(len(statements))]
    for (index, case), expected in zip(args, oracle, strict=True):
        slot = ctypes.c_uint32(SENTINEL)
        events = []
        actual_status = entries[index](*case, _EMIT(events.append), ctypes.byref(slot))
        actual = (_STATUS[actual_status], slot.value, tuple(events))
        if actual != expected:
            raise AssertionError((label, opt, index, case, actual, expected))
        counts[actual[0]] += 1
        digest_observations.update(struct.pack("<3I", actual_status, slot.value, len(events)))
        digest_observations.update(b"".join(event.to_bytes(4, "little") for event in events))
    return {"records": len(oracle), "statuses": dict(sorted(counts.items())),
            "trace_sha256": digest_observations.hexdigest(), "artifact_sha256": digest(library)}


def validate(clang, directory):
    profiles = tuple(LANGUAGES)
    compiler = invoke(clang, ("--version",), directory).stdout.splitlines()
    for profile in profiles:
        definitions = invoke(clang, (*flags(profile), "-dM", "-E", "-"), directory, payload="").stdout.splitlines()
        if not {"#define __CHAR_BIT__ 8", "#define __SIZEOF_INT__ 4"} <= set(definitions):
            raise ValueError((profile, "the profile requires 32-bit unsigned integers"))

    programs = tuple(compile_source(source(op, a, b)) for op, (a, b) in
                     product(WRAPPING, product("ab", repeat=2)))
    templates = make_templates(clang, directory, profiles, programs)
    inputs = {}
    evidence = {}
    args = tuple(product(range(len(programs)), vectors()))
    oracle = tuple(reference(programs[index], vector) for index, vector in args)
    for profile in profiles:
        inputs[profile] = tuple(original(profile, f"probe_{idx}", term)
                                for idx, term in enumerate(programs))
        imported = tuple(recognize(clang, directory, profile, text, templates[profile])
                         for text in inputs[profile])
        if imported != tuple((STATUS["accepted"], program) for program in programs):
            raise AssertionError((profile, "incorrect original import"))
        target = "cpp" if profile == "c" else "c"
        exported = tuple(emit(target, f"probe_{idx}", program.operation, program.operands)
                         for idx, (_, program) in enumerate(imported))
        reimported = tuple(recognize(clang, directory, target, text, templates[target])
                           for text in exported)
        if reimported != imported:
            raise AssertionError((profile, target, "incorrect reimport"))
        for level in (0, 2):
            key = f"{profile}-original-O{level}"
            evidence[key] = compile_and_compare(clang, directory, f"{profile}-original", profile,
                                                inputs[profile], args, oracle, level)
            key = f"{profile}-to-{target}-O{level}"
            evidence[key] = compile_and_compare(clang, directory, f"{profile}-to-{target}", target,
                                                exported, args, oracle, level)

    sources = (HERE / "roundtrip.py", HERE / "original.c.in",
               CORPUS / "run.py", FIXTURE / "integer_fixture.py", FIXTURE / "llvm_integer_probe.py")
    return {
        "toolchain": compiler,
        "records_per_profile": len(oracle),
        "imported_per_language": len(programs),
        "reimported_per_direction": len(programs),
        "native_results": evidence,
        "negative_cases": negative_controls(clang, directory, profiles, programs[1], templates),
        "source_sha256": {path.relative_to(ROOT).as_posix(): digest(path) for path in sources},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-c-family-") as temp:
        print(json.dumps(validate(args.clang, Path(temp)), indent=2))


if __name__ == "__main__":
    main()
