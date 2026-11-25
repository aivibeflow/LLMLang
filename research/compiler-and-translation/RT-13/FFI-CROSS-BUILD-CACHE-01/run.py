#!/usr/bin/env python3
"""Compare package and cache identity across reproducible FFI cross-ABI builds."""
import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import importlib.util
from itertools import product
import json
import re
from shutil import which
from pathlib import Path
import sqlite3
import struct
import tempfile


HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "FFI-AGGREGATE-CROSS-ABI-01"
spec = importlib.util.spec_from_file_location("cross_abi_tools", FIXTURE / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ROLES = ("archive", "shared", "static_client")
PROVIDER_FLAGS = ("-std=c11", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
                  "-fPIC", "-Wall", "-Wextra", "-Werror")


@dataclass(frozen=True)
class Target:
    profile: str
    triple: str
    machine: int
    flags: int
    os_abi: str
    sdk: str = "none:freestanding-linux-syscalls"


TARGETS = (
    Target("aarch64-aapcs64", "aarch64-linux-gnu", 183, 0, "AAPCS64"),
    Target("rv64-lp64d", "riscv64-linux-gnu", 243, 5, "LP64D"),
    Target("rv64-lp64", "riscv64-linux-gnu", 243, 1, "LP64"),
)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(raw):
    return sha256(raw).hexdigest()


def request(target, optimization, inputs, tool):
    files = {name: base.fingerprint(FIXTURE / name)
             for name in ("provider.c", "consumer.c", "fixture.h", "syscalls.S")}
    files["vectors.S"] = base.fingerprint(inputs)
    return {"action": "cross-ffi-package-v1", "build_host": tool,
            "target": asdict(target), "provider_options": [optimization, *PROVIDER_FLAGS,
                                                             *base.PROFILES[target.profile][0]],
            "consumer_optimization": "-O2",
            "inputs": files, "linker_emulation": base.PROFILES[target.profile][2],
            "build_recipe_sha256": {"runner": base.fingerprint(Path(__file__)),
                                    "cross_abi_helpers": base.fingerprint(FIXTURE / "run.py")},
            "shared_link_options": ["-shared", "-soname", "libaffine.so"],
            "static_link_options": ["-static", "-e", "_start"],
            "outputs": list(ROLES), "archive_mode": "rcsD",
            "loader_dependencies": {"archive": [], "shared": [], "static_client": []}}


def elf_identity(raw):
    assert len(raw) >= 64 and raw[:6] == b"\x7fELF\x02\x01"
    kind, machine = struct.unpack_from("<HH", raw, 16)
    flags = struct.unpack_from("<I", raw, 48)[0]
    return kind, machine, flags


def object_inside_archive(path):
    members = base.run(["ar", "t", path], path.parent).stdout
    assert members == b"provider.o\n", members
    return base.run(["ar", "p", path, "provider.o"], path.parent).stdout


def classify(artifact, role, target, scratch):
    if role == "archive":
        file = scratch / "candidate.a"
        file.write_bytes(artifact)
        elf = object_inside_archive(file)
        kind = 1
    else:
        elf = artifact
        kind = {"static_client": 2, "shared": 3}[role]
    return elf_identity(elf) == (kind, target.machine, target.flags)


def build(args, directory, target, optimization, emulator, expected):
    directory.mkdir()
    inputs = directory / "vectors.S"
    base.generate_vectors(inputs)
    sources = {
        "consumer": (FIXTURE / "consumer.c", ["-O2"]),
        "syscalls": (FIXTURE / "syscalls.S", []),
        "vectors": (inputs, []),
    }
    files = {}
    for name, (source, options) in sources.items():
        files[name] = directory / f"{name}.o"
        base.compile_one(args, target.profile, source, files[name], extra=options)
    files["provider"] = directory / "provider.o"
    local = {**base.ENV, "LD_LIBRARY_PATH": str(args.clang_libdir)} if args.clang_libdir else base.ENV
    base.run([args.clang, *base.PROFILES[target.profile][0], optimization, *PROVIDER_FLAGS,
              "-c", FIXTURE / "provider.c", "-o", files["provider"]], directory, local)
    archive = directory / "libaffine.a"
    base.run(["ar", "rcsD", archive, files["provider"]], directory)
    shared = directory / "libaffine.so"
    mode = base.PROFILES[target.profile][2]
    base.run([args.lld, "-m", mode, "-shared", "-soname", "libaffine.so", "-o", shared,
              files["provider"]], directory)
    executable = directory / "client"
    result = base.link(args, target.profile, executable,
                       [files["consumer"], archive, files["syscalls"], files["vectors"]])
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    raw = base.run([emulator, executable], directory).stdout
    assert [list(row) for row in struct.iter_unpack("<7Q", raw)] == expected
    assert b"NEEDED" not in base.run(["readelf", "-dW", shared], directory).stdout
    base.read_elf(executable, target.machine, target.flags)
    artifacts = {"archive": archive.read_bytes(), "shared": shared.read_bytes(),
                 "static_client": executable.read_bytes()}
    assert all(classify(data, role, target, directory) for role, data in artifacts.items())
    return artifacts, digest(raw)


class Cache:
    def __init__(self, db, initialize=True):
        self.db = db
        if initialize:
            db.executescript("""
                CREATE TABLE result (action_key TEXT PRIMARY KEY, manifest BLOB NOT NULL);
                CREATE TABLE object (sha256 TEXT PRIMARY KEY, payload BLOB NOT NULL);
            """)

    def publish(self, key, manifest, artifacts):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO result VALUES (?, ?)", (key, encoded(manifest)))
            for data in artifacts.values():
                self.db.execute("INSERT OR REPLACE INTO object VALUES (?, ?)", (digest(data), data))

    def retrieve(self, key, action, target, expected_manifest, scratch):
        row = self.db.execute("SELECT manifest FROM result WHERE action_key = ?", (key,)).fetchone()
        if row is None:
            return "miss"
        raw = row[0]
        manifest = json.loads(raw)
        if raw != encoded(manifest) or manifest["action"] != action:
            return "request-mismatch"
        if set(manifest["files"]) != set(ROLES):
            return "inventory-mismatch"
        for name, address in manifest["files"].items():
            data = self.db.execute("SELECT payload FROM object WHERE sha256 = ?", (address,)).fetchone()
            if data is None:
                return "missing-object"
            if digest(data[0]) != address:
                return "payload-mismatch"
            try:
                target_matches = classify(data[0], name, target, scratch)
            except AssertionError:
                return "artifact-format-mismatch"
            if not target_matches:
                return "target-mismatch"
        if manifest != expected_manifest:
            return "receipt-mismatch"
        return "exact-hit"


def executable_identity(program, root, env):
    version = base.run([program, "--version"], root, env).stdout.decode().splitlines()[0]
    resolved = base.run(["ldd", program], root, env).stdout.decode()
    assert "not found" not in resolved
    needed = {}
    for line in resolved.splitlines():
        match = re.search(r"^\s*(?:(\S+) => )?(/[^\s]+) \(0x", line)
        if match:
            soname, path = match.groups()
            library = Path(path)
            needed[soname or library.name] = base.fingerprint(library)
    assert needed
    return {"version": version, "sha256": base.fingerprint(program),
            "resolved_libraries_sha256": needed}


def tool_identity(args, root):
    local = {**base.ENV, "LD_LIBRARY_PATH": str(args.clang_libdir)} if args.clang_libdir else base.ENV
    clang = executable_identity(args.clang, root, local)
    lld = executable_identity(args.lld, root, base.ENV)
    assert "19.1.7" in clang["version"] and "19.1.7" in lld["version"]
    return {"machine": base.run(["uname", "-m"], root).stdout.decode().strip(),
            "kernel": base.run(["uname", "-r"], root).stdout.decode().strip(),
            "clang": clang, "lld": lld, "ar": executable_identity(Path(which("ar")), root, base.ENV)}


def verify_no_pic_refusal(args, root):
    foreign = "rv64-lp64d"
    provider = root / "non-pic-provider.o"
    base.compile_one(args, foreign, FIXTURE / "provider.c", provider, extra=["-O0"])
    command = [args.lld, "-m", "elf64lriscv", "-shared", "-o", root / "wrong.so", provider]
    failed = base.run(command, root, check=False)
    assert failed.returncode and b"R_RISCV_HI20" in failed.stderr and b"recompile with -fPIC" in failed.stderr
    return "RV64 non-PIC provider rejected for shared library"


def mutation_controls(cache, action, target, manifest, artifact, alternate, other_recipe, scratch):
    key = digest(encoded(action))
    controls = {}

    def check(label, claim, actual, expected):
        cache.publish(key, claim, actual)
        seen = cache.retrieve(key, action, target, manifest, scratch)
        assert seen == expected, (label, seen, expected)
        controls[label] = seen

    changed_key = {**action, "target": {**action["target"], "sdk": "unexpected-sdk"}}
    assert cache.retrieve(digest(encoded(changed_key)), changed_key, target, manifest, scratch) == "miss"
    controls["changed-target-sdk"] = "miss"
    check("wrong-recipe-descriptor", {**manifest, "action": changed_key}, artifact, "request-mismatch")
    without_shared = {key: value for key, value in manifest["files"].items() if key != "shared"}
    check("omitted-shared-role", {**manifest, "files": without_shared}, artifact, "inventory-mismatch")
    wrong_abi = {**artifact, "shared": alternate["shared"]}
    check("self-consistent-wrong-abi", {**manifest, "files": {role: digest(data) for role, data in wrong_abi.items()}},
          wrong_abi, "target-mismatch")
    wrong_outputs = {**artifact, "archive": other_recipe["archive"]}
    assert classify(wrong_outputs["archive"], "archive", target, scratch)
    check("same-abi-different-provider-recipe",
          {**manifest, "files": {role: digest(data) for role, data in wrong_outputs.items()}},
          wrong_outputs, "receipt-mismatch")
    bad_format = {**artifact, "static_client": b"not an ELF file"}
    check("self-consistent-wrong-format",
          {**manifest, "files": {role: digest(data) for role, data in bad_format.items()}},
          bad_format, "artifact-format-mismatch")
    cache.publish(key, manifest, artifact)
    sha = manifest["files"]["shared"]
    cache.db.execute("UPDATE object SET payload = ? WHERE sha256 = ?", (b"damaged", sha))
    assert cache.retrieve(key, action, target, manifest, scratch) == "payload-mismatch"
    controls["changed-cas-bytes"] = "payload-mismatch"
    return controls


def main():
    parser = argparse.ArgumentParser()
    for name in ("clang", "clang-libdir", "lld", "qemu-aarch64", "qemu-riscv64", "out"):
        parser.add_argument(f"--{name}", type=lambda s: Path(s).absolute(), required=name != "clang-libdir")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rt13-cross-ffi-cache-") as directory:
        root = Path(directory)
        vectors = root / "vectors.S"
        _, expected = base.generate_vectors(vectors)
        tool = tool_identity(args, root)
        observation_profiles = {}
        for architecture in ("aarch64", "riscv64"):
            emulator = getattr(args, f"qemu_{architecture}")
            version = base.run([emulator, "--version"], root).stdout.decode().splitlines()[0]
            assert "10.0.13" in version
            observation_profiles[architecture] = {"version": version, "sha256": base.fingerprint(emulator)}
        db = sqlite3.connect(root / "cache.sqlite")
        cache = Cache(db)
        build_outputs, reports, weaker = {}, {}, {"build-host": {}, "triple": {}}
        false_hits = {"build-host": 0, "triple": 0}
        for target, opt in product(TARGETS, ("-O0", "-O2")):
            label = f"{target.profile}/{opt}"
            arch = "aarch64" if target.machine == 183 else "riscv64"
            emulator = getattr(args, f"qemu_{arch}")
            action = request(target, opt, vectors, tool)
            action_key = digest(encoded(action))
            a, behavior = build(args, root / f"{target.profile}{opt}-first", target, opt, emulator, expected)
            b, repeat = build(args, root / f"{target.profile}{opt}-second", target, opt, emulator, expected)
            assert a == b and behavior == repeat
            manifest = {"action": action, "files": {role: digest(value) for role, value in a.items()},
                        "client_observed_sha256": behavior, "checker": observation_profiles[arch]}
            build_outputs[label] = a
            reports[label] = {"action_key": action_key, "package_manifest": manifest}
            assert cache.retrieve(action_key, action, target, manifest, root) == "miss"
            cache.publish(action_key, manifest, a)
            assert cache.retrieve(action_key, action, target, manifest, root) == "exact-hit"
            weak_keys = {"build-host": digest(encoded({"host": tool, "inputs": action["inputs"]})),
                         "triple": digest(encoded({"triple": target.triple, "opt": opt, "inputs": action["inputs"]}))}
            for name, weak in weak_keys.items():
                previous = weaker[name].setdefault(weak, action_key)
                false_hits[name] += previous != action_key
        assert false_hits == {"build-host": 5, "triple": 2}
        db.close()
        db = sqlite3.connect(root / "cache.sqlite")
        cache = Cache(db, initialize=False)
        for target, opt in product(TARGETS, ("-O0", "-O2")):
            row = reports[f"{target.profile}/{opt}"]
            manifest = row["package_manifest"]
            assert cache.retrieve(row["action_key"], manifest["action"], target, manifest, root) == "exact-hit"
        hard = "rv64-lp64d/-O0"
        claim = reports[hard]["package_manifest"]
        controls = mutation_controls(cache, claim["action"], TARGETS[1], claim, build_outputs[hard],
                                     build_outputs["rv64-lp64/-O0"], build_outputs["rv64-lp64d/-O2"], root)
        report = {"tool_identity": tool, "requests": reports, "reproducible_builds": 12,
                  "checked_artifact_roles": len(ROLES) * 12, "static_observations": len(expected) * 12,
                  "cold_misses_and_exact_reuses": 6, "fresh_connection_reuses": 6, "false_hits_by_key": false_hits,
                  "native_link_control": verify_no_pic_refusal(args, root),
                  "cache_refusal_controls": controls, "sqlite": sqlite3.sqlite_version}
        db.close()
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
