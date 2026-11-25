"""Cross-build freestanding Mach-O libraries and verify the Apple deployment metadata."""

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
FILES = ("abi.h", "provider.c", "consumer.c")
PROFILES = {
    "macos-arm64": ("arm64-apple-macos13.0", "arm64", "macos", "13.0", "14.0"),
    "macos-x64": ("x86_64-apple-macos13.0", "x86_64", "macos", "13.0", "14.0"),
    "ios-arm64": ("arm64-apple-ios16.0", "arm64", "ios", "16.0", "17.0"),
}
PROVIDER = "@rpath/libspan.dylib"


def command(*args, cwd=None, checked=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=checked, timeout=30)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def inspect(args, artifact, arch, platform, minos, install_name, dependence, export):
    result = command(args.objdump, "--macho", "--private-headers", artifact).stdout
    assert re.search(r"(?m)^\s*platform\s+" + platform + r"\s*$", result)
    assert re.search(r"(?m)^\s*minos\s+" + re.escape(minos) + r"\s*$", result)
    assert re.search(r"(?m)^\s*sdk\s+" + re.escape(minos) + r"\s*$", result)
    magic, cpu = struct.unpack_from("<II", artifact.read_bytes())
    assert magic == 0xfeedfacf and cpu == {"arm64": 0x0100000c, "x86_64": 0x01000007}[arch]
    ids = re.findall(r"(?m)^\s*cmd LC_ID_DYLIB\s*\n\s*cmdsize.*\n\s*name (\S+)", result)
    assert ids == [install_name]
    linked = re.findall(r"(?m)^\s*cmd LC_LOAD_DYLIB\s*\n\s*cmdsize.*\n\s*name (\S+)", result)
    assert linked == list(dependence)
    if dependence:
        assert "LC_DYLD_CHAINED_FIXUPS" in result
        assert "LC_RPATH" in result and "@loader_path" in result
    names = command(args.objdump, "--macho", "--exports-trie", artifact).stdout
    assert export in names
    assert "LC_UUID" not in result
    return {
        "target_architecture": arch, "platform": platform, "minimum": minos,
        "declared_sdk_load_command": minos, "install_name": install_name, "dependence": linked,
        "export": export, "sha256": digest(artifact), "size_bytes": artifact.stat().st_size,
    }



def admits(provider, arch, platform, minos, expected_install_name):
    return (
        provider["target_architecture"] == arch
        and provider["platform"] == platform
        and provider["install_name"] == expected_install_name
        and tuple(map(int, provider["minimum"].split("."))) <= tuple(map(int, minos.split(".")))
    )

def linker(args, arch, platform, minos):
    return [args.linker, "-dylib", "-arch", arch, "-platform_version", platform,
            minos, minos, "-no_uuid", "-fixup_chains"]


