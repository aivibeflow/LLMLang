"""Generate one public ABI and validate exact library revisions through six consumers."""

import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
HOSTS = ("consumer.c", "consumer.cc", "consumer.rs", "consumer.py", "consumer.go", "Consumer.java")
FIXTURES = ("public.json", "provider.c.in", "run.py", *HOSTS)
MAX_U64 = 2**64 - 1
SENTINEL = 0xabad1234abcdef01


def command(*args, cwd=None, data=None, env=None, checked=True):
    return subprocess.run(
        args, cwd=cwd, input=data, text=True, capture_output=True, check=checked, timeout=120,
        env={**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1764000000", **(env or {})},
    )


def digest(data):
    return sha256(data).hexdigest()


def filehash(path):
    return digest(path.read_bytes())


def stable(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def provider(args, public, directory, *, increment=None, builtin=False, narrow=False):
    directory.mkdir()
    if (public["operation"], public["parameters"], public["return"]) != (
        "checked_add", ["u64", "u32", "mut pointer<u64>"], "u32",
    ):
        raise ValueError("unsupported public interface")
    header = directory / "public.h"
    slot = "uint32_t" if narrow else "uint64_t"
    header.write_text(f"""#ifndef GENERATED_PUBLIC_H
#define GENERATED_PUBLIC_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {{
#endif
typedef {slot} slot_word;
uint32_t checked_add(uint64_t input, uint32_t enabled, slot_word *output);
#ifdef __cplusplus
}}
#endif
#endif
""", encoding="utf-8")
    source = (HERE / "provider.c.in").read_text(encoding="utf-8")
    source = source.replace("@STEP@", str(public["increment"] if increment is None else increment))
    source = source.replace("@ERROR@", str(public["failure_status"]))
    (directory / "provider.c").write_text(source, encoding="utf-8")
    version = public["symbol_version"]
    (directory / "exports.map").write_text(
        f"{version} {{ global: checked_add; local: *; }};\n", encoding="utf-8",
    )
    build = [args.cc, "-std=c17", "-Wall", "-Wextra", "-Werror", "-fPIC"]
    if builtin:
        build += ["-DUSE_BUILTIN", "-O0"]
    else:
        build.append("-O2")
    command(*build, "-c", "provider.c", "-o", "provider.o", cwd=directory)
    command("ar", "rcsD", "libchecked.a", "provider.o", cwd=directory)
    command(args.cc, "-shared", "-Wl,--no-undefined,--version-script=exports.map,-soname,libchecked.so",
            "provider.o", "-o", "libchecked.so", cwd=directory)
    symbols = command("readelf", "--dyn-syms", "-W", directory / "libchecked.so").stdout
    assert f"checked_add@@{version}" in symbols
    abi = {"profile": "x86_64-linux-gnu SysV LP64", "argument_bits": [64, 32, 64],
           "mutable_pointee_bits": 32 if narrow else 64, "return_bits": 32, "symbol": version}
    return {
        "abi": abi, "abi_sha256": stable(abi), "public_header_sha256": filehash(header),
        "shared_sha256": filehash(directory / "libchecked.so"),
        "static_sha256": filehash(directory / "libchecked.a"),
        "emitted_source_sha256": filehash(directory / "provider.c"),
    }


def build_consumers(args, work, baseline):
    work.mkdir()
    for name in HOSTS:
        shutil.copyfile(HERE / name, work / name)
    shutil.copyfile(baseline / "public.h", work / "public.h")
    commands = {}
    for name, tool, standard, source in (
        ("c", args.cc, "c17", "consumer.c"), ("cpp", args.cxx, "c++20", "consumer.cc"),
    ):
        for mode, link in (
            ("shared", [baseline / "libchecked.so"]), ("static", [baseline / "libchecked.a"]),
        ):
            executable = work / f"{name}-{mode}"
            command(tool, f"-std={standard}", "-O2", "-Wall", "-Wextra", "-Werror", source,
                    *link, "-o", executable, cwd=work)
            link_map = command("readelf", "-dW", executable).stdout
            assert ("libchecked.so" in link_map) == (mode == "shared")
            commands[f"{name}-{mode}"] = ([executable], mode)
    rust = work / "rust"
    command(args.rustc, "--edition=2021", "-Copt-level=2", "--remap-path-prefix", f"{work}=/fixture",
            "-L", f"native={baseline}", "-l", "dylib=checked", "consumer.rs", "-o", rust, cwd=work)
    commands["rust"] = ([rust], "shared")

    go_dir = work / "golang"
    go_dir.mkdir()
    for filename in ("public.h", "libchecked.so"):
        shutil.copyfile(baseline / filename, go_dir / filename)
    shutil.copyfile(work / "consumer.go", go_dir / "main.go")
    (go_dir / "go.mod").write_text("module llmlang.local/typedexport\n\ngo 1.27\n", encoding="utf-8")
    go_env = {
        "GOCACHE": str(args.go_cache.resolve()), "CGO_ENABLED": "1", "CC": args.cc,
        "GOTOOLCHAIN": "local", "GOOS": "linux", "GOARCH": "amd64", "GOAMD64": "v1",
        "GOENV": "off", "GOPROXY": "off", "GOSUMDB": "off", "GOMAXPROCS": "2",
        "GOFLAGS": "", "GOWORK": "off",
    }
    go = work / "go"
    command(args.go, "build", "-p", "2", "-mod=readonly", "-buildvcs=false", "-trimpath",
            "-ldflags=-buildid=", "-o", go, ".", cwd=go_dir, env=go_env)
    commands["go"] = ([go], "shared")

    command(args.java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "--enable-preview",
            "-source", "21", "-target", "21", "Consumer.java", cwd=work)
    assert (work / "Consumer.class").read_bytes()[:8] == bytes.fromhex("cafebabeffff0041")
    commands["java-ffm"] = ([args.java, "--enable-preview", "--enable-native-access=ALL-UNNAMED",
                            "-cp", work, "Consumer"], "explicit-path")
    commands["python"] = ([sys.executable, "-B", work / "consumer.py"], "explicit-path")
    return commands


def source_oracle(cases, increment):
    outputs = []
    for word, enabled in cases:
        result = word + (increment if enabled else 0)
        outputs.append((0, result) if result <= MAX_U64 else (1, SENTINEL))
    return outputs


def collect(args, work):
    public = json.loads((HERE / "public.json").read_text(encoding="utf-8"))
    versions = {
        "base": {}, "compatible_revision": {"builtin": True},
        "different_contract": {"increment": 8}, "different_abi": {"narrow": True},
    }
    builds = {name: provider(args, public, work / name, **settings) for name, settings in versions.items()}
    baseline = builds["base"]
    assert baseline["abi_sha256"] == builds["compatible_revision"]["abi_sha256"] == builds["different_contract"]["abi_sha256"]
    assert baseline["abi_sha256"] != builds["different_abi"]["abi_sha256"]
    assert len({record["shared_sha256"] for record in builds.values()}) == 4

    wrong_abi = work / "different_abi"
    shutil.copyfile(HERE / "consumer.c", wrong_abi / "width-control.c")
    refused = command(args.cc, "-std=c17", "-Wall", "-Wextra", "-Werror",
                       "-fsyntax-only", "width-control.c", cwd=wrong_abi, checked=False)
    assert refused.returncode and "incompatible pointer type" in refused.stderr

    commands = build_consumers(args, work / "consumer", work / "base")
    samples = (0, 1, 7, 12, 31, 0xffffffff, 0x100000000, 2**63 - 1, 2**63,
               *range(MAX_U64 - 8, MAX_U64 + 1))
    cases = list(product(samples, (0, 1, 2, 0xffffffff)))
    input_data = "".join(f"{value} {enabled}\n" for value, enabled in cases)
    reference = source_oracle(cases, 7)
    observed = {}
    for language, (invocation, mode) in commands.items():
        for version in ("base", "compatible_revision", "different_contract"):
            if mode == "static" and version != "base":
                continue
            package = work / version
            flags = [package / "libchecked.so"] if mode == "explicit-path" else []
            loader = {"LD_LIBRARY_PATH": str(package), "LD_PRELOAD": "", "LD_DEBUG": ""}
            if mode != "static":
                loader["LD_DEBUG"] = "libs"
            reply = command(*invocation, *flags, cwd=work, data=input_data, env=loader)
            providers = re.findall(r"calling init:\s+(\S+/libchecked\.so)\b", reply.stderr)
            expected_path = package / "libchecked.so"
            if mode == "static":
                assert not providers and not reply.stderr
            else:
                assert [Path(path).resolve() for path in providers] == [expected_path.resolve()], language
            outputs = [tuple(map(int, row.split())) for row in reply.stdout.splitlines()]
            assert len(outputs) == len(reference)
            errors = sum(actual != expect for actual, expect in zip(outputs, reference))
            assert errors == (sum(a != b for a, b in zip(source_oracle(cases, 8), reference))
                              if version == "different_contract" else 0)
            observed[f"{language}/{version}"] = {
                "observations": len(outputs), "mismatches": errors, "trace_sha256": stable(outputs),
                "admission": "checked" if not errors else "contract-refused",
                "provider_binding": "archive" if mode == "static" else "exact ELF audit",
                "receipt": stable([stable(public), builds[version]["abi_sha256"],
                                   builds[version]["static_sha256" if mode == "static" else "shared_sha256"],
                                   language, mode]),
            }
    for language, (_, mode) in commands.items():
        if mode != "static":
            assert observed[f"{language}/base"]["receipt"] != observed[f"{language}/compatible_revision"]["receipt"]
    assert {v["trace_sha256"] for v in observed.values() if not v["mismatches"]} == {stable(reference)}
    return {
        "profile": "Linux x86-64 SysV LP64, generated C interface version 1",
        "tools": {
            name: command(getattr(args, name), "version" if name == "go" else "--version").stdout.splitlines()[0]
            for name in ("cc", "cxx", "go", "rustc", "java")
        },
        "source_sha256": {name: filehash(HERE / name) for name in FIXTURES},
        "reference_sha256": stable(reference), "source_contract_sha256": stable(public),
        "cases_per_consumer": len(cases), "builds": builds, "routes": observed,
        "different_abi": "compiler refuses wrong pointee and execution is withheld", "stale_receipt_after_compatible_change": "refused",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name, binary in (("cc", "gcc"), ("cxx", "g++"), ("rustc", "rustc"), ("go", "go"), ("java", "java")):
        parser.add_argument(f"--{name}", default=binary)
    parser.add_argument("--go-cache", type=Path, required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-six-language-") as directory:
        evidence = collect(args, Path(directory))
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
