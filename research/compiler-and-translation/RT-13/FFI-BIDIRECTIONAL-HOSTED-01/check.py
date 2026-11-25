"""Check independent C and LLVM FFI consumers and providers for all hosted target cells."""

import argparse
import ctypes
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
MATRIX = runpy.run_path(str(HERE.parent / "FFI-HOSTED-PROFILE-MATRIX-01/check.py"))["PROFILES"]
BASE_EVIDENCE = HERE.parent / "FFI-HOSTED-PROFILE-MATRIX-01/evidence.json"
PROFILE_LEDGER = json.loads(BASE_EVIDENCE.read_text())["profiles"]
U32MAX = (1 << 32) - 1
INPUTS = tuple(product((0, 1, (1 << 31) - 1, 1 << 31, U32MAX - 1, U32MAX), (0, 1, 2, U32MAX)))


def run(args, cwd=None):
    return subprocess.check_output(args, text=True, timeout=30, cwd=cwd)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def host_execute(library):
    probe = ctypes.CDLL(str(library)).ffi_observe
    word = ctypes.c_uint32
    probe.argtypes = [ctypes.POINTER(word), word, ctypes.POINTER(word)]
    probe.restype = word
    rows = []
    for before, delta in INPUTS:
        value = word(before)
        trace = (word * 2)(17, 19)
        status = probe(ctypes.byref(value), delta, trace)
        rows.append([status, value.value, *trace])
    print(json.dumps(rows))


def host_expected():
    rows = []
    for before, delta in INPUTS:
        next_value = before + delta
        rows.append([1, before, 17, 19] if next_value > U32MAX else [0, next_value, before, next_value])
    return rows


def target_flags(target, fmt):
    code = ["-mno-incremental-linker-compatible"] if fmt == "COFF" else ["-fPIC"]
    return [f"--target={target}", "-O2", "-ffreestanding", "-fno-builtin", *code]


def compile_role(options, work, target, fmt, kind, language, wrong=False):
    output = work / f"{kind}.o"
    flags = target_flags(target, fmt)
    if language == "c":
        mode = ["-DPROVIDER"] if kind == "provider" else []
        if wrong:
            mode += ["-DWRONG_SYMBOL"]
        run([options.clang, *flags, "-std=c17", "-Wall", "-Wextra", "-Werror", *mode,
             "-c", HERE / "portable.c", "-o", output])
    else:
        template = (HERE / f"{kind}.ll.in").read_text()
        source = work / f"{kind}.ll"
        source.write_text(template.replace("@TRIPLE@", target).replace("@EXPORT@", "dllexport" if fmt == "COFF" else ""))
        run([options.clang, *flags, "-Wno-override-module", "-c", source, "-o", output])
    return output


def dependency_and_link(options, name, fmt, work, stem, inputs):
    if fmt == "ELF":
        out = work / f"lib{stem}.so"
        command = [options.elf, "-shared", "--no-undefined", "--build-id=none", "-soname", out.name,
                   "-rpath", "$ORIGIN", "-o", str(out)]
        return out, out, [*command, *(str(item) for item in inputs)]
    if fmt == "Mach-O":
        out = work / f"lib{stem}.dylib"
        arch = "x86_64" if name.endswith("x86_64") else "arm64"
        apple_platform, version = ("ios", "16.0") if name.startswith("ios-") else ("macos", "13.0")
        command = [options.macho, "-dylib", "-arch", arch, "-platform_version", apple_platform, version, version,
                   "-no_uuid", "-install_name", f"@rpath/{out.name}", "-o", str(out)]
        return out, out, [*command, *(str(item) for item in inputs)]
    out = work / f"{stem}.dll"
    archive = work / f"{stem}.lib"
    cpu = "x64" if name.endswith("x86_64") else "arm64"
    command = [options.coff, "/dll", "/noentry", "/nodefaultlib", f"/machine:{cpu}", "/timestamp:0",
               f"/out:{out}", f"/implib:{archive}"]
    return out, archive, [*command, *(str(item) for item in inputs)]


def confirm_consumer(options, name, path, fmt, dynamic):
    details = run([options.readobj, "--file-headers", path])
    assert f"Format: {PROFILE_LEDGER[name]["format"]}" in details
    if fmt == "COFF":
        flags = ["--coff-imports", "--coff-exports"]
        linkage = run([options.readobj, *flags, path])
        assert (bool(re.search(r"(?im)^\s*Name: provider.dll$", linkage))) == dynamic
        assert "Name: ffi_observe" in linkage
    else:
        linkage = run([options.readobj, "--needed-libs", path])
        listed = re.search(r"NeededLibraries \[([^]]*)\]", linkage)[1].split()
        assert any("libprovider." in library for library in listed) == dynamic


def cases_for(options, name, target, fmt, work):
    rows = {}
    for provider_language, caller_language in (("c", "llvm"), ("llvm", "c")):
        route = work / f"{name}-{provider_language}"
        route.mkdir()
        provider = compile_role(options, route, target, fmt, "provider", provider_language)
        consumer = compile_role(options, route, target, fmt, "consumer", caller_language)
        archive = route / "provider.a"
        run([options.ar, "rcs", archive, provider])
        shared, imported, build_provider = dependency_and_link(options, name, fmt, route, "provider", [provider])
        run(build_provider, cwd=route)
        results = {}
        for mode, input_file in (("static", archive), ("shared", imported)):
            binary, _, build_consumer = dependency_and_link(options, name, fmt, route, f"consumer-{mode}",
                                                               [consumer, input_file])
            run(build_consumer, cwd=route)
            confirm_consumer(options, name, binary, fmt, mode == "shared")
            result = {"artifact_sha256": digest(binary), "provider_sha256": digest(input_file)}
            if name == "linux-x86_64":
                observed = json.loads(run([sys.executable, "-B", __file__, "execute", binary]))
                assert observed == host_expected()
                result["native_observations"] = len(observed)
            results[mode] = result
        rows[f"{provider_language}-to-{caller_language}"] = results
        if caller_language == "llvm":
            wrong = compile_role(options, route, target, fmt, "consumer", "c", wrong=True)
            _, _, wrong_link = dependency_and_link(options, name, fmt, route, "wrong", [wrong, archive])
            refused = subprocess.run(wrong_link, cwd=route, text=True, capture_output=True, timeout=30, check=False)
            assert refused.returncode and "missing_fixture_step" in refused.stderr
    return {"provider_consumer": rows, "wrong_symbol_refused": True, "target": target, "format": fmt}


def check(options):
    builds = {}
    with TemporaryDirectory() as directory:
        for name, target, fmt, *_ in MATRIX:
            builds[name] = cases_for(options, name, target, fmt, Path(directory))
    assert len(builds) == 16
    inputs = ("portable.c", "provider.ll.in", "consumer.ll.in", "check.py")
    return {"matrix_sha256": digest(BASE_EVIDENCE), "profiles": builds,
            "input_sha256": {name: digest(HERE / name) for name in inputs},
            "native_reference": host_expected(), "native_total": len(INPUTS) * 4,
            "tools": {name: run([getattr(options, name), "--version"]).splitlines()[0]
                      for name in ("clang", "elf", "macho", "coff", "readobj", "ar")}}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "execute":
        host_execute(Path(sys.argv[2]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        for tool in ("clang", "elf", "macho", "coff", "readobj", "ar"):
            parser.add_argument(f"--{tool}", required=True)
        print(json.dumps(check(parser.parse_args()), indent=2, sort_keys=True))
