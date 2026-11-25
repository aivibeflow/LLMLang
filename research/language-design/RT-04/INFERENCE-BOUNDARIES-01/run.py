"""Compile matched small edits under the Rust and Go numeric inference rules."""

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


def cases():
    return {
        "local_inferred": {
            "rust": ("", "let number = 9;", "", "i32:9"),
            "go": ("", "number := 9", "", "int:9"),
        },
        "later_use_requires_u64": {
            "rust": ("", "let number = 9;", "consume(number);", "u64:9"),
            "go": ("", "number := 9", "consume(number)", "int-as-uint64"),
        },
        "local_annotated": {
            "rust": ("", "let number: u32 = 9;", "", "u32:9"),
            "go": ("", "var number uint32 = 9", "", "uint32:9"),
        },
        "annotated_later_conflict": {
            "rust": ("", "let number: u32 = 9;", "consume(number);", "E0308"),
            "go": ("", "var number uint32 = 9", "consume(number)", "uint32-as-uint64"),
        },
        "annotated_explicit_conversion": {
            "rust": ("", "let number: u32 = 9;", "consume(u64::from(number));", "u32:9"),
            "go": ("", "var number uint32 = 9", "consume(uint64(number))", "uint32:9"),
        },
        "public_return_annotation": {
            "rust": ("pub fn api() -> u64 { 9 }", "let number = api();", "", "u64:9"),
            "go": ("func API() uint64 { return 9 }", "number := API()", "", "uint64:9"),
        },
        "public_return_without_concrete_annotation": {
            "rust": ("pub fn api() -> _ { 9u64 }", "let number = api();", "", "E0121"),
            "go": ("func API() { return uint64(9) }", "number := 9", "", "extra-return-value"),
        },
    }


def compile_source(compiler, language, source, output, env):
    if language == "rust":
        args = [compiler, "--edition=2021", "--error-format=json", str(source), "-o", str(output)]
    else:
        args = [compiler, "build", "-o", str(output), str(source)]
    return subprocess.run(args, capture_output=True, check=False, env=env, text=True, timeout=60)


def diagnostic(language, stderr):
    if language == "rust":
        diagnostics = [json.loads(line) for line in stderr.splitlines()]
        codes = [entry["code"]["code"] for entry in diagnostics
                 if entry.get("level") == "error" and entry.get("code")]
        assert len(codes) == 1, diagnostics
        return codes[0]
    for snippet, code in (
        ("variable of type int) as uint64", "int-as-uint64"),
        ("variable of type uint32) as uint64", "uint32-as-uint64"),
        ("too many return values", "extra-return-value"),
    ):
        if snippet in stderr:
            return code
    raise AssertionError(stderr)


def study(compilers, cache):
    folder = Path(__file__).resolve().parent
    receipts = {name: {} for name in cases()}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        env = os.environ | {
            "GOCACHE": str(cache.resolve()),
            "GOENV": "off",
            "GOTOOLCHAIN": "local",
            "GOWORK": "off",
            "GOFLAGS": "",
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "CGO_ENABLED": "0",
        }
        for language, compiler in compilers.items():
            template = (folder / f"{language}.in").read_text()
            source = work / ("main.rs" if language == "rust" else "main.go")
            for name, profiles in cases().items():
                api, declaration, later_use, expected = profiles[language]
                source.write_text(template.replace("@API@", api).replace("@DECLARATION@", declaration)
                                  .replace("@LATER_USE@", later_use))
                output = work / "fixture"
                result = compile_source(compiler, language, source, output, env)
                if result.returncode == 0:
                    observed = subprocess.check_output([output], text=True, timeout=10).strip()
                    status = "accepted"
                else:
                    observed = diagnostic(language, result.stderr)
                    status = "refused"
                assert observed == expected, (name, language, observed, expected, result.stderr)
                receipts[name][language] = {"status": status, "observation": observed}
    return {
        "python": platform.python_version(),
        "rust": subprocess.check_output([compilers["rust"], "-Vv"], text=True).splitlines(),
        "go": subprocess.check_output([compilers["go"], "version"], env=env, text=True).strip(),
        "cases": receipts,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--go", default="go")
    parser.add_argument("--cache", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(study({"rust": args.rustc, "go": args.go}, args.cache), indent=2, sort_keys=True))
