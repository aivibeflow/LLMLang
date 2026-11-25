"""Rebuild release/debug artifacts and compare exact validation keys independently."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASELINE = "aed8cd10deda5e60764774aacf22f40a48fa928f"
ENV = os.environ | {"LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1767225600"}
PROFILES = {"release": ("-g0",), "debug": ("-g", "-gdwarf-5")}
CASES = {
    "baseline": (1, "old.llm", 10, 127),
    "source-location": (1, "new.llm", 40, 127),
    "contract-domain": (1, "old.llm", 10, 255),
    "body": (2, "old.llm", 10, 127),
}


def invoke(*args, cwd):
    return subprocess.check_output(args, cwd=cwd, env=ENV, timeout=30)


def sha(bytes_):
    return hashlib.sha256(bytes_).hexdigest()


def semantic_hash(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def emit(addend, source, line):
    return (
        "#include <stdint.h>\n"
        f'#line {line} "{source}"\n'
        f"uint8_t translate(uint8_t input) {{ return (uint8_t)(input + {addend}u); }}\n"
    ).encode()


def build(tools, directory, variant):
    addend, source, line, max_input = variant
    directory.mkdir()
    generated = emit(addend, source, line)
    (directory / "unit.c").write_bytes(generated)
    observer = (HERE / "observe.c").read_bytes()
    (directory / "observe.c").write_bytes(observer)
    common = ("-std=c17", "-O2", "-Wall", "-Wextra", "-Werror",
              f"-ffile-prefix-map={directory}=/fixture")
    results = {}
    for profile, settings in PROFILES.items():
        object_file = f"{profile}.o"
        executable = f"{profile}.elf"
        invoke(tools.cc, *common, *settings, "-c", "unit.c", "-o", object_file, cwd=directory)
        invoke(tools.cc, *common, "-g0", "observe.c", object_file, "-o", executable, cwd=directory)
        invoke(tools.objcopy, "-O", "binary", "--only-section=.text", object_file, "text.bin",
               cwd=directory)
        decoded_lines = invoke(tools.readelf, "--debug-dump=decodedline", object_file, cwd=directory)
        entries = [raw for raw in decoded_lines.decode().splitlines() if raw.startswith(source + " ")]
        if profile == "debug":
            lines = {int(raw.split()[1]) for raw in entries if raw.split()[1].isdigit()}
            assert lines == {line}
        else:
            assert decoded_lines == b""
        observed = [int(x) for x in invoke(directory / executable, cwd=directory).splitlines()]
        assert observed == [(i + addend) % 256 for i in range(256)]
        results[profile] = {
            "object_sha256": sha((directory / object_file).read_bytes()),
            "text_sha256": sha((directory / "text.bin").read_bytes()),
            "executable_sha256": sha((directory / executable).read_bytes()),
            "decoded_line_sha256": sha(decoded_lines), "decoded_source_rows": entries,
            "outputs": observed,
        }
    assert results["debug"]["text_sha256"] == results["release"]["text_sha256"]
    contract = {"maximum_input_inclusive": max_input, "expected_addend": 1, "modulus": 256}
    subject = {
        "release_executable": results["release"]["executable_sha256"],
        "contract": semantic_hash(contract),
        "observer_source": sha(observer),
        "oracle": "exhaustive-unit-uint8-v1",
    }
    mismatches = [
        i for i in range(max_input + 1)
        if results["release"]["outputs"][i] != (i + contract["expected_addend"]) % contract["modulus"]
    ]
    return {
        "semantic_body": semantic_hash({"argument": "uint8", "addend": addend}),
        "generated_source_sha256": sha(generated), "source_location": [source, line],
        "contract": contract, "validation_subject": subject,
        "validation_key": semantic_hash(subject),
        "validation": {"checked": max_input + 1, "mismatches": mismatches},
        "profiles": results,
    }


def compare(results):
    baseline = results["baseline"]
    expectations = {
        "source-location": (True, False, True, True, 128, 0),
        "contract-domain": (True, True, True, False, 256, 0),
        "body": (False, False, False, False, 128, 128),
    }
    comparisons = {}
    for name, expected in expectations.items():
        other = results[name]
        measured = (
            other["profiles"]["release"]["executable_sha256"]
            == baseline["profiles"]["release"]["executable_sha256"],
            other["profiles"]["debug"]["executable_sha256"]
            == baseline["profiles"]["debug"]["executable_sha256"],
            other["profiles"]["debug"]["text_sha256"]
            == baseline["profiles"]["debug"]["text_sha256"],
            other["validation_key"] == baseline["validation_key"],
            other["validation"]["checked"],
            len(other["validation"]["mismatches"]),
        )
        assert measured == expected, (name, measured, expected)
        columns = ("same_release", "same_debug", "same_machine_text", "same_validation_key",
                   "checked", "mismatches")
        comparisons[name] = dict(zip(columns, measured, strict=True))
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--readelf", default="readelf")
    parser.add_argument("--objcopy", default="objcopy")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-selective-translation-") as temporary:
        directory = Path(temporary)
        versions = {
            name: invoke(getattr(args, name), "--version", cwd=directory).decode().splitlines()[0]
            for name in ("cc", "readelf", "objcopy")
        }
        versions["target"] = invoke(args.cc, "-dumpmachine", cwd=directory).decode().strip()
        results = {name: build(args, directory / name, spec) for name, spec in CASES.items()}
    print(json.dumps({
        "baseline": BASELINE, "tools": versions, "python": platform.python_version(),
        "study_sha256": {name: sha((HERE / name).read_bytes()) for name in ("run.py", "observe.c")},
        "results": results, "comparisons": compare(results),
    }, indent=2))


if __name__ == "__main__":
    main()
