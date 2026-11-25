"""Verify ad-hoc signature page coverage on newly linked synthetic Mach-O libraries."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
PROVIDER = HERE.parent / "FFI-MACHO-PROFILES-01" / "provider.c"
PROFILES = {
    "macos-arm64": ("arm64-apple-macos13.0", "arm64", "macos", "13.0"),
    "macos-x64": ("x86_64-apple-macos13.0", "x86_64", "macos", "13.0"),
    "ios-arm64": ("arm64-apple-ios16.0", "arm64", "ios", "16.0"),
}
LC_SEGMENT_64 = 0x19
LC_CODE_SIGNATURE = 0x1D
SUPER_BLOB = 0xFADE0CC0
CODE_DIRECTORY = 0xFADE0C02


def run(args):
    return subprocess.check_output(args, text=True, timeout=20)


def macho(blob):
    magic, cpu, _, file_type, commands, commands_size = struct.unpack_from("<6I", blob)
    assert magic == 0xFEEDFACF and file_type == 6
    assert commands_size + 32 <= len(blob)
    offset = 32
    signatures = []
    text_sections = []
    for _ in range(commands):
        command, size = struct.unpack_from("<II", blob, offset)
        assert size >= 8 and offset + size <= 32 + commands_size
        if command == LC_CODE_SIGNATURE:
            start, count = struct.unpack_from("<II", blob, offset + 8)
            assert start + count <= len(blob) and start >= 32 + commands_size
            signatures.append((start, count))
        if command == LC_SEGMENT_64:
            sections = struct.unpack_from("<I", blob, offset + 64)[0]
            assert size == 72 + 80 * sections
            for section in range(sections):
                origin = offset + 72 + section * 80
                name = blob[origin:origin + 16].rstrip(b"\0")
                if name == b"__text":
                    text_offset = struct.unpack_from("<I", blob, origin + 48)[0]
                    text_sections.append(text_offset)
        offset += size
    assert offset == 32 + commands_size and len(text_sections) == 1 and len(signatures) <= 1
    return cpu, text_sections[0], signatures[0] if signatures else None


def check_directory(blob, signature):
    start, max_size = signature
    magic, size, count = struct.unpack_from(">III", blob, start)
    assert magic == SUPER_BLOB and 12 + count * 8 <= size <= max_size
    directories = []
    for slot in range(count):
        section_type, relative = struct.unpack_from(">II", blob, start + 12 + slot * 8)
        assert relative >= 12 + count * 8 and relative + 44 <= size
        if section_type == 0:
            directories.append(start + relative)
    assert len(directories) == 1
    base = directories[0]
    magic, length, version, flags, hashes, _, extra_slots, pages, cap = struct.unpack_from(">9I", blob, base)
    digest_size, hash_type, _, page_log = struct.unpack_from(">4B", blob, base + 36)
    assert magic == CODE_DIRECTORY and flags & 2 and extra_slots == 0
    assert digest_size == 32 and hash_type == 2 and page_log < 30
    assert cap == start and base + length <= start + size and hashes + pages * digest_size <= length
    chunk = 1 << page_log
    assert pages == (cap + chunk - 1) // chunk
    bad_pages = []
    for i in range(pages):
        expected = blob[base + hashes + i * digest_size:base + hashes + (i + 1) * digest_size]
        if sha256(blob[i * chunk:min((i + 1) * chunk, cap)]).digest() != expected:
            bad_pages.append(i)
    return {"directory_version": version, "pages": pages, "page_bytes": chunk,
            "code_directory_sha256": sha256(blob[base:base + length]).hexdigest(),
            "bad_pages": bad_pages, "signature_slots": count}


def verify(clang, linker):
    rows = {}
    with TemporaryDirectory() as directory:
        work = Path(directory)
        for name, use_signature in product(PROFILES, (False, True)):
            triple, arch, operating_system, release = PROFILES[name]
            obj = work / "provider.o"
            dylib = work / "libspan.dylib"
            run([clang, f"--target={triple}", "-O2", "-ffreestanding", "-fno-builtin", "-c",
                 PROVIDER, "-o", obj])
            run([linker, "-dylib", "-arch", arch, "-platform_version", operating_system, release, release,
                 "-no_uuid", "-install_name", "@rpath/libspan.dylib",
                 "-adhoc_codesign" if use_signature else "-no_adhoc_codesign", obj, "-o", dylib])
            blob = dylib.read_bytes()
            cpu, text, signature = macho(blob)
            assert (signature is not None) == use_signature
            record = {"file_sha256": sha256(blob).hexdigest(), "cpu": cpu, "signature_present": use_signature}
            if use_signature:
                checked = check_directory(blob, signature)
                assert not checked["bad_pages"]
                modified = bytearray(blob)
                modified[text] ^= 1
                variant = bytes(modified)
                assert macho(variant) == (cpu, text, signature)
                changed = check_directory(variant, signature)
                assert changed["bad_pages"] == [text // checked["page_bytes"]]
                record["directory"] = checked
                record["changed_text_page_detected"] = changed["bad_pages"][0]
            rows[f"{name}/{'ad-hoc' if use_signature else 'unsigned'}"] = record
    return {"profiles": rows, "source_sha256": sha256(PROVIDER.read_bytes()).hexdigest(),
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "clang": run([clang, "--version"]).splitlines()[0], "lld": run([linker, "--version"]).splitlines()[0]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--linker", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.clang, args.linker), indent=2, sort_keys=True))
