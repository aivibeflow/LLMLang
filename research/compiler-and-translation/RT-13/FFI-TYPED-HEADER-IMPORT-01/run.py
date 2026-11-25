"""Extract an exact C ABI subset and test independently scoped adapters."""

import _sha2
import argparse
from errno import EBADF
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
SYMBOLS = ("read", "sqlite3_stricmp", "EVP_Digest")
TYPES = {
    "int": "i32",
    "ssize_t": "isize",
    "size_t": "usize",
    "void *": "pointer<void>",
    "const void *": "pointer<const void>",
    "const char *": "pointer<const c_char>",
    "unsigned char *": "pointer<u8>",
    "unsigned int *": "pointer<u32>",
    "const EVP_MD *": "pointer<const opaque<EVP_MD>>",
    "ENGINE *": "pointer<opaque<ENGINE>>",
}
ALIASES = {
    "size_t": "unsigned long", "ssize_t": "long",
    "EVP_MD": "struct evp_md_st", "ENGINE": "struct engine_st",
}
HEADERS = {
    "posix": Path("/usr/include/unistd.h"),
    "openssl": Path("/usr/include/openssl/evp.h"),
    "openssl_types": Path("/usr/include/openssl/types.h"),
}
WORDS = (b"", b"A", b"a", b"AB", b"ab", b"A1_", b"a1_", b"b", b"B",
         bytes.fromhex("c384"), bytes.fromhex("c3a4"), bytes.fromhex("7f"))


def command(*args, cwd=None, checked=True):
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1764000000"}
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True, check=checked, timeout=30,
    )


def digest(data):
    return sha256(data).hexdigest()


def hash_file(path):
    return digest(path.read_bytes())


def importer(args, work):
    source = HERE / "import.c"
    flags = ["-std=c17", "-I", args.sqlite_headers]
    result = command(args.clang, *flags, "-Xclang", "-ast-dump=json", "-fsyntax-only", source)
    decls = json.loads(result.stdout)["inner"]
    aliases = {}
    functions = {}
    for node in decls:
        name = node.get("name")
        if node["kind"] == "TypedefDecl" and name in ALIASES:
            aliases[name] = node["type"].get("desugaredQualType", node["type"]["qualType"])
        if node["kind"] != "FunctionDecl" or name not in SYMBOLS:
            continue
        assert name not in functions and not node.get("variadic") and node.get("storageClass") != "static"
        parameters = [p["type"]["qualType"] for p in node.get("inner", []) if p["kind"] == "ParmVarDecl"]
        returns = node["type"]["qualType"].split(" (", 1)[0]
        assert node["type"]["qualType"] == f"{returns} ({', '.join(parameters)})"
        functions[name] = {
            "return": TYPES[returns],
            "parameters": [TYPES[p] for p in parameters],
            "c_return": returns, "c_parameters": parameters,
        }
    assert set(functions) == set(SYMBOLS)
    assert aliases == ALIASES
    macros = command(args.clang, *flags, "-dM", "-E", source).stdout
    assert re.search(r"(?m)^#define __SIZEOF_POINTER__ 8$", macros)
    assert re.search(r"(?m)^#define __SIZEOF_INT__ 4$", macros)
    assert re.search(r"(?m)^#define __SIZEOF_SIZE_T__ 8$", macros)
    assert re.search(r"(?m)^#define __BYTE_ORDER__ __ORDER_LITTLE_ENDIAN__$", macros)
    contracts = json.loads((HERE / "contracts.json").read_text(encoding="utf-8"))
    assert set(contracts) == set(functions)
    header = work / "bindings.h"
    generate_header(header, functions)
    return functions, aliases, contracts, header


