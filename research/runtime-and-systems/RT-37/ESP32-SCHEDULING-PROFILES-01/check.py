"""Audit separate Xtensa and RV32 firmware profiles and static vendor dependencies."""

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
IDF_REVISION = "2c211b236707889e8400c4dc5644dd5c4ee071e0"
WIFI_REVISION = "e0befaa593277b4e80726079fbd521b4681754c2"
FIRMWARE = "llmlang_esp_scheduler"


def run(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.STDOUT, text=True, timeout=30)


def digest(file):
    return sha256(file.read_bytes()).hexdigest()


def qemu_defaults(idf, target):
    source = idf / "tools/idf_py_actions/qemu_ext.py"
    tree = ast.parse(source.read_text())
    table = next(node.value for node in tree.body
                 if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "QEMU_TARGETS")
    record = next(expression for key, expression in zip(table.keys, table.values) if key.value == target)
    options = shlex.split(ast.literal_eval(record.args[3]))
    efuse = bytes.fromhex(ast.literal_eval(record.args[4].args[0]))
    return options, efuse


def emulate(idf, build, target, qemu, expected, work):
    options, efuse = qemu_defaults(idf, target)
    image = work / "flash.bin"
    run([sys.executable, "-m", "esptool", "--chip", target, "merge-bin", "-o", image,
         "--pad-to-size", "4MB", "@flash_args"], cwd=build)
    fake_fuses = work / "efuse.bin"
    fake_fuses.write_bytes(efuse)
    flash_copy = work / "flash-copy.bin"
    shutil.copyfile(image, flash_copy)
    cmd = [qemu, *options, "-nographic", "-serial", "mon:stdio", "-nic", "none",
           "-drive", f"file={flash_copy},if=mtd,format=raw",
           "-drive", f"file={fake_fuses},if=none,format=raw,id=efuse",
           "-global", f"driver=nvram.{target}.efuse,property=drive,value=efuse",
           "-global", f"driver=timer.{target}.timg,property=wdt_disable,value=true"]
    with subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as process:
        try:
            data, _ = process.communicate(timeout=8)
            raise ValueError(data.decode(errors="replace"))
        except subprocess.TimeoutExpired:
            process.terminate()
            data, _ = process.communicate(timeout=3)
    log = data.decode(errors="replace").splitlines()
    trace = [line for line in log if re.fullmatch(r"S:[0-9:]+", line)]
    assert trace == [expected], log[-24:]
    return {"trace": trace[0], "flash_sha256": digest(image)}


def machine(elf, expected):
    header = run(["readelf", "-hW", elf])
    line = next(line.strip() for line in header.splitlines() if "Machine:" in line)
    assert expected in line
    assert "ELF32" in header
    return line.split(":", 1)[1].strip()


def minimal(compiler, architecture, flags, work):
    image = work / "freestanding.elf"
    run([compiler, *flags, "-ffreestanding", "-fno-stack-protector", "-nostdlib", "-Os",
         "-Wl,--no-undefined,--build-id=none,-e,reduce", HERE / "freestanding.c", "-o", image])
    description = machine(image, architecture)
    assert "NEEDED" not in run(["readelf", "-dW", image])
    symbols = run(["readelf", "-sW", image])
    assert any(line.strip().endswith(" reduce") for line in symbols.splitlines())
    named_symbols = [line.split() for line in symbols.splitlines() if re.match(r"\s*\d+:", line)]
    assert all(fields[6] != "UND" for fields in named_symbols if len(fields) >= 8)
    return {"machine": description, "sha256": digest(image), "runtime_dependencies": 0}


def radio(idf, wifi_build, baseline):
    directory = idf / "components/esp_wifi/lib"
    assert run(["git", "-C", directory, "rev-parse", "HEAD"]).strip() == WIFI_REVISION
    selected = {}

    def matched_members(build):
        mapping = (build / f"{FIRMWARE}.map").read_text(errors="replace")
        first = mapping.split("Discarded input sections", 1)[0]
        return re.findall(r"/esp_wifi/lib/esp32/(lib\w+\.a)\(([^)]+)\)", first)

    assert not matched_members(baseline)
    included = matched_members(wifi_build)
    for archive in sorted({name for name, _ in included}):
        selected[archive] = {"sha256": digest(directory / "esp32" / archive),
                             "members": len({member for name, member in included if name == archive})}
    assert "libnet80211.a" in selected and "libpp.a" in selected
    return {"radio_disabled_vendor_archives": 0, "radio_enabled_vendor_archives": selected,
            "application_bytes": {"disabled": (baseline / f"{FIRMWARE}.bin").stat().st_size,
                                  "enabled": (wifi_build / f"{FIRMWARE}.bin").stat().st_size},
            "vendor_revision": WIFI_REVISION, "observation": "static_link_map"}


def check(args):
    assert run(["git", "-C", args.idf, "rev-parse", "HEAD"]).strip() == IDF_REVISION
    profiles = {
        "esp32-dual": (args.dual, "esp32", "Xtensa", args.xtensa_qemu, "S:2:0:1:1:2"),
        "esp32-unicore": (args.single, "esp32", "Xtensa", args.xtensa_qemu, "S:1:0:0:1:2"),
        "esp32c3-unicore": (args.c3, "esp32c3", "RISC-V", args.rv_qemu, "S:1:0:0:1:2"),
    }
    rows = {}
    with TemporaryDirectory() as directory:
        work = Path(directory)
        for name, (build, target, expected_machine, qemu, expected) in profiles.items():
            elf = build / f"{FIRMWARE}.elf"
            rows[name] = {"machine": machine(elf, expected_machine), "elf_sha256": digest(elf),
                          **emulate(args.idf, build, target, qemu, expected, work)}
        bounded = {
            "xtensa": minimal(args.xtensa_gcc, "Xtensa", ["-mabi=windowed"], work),
            "rv32": minimal(args.rv_gcc, "RISC-V", ["-march=rv32imc", "-mabi=ilp32"], work),
        }
    return {"profiles": rows, "freestanding": bounded, "radio": radio(args.idf, args.wifi, args.dual),
            "idf": IDF_REVISION, "qemu": {kind: run([exe, "--version"]).splitlines()[0]
                                         for kind, exe in (("xtensa", args.xtensa_qemu), ("rv32", args.rv_qemu))}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for item in ("idf", "dual", "single", "wifi", "c3", "xtensa-qemu", "rv-qemu", "xtensa-gcc", "rv-gcc"):
        parser.add_argument(f"--{item}", required=True, type=lambda p: Path(p).resolve())
    print(json.dumps(check(parser.parse_args()), indent=2, sort_keys=True))