def collect(args, root):
    profiles = {}
    for profile, (triple, arch, platform, minos, later) in PROFILES.items():
        work = root / profile
        work.mkdir()
        for name in FILES:
            shutil.copyfile(HERE / name, work / name)
        cflags = [args.clang, f"--target={triple}", "-std=c17", "-ffreestanding",
                  "-fno-builtin", "-Wall", "-Wextra", "-Werror", "-O2"]
        for name in ("provider", "consumer"):
            command(*cflags, "-c", f"{name}.c", "-o", f"{name}.o", cwd=work)
        command(*cflags, "-S", "-emit-llvm", "provider.c", "-o", "provider.ll", cwd=work)
        ir = next(row for row in (work / "provider.ll").read_text().splitlines()
                  if row.startswith("define ") and "@update_span" in row)
        assert "sret(" not in ir
        command(args.ar, "rcsD", "libspan.a", "provider.o", cwd=work)
        args_link = linker(args, arch, platform, minos)
        command(*args_link, "-install_name", PROVIDER,
                "-exported_symbol", "_update_span", "provider.o", "-o", "libspan.dylib", cwd=work)
        command(*args_link, "-install_name", "@rpath/libstatic-client.dylib",
                "-exported_symbol", "_observe_span",
                "consumer.o", "libspan.a", "-o", "libstatic-client.dylib", cwd=work)
        command(*args_link, "-install_name", "@rpath/libdynamic-client.dylib", "-rpath", "@loader_path",
                "-exported_symbol", "_observe_span",
                "consumer.o", "libspan.dylib", "-o", "libdynamic-client.dylib", cwd=work)
        command(*linker(args, arch, platform, later), "-install_name", PROVIDER,
                "-exported_symbol", "_update_span", "provider.o", "-o", "later-provider.dylib", cwd=work)
        late = command(
            *args_link, "-install_name", "@rpath/liblate-client.dylib", "-rpath", "@loader_path",
            "consumer.o", "later-provider.dylib", "-o", "liblate-client.dylib",
            cwd=work, checked=False,
        )
        late_meta = inspect(args, work / "later-provider.dylib", arch, platform, later, PROVIDER, (),
                            "_update_span")
        assert not admits(late_meta, arch, platform, minos, PROVIDER)
        if late.returncode:
            assert not (work / "liblate-client.dylib").exists()
        else:
            inspect(args, work / "liblate-client.dylib", arch, platform, minos,
                    "@rpath/liblate-client.dylib", (PROVIDER,), "_observe_span")
        checked_provider = inspect(args, work / "libspan.dylib", arch, platform, minos, PROVIDER, (),
                                   "_update_span")
        assert admits(checked_provider, arch, platform, minos, PROVIDER)
        profiles[profile] = {
            "triple": triple, "coverage": "cross-build-only",
            "static_archive_sha256": digest(work / "libspan.a"), "call_lowering": ir,
            "provider": checked_provider,
            "static_client": inspect(args, work / "libstatic-client.dylib", arch, platform, minos,
                                     "@rpath/libstatic-client.dylib", (), "_observe_span"),
            "dynamic_client": inspect(args, work / "libdynamic-client.dylib", arch, platform, minos,
                                      "@rpath/libdynamic-client.dylib", (PROVIDER,), "_observe_span"),
            "later_deployment_control": {
                "link": "refused" if late.returncode else "accepted",
                "reported_warning": "warning:" in late.stderr,
                "exact_package_gate": "refused", "provider": late_meta,
            },
        }

    for client, provider in (("macos-arm64", "ios-arm64"), ("ios-arm64", "macos-arm64"),
                             ("macos-x64", "macos-arm64")):
        _, arch, platform, minos, _ = PROFILES[client]
        client_root = root / client
        wrong = command(
            *linker(args, arch, platform, minos), "-install_name", "@rpath/wrong.dylib",
            "-rpath", "@loader_path", "-exported_symbol", "_observe_span",
            "consumer.o", root / provider / "libspan.dylib", "-o", "wrong.dylib",
            cwd=client_root, checked=False,
        )
        selected = profiles[provider]["provider"]
        assert not admits(selected, arch, platform, minos, PROVIDER)
        if wrong.returncode:
            assert not (client_root / "wrong.dylib").exists(), wrong.stderr
        else:
            inspect(args, client_root / "wrong.dylib", arch, platform, minos,
                    "@rpath/wrong.dylib", (PROVIDER,), "_observe_span")
        profiles[client]["wrong_provider_control"] = {
            "provider_profile": provider, "link": "refused" if wrong.returncode else "accepted",
            "reported_warning": "warning:" in wrong.stderr, "exact_package_gate": "refused",
        }

    return {
        "profiles": profiles,
        "tools": {
            name: command(getattr(args, name), "--version").stdout.splitlines()[0]
            for name in ("clang", "linker", "ar", "objdump")
        },
        "sources": {name: digest(HERE / name) for name in ("run.py", *FILES)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, tool in (("clang", "clang"), ("linker", "ld64.lld"), ("ar", "llvm-ar"),
                       ("objdump", "llvm-objdump")):
        parser.add_argument(f"--{name}", default=tool)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-ffi-macho-") as temporary:
        evidence = collect(args, Path(temporary))
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
