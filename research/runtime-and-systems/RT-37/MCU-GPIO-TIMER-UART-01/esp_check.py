"""Run native C and two ESP-IDF images against separate reference observations."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REV3_FUSES = bytes.fromhex(
    "00000000000000000000000000800000000000000000100000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000"
)


def run(args):
    return subprocess.check_output(args, text=True, timeout=30)


def native_trace(work):
    gcc = ["cc", "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror"]
    objects = [work / f"{name}.o" for name in ("pilot", "format")]
    for obj in objects:
        run([*gcc, "-c", HERE / f"{obj.stem}.c", "-o", obj])
    archive = work / "libpilot.a"
    run(["ar", "rcs", archive, *objects])
    native, reference = work / "native", work / "reference"
    run([*gcc, HERE / "native.c", archive, "-o", native])
    run([*gcc, HERE / "reference.c", "-o", reference])
    actual, expected = run([native]).splitlines(), run([reference]).splitlines()
    assert actual == expected and len(expected) == 6
    return expected


def qemu_log(qemu, flash, work, control):
    efuses = work / "efuses.bin"
    efuses.write_bytes(REV3_FUSES)
    local_flash = work / "flash.bin"
    shutil.copyfile(flash, local_flash)
    cmd = [qemu, "-M", "esp32", "-m", "4M", "-nographic", "-serial", "mon:stdio", "-nic", "none",
           "-drive", f"file={local_flash},if=mtd,format=raw",
           "-drive", f"file={efuses},if=none,format=raw,id=efuse",
           "-global", "driver=nvram.esp32.efuse,property=drive,value=efuse",
           "-global", "driver=timer.esp32.timg,property=wdt_disable,value=true"]
    with subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as process:
        try:
            data, _ = process.communicate(timeout=7)
            raise ValueError(f"emulator exited early on {control}: {data.decode(errors='replace')}")
        except subprocess.TimeoutExpired:
            process.terminate()
            data, _ = process.communicate(timeout=3)
    return data.decode(errors="replace").splitlines()


def check(options):
    symbols = run([options.nm, "--defined-only", options.elf]).splitlines()
    provided = {"pilot_step", "pilot_emit_result", "app_main", "gptimer_new_timer", "gpio_config", "uart_write_bytes"}
    assert provided <= {line.split()[-1] for line in symbols if line.split()}
    flash = options.build / "flasher_args.json"
    files = json.loads(flash.read_text())
    assert set(files["flash_files"]) == {"0x1000", "0x8000", "0x10000"}
    assert files["flash_settings"]["flash_size"] == "4MB" and files["extra_esptool_args"]["chip"] == "esp32"
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        expected = native_trace(work)
        positive = qemu_log(options.qemu, options.valid_flash, work, "valid")
        assert [line for line in positive if re.fullmatch(r"P:\d:\d", line)] == expected
        assert any("Multicore app" in line for line in positive)
        invalid = qemu_log(options.qemu, options.invalid_flash, work, "invalid pin")
        assert any("ESP_ERR_INVALID_ARG" in line and "0x102" in line for line in invalid)
        assert all(not re.fullmatch(r"P:\d:\d", line) for line in invalid)

    return {"native_reference": expected, "esp32_uart": expected, "native_controls": 10,
            "gpio34_output": "ESP_ERR_INVALID_ARG", "gpio34_output_trace": [],
            "flash_offsets": sorted(files["flash_files"]), "flash_size": files["flash_settings"]["flash_size"],
            "elf_sha256": sha256(options.elf.read_bytes()).hexdigest(),
            "firmware_flash_sha256": sha256(options.valid_flash.read_bytes()).hexdigest(),
            "invalid_flash_sha256": sha256(options.invalid_flash.read_bytes()).hexdigest(),
            "qemu": run([options.qemu, "--version"]).splitlines()[0],
            "qemu_sha256": sha256(Path(options.qemu).read_bytes()).hexdigest(),
            "linked_symbols": sorted(provided), "id": "esp32-multicore-qemu-only"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--nm", required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--valid-flash", type=Path, required=True)
    parser.add_argument("--invalid-flash", type=Path, required=True)
    print(json.dumps(check(parser.parse_args()), indent=2, sort_keys=True))
