"""Compare pinned Renode Cortex-M UART traces and GPIO output latches with the pilot."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from esp_check import native_trace


PROFILES = {
    "f1": ("stm32f103.repl", "0x4001080C", 1 << 5),
    "f4": ("stm32f4.repl", "0x40020C14", 1 << 12),
}


def run_profile(renode, firmware, work, model, gpio_address, pin):
    platform = renode.parent / "platforms/cpus" / model
    # Diagnostic SVD download is unrelated to device behavior in these models.
    source = platform.read_bytes()
    lines = source.decode().splitlines()
    assert sum(line.lstrip().startswith("ApplySVD ") for line in lines) == 1
    local_platform = work / model
    local_platform.write_text("\n".join(line for line in lines if not line.lstrip().startswith("ApplySVD ")) + "\n")
    uart = work / f"{model}.uart"
    script = work / f"{model}.resc"
    script.write_text(f'''mach create
machine LoadPlatformDescription @{local_platform}
sysbus LoadELF @{firmware}
sysbus.usart2 CreateFileBackend @{uart}
cpu PerformanceInMips 10
emulation RunFor "0.65"
sysbus ReadDoubleWord {gpio_address}
quit
''')
    environment = {**os.environ, "XDG_CONFIG_HOME": str(work), "XDG_CACHE_HOME": str(work)}
    completed = subprocess.run([renode, "--console", "--disable-xwt", "--plain", script],
                               env=environment, stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, timeout=20, check=True)
    latch = re.findall(r"(?m)^0x([0-9a-fA-F]{8})\s*$", completed.stdout)
    assert len(latch) == 1, completed.stdout
    assert int(latch[0], 16) & pin
    return {"model_sha256": sha256(source).hexdigest(), "trace": uart.read_text().splitlines(),
            "gpio_latch_address": gpio_address, "gpio_level": 1}


def check(renode, builds):
    with TemporaryDirectory() as directory:
        work = Path(directory)
        expected = native_trace(work)
        rows = {}
        for name, profile in PROFILES.items():
            firmware = builds / name / "firmware.elf"
            row = run_profile(renode, firmware, work, *profile)
            assert row["trace"] == expected
            rows[name] = row
    version = subprocess.check_output([renode, "--version"], text=True, timeout=10).splitlines()[0]
    return {"emulator": version, "emulator_sha256": sha256(renode.read_bytes()).hexdigest(),
            "native_reference": expected, "profiles": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renode", type=Path, required=True)
    parser.add_argument("--builds", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.renode.resolve(), args.builds.resolve()), indent=2, sort_keys=True))
