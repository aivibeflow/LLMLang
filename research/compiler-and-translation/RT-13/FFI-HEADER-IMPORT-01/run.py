#!/usr/bin/env python3
"""Extract pinned C ABI declarations and exercise named lifetime contracts."""
import argparse
import ctypes as C
import errno
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from hashlib import sha256


HERE = Path(__file__).resolve().parent
ENV = {key: value for key, value in os.environ.items() if not key.startswith("LD_")}
ENV.update({"LC_ALL": "C", "TZ": "UTC"})
FAMILIES = {
    "libc": ("close", "dup"),
    "sqlite": ("sqlite3_open", "sqlite3_prepare_v2", "sqlite3_close", "sqlite3_close_v2",
               "sqlite3_step", "sqlite3_column_int", "sqlite3_finalize", "sqlite3_libversion"),
    "crypto": ("EVP_MD_CTX_new", "EVP_MD_CTX_free", "EVP_DigestInit_ex", "EVP_DigestUpdate",
               "EVP_DigestFinal", "EVP_DigestFinal_ex", "EVP_MD_CTX_get0_md", "EVP_sha256",
               "OpenSSL_version"),
}
REJECTED = {"open": "variadic-signature", "sqlite3_exec": "function-pointer-parameter"}
C_TYPES = {
    "int": "c_int",
    "void": "void",
    "size_t": "c_size_t",
    "unsigned char *": "p_ubyte",
    "unsigned int *": "p_uint",
    "const char *": "c_char_p",
    "const char **": "p_char_p",
    "const void *": "c_void_p",
    "sqlite3 *": "c_void_p",
    "sqlite3 **": "p_void_p",
    "sqlite3_stmt *": "c_void_p",
    "sqlite3_stmt **": "p_void_p",
    "EVP_MD_CTX *": "c_void_p",
    "const EVP_MD_CTX *": "c_void_p",
    "const EVP_MD *": "c_void_p",
    "ENGINE *": "c_void_p",
}
CARRIERS = {
    "c_int": C.c_int, "void": None, "c_size_t": C.c_size_t,
    "p_ubyte": C.POINTER(C.c_ubyte), "p_uint": C.POINTER(C.c_uint),
    "c_char_p": C.c_char_p, "p_char_p": C.POINTER(C.c_char_p),
    "c_void_p": C.c_void_p, "p_void_p": C.POINTER(C.c_void_p),
}
VECTORS = {
    "": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "abc": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    "hello": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
    "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq":
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
}


def run(command, cwd, env=ENV):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result.stdout


def fingerprint(path):
    return sha256(path.read_bytes()).hexdigest()


def replace_origin(path, include, resource):
    if path == HERE / "input.c":
        return "fixture/input.c"
    if path.is_relative_to(include):
        return "sqlite-include/" + str(path.relative_to(include))
    if path.is_relative_to(resource):
        return "compiler-resource/" + str(path.relative_to(resource))
    return path.as_posix()


def clang_inventory(args, root):
    environment = {**ENV, "LD_LIBRARY_PATH": str(args.clang_libdir)} if args.clang_libdir else ENV
    clang = [args.clang, "-target", "x86_64-pc-linux-gnu", "-std=c11",
             "-D_POSIX_C_SOURCE=200809L", "-I", args.sqlite_include]
    version = run([args.clang, "--version"], root, environment).splitlines()[0]
    ast = json.loads(run(clang + ["-Xclang", "-ast-dump=json", "-fsyntax-only", HERE / "input.c"],
                         root, environment))
    dependencies = run(clang + ["-M", HERE / "input.c"], root, environment)
    files = [Path(name) for name in shlex.split(dependencies.replace("\\\n", "").split(":", 1)[1])]
    resources = Path(run([args.clang, "-print-resource-dir"], root, environment).strip()).resolve()
    headers = {replace_origin(path.resolve(), args.sqlite_include, resources): fingerprint(path)
               for path in files}
    assert any(path.endswith("/sqlite3.h") for path in headers)
    assert any(path.endswith("/openssl/evp.h") for path in headers)
    return version, ast["inner"], headers


def declaration(decl):
    qual_type = decl["type"]["qualType"]
    parameters = [child["type"]["qualType"] for child in decl.get("inner", [])
                  if child["kind"] == "ParmVarDecl"]
    if decl.get("variadic"):
        return "variadic-signature"
    if any("(*" in parameter for parameter in parameters):
        return "function-pointer-parameter"
    result = qual_type.split("(", 1)[0].strip()
    return {"declaration_type": qual_type, "result": result, "parameters": parameters,
            "ffi_result": C_TYPES[result], "ffi_parameters": [C_TYPES[type_] for type_ in parameters],
            "attributes": sorted(child["kind"] for child in decl.get("inner", [])
                                 if child["kind"].endswith("Attr"))}


