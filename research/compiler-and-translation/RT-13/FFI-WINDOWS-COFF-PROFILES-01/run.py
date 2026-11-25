"""Build two Windows COFF profiles with distinct static and import library closure."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
PROFILES = {
    "x64": ("x86_64-pc-windows-msvc", "X64", "IMAGE_FILE_MACHINE_AMD64"),
    "arm64": ("aarch64-pc-windows-msvc", "ARM64", "IMAGE_FILE_MACHINE_ARM64"),
}
IMPORT_MACHINE = {"x64": 0x8664, "arm64": 0xaa64}
SOURCE = ("api.h", "provider.c", "consumer.c")


def run(*command, cwd=None, checked=True):
    return subprocess.run(command, cwd=cwd, check=checked, text=True, capture_output=True, timeout=30)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def inspect(args, path, machine, *, exports=(), libraries=()):
    data = run(args.readobj, "--file-headers", "--coff-exports", "--coff-imports", path).stdout
    assert f"Machine: {machine}" in data
    resolved_exports = re.findall(r"(?m)^\s+Name: (\w+)\s*$", data)
    for symbol in exports:
        assert symbol in resolved_exports
    observed = re.findall(r"Name: ([-\w.]+\.dll)\b", data)
    assert observed == list(libraries), (path, observed)
    imported_symbols = re.findall(r"Symbol: (\w+)\b", data)
    assert imported_symbols == (["record_step"] if libraries else [])
    return {
        "size_bytes": path.stat().st_size, "sha256": digest(path), "machine": machine,
        "import_libraries": observed, "import_symbols": imported_symbols,
        "export_symbols": list(exports),
    }



def import_record(path):
    archive = path.read_bytes()
    assert archive.startswith(b"!<arch>\n")
    cursor = 8
    imports = []
    while cursor < len(archive):
        header = archive[cursor:cursor + 60]
        assert header[58:] == b"`\n"
        size = int(header[48:58])
        content = archive[cursor + 60:cursor + 60 + size]
        if content[:4] == b"\x00\x00\xff\xff":
            machine = struct.unpack_from("<H", content, 6)[0]
            symbol, library, *_ = content[20:].split(b"\0")
            imports.append((machine, symbol.decode("ascii"), library.decode("ascii")))
        cursor += 60 + size + (size % 2)
    assert len(imports) == 1
    return imports[0]

def build(args, root, target, machine):
    for name in SOURCE:
        shutil.copyfile(HERE / name, root / name)
    profile = [args.clang, f"--target={target}", "-std=c17", "-ffreestanding", "-fno-builtin",
               "-Wall", "-Wextra", "-Werror", "-mno-incremental-linker-compatible", "-O2"]
    for source, output, option in (
        ("provider.c", "provider-static.obj", []),
        ("provider.c", "provider-dll.obj", ["-DEXPORT_DLL"]),
        ("provider.c", "wrong-dll.obj", ["-DEXPORT_DLL", "-DWRONG_EXPORT"]),
        ("consumer.c", "consumer-static.obj", []),
        ("consumer.c", "consumer-shared.obj", ["-DIMPORT_DLL"]),
    ):
        run(*profile, *option, "-c", source, "-o", output, cwd=root)
        assert struct.unpack_from("<I", (root / output).read_bytes(), 4)[0] == 0
    run(*profile, "-S", "-emit-llvm", "provider.c", "-o", "provider.ll", cwd=root)
    ir = (root / "provider.ll").read_text(encoding="utf-8")
    signature = next(line.strip() for line in ir.splitlines() if line.startswith("define ") and "@record_step" in line)
    link = [args.linker, f"/machine:{machine}", "/nodefaultlib", "/timestamp:0"]
    run(*link, "/dll", "/noentry", "/out:provider.dll", "/implib:provider-import.lib",
        "provider-dll.obj", cwd=root)
    run(*link, "/dll", "/noentry", "/out:wrong.dll", "/implib:wrong-import.lib",
        "wrong-dll.obj", cwd=root)
    run(args.ar, "rcsD", "provider-static.lib", "provider-static.obj", cwd=root)
    main = [*link, "/subsystem:console", "/entry:mainCRTStartup"]
    for output, consumer, provider in (
        ("static.exe", "consumer-static.obj", "provider-static.lib"),
        ("shared.exe", "consumer-shared.obj", "provider-import.lib"),
        ("static-compiled-imported.exe", "consumer-static.obj", "provider-import.lib"),
    ):
        run(*main, f"/out:{output}", consumer, provider, cwd=root)
    missing = (
        ("no_requested_export", "wrong-import.lib"),
        ("static_archive_for_dllimport", "provider-static.lib"),
    )
    for name, wrong in missing:
        result = run(*main, f"/out:{name}.exe", "consumer-shared.obj", wrong, cwd=root, checked=False)
        assert result.returncode and "undefined symbol" in result.stderr and "record_step" in result.stderr
        assert not (root / f"{name}.exe").exists()
    assert run(args.ar, "t", "provider-static.lib", cwd=root).stdout.splitlines() == ["provider-static.obj"]
    return signature


def collect(args, temp):
    records = {}
    for name, (target, machine, coff_magic) in PROFILES.items():
        root = temp / name
        root.mkdir()
        signature = build(args, root, target, machine)
        if name == "x64":
            assert "sret(" in signature and signature.startswith("define dso_local void")
        else:
            assert "sret(" not in signature and "[2 x i64]" in signature
        metadata = {
            "provider-dll": inspect(args, root / "provider.dll", coff_magic, exports=("record_step",)),
            "static-consumer": inspect(args, root / "static.exe", coff_magic),
            "load-time-dll-consumer": inspect(args, root / "shared.exe", coff_magic, libraries=("provider.dll",)),
            "static-compiled-consumer-with-import-library": inspect(
                args, root / "static-compiled-imported.exe", coff_magic, libraries=("provider.dll",)),
        }
        archive_machine, symbol, library = import_record(root / "provider-import.lib")
        assert (archive_machine, symbol, library) == (IMPORT_MACHINE[name], "record_step", "provider.dll")
        records[name] = {
            "target": target, "executable_evidence": "cross-build-only",
            "import_record": {"machine": hex(archive_machine), "symbol": symbol, "dll": library},
            "call_lowering": signature,
            "artifacts": metadata,
            "static_archive_sha256": digest(root / "provider-static.lib"),
            "import_library_sha256": digest(root / "provider-import.lib"),
            "missing_symbol_and_wrong_library_mode": ["refused", "refused"],
        }

    for name, (_, machine, coff_magic) in PROFILES.items():
        other = next(key for key in PROFILES if key != name)
        root = temp / name
        controls = {}
        for mode in ("static", "import"):
            out = root / f"wrong-machine-{mode}.exe"
            consumer = "consumer-static.obj" if mode == "static" else "consumer-shared.obj"
            result = run(
                args.linker, f"/machine:{machine}", "/nodefaultlib", "/timestamp:0", "/subsystem:console",
                "/entry:mainCRTStartup", f"/out:{out.name}", consumer,
                temp / other / f"provider-{mode}.lib", cwd=root, checked=False,
            )
            if result.returncode:
                assert "machine type" in result.stderr and not out.exists(), result.stderr
                controls[mode] = {"link": "refused"}
            else:
                assert mode == "import"
                assert import_record(temp / other / "provider-import.lib")[0] != IMPORT_MACHINE[name]
                assert records[other]["artifacts"]["provider-dll"]["machine"] != coff_magic
                wrong_import = inspect(args, out, coff_magic, libraries=("provider.dll",))
                assert wrong_import["sha256"] == records[name]["artifacts"]["load-time-dll-consumer"]["sha256"]
                controls[mode] = {
                    "link": "accepted", "artifact": wrong_import,
                    "exact_package_gate": "refused", "same_executable_bytes_as_matching_import": True,
                }
        assert controls["static"]["link"] == "refused"
        records[name]["wrong_architecture_controls"] = controls
    return {
        "profiles": records,
        "tools": {
            name: run(getattr(args, name), "--version").stdout.splitlines()[0]
            for name in ("clang", "linker", "ar", "readobj")
        },
        "source_hashes": {name: digest(HERE / name) for name in ("run.py", *SOURCE)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, binary in (
        ("clang", "clang"), ("linker", "lld-link"), ("ar", "llvm-ar"), ("readobj", "llvm-readobj"),
    ):
        parser.add_argument(f"--{name}", default=binary)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-windows-coff-") as session:
        evidence = collect(args, Path(session))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
