"""Compose the verified wrapping adapters and check the RT-30 reference matrix."""

import argparse
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RT30 = HERE.parent
RT13 = HERE.parents[1] / "RT-13" / "GENERATED-GO-INTEGERS-01"
sys.path.insert(0, str(RT13))
from run import FIXTURE, GO_VERSION, source, reference, vectors
from lower_go import lower
from integer_fixture import WRAPPING, compile_source


ADAPTERS = {
    "c_family": "C-FAMILY-ROUNDTRIP-01/roundtrip.py",
    "go": "GO-ROUNDTRIP-01/roundtrip.py",
    "rust": "RUST-WRAPPING-ROUNDTRIP-01/roundtrip.py",
}
TARGETS = ("c", "cpp", "go", "rust")
ROUTES = ("llmlang-fixture", *TARGETS)
OBSERVATIONS = ("status", "output_slot", "ordered_callbacks")


def load(adapter):
    path = RT30 / ADAPTERS[adapter]
    spec = importlib.util.spec_from_file_location(f"rt30_{adapter}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def records_sha256(expected):
    trace = sha256()
    for status, slot, events in expected:
        if status != "ok" or len(events) != 2:
            raise ValueError(("expected wrapping fixture profile", status, events))
        trace.update(struct.pack("<5I", 0, slot, 2, *events))
    return trace.hexdigest()


def import_profiles(args, modules, directory, programs):
    c_family, go, rust = modules
    directory.mkdir()
    c_templates = c_family.make_templates(args.clang, directory, ("c", "cpp"), programs)
    imported = {"llmlang-fixture": programs}
    for profile in ("c", "cpp"):
        readings = tuple(c_family.recognize(
            args.clang, directory, profile, c_family.original(profile, f"source_{index}", program),
            c_templates[profile],
        ) for index, program in enumerate(programs))
        if readings != tuple(("accepted", term) for term in programs):
            raise ValueError((profile, "import changed the checked program"))
        imported[profile] = tuple(term for _, term in readings)

    go_directory = directory / "go-import"
    go_directory.mkdir()
    (go_directory / "go.mod").write_text("module llmlang.local/matriximport\n\ngo 1.27\n", encoding="utf-8")
    (go_directory / "main.go").write_bytes((RT30 / "GO-ROUNDTRIP-01/import.go").read_bytes())
    go_importer = go.build(args, go_directory, "standalone")
    imported["go"] = tuple(go.program_from_result(go.recognize(
        go_importer, directory / "go-input.go", go.original_source(i, term.operation, *term.operands),
    )) for i, term in enumerate(programs))

    rust_target = directory / "rust-target"
    rust_manifest = RT30 / "RUST-WRAPPING-ROUNDTRIP-01/Cargo.toml"
    rust.invoke(args.cargo, ("build", "--offline", "--locked", "--manifest-path", rust_manifest,
                             "--target-dir", rust_target), directory, cargo_rustc=args.rustc)
    rust_importer = rust_target / "debug/bounded-wrapping-import"
    rust_readings = tuple(rust.recognize(rust_importer, directory, rust.original(i, term))
                          for i, term in enumerate(programs))
    if rust_readings != tuple(("accepted", term) for term in programs):
        raise ValueError(("rust", "import changed the checked program"))
    imported["rust"] = tuple(term for _, term in rust_readings)

    if any(terms != programs for terms in imported.values()):
        raise ValueError("Cross-profile import changed checked scalar programs")
    return imported


def native_route(args, modules, directory, target, terms, cases, expected, packet):
    c_family, go, rust = modules
    directory.mkdir()
    if target in ("c", "cpp"):
        programs = tuple(c_family.emit(target, f"probe_{i}", term.operation, term.operands)
                         for i, term in enumerate(terms))
        observed = c_family.compile_and_compare(args.clang, directory, "probe", target,
                                                programs, cases, expected, 2)
        return {"observations": observed["records"], "trace_sha256": observed["trace_sha256"]}
    if target == "go":
        go_dir = directory / "go"
        go.emit_project(go_dir, lower(terms), "standalone", len(terms))
        executable = go.build(args, go_dir, "standalone")
        stream = tuple(go.standalone(executable, cases))
        if stream != expected:
            raise ValueError("Native Go route disagrees with the checked source")
        return {"observations": len(stream), "trace_sha256": records_sha256(stream)}

    fixtures = tuple(rust.emit(index, term) for index, term in enumerate(terms))
    host = rust.write_host(directory, "exported", fixtures)
    executable = rust.native_build(args.rustc, directory, host, "exported", 3, "yes")
    observed = rust.observations(executable, directory, packet, expected)
    return {"observations": observed["records"], "trace_sha256": observed["trace_sha256"]}


def verify(args, directory):
    modules = tuple(load(adapter) for adapter in ADAPTERS)
    c_family, go, rust = modules
    toolchain = {
        "clang": c_family.invoke(args.clang, ("--version",), directory).stdout.splitlines(),
        "go": go.run(args.go, "version").decode().strip(),
        "rustc": rust.invoke(args.rustc, ("-vV",), directory).stdout.decode().splitlines(),
    }
    if toolchain["go"] != GO_VERSION:
        raise ValueError(toolchain["go"])
    programs = tuple(compile_source(source(op, left, right))
                     for op, (left, right) in product(WRAPPING, product("ab", repeat=2)))
    imported = import_profiles(args, modules, directory / "imports", programs)
    cases = tuple(product(range(len(programs)), vectors()))
    expected = tuple(reference(programs[index], vector) for index, vector in cases)
    digest_expected = records_sha256(expected)
    packet = b"".join(struct.pack("<4I", index, *vector) for index, vector in cases)

    matrix = {}
    ir = "llmlang-fixture"
    matrix[ir] = {ir: {"status": "not-a-translation"}}
    for source_profile in TARGETS:
        matrix[source_profile] = {ir: {"status": "restricted-checked-import",
                                       "checked_programs": len(imported[source_profile])}}
    for source_profile, target in product(ROUTES, TARGETS):
        evidence = native_route(args, modules, directory / f"{source_profile}-to-{target}", target,
                                imported[source_profile], cases, expected, packet)
        if evidence != {"observations": len(expected), "trace_sha256": digest_expected}:
            raise ValueError((source_profile, target, evidence))
        matrix[source_profile][target] = {"status": "restricted-differential-pass", **evidence}

    inputs = [HERE / "matrix.py", *(RT30 / name for name in ADAPTERS.values()),
              RT30 / "C-FAMILY-ROUNDTRIP-01/original.c.in",
              RT30 / "GO-ROUNDTRIP-01/import.go",
              RT30 / "GO-ROUNDTRIP-01/original.go.in",
              RT30 / "RUST-WRAPPING-ROUNDTRIP-01/src/main.rs",
              RT30 / "RUST-WRAPPING-ROUNDTRIP-01/Cargo.toml",
              RT30 / "RUST-WRAPPING-ROUNDTRIP-01/Cargo.lock",
              RT30 / "RUST-WRAPPING-ROUNDTRIP-01/original.rs.in",
              RT30 / "RUST-WRAPPING-ROUNDTRIP-01/host.rs.in",
              RT13 / "lower_go.py", RT13 / "run.py", RT13 / "host.go",
              FIXTURE / "integer_fixture.py", FIXTURE / "llvm_integer_probe.py"]
    return {
        "profile": "closed u32 wrapping, returning callbacks and writable noninterfering slot",
        "toolchain": toolchain,
        "observed_fields": OBSERVATIONS,
        "programs_per_source": len(programs),
        "request_sha256": sha256(packet).hexdigest(),
        "required_trace_sha256": digest_expected,
        "observed_native_routes": len(ROUTES) * len(TARGETS),
        "total_native_observations": len(ROUTES) * len(TARGETS) * len(expected),
        "matrix": matrix,
        "source_sha256": {path.relative_to(ROOT).as_posix(): digest(path) for path in inputs},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--go", default="go")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--cache", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-wrapping-matrix-") as scratch:
        print(json.dumps(verify(args, Path(scratch)), indent=2))


if __name__ == "__main__":
    main()
