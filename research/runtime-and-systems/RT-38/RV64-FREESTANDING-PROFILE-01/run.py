"""Validate the archived evidence for a bounded privileged freestanding profile."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
DIRECTION = HERE.parents[1]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def checked_bytes(relative, content_hash):
    path = (DIRECTION / relative).resolve()
    require(path.is_relative_to(DIRECTION), relative)
    data = path.read_bytes()
    require(sha256(data).hexdigest() == content_hash, f"changed evidence: {relative}")
    return data


def scope(profile, domain, claim):
    if domain != "rv64-qemu-single-hart" or claim in profile["limits"]:
        return "outside-profile"
    archive = profile["archives"].get(claim)
    if archive is None:
        return "unknown-evidence"
    return archive["kind"]


def verify(profile):
    platform = profile["platform"]
    tools = profile["toolchain"]
    archives = {key: json.loads(checked_bytes(ref["path"], ref["sha256"]))
                for key, ref in profile["archives"].items()}
    sources = {Path(path).parent.name + "/" + Path(path).name: checked_bytes(path, digest).decode()
               for path, digest in profile["pinned_sources"].items()}
    image_counts = {}
    digest_fields = set()
    for claim, archive in archives.items():
        images = archive["images"]
        image_counts[claim] = len(images)
        if claim == "startup-closure":
            require(archive["target"] == "thumbv7m-none-eabi" and archive["machine"] == "lm3s6965evb",
                    "RT-37 profile cannot supply RV64 target evidence")
            require("llvm_unspecified_unwind_O0" in archive["controls"], "independent closure control missing")
            continue
        require((archive["machine"], archive["harts"]) == (platform["machine"], platform["harts"]), claim)
        require(archive.get("cpu", platform["cpu"]) == platform["cpu"], claim)
        require(tools["llvm"] in archive["tools"]["mc"] and tools["llvm"] in archive["tools"]["lld"]
                and tools["qemu"] in archive["tools"]["qemu"], claim)
        for name, image in images.items():
            require(re.fullmatch("[a-f0-9]{64}", image["elf_sha256"]), name)
            digest_fields.add(image["elf_sha256"])

    for name in ("riscv-trap-isolation", "riscv-cooperative-scheduler", "riscv-address-spaces"):
        source = sources[f"{name}/run.py"]
        for flag, value in (("-machine", platform["machine"]), ("-cpu", platform["cpu"]),
                            ("-m", f"{platform['memory_mib']}M"), ("-smp", platform["harts"]), ("-bios", platform["bios"])):
            require(f'"{flag}", "{value}"' in source, (name, flag, value))
    trap = sources["riscv-trap-isolation/run.py"]
    for check in (platform["kernel_entry"], "INTERP|DYNAMIC", "--undefined-only", platform["target"]):
        require(check in trap, check)
    for extension in platform["instruction_attributes"]:
        require(f"+{extension}" in trap, extension)
    boot = sources["riscv-cooperative-scheduler/boot.s"]
    for item in ("csrrw sp, mscratch, sp", "csrr t0, mcause", "csrw mepc, t0", "mret", "ecall"):
        require(item in boot, item)
    integrated = archives["isolated-ipc"]
    remap = archives["local-translation"]["qemu_scope"]
    require(integrated["qemu_scope"]["revision"] == remap["revision"] == tools["qemu_source"], "QEMU source mismatch")
    require(integrated["qemu_scope"]["flushes_on_changed_satp"] and not remap["address_operand_used"], "QEMU scope")
    shared = integrated["images"]["shared_asid_full_fence"]
    no_fence = integrated["images"]["shared_asid_missing_fence"]
    require(shared["uart"] == no_fence["uart"] and "sfence.vma" in shared["translation_switch_instructions"]
            and "sfence.vma" not in no_fence["translation_switch_instructions"], "fence discriminator")
    require(shared["page_table_bytes"] == 6 * 4096, "unexpected page tables")
    return image_counts, len(digest_fields)


def controls(profile):
    cases = (
        ("rv64-qemu-single-hart", "entry-and-trap", "executable-closure-and-qemu"),
        ("rv64-qemu-single-hart", "isolated-ipc", "linked-instructions-and-qemu"),
        ("rv64-qemu-single-hart", "frame-allocation", "separate-model-and-qemu"),
        ("rv64-qemu-single-hart", "startup-closure", "shared-method-only"),
        ("rv64-physical", "isolated-ipc", "outside-profile"),
        ("rv64-qemu-smp", "isolated-ipc", "outside-profile"),
        ("rv64-qemu-single-hart", "source-to-linked-refinement", "outside-profile"),
        ("rv64-qemu-single-hart", "preemption", "outside-profile"),
        ("rv64-qemu-single-hart", "supervisor-kernel-entry", "outside-profile"),
        ("rv64-qemu-single-hart", "new-linker-profile", "unknown-evidence"),
    )
    outcomes = {}
    for domain, claim, expected in cases:
        observed = scope(profile, domain, claim)
        require(observed == expected, (domain, claim, observed))
        outcomes[f"{domain}/{claim}"] = observed
    return outcomes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = HERE / "profile.json"
    profile = json.loads(manifest.read_text())
    counts, unique = verify(profile)
    report = {
        "profile_sha256": sha256(manifest.read_bytes()).hexdigest(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "verified_archive_count": len(counts), "archived_image_rows": counts, "distinct_rv64_elf_digests": unique,
        "scope_controls": controls(profile),
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
