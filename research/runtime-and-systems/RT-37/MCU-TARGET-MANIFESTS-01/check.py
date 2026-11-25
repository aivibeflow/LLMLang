"""Verify pinned MCU profiles and distinguish incompatible object call conventions."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.request import urlopen


HERE = Path(__file__).resolve().parent


def run(args):
    return subprocess.check_output(args, text=True, timeout=30)


def vendor_files(manifest, cache):
    cache.mkdir(parents=True, exist_ok=True)
    texts = {}
    for name, source in manifest["sources"].items():
        path = cache / name
        if not path.exists():
            with urlopen(source["url"], timeout=20) as response:
                path.write_bytes(response.read())
        data = path.read_bytes()
        assert sha256(data).hexdigest() == source["sha256"], name
        texts[name] = data.decode()
    return texts


def check_st(profiles, sources):
    for name, flash_region in (("f1", "FLASH"), ("f4", "ROM")):
        schema = profiles[name]
        layout = sources[f"{name}-layout.ld"]
        regions = re.findall(r"^\s*(\w+)\s*\([^)]*\)\s*:\s*ORIGIN\s*=\s*(0x[0-9a-f]+),\s*LENGTH\s*=\s*(\d+)K",
                             layout, re.M | re.I)
        parsed = {label: [start, int(kib) * 1024] for label, start, kib in regions}
        allowed = {"flash": parsed[flash_region], "sram": parsed["RAM"]}
        if name == "f4":
            allowed["ccm"] = parsed["CCMRAM"]
        assert allowed == schema["memory"]
        startup = sources[f"{name}-startup.s"]
        for marker in ("Reset_Handler", ".isr_vector", "SystemInit", "TIM2_IRQHandler", "USART2_IRQHandler"):
            assert marker in startup
        for key, marker in (("core", "HCLK"), ("apb1", "APB1 Prescaler"), ("apb2", "APB2 Prescaler")):
            line = next(line for line in sources[f"{name}-main.c"].splitlines() if marker in line)
            value = int(re.search(r"=\s*(\d+)", line)[1])
            actual = value if key == "core" else schema["clocks_hz"]["core"] // value
            assert actual == schema["clocks_hz"][key]
    for marker in ("fpu.value.fpv4-sp-d16", "floatabi.value.hard"):
        assert marker in sources["f4-cproject"]


def check_esp(profile, sources):
    assert "xtensa-esp32-elf-gcc" in sources["esp-toolchain-esp32.cmake"]
    assert "call_start_cpu0" in sources["esp-bootloader_start.c"]
    assert "bootloader_utility_load_boot_image" in sources["esp-bootloader_start.c"]
    assert "call_start_cpu0" in sources["esp-cpu_start.c"]
    assert "call_start_cpu1" in sources["esp-cpu_start.c"]
    for region in ("0x40080000", "0x400D0020", "0x3FFB0000", "0x3F400020"):
        assert region in sources["esp-memory.ld.in"]
    assert re.search(r"factory\s*,\s*app\s*,\s*factory\s*,\s*,\s*1M", sources["esp-partitions_singleapp.csv"])
    assert "default ESP_DEFAULT_CPU_FREQ_MHZ_160" in sources["esp-Kconfig.cpu"]
    assert profile["clocks_hz"]["core"] == 160_000_000
    tools = json.loads(sources["esp-tools.json"])["tools"]
    version = next(tool for tool in tools if tool["name"] == "xtensa-esp-elf")["versions"][0]
    return {"name": version["name"], **version["linux-amd64"]}


def compile_probes(profiles, arm, xtensa, objdump):
    evidence = {}
    with TemporaryDirectory() as folder:
        obj = Path(folder) / "probe.o"
        arm_profiles = {name: profiles[name]["compiler_flags"] for name in ("f1", "f4")}
        arm_profiles["f4-softfp-control"] = [*arm_profiles["f4"][:-1], "-mfloat-abi=softfp"]
        for name, flags in arm_profiles.items():
            run([arm, "--target=arm-none-eabi", *flags, "-ffreestanding", "-O2", "-c", str(HERE / "probe.c"),
                 "-o", str(obj)])
            info = run(["readelf", "-A", str(obj)])
            hard = "Tag_ABI_VFP_args: VFP registers" in info
            assert hard == (name == "f4")
            evidence[name] = {"vfp_parameter_registers": hard, "sha256": sha256(obj.read_bytes()).hexdigest()}
        for label, abi_flags in (("esp-default", []), ("esp-call0-control", ["-mabi=call0"])):
            flags = [*profiles["esp"]["compiler_flags"], *abi_flags]
            macros = run([xtensa, *flags, "-dM", "-E", "-x", "c", "/dev/null"])
            windowed = "__XTENSA_WINDOWED_ABI__" in macros
            call0 = "__XTENSA_CALL0_ABI__" in macros
            assert windowed == (label == "esp-default") and call0 != windowed
            run([xtensa, *flags, "-ffreestanding", "-O2", "-c", str(HERE / "probe.c"), "-o", str(obj)])
            assembly = run([objdump, "-d", str(obj)])
            calls = re.findall(r"\bcallx?(?:0|4|8|12)\b", assembly)
            assert calls and all(call.endswith("8" if windowed else "0") for call in calls)
            evidence[label] = {"windowed": windowed, "calls": calls, "sha256": sha256(obj.read_bytes()).hexdigest()}
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--xtensa", required=True)
    parser.add_argument("--xtensa-objdump", required=True)
    args = parser.parse_args()
    payload = (HERE / "manifests.json").read_bytes()
    manifests = json.loads(payload)
    sources = vendor_files(manifests, args.cache)
    profiles = manifests["profiles"]
    check_st(profiles, sources)
    xtensa_pin = check_esp(profiles["esp"], sources)
    print(json.dumps({
        "manifest_sha256": sha256(payload).hexdigest(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "vendor_files_verified": len(sources),
        "arm_toolchain": run([args.arm, "--version"]).splitlines()[0],
        "xtensa_toolchain": run([args.xtensa, "--version"]).splitlines()[0],
        "xtensa_toolchain_vendor_pin": xtensa_pin,
        "objects": compile_probes(profiles, args.arm, args.xtensa, args.xtensa_objdump),
    }, indent=2, sort_keys=True))
