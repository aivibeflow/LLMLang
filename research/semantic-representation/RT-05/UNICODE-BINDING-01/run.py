#!/usr/bin/env python3
"""Compare native source-name resolution with Unicode-based SPG projections."""

import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unicodedata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, make_snapshot

SHARED = {
    "ascii_same": ("value", "value"),
    "ascii_distinct": ("alpha", "beta"),
    "acute": ("café", "cafe\u0301"),
    "hangul": ("가", "가"),
    "kelvin": ("K", "K"),
    "angstrom": ("Å", "Å"),
    "compatibility_mu": ("μ", "µ"),
    "fullwidth": ("A", "Ａ"),
    "ligature": ("ff", "ﬀ"),
    "math_compatibility": ("a", "𝐚"),
    "different_script": ("a", "а"),
    "ordered_marks": ("a\u0301\u0323", "a\u0323\u0301"),
}
ESCAPED = {
    "escaped_ascii": ("identifier", r"\u0069dentifier"),
    "escaped_acute": ("café", r"caf\u00e9"),
    "escape_preserves_decomposition": ("café", r"cafe\u0301"),
    "escaped_astral": ("𝐚", r"\u{1d41a}"),
}
MODES = ("source_token", "decoded", "nfc", "nfkc", "nfkc_all_text", "same_cell", "native_profile")
SIDES = {"python": "nfkc", "node": "decoded", "rust": "nfc"}


def unescape(name):
    return re.sub(r"\\u(?:\{([0-9a-f]+)\}|([0-9a-f]{4}))",
                  lambda match: chr(int(match[1] or match[2], 16)), name)


def quote(value):
    return json.dumps(value, ensure_ascii=False)


def sources(directory):
    python = []
    js = []
    rust = []
    for index, pair in enumerate(SHARED.values()):
        first, second = pair
        equality = f"{quote(first)} == {quote(second)}"
        python.append(f"def case_{index}():\n    {first} = 11\n    _before = {first}\n"
                      f"    captured = lambda: {first}\n    {second} = 29\n"
                      f"    return [_before, {first}, {second}, captured(), {equality}]\n")
        rust.append(f"fn case_{index}() {{\n    let {first} = 11;\n    let before = {first};\n"
                    f"    let captured = || {first};\n    let {second} = 29;\n"
                    f"    println!(\"[{{}},{{}},{{}},{{}},{{}}]\", before, {first}, {second}, captured(), {equality});\n}}\n")
    py_ids = [f"case_{index}()" for index in range(len(SHARED))]
    python.append("import json\nfor row in [" + ", ".join(py_ids) + "]: print(json.dumps(row))")
    rust.append("fn main() {\n" + "\n".join(f"    {function};" for function in py_ids) + "\n}")
    for index, (first, second) in enumerate([*SHARED.values(), *ESCAPED.values()]):
        literals = f"{quote(unescape(first))} === {quote(unescape(second))}"
        js.append(f"function case_{index}() {{\n    var {first} = 11;\n    const before = {first};\n"
                  f"    const captured = () => {first};\n    var {second} = 29;\n"
                  f"    return [before, {first}, {second}, captured(), {literals}];\n}}")
    js_ids = ", ".join(f"case_{index}()" for index in range(len(SHARED) + len(ESCAPED)))
    js.append(f"for (const row of [{js_ids}]) console.log(JSON.stringify(row));")
    outputs = {}
    for profile, suffix, code in (("python", "py", python), ("node", "js", js), ("rust", "rs", rust)):
        path = directory / f"scope.{suffix}"
        path.write_text("\n".join(code) + "\n", encoding="utf-8")
        outputs[profile] = path
    return outputs


def observations(command):
    data = subprocess.check_output(command, text=True, timeout=30)
    return [json.loads(line) for line in data.splitlines()]


def resolve(case, profile, mode):
    literal = tuple(unescape(item) for item in case)
    selected = SIDES[profile] if mode in {"native_profile", "same_cell"} else mode
    if selected == "source_token":
        keys = case
    elif selected == "decoded":
        keys = literal
    else:
        rule = "NFC" if selected == "nfc" else "NFKC"
        keys = tuple(unicodedata.normalize(rule, item) for item in literal)
    if selected == "nfkc_all_text":
        literal = tuple(unicodedata.normalize("NFKC", item) for item in literal)
    alias = keys[0] == keys[1]
    shared = alias and (profile != "rust" or mode == "same_cell")
    # A new Rust let shadows the name but leaves a prior capture bound to its original cell.
    return {"type": "name-resolution-fixture-v1", "declared_values": [11, 29],
            "assignment_cells": [0, 0 if shared else 1], "read_occurrences": [0, 1 if alias else 0, 1],
            "capture_cell": 0, "literal_values": literal}


