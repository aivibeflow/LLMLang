#!/usr/bin/env python3
"""Compare generic result inference and explicit public type boundaries in Rust and Go."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

RUST = """
fn fresh<T: Default>() -> T { T::default() }
fn echo<T>(value: T) -> T { value }
fn emit<T: std::fmt::Display>(value: T) {
    println!("{}:{}", std::any::type_name::<T>(), value);
}
HELPERS
fn main() { BODY }
"""
GO = """
package main
import "fmt"
func fresh[T any]() T { var value T; return value }
func echo[T any](value T) T { return value }
func emit[T any](value T) { fmt.Printf("%T:%v\\n", value, value) }
HELPERS
func main() { BODY }
"""

# Each row contains an optional declaration, an operation and an exact
# observation or a compiler diagnostic category for the given language.
CASES = {
    "explicit-type-argument": {
        "rust": ("", "emit(fresh::<u16>());", "u16:0"),
        "go": ("", "emit(fresh[uint16]())", "uint16:0"),
    },
    "typed-result-assignment": {
        "rust": ("", "let x: u16 = fresh(); emit(x);", "u16:0"),
        "go": ("", "var x uint16 = fresh(); emit(x)", "cannot infer T"),
    },
    "typed-return-context": {
        "rust": ("fn pick() -> u16 { fresh() }", "emit(pick());", "u16:0"),
        "go": ("func pick() uint16 { return fresh() }", "emit(pick())", "cannot infer T"),
    },
    "typed-function-value": {
        "rust": ("", "let f: fn() -> u16 = fresh; emit(f());", "u16:0"),
        "go": ("", "var f func() uint16 = fresh; emit(f())", "uint16:0"),
    },
    "argument-supplies-type": {
        "rust": ("", "emit(echo(7u16));", "u16:7"),
        "go": ("", "emit(echo(uint16(7)))", "uint16:7"),
    },
    "unconstrained-call": {
        "rust": ("", "let _ = fresh();", "E0283"),
        "go": ("", "_ = fresh()", "cannot infer T"),
    },
    "incompatible-use-contexts": {
        "rust": ("fn small(_: &u16) {} fn large(_: &u32) {}",
                 "let value = fresh(); small(&value); large(&value);", "E0308"),
        "go": ("func small(uint16) {}\nfunc large(uint32) {}",
               "value := fresh(); small(value); large(value)", "cannot infer T"),
    },
    "default-literal-through-generic-call": {
        "rust": ("", "emit(echo(7));", "i32:7"),
        "go": ("", "emit(echo(7))", "int:7"),
    },
    "explicit-public-annotation-survives-private-type-edit": {
        "rust": ("fn baseline() -> u16 { let value = 7; value }\n"
                 "fn edited() -> u16 { let value = echo(7u32); value as u16 }",
                 "emit(baseline()); emit(edited());", "u16:7\nu16:7"),
        "go": ("func baseline() uint16 { return 7 }\n"
               "func edited() uint16 { value := echo(uint32(7)); return uint16(value) }",
               "emit(baseline()); emit(edited())", "uint16:7\nuint16:7"),
    },
}


def execute(work, language, binary, env, name, configuration):
    definitions, body, expected = configuration
    template = RUST if language == "rust" else GO
    source = template.replace("HELPERS", definitions).replace("BODY", body)
    path = work / ("main.rs" if language == "rust" else "main.go")
    path.write_text(source, encoding="utf-8")
    if language == "rust":
        argv = [binary, "--edition=2021", "--remap-path-prefix", f"{work}=/fixture",
                path.name, "-o", "app"]
    else:
        argv = [binary, "build", "-trimpath", "-o", "app", path.name]
    process = subprocess.run(argv, cwd=work, capture_output=True, text=True, check=False, env=env)
    assert not process.stdout
    warnings = ("E0283", "E0308", "cannot infer T")
    if expected in warnings:
        assert process.returncode != 0 and expected in process.stderr, (name, language, process.stderr)
        return {"decision": "refused", "diagnostic": expected}
    if process.returncode:
        raise AssertionError((name, language, process.stderr))
    active = subprocess.check_output(["./app"], cwd=work, text=True, env=env)
    assert active == expected + "\n"
    return {"decision": "compiled", "stdout": active.splitlines(),
            "native_digest": sha256(active.encode()).hexdigest()}


def experiment(directory):
    tools = {"rust": os.environ.get("RUSTC", "rustc"), "go": os.environ.get("GO", "go")}
    env = os.environ.copy()
    env.update({
        "GOENV": "off", "GOTOOLCHAIN": "local", "GOFLAGS": "", "GOWORK": "off",
        "GOPATH": str(directory / "gopath"), "GOMODCACHE": str(directory / "modules"),
        "GOCACHE": str(directory / "cache"), "CGO_ENABLED": "0", "GOMAXPROCS": "2",
    })
    rows = []
    for name, pair in CASES.items():
        for language, configuration in pair.items():
            work = directory / f"{name}-{language}"
            work.mkdir()
            rows.append({"case": name, "language": language,
                         **execute(work, language, tools[language], env, name, configuration)})
    assert sum(row["decision"] == "compiled" for row in rows) == 12
    return {
        "format": "generic-context-inference-01",
        "toolchains": {
            "rust": subprocess.check_output([tools["rust"], "--version"], text=True, env=env).strip(),
            "go": subprocess.check_output([tools["go"], "version"], text=True, env=env).strip(),
        },
        "rows": rows,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-contextual-inference-") as work:
        result = experiment(Path(work))
    raw = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(raw, encoding="utf-8")
    else:
        print(raw, end="")
