#!/usr/bin/env python3
"""Compare live descriptor, DWARF offsets and native record behavior separately."""

from collections import Counter
import ctypes
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
FIELDS = ("amount", "category", "flags")
WIDTH = (4, 4, 2)
VARIANTS = {
    "canonical": (0, 0, 0),
    "same_size_swap": (1, 0, 0),
    "same_size_prefix": (2, 0, 0),
    "packed": (3, 0, 0),
    "stale_descriptor": (1, 1, 0),
    "same_layout_new_behavior": (0, 0, 1),
    "same_size_wide_field": (4, 0, 0),
    "stale_field_width": (4, 2, 0),
}
VALUES = ((0, 1, 705, 2**32 - 1), (0, 2, 311, 2**32 - 1), (0, 3, 17, 2**16 - 1))
GATES = ("symbol", "size_alignment", "descriptor", "verified_direct", "verified_adapter", "exact_behavior")
DIE = re.compile(r"\s*<(\d+)><([0-9a-f]+)>: Abbrev Number: \d+(?: \((DW_TAG_\w+)\))?")
ATTR = re.compile(r".*?\bDW_AT_(\w+)\s*:\s*(.*)")


def command(arguments):
    return subprocess.check_output(arguments, text=True, timeout=30)


def digest(data):
    return sha256(data).hexdigest()


def build(scratch, name, optimize):
    layout, stale, drift = VARIANTS[name]
    output = scratch / f"{name}-O{optimize}.so"
    source = scratch / "provider.c"
    subprocess.run(
        ["cc", "-std=c17", "-g", "-gdwarf-4", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror",
         f"-fdebug-prefix-map={scratch}=/llmlang/record-layout", "-Wl,--build-id=none",
         f"-O{optimize}", f"-DLAYOUT={layout}", f"-DSTALE_DESCRIPTOR={stale}", f"-DDIFFERENT_BEHAVIOR={drift}",
         str(source), "-o", str(output)], cwd=scratch, check=True, timeout=30,
    )
    return output


def dwarf_layout(provider):
    """Extract the fixture struct layout from DWARF and the ELF byte order."""
    entries = []
    for line in command(["readelf", "--debug-dump=info", str(provider)]).splitlines():
        node = DIE.fullmatch(line)
        attr = ATTR.fullmatch(line)
        if node:
            entries.append((int(node[1]), int(node[2], 16), node[3], {}))
        elif attr and entries:
            entries[-1][3][attr[1]] = attr[2]

    by_offset = {offset: (kind, attrs) for _, offset, kind, attrs in entries}
    matches = [(index, depth, attributes) for index, (depth, _, kind, attributes) in enumerate(entries)
               if kind == "DW_TAG_structure_type" and attributes.get("name", "").split(": ")[-1] == "wire_record"]
    (index, depth, attributes), = matches
    offsets, widths = {}, {}

    def type_width(reference):
        kind, attrs = by_offset[int(reference.strip("<>"), 16)]
        while kind == "DW_TAG_typedef":
            kind, attrs = by_offset[int(attrs["type"].strip("<>"), 16)]
        assert kind == "DW_TAG_base_type" and attrs["encoding"].endswith("(unsigned)")
        return int(attrs["byte_size"], 0)

    for level, _, kind, member in entries[index + 1:]:
        if level <= depth:
            break
        if kind == "DW_TAG_member" and level == depth + 1:
            field = member["name"].split(": ")[-1]
            offsets[field] = int(member["data_member_location"], 0)
            widths[field] = type_width(member["type"])
    assert set(offsets) == set(FIELDS)
    elf = provider.read_bytes()[:6]
    assert elf[:4] == b"\x7fELF" and elf[5] in {1, 2}
    return {"size": int(attributes["byte_size"], 0), "offsets": [offsets[name] for name in FIELDS],
            "widths": [widths[name] for name in FIELDS], "endian": "little" if elf[5] == 1 else "big"}


def inspect(library):
    function = library.layout_word
    function.argtypes = [ctypes.c_uint]
    function.restype = ctypes.c_size_t
    size, align, *details = (function(index) for index in range(9))
    return {"size": size, "alignment": align, "offsets": details[:3], "widths": details[3:6],
            "endian": "little" if details[6] else "big"}


def bytes_for(descriptor, values):
    data = bytearray(descriptor["size"])
    for offset, width, value in zip(descriptor["offsets"], descriptor["widths"], values, strict=True):
        data[offset:offset + width] = value.to_bytes(width, descriptor["endian"])
    return bytes(data)


def observations(library, descriptor):
    score = library.score_record
    score.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint64)]
    score.restype = ctypes.c_int
    result = []
    for values in product(*VALUES):
        data = bytes_for(descriptor, values)
        buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        score_value = ctypes.c_uint64()
        status = score(buffer, len(data), ctypes.byref(score_value))
        result.append([status, score_value.value if status == 0 else None])
    return result


