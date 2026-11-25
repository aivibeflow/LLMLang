"""Compare cross-translation-unit C++ return ABI with an explicit C facade."""

import argparse
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
BY_VALUE = "_Z11make_recordj"
EXPECTED_VALUES = [f"{value},{2 * value + 1}" for value in range(16)]


def run(args):
    return subprocess.check_output(args, cwd=HERE, text=True, timeout=30)


def locate_definition(llvm_text, symbol):
    matches = [line for line in llvm_text.splitlines() if line.startswith("define ") and f"@{symbol}(" in line]
    assert len(matches) == 1
    return matches[0]


def study(options):
    assert platform.machine() == "x86_64"
    cxx = (options.clang, "--driver-mode=g++", "-std=c++20", "-Wall", "-Wextra", "-Werror")
    gxx = (options.gxx, "-std=c++20", "-Wall", "-Wextra", "-Werror")
    cases = {}
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        c_client = work / "c-client.o"
        run([options.gcc, "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", "-c", "client.c", "-o", c_client])
        for nontrivial in (0, 1):
            for level in (0, 2):
                flags = (f"-O{level}", f"-DNONTRIVIAL={nontrivial}")
                provider = work / "provider.o"
                ll = work / "provider.ll"
                direct = work / "cpp-client"
                facade = work / "c-facade"
                run([*cxx, *flags, "-c", "provider.cc", "-o", provider])
                run([*cxx, *flags, "-S", "-emit-llvm", "provider.cc", "-o", ll])
                run([*gxx, *flags, "client.cc", provider, "-o", direct])
                run([*gxx, *flags, c_client, provider, "-o", facade])
                symbols = run(["nm", "--defined-only", provider])
                assert all(re.search(rf"\b{symbol}$", symbols, re.M) for symbol in (BY_VALUE, "emit_record"))
                ir = ll.read_text()
                value_line = locate_definition(ir, BY_VALUE)
                facade_line = locate_definition(ir, "emit_record")
                if nontrivial:
                    assert f"void @{BY_VALUE}(ptr" in value_line and "sret(%struct.Record)" in value_line, value_line
                    abi = "indirect-hidden-return-pointer"
                else:
                    assert f"i64 @{BY_VALUE}(i32" in value_line, value_line
                    abi = "i64-direct-return"
                assert "void @emit_record(i32" in facade_line and "sret(" not in facade_line
                assert facade_line.count("ptr") == 2, facade_line
                cpp_outputs = run([direct]).splitlines()
                c_outputs = run([facade]).splitlines()
                expected = [*EXPECTED_VALUES, f"retired={16 if nontrivial else 0}"]
                assert cpp_outputs == ["layout=8,4,0,4", *expected]
                assert c_outputs == expected
                cases[f"{'nontrivial' if nontrivial else 'trivial'}-O{level}"] = {
                    "layout": [8, 4, 0, 4],
                    "by_value_symbol": BY_VALUE,
                    "by_value_abi": abi,
                    "facade_abi": "void(i32,ptr,ptr)",
                    "cpp_observations": cpp_outputs,
                    "c_facade_observations": c_outputs,
                }
    return {
        "python": platform.python_version(),
        "clang": run([options.clang, "--version"]).splitlines()[0],
        "gcc": run([options.gcc, "--version"]).splitlines()[0],
        "gxx": run([options.gxx, "--version"]).splitlines()[0],
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--gcc", default="gcc")
    parser.add_argument("--gxx", default="g++")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