def import_and_resolve(nodes, libs):
    requested = {name for names in FAMILIES.values() for name in names} | set(REJECTED)
    typed = {}
    for node in nodes:
        name = node.get("name")
        if node["kind"] == "FunctionDecl" and name in requested:
            parsed = declaration(node)
            assert name not in typed or typed[name] == parsed, name
            typed[name] = parsed
    assert set(typed) == requested
    rejected = {key: typed.pop(key) for key in REJECTED}
    assert rejected == REJECTED
    bound = {}
    for family, functions in FAMILIES.items():
        library = C.CDLL(str(libs[family]), use_errno=True)
        for function in functions:
            request = typed[function]
            native = getattr(library, function)
            native.restype = CARRIERS[request["ffi_result"]]
            native.argtypes = [CARRIERS[carrier] for carrier in request["ffi_parameters"]]
            request["family"] = family
            bound[function] = native
    try:
        getattr(C.CDLL(str(libs["sqlite"])), "sqlite3_fixture_missing")
    except AttributeError:
        rejected["sqlite3_fixture_missing"] = "missing-symbol"
    else:
        raise AssertionError("missing symbol resolved")
    return typed, bound, rejected


def sqlite_case(ffi, symbol, pending, value):
    db = C.c_void_p()
    assert ffi["sqlite3_open"](b":memory:", C.byref(db)) == 0
    statements = [C.c_void_p() for _ in range(pending)]
    for index, statement in enumerate(statements):
        sql = f"SELECT {value + index}".encode()
        assert ffi["sqlite3_prepare_v2"](db, sql, -1, C.byref(statement), None) == 0
    status = ffi[symbol](db)
    steps = []
    for statement in statements:
        step = ffi["sqlite3_step"](statement)
        result = ffi["sqlite3_column_int"](statement, 0)
        finalized = ffi["sqlite3_finalize"](statement)
        steps.append((step, result, finalized))
    second = ffi["sqlite3_close"](db) if status == 5 else -1
    expected = 5 if symbol == "sqlite3_close" and pending else 0
    assert status == expected and second == (0 if expected == 5 else -1)
    assert steps == [(100, value + index, 0) for index in range(pending)]
    return [status, *[item for step in steps for item in step], second]


def crypto_case(ffi, symbol, message):
    ctx = ffi["EVP_MD_CTX_new"]()
    assert ctx
    raw = message.encode()
    payload = C.create_string_buffer(raw, len(raw) + 1)
    output = (C.c_ubyte * 64)()
    length = C.c_uint()
    try:
        assert ffi["EVP_DigestInit_ex"](ctx, ffi["EVP_sha256"](), None) == 1
        assert ffi["EVP_DigestUpdate"](ctx, payload, len(raw)) == 1
        result = ffi[symbol](ctx, output, C.byref(length))
        digest = bytes(output[:length.value]).hex()
        retained = bool(ffi["EVP_MD_CTX_get0_md"](ctx))
        reinit = ffi["EVP_DigestInit_ex"](ctx, None, None)
        assert result == 1 and digest == VECTORS[message]
        assert retained == (symbol == "EVP_DigestFinal_ex") and int(retained) == reinit
        second = "-"
        if reinit:
            assert ffi["EVP_DigestUpdate"](ctx, payload, len(raw)) == 1
            assert ffi["EVP_DigestFinal_ex"](ctx, output, C.byref(length)) == 1
            second = bytes(output[:length.value]).hex()
            assert second == digest
        return [str(result), digest, str(int(retained)), str(reinit), second]
    finally:
        ffi["EVP_MD_CTX_free"](ctx)


def descriptor_case(ffi, symbol, value):
    reader, writer = os.pipe()
    status = ffi[symbol](reader)
    assert status >= 0
    try:
        os.fstat(reader)
    except OSError as error:
        original, observed_errno = False, error.errno
    else:
        original, observed_errno = True, 0
    read = -1
    if symbol == "dup":
        assert original and status != reader
        os.close(reader)
        os.write(writer, bytes([value]))
        read = os.read(status, 1)[0]
        os.close(status)
    else:
        assert not original and observed_errno == errno.EBADF
    os.close(writer)
    return [int(status > 0), int(original), observed_errno, read]