def oracle():
    return [[0, 11 * amount + 103 * category + 1009 * flags] for amount, category, flags in product(*VALUES)]


def fits(descriptor):
    if tuple(descriptor["widths"]) != WIDTH:
        return False
    used = set()
    for offset, width in zip(descriptor["offsets"], descriptor["widths"], strict=True):
        positions = set(range(offset, offset + width))
        if offset < 0 or offset + width > descriptor["size"] or used & positions:
            return False
        used |= positions
    return True


def compare(selected, expected_layout, expected_values, identity):
    descriptor = selected["metadata"]
    debug = selected["dwarf"]
    says_expected = descriptor == expected_layout
    same_dimensions = (descriptor["size"], descriptor["alignment"]) == (
        expected_layout["size"], expected_layout["alignment"])
    verified = fits(descriptor) and all(descriptor[key] == value for key, value in debug.items())
    exact = selected["adapter_observations"] == expected_values
    decision = {
        "symbol": (True, selected["fixed_observations"]),
        "size_alignment": (same_dimensions, selected["fixed_observations"]),
        "descriptor": (says_expected, selected["fixed_observations"]),
        "verified_direct": (says_expected and verified, selected["fixed_observations"]),
        "verified_adapter": (verified, selected["adapter_observations"]),
        "exact_behavior": (verified and exact, selected["adapter_observations"]),
    }
    return {key: {"accepted": gate,
                  "wrong_vectors": sum(left != right for left, right in zip(values, expected_values)) if gate else 0,
                  "checked_provider_sha256": identity if gate and key == "exact_behavior" else None}
            for key, (gate, values) in decision.items()}


def run(scratch):
    source = HERE / "provider.c"
    (scratch / source.name).write_bytes(source.read_bytes())
    rows = []
    expected_values = oracle()
    expected_layout = {"size": 12, "alignment": 4, "offsets": [0, 4, 8], "widths": [4, 4, 2],
                       "endian": "little"}
    for name, optimize in product(VARIANTS, (0, 3)):
        provider = build(scratch, name, optimize)
        identity = digest(provider.read_bytes())
        library = ctypes.CDLL(str(provider))
        descriptor = inspect(library)
        debug = dwarf_layout(provider)
        direct = observations(library, expected_layout)
        adapted = observations(library, descriptor)
        selected = {"metadata": descriptor, "dwarf": debug,
                    "fixed_observations": direct, "adapter_observations": adapted}
        gates = compare(selected, expected_layout, expected_values, identity)
        rows.append({"case": name, "optimization": optimize, "provider_sha256": identity,
                     "layout_receipt": digest(json.dumps([identity, debug], separators=(",", ":")).encode()),
                     **selected, "gates": gates})
    for name in VARIANTS:
        first, second = [row for row in rows if row["case"] == name]
        assert first["provider_sha256"] != second["provider_sha256"]
        assert first["layout_receipt"] != second["layout_receipt"]
        for key in ("metadata", "dwarf", "fixed_observations", "adapter_observations"):
            assert first[key] == second[key]
    assert all(row["gates"]["exact_behavior"]["accepted"] ==
               (row["case"] in {"canonical", "same_size_swap", "same_size_prefix", "packed"})
               for row in rows)
    for row in rows:
        if row["case"] in {"stale_descriptor", "stale_field_width"}:
            assert row["gates"]["descriptor"]["accepted"] and not row["gates"]["verified_adapter"]["accepted"]
        if row["case"] == "same_layout_new_behavior":
            assert row["gates"]["verified_direct"]["accepted"] and not row["gates"]["exact_behavior"]["accepted"]
    rollup = {}
    for gate in GATES:
        values = Counter()
        for row in rows:
            values["accepted"] += row["gates"][gate]["accepted"]
            values["wrong_vectors"] += row["gates"][gate]["wrong_vectors"]
        rollup[gate] = dict(values)
    return {
        "schema": "llmlang-rt13-native-record-layout/1", "python": platform.python_version(),
        "cc": command(["cc", "--version"]).splitlines()[0], "target": command(["cc", "-dumpmachine"]).strip(),
        "readelf": command(["readelf", "--version"]).splitlines()[0], "expected_layout": expected_layout,
        "provider_source_sha256": digest(source.read_bytes()), "runner_sha256": digest(Path(__file__).read_bytes()),
        "vectors_per_route": len(expected_values), "artifact_count": len(rows),
        "native_invocations": 2 * len(rows) * len(expected_values), "rollup": rollup,
        "values": VALUES, "observations": rows,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt13-layout-") as scratch:
        result = run(Path(scratch))
    observations = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row) for row in observations))
    print("  ]\n}")
