"""Build and run the draft syscall packages through an independent MCP client."""

import argparse
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile

import json

from mcp_e2e import read_object, server

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
NATIVE_EXPORT = re.compile(r"pub unsafe fn llmlang_syscall_(\w+)\s*\(")
FILE_LIMIT = 4096


def read_package(path):
    return {file.name: file.read_bytes() for file in sorted(path.iterdir())}


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
        dependency = EXAMPLES / "linux.syscalls"
        original_dependency = read_package(dependency)
        programs = sorted(EXAMPLES.glob("000[4-8]-syscall-*"))
        assert len(programs) == 5
        for package in [dependency, *programs]:
            before = read_package(package)
            imported = client.call("import_package", {"path": str(package)})
            assert imported["verification_status"] == "unchecked"
            build = client.call("build_package", {
                "snapshot_id": imported["snapshot_id"], "target": "linux-x86_64",
            })
            assert build["verification_status"] == "unchecked"
            artifact = Path(build["artifact"])
            assert artifact.is_file() and artifact.is_relative_to(Path(directory, "state", "artifacts"))
            generated = set(NATIVE_EXPORT.findall(capture.read_text()))
            assert not list(compile_tmp.iterdir()), "temporary source directory survived the build"
            assert read_package(package) == before, package
            if package == dependency:
                raw_functions = json.loads((package / "functions.json").read_bytes())
                assert len(raw_functions) == 358
                assert all(row["canonicalBody"]["stringValue"].startswith("{\n")
                           for row in raw_functions)
                assert all("builtin__syscall(" in row["canonicalBody"]["stringValue"]
                           for row in raw_functions)
                assert artifact.suffix == ".rlib"
                assert len(generated) == 355
                assert {"rt_sigreturn", "vfork", "uretprobe"}.isdisjoint(generated)
                continue

            source = (package / "main.llmlang").read_text()
            body = source[source.index("{"):].rstrip()
            main, = json.loads((package / "functions.json").read_bytes())
            assert main["canonicalBody"] == {"stringValue": body}
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
            imports = {line.rsplit(".", 1)[-1] for line in source.splitlines()
                       if line.startswith("import linux.syscalls.")}
            assert generated == imports, (package, generated, imports)
            payload = bytes(range(256)) * 83 + b"\x00\xff"
            if package.name == "0004-syscall-echo":
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
        assert read_package(dependency) == original_dependency


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        exercise(args.server.resolve(), directory)
    print("Native package build, reachability, execution, and read-only package checks passed")