def generate_header(path, functions, *, narrow=False):
    lines = [(HERE / "import.c").read_text(encoding="utf-8").strip()]
    for name in SYMBOLS:
        proposal = functions[name]
        parameters = proposal["c_parameters"].copy()
        if narrow and name == "read":
            parameters[2] = "unsigned int"
        lines.append(f"typedef {proposal['c_return']} (*import_{name})({', '.join(parameters)});")
        lines.append(
            f'_Static_assert(__builtin_types_compatible_p(__typeof__(&{name}), import_{name}), '
            f'"imported signature mismatch for {name}");'
        )
    lines.extend(['#include "adapter.h"', ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def expected_rows():
    output = {"read": {}, "compare": {}, "digest": {}}
    contents = b"abcdefghijklmnopq"
    for request, capacity, valid in product((0, 1, 7, 16, 32, 33, 80), (0, 8, 32, 64), (0, 1)):
        if request > capacity:
            result = (2, 0, 0, "")
        elif not valid:
            result = (1, EBADF, 0, "")
        else:
            taken = contents[:request]
            result = (0, 0, len(taken), taken.hex())
        output["read"][request, capacity, valid] = result
    for left, right in product(range(len(WORDS)), repeat=2):
        a, b = WORDS[left].lower(), WORDS[right].lower()
        output["compare"][left, right] = ((a > b) - (a < b),)
    for length, salt in product((0, 1, 2, 7, 32, 63, 64, 129, 256), (0, 17, 34)):
        message = bytes((i * 37 + salt) % 256 for i in range(length))
        output["digest"][length, salt] = (1, 32, _sha2.sha256(message).hexdigest())
    return output


def observe(output, expected, mode):
    bindings = {}
    versions = {}
    observed = {name: {} for name in expected}
    for line in output.splitlines():
        kind, *fields = line.split()
        if kind == "binding":
            name, path = fields
            provider = Path(path).resolve()
            bindings[name] = {"file": provider.name, "sha256": hash_file(provider)}
        elif kind.endswith("_version"):
            versions[kind] = " ".join(fields)
        else:
            keys = int(fields[0]), int(fields[1])
            values = (int(fields[2]),) if kind == "compare" else ()
            if kind == "read":
                keys = (*keys, int(fields[2]))
                raw = fields[3:]
                values = (*map(int, raw[:3]), raw[3] if len(raw) == 4 else "")
            elif kind == "digest":
                values = int(fields[2]), int(fields[3]), fields[4]
            assert keys not in observed[kind]
            observed[kind][keys] = values
    assert set(bindings) == {"posix", "sqlite", "openssl"}
    assert versions["sqlite_version"] == "3.46.1" and versions["openssl_version"].startswith("OpenSSL 3.5.7")
    assert all(rows.keys() == expected[kind].keys() for kind, rows in observed.items())
    failures = {
        kind: sum(expected[kind][key] != val for key, val in rows.items())
        for kind, rows in observed.items()
    }
    assert failures == {"read": 0, "compare": 0, "digest": 27 if mode == "same_abi_wrong_algorithm" else 0}
    return {
        "symbols": bindings, "versions": versions, "mismatches": failures,
        "observations": {kind: len(rows) for kind, rows in observed.items()},
        "native_trace_sha256": digest("\n".join(
            line for line in output.splitlines() if line.split()[0] in expected
        ).encode("utf-8")),
    }


def collect(args, work):
    functions, aliases, contracts, header = importer(args, work)
    shutil.copyfile(HERE / "host.c", work / "host.c")
    shutil.copyfile(HERE / "adapter.h.in", work / "adapter.h")
    flags = [args.cc, "-std=c17", "-Wall", "-Wextra", "-Werror", "-I", args.sqlite_headers, "host.c"]
    libs = ["-l:libsqlite3.so.0", "-lcrypto", "-ldl"]
    expected = expected_rows()
    profiles = {}
    for name, options in (
        ("O0", ["-O0"]), ("O2", ["-O2"]),
        ("same_abi_wrong_algorithm", ["-O2", "-DCHANGE_DIGEST"]),
    ):
        target = work / name
        command(*flags, *options, *libs, "-o", target, cwd=work)
        output = command(target).stdout
        elf = command("readelf", "-dW", target).stdout
        needed = re.findall(r"\(NEEDED\).*\[([^]]+)\]", elf)
        assert set(needed) == {"libc.so.6", "libsqlite3.so.0", "libcrypto.so.3"}
        profiles[name] = {
            **observe(output, expected, name), "needed": needed, "elf_sha256": hash_file(target),
        }
    header_sha = hash_file(header)
    generate_header(header, functions, narrow=True)
    refused = command(*flags, "-fsyntax-only", cwd=work, checked=False)
    assert refused.returncode and "imported signature mismatch for read" in refused.stderr
    assert profiles["O0"]["native_trace_sha256"] == profiles["O2"]["native_trace_sha256"]
    return {
        "target": "Linux x86-64 LP64 little-endian",
        "tools": {
            "clang": command(args.clang, "--version").stdout.splitlines()[0],
            "cc": command(args.cc, "--version").stdout.splitlines()[0],
        },
        "declarations": functions, "underlying_types": aliases, "behavioral_contracts": contracts,
        "headers_sha256": {
            name: hash_file(path)
            for name, path in {**HEADERS, "sqlite": args.sqlite_headers / "sqlite3.h"}.items()
        },
        "generated_declarations_and_adapter_include_sha256": header_sha,
        "wrong_width_control": "refused by compiler static type check",
        "profiles": profiles,
        "source_sha256": {
            name: hash_file(HERE / name)
            for name in ("run.py", "host.c", "import.c", "adapter.h.in", "contracts.json")
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--sqlite-headers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-typed-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
