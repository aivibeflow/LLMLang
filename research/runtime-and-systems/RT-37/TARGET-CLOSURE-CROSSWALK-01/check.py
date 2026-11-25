"""Cross-check exact archived runtime closure, startup and resource observations."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "closure": "cortex-m3-closure/results.json",
    "startup": "cortex-m3-startup-retention/evidence.json",
    "allocator": "cortex-m3-allocator/results.json",
    "manifests": "MCU-TARGET-MANIFESTS-01/manifests.json",
    "stm32": "MCU-GPIO-TIMER-UART-01/stm32-evidence.json",
    "renode": "MCU-GPIO-TIMER-UART-01/arm-emulator-evidence.json",
    "esp": "ESP32-SCHEDULING-PROFILES-01/evidence.json",
}


def cortex(closure, startup, allocator):
    assert len(closure["images"]) == 5
    assert closure["steps_per_image"] == 14
    assert len({tuple(image["uart"]) for image in closure["images"].values()}) == 1
    assert set(closure["controls"].values()) == {
        "panic_const_add_overflow", "__aeabi_uldivmod", "__aeabi_unwind_cpp_pr0", "X",
    }
    profiles = startup["profiles"]
    baseline = profiles["exact_sections"]
    assert len(profiles) == 4
    assert all(row["sections"] == baseline["sections"] for row in profiles.values())
    assert all(row["uart"] != baseline["uart"] for label, row in profiles.items() if label != "exact_sections")
    allocator_images = allocator["images"]
    assert len(allocator_images) == 4 and allocator["case_count"] == 644 and allocator["requests_per_image"] == 676
    assert all(row["arena"]["arena"] == "0x20000000" and row["arena"]["arena_end"] == "0x20000040"
               for row in allocator_images.values())
    assert allocator["control"]["expected"] != allocator["control"]["observed"]
    return {
        "boot_images": len(closure["images"]),
        "exact_startup_images": 1,
        "same_layout_startup_controls": len(profiles) - 1,
        "link_or_boot_controls": closure["controls"],
        "allocation_cases": allocator["case_count"],
        "allocation_observations": len(allocator_images) * allocator["requests_per_image"],
        "maximum_arena_bytes": 64,
        "allocation_profiles": sorted({row["linked_reservation_routine"] for row in allocator_images.values()}),
        "flash_extents_bytes": {name: row["flash_extent_bytes"] for name, row in closure["images"].items()},
    }


def make_report():
    raw = {key: (ROOT / path).read_bytes() for key, path in SOURCES.items()}
    data = {key: json.loads(payload) for key, payload in raw.items()}
    manifests = data["manifests"]["profiles"]
    arm = {}
    for key in ("f1", "f4"):
        target = manifests[key]
        image = data["stm32"][key]
        observed = data["renode"]["profiles"][key]
        assert image["vector"] == target["memory"]["flash"][0]
        assert image["foreign_object_refused"] and image["missing_archive_member_refused"]
        assert observed["trace"] == data["renode"]["native_reference"]
        arm[key] = {"profile": target["abi"], "flash_origin": image["vector"],
                    "uart_observations": len(observed["trace"]), "closure": "vendor-LL-CMSIS"}

    esp = data["esp"]
    assert set(esp["freestanding"]) == {"rv32", "xtensa"}
    assert all(profile["runtime_dependencies"] == 0 for profile in esp["freestanding"].values())
    assert esp["profiles"]["esp32-dual"]["trace"] == "S:2:0:1:1:2"
    assert esp["profiles"]["esp32-unicore"]["machine"] != esp["profiles"]["esp32c3-unicore"]["machine"]
    assert not esp["radio"]["radio_disabled_vendor_archives"]

    return {
        "pinned_evidence": {key: {"path": SOURCES[key], "sha256": sha256(payload).hexdigest()}
                            for key, payload in raw.items()},
        "cortex_m3": cortex(data["closure"], data["startup"], data["allocator"]),
        "stm32": arm,
        "esp": {"standalone_linked_architectures": sorted(esp["freestanding"]),
                "sdk_boot_profiles": sorted(esp["profiles"]),
                "optional_radio_vendor_archives": len(esp["radio"]["radio_enabled_vendor_archives"])},
    }


if __name__ == "__main__":
    print(json.dumps(make_report(), indent=2, sort_keys=True))