def evaluate(body):
    values = body["declared_values"]
    literal_first, literal_second = body["literal_values"]
    cells = body["assignment_cells"]
    captured = values[max(index for index, cell in enumerate(cells) if cell == body["capture_cell"])]
    return [*[values[ref] for ref in body["read_occurrences"]], captured, literal_first == literal_second]


def python_lowered(source):
    parsed = ast.parse(source.read_text())
    names = []
    for node in parsed.body:
        if isinstance(node, ast.FunctionDef):
            first, read, capture, second, end = node.body
            two = [first.targets[0].id, second.targets[0].id]
            assert read.value.id == capture.value.body.id == two[0]
            assert [name.id for name in end.value.elts[1:3]] == two
            names.append(two)
    return names


def run(directory):
    emitted = sources(directory)
    profiles = {
        "python": observations([sys.executable, "-B", str(emitted["python"])]),
        "node": observations(["node", str(emitted["node"])]),
    }
    for opt in (0, 3):
        binary = directory / f"scope-rust-{opt}"
        subprocess.run(["rustc", "--edition=2021", "-Awarnings", "-C", f"opt-level={opt}",
                        str(emitted["rust"]), "-o", str(binary)], check=True, timeout=30)
        profiles[f"rust_O{opt}"] = observations([str(binary)])
    assert profiles["rust_O0"] == profiles["rust_O3"]
    names = python_lowered(emitted["python"])
    assert names == [[unicodedata.normalize("NFKC", item) for item in case] for case in SHARED.values()]
    store = ContentStore()
    results = []
    metrics = {profile: Counter() for profile in profiles}
    selections = {profile: {mode: {} for mode in MODES} for profile in profiles}
    for profile, values in profiles.items():
        group = {**SHARED, **ESCAPED} if profile == "node" else SHARED
        assert len(group) == len(values)
        front = "rust" if profile.startswith("rust") else profile
        for (case, pair), native in zip(group.items(), values, strict=True):
            candidate = {}
            for mode in MODES:
                projection = resolve(pair, front, mode)
                address = store.put("rt05-unicode-resolved-bindings-v1", projection)
                actual = evaluate(store.get(address).payload)
                selections[profile][mode][case] = address
                metrics[profile][mode] += actual != native
                candidate[mode] = {"artifact": address, "output": actual}
                if mode == "native_profile":
                    assert actual == native
            results.append({"profile": profile, "case": case, "source_tokens": pair,
                            "native": native, "candidate": candidate})
    assert any(metric["source_token"] for metric in metrics.values())
    assert all(metric["nfkc_all_text"] > 0 for metric in metrics.values())
    assert metrics["rust_O0"]["same_cell"] > 0
    assert metrics["node"]["decoded"] == metrics["python"]["nfkc"] == metrics["rust_O0"]["nfc"] == 0
    roots = {profile: {mode: make_snapshot(selection).root_hash for mode, selection in modes.items()}
             for profile, modes in selections.items()}
    assert roots["rust_O0"] == roots["rust_O3"]
    common_source_policies = {front: make_snapshot({key: selections[front]["native_profile"][key] for key in SHARED})
                              .root_hash for front in ("node", "python", "rust_O0")}
    assert len(set(common_source_policies.values())) == len(common_source_policies)
    return {
        "schema": "llmlang-rt05-unicode-binding/1", "python": platform.python_version(),
        "python_unicode": unicodedata.unidata_version,
        "node": subprocess.check_output(["node", "-p", "process.version"], text=True).strip(),
        "node_unicode": subprocess.check_output(["node", "-p", "process.versions.unicode"], text=True).strip(),
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True).splitlines(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {front: sha256(path.read_bytes()).hexdigest() for front, path in emitted.items()},
        "shared_source_cases": len(SHARED), "javascript_escape_cases": len(ESCAPED), "native_observations": len(results),
        "profile_mismatches": metrics, "snapshots": roots, "shared_native_profile_roots": common_source_policies,
        "python_ast_name_pairs": names, "observations": results,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-unicode-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
