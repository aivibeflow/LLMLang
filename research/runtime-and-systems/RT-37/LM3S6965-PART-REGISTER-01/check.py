"""Compare the selected manufacturer register rules to pinned Cortex-M3 observations."""

import argparse
from itertools import product
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REVISION = "23e5e3c808fdb4da21ed363cc69e568bffedb668"
ROOT = "research/runtime-and-systems/RT-37"
MANUAL = {
    "part": "LM3S6965", "document": "SPMS144I", "cover_revision": "I", "date": "2014-07-15",
    "url": "https://www.ti.com/lit/ds/symlink/lm3s6965.pdf",
    "printed_pages": {"STCTRL": [106], "STCURRENT": [109], "PEND0": [114], "UNPEND0": [116],
                      "GPIODATA": [293, 294, 300], "GPIOICR": [308]},
}
GPIOF = 0x40025000
SYSTEM = 0xE000E000


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def gpio_write(prior, mask, value):
    return (prior & ~mask) | (value & mask)


def check():
    inputs = {}
    ledgers = {}
    for name, relative in {
        "nvic": "cortex-m3-nvic-clear/evidence.json",
        "systick": "cortex-m3-volatile/results.json",
        "timer": "cortex-m3-timer/results.json",
        "metadata": "mmio-metadata/results.json",
    }.items():
        path = f"{ROOT}/{relative}"
        subject = f"{REVISION}:{path}"
        raw = git("show", subject)
        inputs[name] = {"path": path, "blob": git("rev-parse", subject).decode().strip(),
                        "sha256": sha256(raw).hexdigest()}
        ledgers[name] = json.loads(raw)

    # The Rev. I table distinguishes write-one set and write-one clear alias effects.
    nvic = {}
    for strategy, group in ledgers["nvic"]["results"].items():
        measurements = []
        for row in group["records"]:
            initial = row["before_set_alias"]
            selected = row["target_mask"]
            assert initial == row["before_clear_alias"]
            if strategy == "write_selected_bit_to_set_alias":
                expected = initial | selected
            else:
                payloads = {"clear_selected_bit": selected,
                            "read_and_not_then_write_clear": initial & ~selected,
                            "read_or_then_write_clear": initial | selected}
                expected = initial & ~payloads[strategy]
            assert expected == row["after_pending"]
            measurements.append({"initial": initial, "selected_mask": selected, "final": expected})
        nvic[strategy] = measurements

    systick = ledgers["systick"]["images"]
    assert all(systick[name]["uart"] == "B10!" for name in (
        "llvm-volatile-O0", "llvm-volatile-O2", "rust-volatile-O2"
    ))
    assert systick["rust-volatile-reset-O2"]["uart"] == "B00!"
    assert ledgers["metadata"]["core_header"]["registers"]["SysTick.CTRL"]["address"] == hex(SYSTEM + 0x10)
    assert ledgers["metadata"]["core_header"]["registers"]["SysTick.VAL"]["address"] == hex(SYSTEM + 0x18)

    inputs_subset = 0
    for prior, mask, value in product(range(8), repeat=3):
        expected = 0
        for bit in range(3):
            selected = 1 << bit
            source = value if mask & selected else prior
            expected += source & selected
        assert gpio_write(prior, mask, value) == expected
        inputs_subset += 1

    offset = 0x008
    mask = (offset >> 2) & 0xFF
    assert mask == 2
    assert (GPIOF + offset) == int(ledgers["metadata"]["evidence"]["pin_1_alias_write"], 16)
    assert (0xBE & (0x0C4 >> 2)) == 0x30
    assert (gpio_write(0xFF, 0x098 >> 2, 0xEB) & (0x098 >> 2)) == 0x22
    assert gpio_write(1, mask, 2) == 3 and gpio_write(1, 0xFF, 2) == 2
    timer = ledgers["timer"]
    for profile in timer["images"].values():
        states = [int(pair.split("/")[1], 16) for pair in profile["trace"].removeprefix("B ").split("#")[0].split()]
        assert len(states) == timer["steps_per_image"] and all(value in (1, 3) for value in states)
    wrong = timer["controls"]["write_unmasked_gpio"]
    assert wrong == "BG02X"
    return {
        "branch_revision": REVISION, "python": sys.version.split()[0], "manual": MANUAL, "pinned_ledgers": inputs,
        "systick": {"ctrl_address": hex(SYSTEM + 0x10), "current_address": hex(SYSTEM + 0x18),
                    "observed_volatile_control": "B10!", "observed_current_write_control": "B00!",
                    "dap_disposition": "manufacturer_rule_only"},
        "nvic": {"pending_set_address": hex(SYSTEM + 0x200), "pending_clear_address": hex(SYSTEM + 0x280),
                 "cases": nvic},
        "gpio": {"port_f": hex(GPIOF), "pin_1_alias": hex(GPIOF + offset), "clear_irq": hex(GPIOF + 0x41C),
                 "checked_three_bit_inputs": inputs_subset, "manual_masked_read_example": "0x30",
                 "masked_writes_preserve_pin_zero": True, "wrong_full_port_write": wrong,
                 "timer_profiles": len(timer["images"]), "gpio_irq_clear": "manufacturer_rule_only"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(json.dumps(check(), indent=2, sort_keys=True) + "\n")
