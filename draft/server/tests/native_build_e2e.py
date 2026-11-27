"""Build and run the draft native packages through an independent MCP client."""

import argparse
import os
from pathlib import Path
import re
import resource
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile

import json

from mcp_e2e import read_object, server

DRAFT = Path(__file__).resolve().parents[2]
EXAMPLES = DRAFT / "examples"
NATIVE_EXPORT = re.compile(r"pub unsafe fn llmlang_syscall_(\w+)\s*\(")
FILE_LIMIT = 4096
CLI_CASES = (
    DRAFT.parent / "research/language-design/PROTOTYPES/CLI-WORKLOADS-01/run.py"
)


def read_package(path):
    return {file.name: file.read_bytes() for file in sorted(path.iterdir())}


def selected_exports(files):
    version = json.loads(files["package.json"])["selection"]["version"]
    version_row, = (row for row in json.loads(files["versions.json"]) if row["version"] == version)
    names = {row["interfaceHash"]: row["name"] for row in json.loads(files["interfaces.json"])}
    return {names[row["interfaceHash"]]: row["implHash"]
            for row in json.loads(files["bindings.json"])
            if row["versionHash"] == version_row["versionHash"]}


def execute(artifact, *arguments, data=b"", errno=None, stdout=subprocess.PIPE, preexec_fn=None):
    result = subprocess.run(
        [artifact, *arguments], input=data, stdout=stdout, stderr=subprocess.PIPE,
        preexec_fn=preexec_fn, timeout=10,
    )
    expected = b"" if errno is None else f"Error: Kernel(Errno({errno}))\n".encode()
    assert result.stderr == expected, result
    return result.returncode, result.stdout


def limit_file_size():
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))


def check_calculator(artifact):
    corpus = runpy.run_path(str(CLI_CASES))
    cases = [case for case in corpus["CASES"] if case.program == "calculator"]
    cases.extend([
        corpus["calculation"]("calculator-buffer-boundary", b" " * 4094 + b"12 + 30\n", b"42\n"),
        corpus["calculation"]("calculator-first-record", b"20 / 4\n1 / 0\n", b"5\n"),
        corpus["calculation"]("calculator-split-expression", b"1 +\n2\n", stderr=b"invalid input\n"),
    ])
    for case in cases:
        result = corpus["run_case"]([artifact], case)
        assert (result.returncode, result.stdout, result.stderr) == (
            0 if case.success else 1, case.stdout, case.stderr,
        ), (case.identifier, result)
    with open("/dev/full", "wb") as full:
        assert execute(artifact, data=b"1 + 2\n", stdout=full) == (1, None)


def check_executable(artifact, debug, freestanding):
    assert debug.is_file() and debug.parent == artifact.parent
    sections = subprocess.check_output(["readelf", "-SW", artifact], text=True)
    assert ".debug_info" not in sections and ".symtab" not in sections, sections
    debug_sections = subprocess.check_output(
        ["readelf", "-SW", debug], stderr=subprocess.PIPE, text=True,
    )
    assert ".debug_info" in debug_sections and ".symtab" in debug_sections, debug_sections
    link = subprocess.check_output(["readelf", "-p", ".gnu_debuglink", artifact])
    assert os.fsencode(debug.name) in link, link
    if freestanding:
        headers = subprocess.check_output(["readelf", "-lW", artifact], text=True)
        assert "INTERP" not in headers and "DYNAMIC" not in headers, headers
        symbols = subprocess.check_output(["readelf", "-sW", debug], text=True)
        assert re.search(r"\b_start$", symbols, re.M) and "lang_start_internal" not in symbols


