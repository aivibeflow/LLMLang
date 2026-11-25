"""Compare runtime declaration, byte identity and observations for controlled native providers."""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
INTERFACE_V1 = 1
BASE_LABEL = "1.0.0"
UNTOUCHED = -101
INPUTS = [-(2**31), -1, *range(32), 32, 2**31 - 1]
BUILD_MATRIX = {
    "baseline": (INTERFACE_V1, BASE_LABEL, "baseline", 0),
    "metadata-only": (INTERFACE_V1, BASE_LABEL, "rebuilt", 0),
    "changed-behavior": (INTERFACE_V1, BASE_LABEL, "baseline", 3),
    "new-version-label": (INTERFACE_V1, "1.1.0", "baseline", 0),
    "other-interface": (2, BASE_LABEL, "baseline", 0),
}
EXPECTED = {
    # interface, interface + label, interface + artifact, v1 trace differences
    "baseline": (True, True, True, 0),
    "identical-copy": (True, True, True, 0),
    "metadata-only": (True, True, False, 0),
    "changed-behavior": (True, True, False, 24),
    "new-version-label": (True, False, False, 0),
    "other-interface": (False, False, False, None),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(argv, directory):
    return subprocess.run(argv, cwd=directory, check=True, capture_output=True, text=True,
                          timeout=60, env={**os.environ, "LC_ALL": "C"})


def build(cc, directory):
    for name, (interface, label, stamp, offset) in BUILD_MATRIX.items():
        target = directory / name
        target.mkdir()
        invoke([cc, "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2", "-fPIC", "-shared",
                "-Wl,-soname,libprobe.so.1", f"-DPROBE_INTERFACE={interface}",
                f'-DPROBE_LABEL="{label}"', f'-DPROBE_STAMP="{stamp}"',
                f"-DPROBE_OFFSET={offset}", str(HERE / "provider.c"), "-o", "libprobe.so.1"],
               target)
    (directory / "identical-copy").mkdir()
    shutil.copyfile(directory / "baseline/libprobe.so.1",
                    directory / "identical-copy/libprobe.so.1")


def v1_oracle(value):
    if value not in range(32):
        return [value, 1, UNTOUCHED]
    quotient, _ = divmod(value, 4)
    return [value, 0, quotient]


def observe(path, baseline_digest):
    artifact = digest(path)
    library = ctypes.CDLL(str(path))
    library.probe_label.argtypes = []
    library.probe_label.restype = ctypes.c_char_p
    library.probe_build_stamp.argtypes = []
    library.probe_build_stamp.restype = ctypes.c_char_p
    library.probe_interface.argtypes = []
    library.probe_interface.restype = ctypes.c_uint32
    interface = library.probe_interface()
    label = library.probe_label().decode("ascii")
    abi_accepted = interface == INTERFACE_V1
    decisions = {
        "interface": abi_accepted,
        "interface_and_label": abi_accepted and label == BASE_LABEL,
        "interface_and_artifact": abi_accepted and artifact == baseline_digest,
    }

    # Collect the controlled behavior even for rejected artifacts with this interface.
    # The other interface is left uncalled through the v1 operation signature.
    traces = []
    differences = None
    if abi_accepted:
        library.probe_quantize.argtypes = [ctypes.c_int32, ctypes.POINTER(ctypes.c_int32)]
        library.probe_quantize.restype = ctypes.c_int32
        for value in INPUTS:
            slot = ctypes.c_int32(UNTOUCHED)
            status = library.probe_quantize(value, ctypes.byref(slot))
            traces.append([value, status, slot.value])
        differences = [trace[0] for trace in traces if trace != v1_oracle(trace[0])]

    return {
        "artifact_sha256": artifact,
        "declared_interface": interface,
        "declared_label": label,
        "reported_build_stamp": library.probe_build_stamp().decode("ascii"),
        "decisions": decisions,
        "v1_difference_inputs": differences,
        "traces_input_status_slot": traces,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="native-runtime-version-") as temp:
        directory = Path(temp)
        build(args.cc, directory)
        baseline_digest = digest(directory / "baseline/libprobe.so.1")
        rows = {}
        for name, (interface, label, artifact, difference_count) in EXPECTED.items():
            row = observe(directory / name / "libprobe.so.1", baseline_digest)
            assert row["decisions"] == {
                "interface": interface,
                "interface_and_label": label,
                "interface_and_artifact": artifact,
            }, (name, row)
            differences = row["v1_difference_inputs"]
            expected_inputs = [value for value in range(32) if value % 4] if difference_count else []
            if difference_count is None:
                assert differences is None and row["traces_input_status_slot"] == []
            else:
                assert differences == expected_inputs and len(differences) == difference_count
                assert len(row["traces_input_status_slot"]) == len(INPUTS)
            rows[name] = row
        assert len({row["artifact_sha256"] for row in rows.values()}) == len(BUILD_MATRIX)
        receipt = {
            "compiler": invoke([args.cc, "--version"], directory).stdout.splitlines()[0],
            "target": invoke([args.cc, "-dumpmachine"], directory).stdout.strip(),
            "source_sha256": {name: digest(HERE / name) for name in ("provider.c", "run.py")},
            "providers": rows,
            "native_operations": sum(len(row["traces_input_status_slot"]) for row in rows.values()),
        }
        print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
