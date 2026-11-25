"""Bind resolved native cross-build artifacts to the existing package/cache admission path."""

import argparse
import json
from pathlib import Path
import platform
import re
import runpy
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
DELIVERY = runpy.run_path(str(RESEARCH / "toolchain-and-collaboration/RT-11/PACKAGE-CACHE-DELIVERY-01/run.py"))
OPTIONAL = DELIVERY["OPTIONAL"]
HASH = OPTIONAL["sha"]
ENCODE = OPTIONAL["json_bytes"]
STATIC = OPTIONAL["STATIC"]
SOURCE = HERE / "provider.c"
PROFILES = {
    "linux-x64": ("x86_64-linux-gnu", "elf", "elf64-x86-64"),
    "linux-arm64": ("aarch64-linux-gnu", "elf", "elf64-littleaarch64"),
    "macos-arm64": ("arm64-apple-macos13.0", "macho", "Mach-O arm64"),
    "windows-x64": ("x86_64-pc-windows-msvc", "coff", "COFF-x86-64"),
}


def run(args, cwd=None):
    return subprocess.check_output(args, text=True, timeout=30, cwd=cwd)


def build(options, directory, name, root):
    triple, format_name, inspection = PROFILES[name]
    linkers = {"elf": options.elf, "macho": options.macho, "coff": options.coff}
    linker = linkers[format_name]
    config = ["-std=c17", "-O2", "-ffreestanding", "-fno-builtin"]
    if format_name != "coff":
        config.append("-fPIC")
    else:
        config.append("-mno-incremental-linker-compatible")
    obj = directory / "provider.o"
    run([options.clang, f"--target={triple}", *config, "-c", SOURCE, "-o", obj])
    if format_name == "elf":
        artifact = directory / "provider.so"
        link_flags = ["-shared", "--build-id=none", "-soname", "provider.so", "-o", artifact.name, obj.name]
    elif format_name == "macho":
        artifact = directory / "provider.dylib"
        link_flags = ["-dylib", "-arch", "arm64", "-platform_version", "macos", "13.0", "13.0",
                      "-no_uuid", "-install_name", "@rpath/provider.dylib", "-o", artifact.name, obj.name]
    else:
        artifact = directory / "provider.dll"
        link_flags = ["/dll", "/noentry", "/nodefaultlib", "/machine:x64", "/timestamp:0",
                      f"/out:{artifact.name}", obj.name]
    run([linker, *link_flags], cwd=directory)
    details = run([options.readobj, "--file-headers", artifact])
    assert f"Format: {inspection}" in details
    if format_name == "coff":
        imports = run([options.readobj, "--coff-imports", artifact])
        assert "Import {" not in imports
    else:
        dependencies = run([options.readobj, "--needed-libs", artifact])
        listed = re.search(r"NeededLibraries \[([^]]*)\]", dependencies)[1].split()
        own_install_name = ["@rpath/provider.dylib"] if format_name == "macho" else []
        assert listed == own_install_name
    descriptors = {
        "target": {"triple": triple, "object_format": format_name},
        "toolchain": {"host": platform.machine(), "compiler": HASH(Path(options.clang).read_bytes()),
                      "linker": HASH(Path(linker).read_bytes()), "linker_entrypoint": Path(linker).name},
        "configuration": {"compile": config, "link": link_flags, "sysroot": "none"},
        "runtime": {"closure": "fixture-no-system-runtime", "procedure": "shared-provider-only"},
    }
    payload = artifact.read_bytes()
    record = OPTIONAL["sample_record"](
        action_kind="compile", action_implementation=HASH(Path(__file__).read_bytes()),
        input_hashes=[root, HASH(SOURCE.read_bytes())],
        toolchain_identity=HASH(ENCODE(descriptors["toolchain"])),
        target_profile_digest=HASH(ENCODE(descriptors["target"])),
        configuration_digest=HASH(ENCODE(descriptors["configuration"])),
        runtime_identity=HASH(ENCODE(descriptors["runtime"])),
        output_artifacts=[HASH(payload)],
    )
    return payload, record, descriptors


def evaluate(work, core, identity, record, payloads, trusted, catalog, name):
    encoded = OPTIONAL["encode_index"](*catalog)
    folder = work / name
    DELIVERY["write_delivery"](folder, core, encoded, payloads, DELIVERY["LAYOUTS"]["fully-detached"])
    actual, outcomes, _ = DELIVERY["read_delivery"](
        folder, work, ("compile",), {"compile": record}, trusted, True,
    )
    assert actual == identity
    return outcomes["compile"]


def check(options):
    with TemporaryDirectory() as directory:
        work = Path(directory)
        core_path = work / "core.llpkg"
        STATIC["static_archive"](core_path, STATIC["sample_index"]())
        core = core_path.read_bytes()
        identity = OPTIONAL["checked_core"](core, work)
        builds = {name: build(options, work, name, identity["package_root"]) for name in PROFILES}
        records = [record for _, record, _ in builds.values()]
        payloads = {HASH(payload): payload for payload, _, _ in builds.values()}
        trusted = {record["action_key"]: record["output_artifacts"] for record in records}
        assert len(trusted) == len(payloads) == 4
        rows = {}
        key_dimensions = ("toolchain_identity", "target_profile_digest", "configuration_digest", "runtime_identity")
        for name, (payload, record, descriptors) in builds.items():
            assert evaluate(work, core, identity, record, payloads, trusted, records, f"{name}-exact") == "hit"
            controls = {}
            for field in (*key_dimensions, "input_hashes"):
                changes = {field: HASH(field.encode())}
                if field == "input_hashes":
                    changes[field] = [identity["package_root"], changes[field]]
                modified = OPTIONAL["sample_record"](**{**record, **changes})
                controls[field] = evaluate(work, core, identity, modified, payloads, trusted, records, f"{name}-{field}")
                assert controls[field] == "action-miss"
            output_hash, = record["output_artifacts"]
            replaced = {**payloads, output_hash: payload + b"bad"}
            assert evaluate(work, core, identity, record, replaced, trusted, records, f"{name}-invalid") == "digest-refused"
            other = next(row for row in records if row["action_key"] != record["action_key"])
            wrong = {**record, "output_artifacts": other["output_artifacts"]}
            changed_catalog = [wrong if row["action_key"] == wrong["action_key"] else row for row in records]
            assert evaluate(work, core, identity, record, payloads, trusted, changed_catalog, f"{name}-untrusted") == "receipt-refused"
            rows[name] = {"binding": record, "inputs": descriptors, "exact_artifact": "hit",
                          "mutated_fields": controls, "changed_artifact": "digest-refused",
                          "wrong_attested_artifact": "receipt-refused"}
    return {"core_package": identity, "profiles": rows, "source_sha256": HASH(SOURCE.read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for tool in ("clang", "elf", "macho", "coff", "readobj"):
        parser.add_argument(f"--{tool}", required=True)
    print(json.dumps(check(parser.parse_args()), indent=2, sort_keys=True))