def check_stdlib(artifact, exports, directory):
    assert set(exports) == {
        "stdlib.write", "stdlib.syscall", "stdlib.errno_message", "stdlib.cstring_from_bytes",
        "stdlib.trap", "stdlib.sockaddr_in_loopback", "stdlib.sockaddr_in_size",
    }, exports
    output = Path(directory, "utf8-output")
    harness = Path(directory, "stdlib-test.rs")
    harness.write_text(
        "use std::{fs::File, os::fd::AsRawFd};\n"
        "fn main() {\n"
        "    let output = File::create(std::env::args_os().nth(1).unwrap()).unwrap();\n"
        f"    use llmlang_native::{exports['stdlib.write']} as write;\n"
        f"    use llmlang_native::{exports['stdlib.syscall']} as syscall;\n"
        '    assert_eq!(write(output.as_raw_fd(), "Привет!\\n"), Ok(()));\n'
        '    assert_eq!(write(-1, "error"), Err(9));\n'
        "    assert_eq!(unsafe { syscall(39, 0, 0, 0, 0, 0, 0) }, std::process::id() as isize);\n"
        "    assert_eq!(unsafe { syscall(15, 0, 0, 0, 0, 0, 0) }, -38);\n"
        "}\n",
        encoding="utf-8",
    )
    program = Path(directory, "stdlib-test")
    subprocess.run(
        [os.environ["LLMLANG_REAL_RUSTC"], "--edition=2021", "--crate-name", "stdlib_test",
         "--extern", f"llmlang_native={artifact}", "-o", program, harness],
        check=True, timeout=30,
    )
    assert execute(program, output) == (0, b"")
    assert output.read_bytes() == "Привет!\n".encode()