def samples(ffi, executable, root):
    suites = [
        ("sqlite", ("sqlite3_close", "sqlite3_close_v2"),
         [(pending, value) for pending in range(3) for value in (0, 1, 7, 111)], sqlite_case),
        ("crypto", ("EVP_DigestFinal", "EVP_DigestFinal_ex"),
         [(message,) for message in VECTORS], crypto_case),
        ("libc", ("close", "dup"), [(value,) for value in (0, 1, 42, 255)], descriptor_case),
    ]
    rows = {}
    for family, symbols, inputs, evaluate in suites:
        records = []
        for arguments in inputs:
            meanings = {}
            for symbol in symbols:
                actual = evaluate(ffi, symbol, *arguments)
                native = run([executable, family, symbol, *map(str, arguments)], root).strip().split("\t")
                assert list(map(str, actual)) == native, (symbol, arguments, actual, native)
                meanings[symbol] = actual
            records.append({"inputs": arguments, "native_and_generated": meanings,
                            "same_native_observations": meanings[symbols[0]] == meanings[symbols[1]]})
        rows[family] = records
    return rows


def bind_contracts(typed, libraries, pairs):
    contracts = json.loads((HERE / "contracts.json").read_bytes())
    assert set(contracts) == {symbol for pair in pairs for symbol in pair}

    def key(symbol, contract, native_hash):
        binding = {"symbol": symbol, "c_type": typed[symbol]["declaration_type"],
                   "contract": contract, "library_sha256": native_hash}
        return sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    receipts, controls = {}, {}
    for first, second in pairs:
        for original, alternate in ((first, second), (second, first)):
            artifact = libraries[typed[original]["family"]]
            pinned = key(original, contracts[original], artifact)
            mutations = {
                "alternate-symbol": key(alternate, contracts[original], artifact),
                "alternate-contract": key(original, contracts[alternate], artifact),
                "different-library": key(original, contracts[original], "0" * 64),
            }
            assert all(pinned != changed for changed in mutations.values())
            receipts[original] = pinned
            controls[original] = mutations
    return {"contracts": contracts, "scoped_binding_sha256": receipts, "refused_identity_controls": controls}


def main():
    parser = argparse.ArgumentParser()
    for flag in ("clang", "clang-libdir", "sqlite-include", "sqlite-library", "crypto-library",
                 "libc-library", "out"):
        parser.add_argument(f"--{flag}", type=lambda value: Path(value).resolve(),
                            required=flag != "clang-libdir")
    args = parser.parse_args()
    libs = {"sqlite": args.sqlite_library, "crypto": args.crypto_library, "libc": args.libc_library}
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-header-") as directory:
        root = Path(directory)
        compiler, nodes, headers = clang_inventory(args, root)
        typed, ffi, refusals = import_and_resolve(nodes, libs)
        executable = root / "reference"
        run(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", args.sqlite_include,
             HERE / "consumer.c", args.sqlite_library, args.crypto_library, "-o", executable], root)
        mapped = {}
        for soname, path in re.findall(r"^\s*(\S+) => (\S+) ", run(["ldd", executable], root), re.M):
            mapped[soname] = Path(path).resolve()
        assert set(libs.values()) <= set(mapped.values())
        versions = {
            "clang": compiler, "sqlite": ffi["sqlite3_libversion"]().decode(),
            "openssl": ffi["OpenSSL_version"](0).decode(),
        }
        assert versions["sqlite"] == "3.46.1" and "OpenSSL 3.5.7" in versions["openssl"]
        pairs = [("sqlite3_close", "sqlite3_close_v2"), ("EVP_DigestFinal", "EVP_DigestFinal_ex"),
                 ("close", "dup")]
        for first, second in pairs:
            assert typed[first]["declaration_type"] == typed[second]["declaration_type"]
        observations = samples(ffi, executable, root)
        mismatches = {family: sum(not row["same_native_observations"] for row in records)
                      for family, records in observations.items()}
        assert mismatches == {"sqlite": 8, "crypto": 4, "libc": 4}
        library_hashes = {name: fingerprint(path) for name, path in libs.items()}
        result = {"tool_versions": versions, "headers_sha256": headers, "declarations": typed,
                  "libraries_sha256": library_hashes, "contract_binding": bind_contracts(typed, library_hashes, pairs),
                  "refusals": refusals, "same_signature_pairs": pairs,
                  "behaviors": observations, "signature_only_wrong_pairs": mismatches}
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
