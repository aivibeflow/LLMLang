"""Compile exact STM32 LL/CMSIS firmware profiles and check static-link controls."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
PROFILES = {
    "f1": {"board": "STM32F103RB-Nucleo", "chip": "STM32F103xB", "cpu": "cortex-m3",
           "abi": ["-mfloat-abi=soft"], "vector": "0x08000000"},
    "f4": {"board": "STM32F4-Discovery", "chip": "STM32F407xx", "cpu": "cortex-m4",
           "abi": ["-mfpu=fpv4-sp-d16", "-mfloat-abi=hard"], "vector": "0x08000000"},
}
SDK_REVISIONS = {
    "f1": ("8a76309ed1250d817e9c888c4417171d2ba3ba63", "77fbb30b7a1d02533980400083e48c559aae5a4f"),
    "f4": ("3c77349ce04c8af401454cc51f85ea9a50e34fc1", "b6f0ed3829f3829eb358a2e7417d80bba1a42db7"),
}


def execute(args, check=True):
    return subprocess.run(args, capture_output=True, text=True, timeout=30, check=check)


def setup_and_build(name, options):
    profile = PROFILES[name]
    sdk = options.sources / f"stm32-{name}"
    common = sdk / "common/Drivers/CMSIS/Include"
    device = sdk / "device"
    hal = sdk / "hal"
    for location, expected in zip((device, hal), SDK_REVISIONS[name]):
        assert execute(["git", "-C", location, "rev-parse", "HEAD"]).stdout.strip() == expected
    target = options.output / name
    target.mkdir(exist_ok=True, parents=True)
    flags = ["--target=arm-none-eabi", "-mthumb", f"-mcpu={profile['cpu']}", *profile["abi"]]
    compiler = [options.clang, *flags, "-Os", "-ffreestanding", "-fno-builtin",
                "-ffunction-sections", "-fdata-sections", f"-D{profile['chip']}",
                "-I", common, "-I", device / "Include", "-I", hal / "Inc", "-I", HERE]
    sources = {
        "pilot": HERE / "pilot.c", "format": HERE / "format.c", "main": HERE / "stm32.c",
        "startup": options.sources / f"{name}-startup.s",
        "system": device / f"Source/Templates/system_stm32{name}xx.c",
    }
    objects = {label: target / f"{label}.o" for label in sources}
    for label, source in sources.items():
        built = execute([*compiler, "-c", source, "-o", objects[label]], check=False)
        if built.returncode:
            raise AssertionError((name, label, built.stderr))

    archive = target / "libpilot.a"
    execute([options.ar, "rcs", archive, objects["pilot"], objects["format"]])
    image = target / "firmware.elf"
    layout = options.sources / f"{name}-layout.ld"
    if name == "f4":
        # Normalize the vendor GNU script for LLD 19 while preserving its map.
        text = layout.read_text()
        assignment = next(line for line in text.splitlines() if line.startswith("_estack ="))
        assert text.count(assignment) == 1 and text.count("SECTIONS") == 1
        adapted = text.replace(assignment, "").replace("SECTIONS", assignment + "\n\nSECTIONS")
        layout = target / "lld-layout.ld"
        layout.write_text(adapted.replace(" (READONLY)", ""))
    link = [options.linker, "--gc-sections", "--no-undefined", "--build-id=none", "-T", layout,
            objects["startup"], objects["system"], objects["main"]]
    linked = execute([*link, archive, "-o", image], check=False)
    if linked.returncode:
        raise AssertionError((name, linked.stderr))

    members = execute([options.ar, "t", archive]).stdout.splitlines()
    assert members == ["pilot.o", "format.o"]
    symbols = execute(["readelf", "-sW", image]).stdout
    for symbol in ("Reset_Handler", "SystemInit", "pilot_step", "pilot_emit_result"):
        assert any(f" {symbol}" in entry and " UND " not in entry for entry in symbols.splitlines())
    sections = execute(["readelf", "-SW", image]).stdout
    assert any(".isr_vector" in line and profile["vector"][2:] in line for line in sections.splitlines())
    assert "NEEDED" not in execute(["readelf", "-dW", image]).stdout

    missing = execute([*link, objects["pilot"], "-o", target / "missing.elf"], check=False)
    assert missing.returncode and "pilot_emit_result" in missing.stderr
    wrong_target = target / "wrong-target.o"
    execute([options.clang, "--target=x86_64-linux-gnu", "-ffreestanding", "-c", HERE / "format.c", "-o", wrong_target])
    mismatched = execute([*link, objects["pilot"], wrong_target, "-o", target / "wrong.elf"], check=False)
    assert mismatched.returncode and ("incompatible" in mismatched.stderr or "format" in mismatched.stderr or "wrong format" in mismatched.stderr)
    return {"vector": profile["vector"], "static_members": members, "linked_exact_symbols": 4,
            "missing_archive_member_refused": True, "foreign_object_refused": True,
            "sdk_revisions": SDK_REVISIONS[name], "elf_sha256": sha256(image.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--linker", required=True)
    parser.add_argument("--ar", required=True)
    args = parser.parse_args()
    print(json.dumps({name: setup_and_build(name, args) for name in PROFILES}, indent=2, sort_keys=True))