def exercise(executable, directory):
    compiler = Path(directory, "rustc")
    capture = Path(directory, "captured.rs")
    compile_tmp = Path(directory, "compiler-tmp")
    compile_tmp.mkdir()
    compiler.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "source = Path(sys.argv[-1]).resolve()\n"
        "assert source.parent.parent == Path(os.environ['TMPDIR']).resolve()\n"
        "Path(os.environ['LLMLANG_CAPTURE']).write_bytes(source.read_bytes())\n"
        "compiler = os.environ['LLMLANG_REAL_RUSTC']\n"
        "os.execv(compiler, [compiler, *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    compiler.chmod(0o700)
    os.environ["LLMLANG_REAL_RUSTC"] = shutil.which(os.environ.get("RUSTC", "rustc"))
    os.environ["LLMLANG_CAPTURE"] = str(capture)
    os.environ["RUSTC"] = str(compiler)
    os.environ["TMPDIR"] = str(compile_tmp)

    with server(executable, Path(directory, "state"), "python3") as client:
        builtin = DRAFT / "builtin"
        stdlib = DRAFT / "stdlib"
        dependency = EXAMPLES / "linux.syscalls"
        hello = EXAMPLES / "0001-hello-world"
        calculator = EXAMPLES / "0003-calculator"
        syscall_hello = EXAMPLES / "0009-syscall-hello-world"
        original_dependencies = {path: read_package(path) for path in (builtin, stdlib, dependency)}
        programs = sorted(EXAMPLES.glob("000[4-8]-syscall-*"))
        assert len(programs) == 5
        missing = client.call("import_package", {"path": str(stdlib)}, succeeds=False)
        assert missing["code"] == "MissingDependency", missing
        for package in [builtin, stdlib, dependency, hello, calculator, syscall_hello, *programs]:
            before = read_package(package)
            assert json.loads(before["manifest.json"])["profile"] == "llmlang.spg.tables.v5"
            assert before["functions.dump"].startswith(b"LLSPG\x05\r\n")
            imported = client.call("import_package", {"path": str(package)})
            assert imported["verification_status"] == "unchecked"
            build = client.call("build_package", {
                "snapshot_id": imported["snapshot_id"], "target": "linux-x86_64",
            })
            assert build["verification_status"] == "unchecked"
            artifact = Path(build["artifact"])
            assert artifact.is_file() and artifact.is_relative_to(Path(directory, "state", "artifacts"))
            generated_source = capture.read_text()
            generated = set(NATIVE_EXPORT.findall(generated_source))
            assert not list(compile_tmp.iterdir()), "temporary source directory survived the build"
            assert read_package(package) == before, package
            if package in (builtin, stdlib, dependency):
                assert "debug_artifact" not in build, build
            else:
                freestanding = package.name in {
                    "0006-syscall-pipe-poll", "0008-syscall-tcp-echo", "0009-syscall-hello-world",
                }
                assert ("#![no_std]" in generated_source) == freestanding, package
                check_executable(artifact, Path(build["debug_artifact"]), freestanding)
            if package == builtin:
                assert artifact.suffix == ".rlib" and not generated
                builtin_symbols = build["exports"]
                builtin_exports = selected_exports(before)
                assert set(builtin_symbols) == set(builtin_exports)
                assert all("builtin__" in row["canonicalBody"]
                           for row in json.loads(before["functions.json"]))
                continue

            reachable_builtin = {name for name, symbol in builtin_symbols.items()
                                 if re.search(rf"\bfn {symbol}\s*\(", generated_source)}
            if package == stdlib:
                assert artifact.suffix == ".rlib" and not generated
                check_stdlib(artifact, build["exports"], directory)
                stdlib_symbols = build["exports"]
                stdlib_exports = selected_exports(before)
                assert reachable_builtin == set(builtin_symbols)
                assert set(builtin_exports) == {
                    name.replace("stdlib.", "builtin.", 1) for name in stdlib_exports
                }
                assert all("builtin__" not in row["canonicalBody"] and "builtin::" in row["canonicalBody"]
                           for row in json.loads(before["functions.json"]))
                obligations = json.loads(before["verification_obligations.json"])
                assert {(row["callerImplHash"], row["calleeImplHash"]) for row in obligations} == {
                    (impl, builtin_exports[name.replace("stdlib.", "builtin.", 1)])
                    for name, impl in stdlib_exports.items()
                }
                syscall_impl = stdlib_exports["stdlib.syscall"]
                continue

            reachable_stdlib = {name for name, symbol in stdlib_symbols.items()
                                if re.search(rf"\bfn {symbol}\s*\(", generated_source)}
            if package == dependency:
                assert reachable_stdlib == {"stdlib.syscall"}
                assert reachable_builtin == {"builtin.syscall"}
                raw_functions = json.loads((package / "functions.json").read_bytes())
                assert len(raw_functions) == 358
                assert all(row["canonicalBody"].startswith("{\n")
                           for row in raw_functions)
                assert all("stdlib::syscall(" in row["canonicalBody"]
                           for row in raw_functions)
                assert all("builtin__" not in row["canonicalBody"] for row in raw_functions)
                obligations = json.loads((package / "verification_obligations.json").read_bytes())
                assert {row["callerImplHash"] for row in obligations
                        if row["calleeImplHash"] == syscall_impl} == {
                    row["implHash"] for row in raw_functions}
                stdlib_trap = stdlib_symbols["stdlib.trap"].replace("llmlang_source_", "sha256:")
                restorer, = (row["implHash"] for row in raw_functions
                             if "stdlib::trap()" in row["canonicalBody"])
                extra, = (row for row in obligations if row["calleeImplHash"] != syscall_impl)
                assert (extra["callerImplHash"], extra["calleeImplHash"]) == (restorer, stdlib_trap)
                assert artifact.suffix == ".rlib"
                assert len(generated) == 355
                assert {"rt_sigreturn", "vfork", "uretprobe"}.isdisjoint(generated)
                linux_exports = selected_exports(before)
                continue

            main, = json.loads(before["functions.json"])
            assert selected_exports(before) == {f"{package.name}.main": main["implHash"]}
            body = main["canonicalBody"]
            assert isinstance(body, str) and body.startswith("{") and body.endswith("}")
            assert "builtin__" not in body
            assert "typedSignature" not in main
            signatures = json.loads((package / "function_signatures.json").read_bytes())
            signature, = signatures
            assert main["functionSignatureHash"] == signature["functionSignatureHash"]
            assert signature["functionSignatureContent"].endswith(" -> ExitStatus")
            obligations = json.loads((package / "verification_obligations.json").read_bytes())
            assert all(row["kind"] == "call_compatibility"
                       and row["callerImplHash"] == main["implHash"] for row in obligations)
            main_object = read_object(
                client, f"llmlang://snapshot/{imported['snapshot_id']}/object/functions/{main['implHash']}",
            )
            assert main_object["row"]["canonical_body"] == body
            assert {link["uri"].rsplit("/", 1)[-1].replace("%3A", ":")
                    for link in main_object["outgoing"] if link["relation"] == "Callee"} == {
                        row["calleeImplHash"] for row in obligations
                    }
            callee_pins = {row["calleeImplHash"] for row in obligations}
            linux_calls = {name.rsplit(".", 1)[-1] for name, impl in linux_exports.items()
                           if impl in callee_pins}
            stdlib_calls = {name for name, impl in stdlib_exports.items() if impl in callee_pins}
            assert len(linux_calls) + len(stdlib_calls) == len(callee_pins), (package, obligations)
            assert generated == linux_calls, (package, generated, linux_calls)
            expected_stdlib = stdlib_calls | ({"stdlib.syscall"} if linux_calls else set())
            assert reachable_stdlib == expected_stdlib, (package, reachable_stdlib, expected_stdlib)
            expected_builtin = {name.replace("stdlib.", "builtin.", 1) for name in expected_stdlib}
            assert reachable_builtin == expected_builtin, (package, reachable_builtin, expected_builtin)
            payload = bytes(range(256)) * 83 + b"\x00\xff"
            if package == hello:
                assert callee_pins == {stdlib_exports["stdlib.write"]}
            elif package == syscall_hello:
                assert callee_pins == {linux_exports["linux.syscalls.write"]}
            if package in (hello, syscall_hello):
                assert execute(artifact) == (0, b"Hello, world!\n")
                assert execute(artifact, "ignored", data=b"ignored") == (0, b"Hello, world!\n")
                with open("/dev/full", "wb") as full:
                    assert execute(artifact, stdout=full) == (1, None)
                read_end, write_end = os.pipe()
                os.close(read_end)
                try:
                    assert execute(artifact, stdout=write_end) == (1, None)
                finally:
                    os.close(write_end)
            elif package == calculator:
                assert linux_calls == {"read", "write"}
                check_calculator(artifact)
            elif package.name == "0004-syscall-echo":
                errno_impl = stdlib_symbols["stdlib.errno_message"].replace("llmlang_source_", "sha256:")
                wrapper = next(link for link in main_object["outgoing"]
                               if link["relation"] == "Callee"
                               and link["uri"].rsplit("/", 1)[-1].replace("%3A", ":") != errno_impl)
                wrapper_object = read_object(client, wrapper["uri"])
                assert any(link["relation"] == "Callee"
                           and link["uri"].rsplit("/", 1)[-1].replace("%3A", ":") == syscall_impl
                           for link in wrapper_object["outgoing"])
                assert execute(artifact) == (0, b"")
                assert execute(artifact, data=payload) == (0, payload)
                read_end, write_end = os.pipe()
                os.close(read_end)
                try:
                    assert execute(artifact, data=b"broken output", stdout=write_end, errno=32) == (1, None)
                finally:
                    os.close(write_end)
            elif package.name == "0005-syscall-copy":
                path = Path(directory, "source")
                path.write_bytes(payload)
                dest = Path(directory, "destination")
                assert execute(artifact, path, dest) == (0, b"")
                assert dest.read_bytes() == payload
                assert execute(artifact, path, dest, errno=17) == (1, b"")
                assert dest.read_bytes() == payload
                assert execute(artifact, path, Path(directory, "missing", "destination"), errno=2) == (1, b"")
                limited = Path(directory, "limited")
                assert execute(artifact, path, limited, errno=27, preexec_fn=limit_file_size) == (1, b"")
                assert limited.read_bytes() == payload[:FILE_LIMIT]
                path.write_bytes(b"")
                empty = Path(directory, "empty")
                assert execute(artifact, path, empty) == (0, b"")
                assert empty.read_bytes() == b""
            elif package.name == "0007-syscall-child":
                assert execute(artifact) == (23, b"")
            elif package.name == "0008-syscall-tcp-echo":
                assert execute(artifact) == (0, b"LLMLang TCP echo\x00\xff\n")
            else:
                assert execute(artifact) == (0, b"")
        assert all(read_package(path) == original for path, original in original_dependencies.items())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        exercise(args.server.resolve(), directory)
    print("Native package build, reachability, execution, and read-only package checks passed")
