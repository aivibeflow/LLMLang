"""Generate typed Win32 declarations from MinGW headers and inspect exact PE imports."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
TRIPLE = "x86_64-w64-windows-gnu"
SYMBOLS = {"CreateFileW": "fileapi.h", "CloseHandle": "handleapi.h", "GetLastError": "errhandlingapi.h"}


def run(args, **options):
    return subprocess.check_output(args, text=True, timeout=30, **options)


def json_objects(data):
    decoder = json.JSONDecoder()
    rest = data.lstrip()
    while rest:
        root, index = decoder.raw_decode(rest)
        yield root
        rest = rest[index:].lstrip()


def get_symbols(compiler, flags):
    selected = {}
    for name in SYMBOLS:
        raw = run([compiler, *flags, "-fsyntax-only", "-Xclang", "-ast-dump=json",
                   "-Xclang", "-ast-dump-filter", "-Xclang", name, "-x", "c", "-"],
                  input="#include <windows.h>\n")
        rows = [item for item in json_objects(raw) if item.get("kind") == "FunctionDecl" and item.get("name") == name]
        assert len(rows) == 1
        node = rows[0]
        parameters = [inner["type"] for inner in node.get("inner", []) if inner["kind"] == "ParmVarDecl"]
        assert any(inner["kind"] == "DLLImportAttr" for inner in node.get("inner", []))
        selected[name] = {
            "return_type": node["type"]["qualType"].split(" (", 1)[0],
            "parameters": [parameter["qualType"] for parameter in parameters],
            "desugared_parameters": [parameter.get("desugaredQualType", parameter["qualType"])
                                      for parameter in parameters],
            "header": SYMBOLS[name], "attribute": "DLLImportAttr",
        }
    return selected


def declarations(rows):
    lines = ["#include <windows.h>", ""]
    for name, record in rows.items():
        parameters = ", ".join(record["parameters"]) or "void"
        lines.append(f'typedef {record["return_type"]} (WINAPI *signature_{name})({parameters});')
        lines.append(f'_Static_assert(__builtin_types_compatible_p(__typeof__(&{name}), signature_{name}), "{name}");')
    return "\n".join(lines) + "\n"


def trace(work):
    executable = work / "native"
    run(["cc", "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", HERE / "adapter.c", HERE / "mock.c", "-o", executable])
    actual = run([executable]).splitlines()
    expected = []
    for _, opened, closed in product((False, True), repeat=3):
        if not opened:
            expected.append("open:0:5:1")
        else:
            expected.append("open:1:0:0:close:1:0:0" if closed else "open:1:0:0:close:0:6:1")
    assert actual == expected
    return actual


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def verify(options):
    include = options.mingw / "include"
    kernel_imports = options.mingw / "lib/libkernel32.a"
    flags = [f"--target={TRIPLE}", "-DWIN32_LEAN_AND_MEAN", "-D_WIN32_WINNT=0x0a00", "-isystem", include]
    rows = get_symbols(options.clang, flags)
    with TemporaryDirectory() as directory:
        work = Path(directory)
        generated = work / "generated.h"
        content = declarations(rows)
        generated.write_text(content)
        clang = [options.clang, *flags, "-std=c17", "-ffreestanding", "-fno-builtin", "-O2",
                 "-mno-incremental-linker-compatible", "-I", work]
        obj = work / "adapter.obj"
        dll = work / "adapter.dll"
        run([*clang, "-c", HERE / "adapter.c", "-o", obj])
        run([options.lld, "/dll", "/noentry", "/nodefaultlib", "/machine:x64", "/timestamp:0",
             f"/out:{dll}", obj, kernel_imports])
        data = run([options.readobj, "--coff-imports", "--coff-exports", dll])
        assert len(re.findall(r"(?im)^\s*Name: kernel32.dll$", data)) == 1
        assert {name for name in SYMBOLS if f"Symbol: {name} " in data} == set(SYMBOLS)
        assert all(f"Name: {name}" in data for name in ("open_reader", "close_owned"))
        generated.write_text(content.replace("typedef DWORD (WINAPI *signature_GetLastError)",
                                             "typedef unsigned long long (WINAPI *signature_GetLastError)"))
        assert generated.read_text() != content
        wrong = subprocess.run([*clang, "-fsyntax-only", HERE / "adapter.c"], text=True, capture_output=True,
                               check=False, timeout=15)
        assert wrong.returncode and "GetLastError" in wrong.stderr
        return {
            "target": TRIPLE, "sdk_scope": "MinGW header and import archive only",
            "tool_versions": {tool: run([getattr(options, tool), "--version"]).splitlines()[0]
                              for tool in ("clang", "lld", "readobj")},
            "symbols": rows, "header_sha256": {name: digest(include / name) for name in SYMBOLS.values()},
            "generated_header_sha256": sha256(content.encode()).hexdigest(),
            "kernel32_import_archive_sha256": digest(kernel_imports), "linked_dll_sha256": digest(dll),
            "imports": sorted(SYMBOLS), "import_archive": "libkernel32.a", "dependent_dll": "KERNEL32.dll",
            "source_sha256": {path: digest(HERE / path) for path in ("adapter.c", "mock.c", "mock_api.h", "check.py")},
            "wrong_64_bit_error_type_refused": True, "native_mock_trace": trace(work),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mingw", required=True, type=Path)
    for tool in ("clang", "lld", "readobj"):
        parser.add_argument(f"--{tool}", required=True)
    print(json.dumps(verify(parser.parse_args()), indent=2, sort_keys=True))
