"""Check fixed static bindings and draining native runtime invocation leases."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
TRIALS = 16


def run(*command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    if result.returncode or result.stderr:
        raise ValueError((command, result.returncode, result.stderr))
    return result.stdout


def expected():
    def call(label, provider, value):
        result = (3 * value + 1) % (1 << 32)
        return f"{label} {provider} {result} {value} 1"
    return [
        call("static-before", 1, 9),
        "retained-during-replacement 1",
        "stale-new-call-rejected 1",
        "independent-rejection-controls 2",
        call("runtime-after", 2, 9),
        call("static-after", 1, 9),
        call("runtime-already-started", 1, (1 << 32) - 1),
        "retired-handle-released 1",
        "runtime-no-binding 1",
        call("static-without-runtime-binding", 1, 9),
    ]


def build_and_check(compiler, stage, headers=()):
    stage.mkdir()
    flags = ("-O2", "-std=c17", "-Wall", "-Wextra", "-Werror", f"-ffile-prefix-map={HERE}=.", *headers)
    static = stage / "static.o"
    probe = stage / "probe"
    run(compiler, *flags, "-DPROVIDER_ID=1", "-c", HERE / "provider.c", "-o", static)
    run(compiler, *flags, "-pthread", HERE / "probe.c", static, "-ldl", "-o", probe)
    shared = []
    for revision in (1, 2):
        library = stage / f"provider-{revision}.so"
        run(compiler, *flags, "-shared", "-fPIC", f"-DPROVIDER_ID={revision}", HERE / "provider.c", "-o", library)
        shared.append(library)
    needed = run("readelf", "-d", probe)
    symbols = run("nm", "--defined-only", probe).splitlines()
    has_static_symbol = any(line.split()[-2:] == ["T", "step"] for line in symbols)
    if not has_static_symbol or any(library.name in needed for library in shared):
        raise ValueError("probe did not preserve the explicit static-link boundary")
    oracle = expected()
    for _ in range(TRIALS):
        observations = run(probe, *shared).splitlines()
        if observations != oracle:
            raise ValueError(observations)
    return {
        "compiler": run(compiler, "--version").splitlines()[0],
        "trials": TRIALS,
        "shared_objects_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in shared},
        "statically_defined_step": has_static_symbol,
        "trace": observations,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt13-binding-") as temp:
        scratch = Path(temp)
        gcc_headers = run("gcc", "-print-file-name=include").strip()
        evidence = {
            "profiles": {
                "gcc": build_and_check("gcc", scratch / "gcc"),
                "clang": build_and_check(args.clang, scratch / "clang", ("-isystem", gcc_headers)),
            },
            "tools": {"glibc": run("getconf", "GNU_LIBC_VERSION").strip(),
                      "binutils": run("readelf", "--version").splitlines()[0]},
            "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ("provider.h", "provider.c", "probe.c", "run.py")},
        }
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
