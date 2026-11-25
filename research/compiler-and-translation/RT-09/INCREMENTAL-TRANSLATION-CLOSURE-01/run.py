"""Exercise persistent selective native translation and verification on a declared graph."""

import argparse
from collections import Counter
import ctypes
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
PARTITIONS = {"low": (0, 128), "high": (128, 256)}
CONTRACT_ADDEND = {"a": 7, "b": 11}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def identity(*fields):
    return digest(encode(fields))


def command(*args, cwd=None):
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1764000000"}
    return subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, check=True, text=True, timeout=30
    ).stdout.strip()


@dataclass(frozen=True)
class Stage:
    location: str = "a-old.llm"
    dependency_body: int = 7
    a_partitions: tuple[str, ...] = ("low",)
    a_oracle_revision: int = 1


class Store:
    def __init__(self, root, cc, toolchain):
        self.root = root
        self.cc = cc
        self.toolchain = toolchain
        self.entry_path = root / "index.json"
        (root / "blobs").mkdir(parents=True, exist_ok=True)
        self.entries = (
            json.loads(self.entry_path.read_text(encoding="utf-8")) if self.entry_path.exists() else {}
        )
        self.work = Counter({"release_compile": 0, "link": 0, "debug_compile": 0, "verify": 0})
        self.fixture = digest(Path(__file__).read_bytes())

    def blob(self, artifact):
        path = self.root / "blobs" / artifact
        assert digest(path.read_bytes()) == artifact
        return path

    def record_artifact(self, key, action, build):
        key = identity(action, self.toolchain, self.fixture, key)
        if key not in self.entries:
            data = build()
            artifact = digest(data)
            (self.root / "blobs" / artifact).write_bytes(data)
            self.entries[key] = artifact
            self.work[action] += 1
        artifact = self.entries[key]
        self.blob(artifact)
        return artifact

    def compile(self, code, *, debug=False):
        options = ["-std=c17", "-ffreestanding", "-fPIC", "-fvisibility=hidden", "-O2"]
        action = "debug_compile" if debug else "release_compile"
        with tempfile.TemporaryDirectory(dir=self.root, prefix="build-") as temporary:
            directory = Path(temporary)
            if debug:
                options.extend(["-gdwarf-5", f"-ffile-prefix-map={directory}=/fixture"])
            (directory / "unit.c").write_text(code, encoding="utf-8")

            def build():
                command(self.cc, *options, "-c", "unit.c", "-o", "unit.o", cwd=directory)
                return (directory / "unit.o").read_bytes()

            stable_options = [option for option in options if not option.startswith("-ffile-prefix-map=")]
            return self.record_artifact([code, stable_options], action, build)

    def link(self, name, compiled):
        options = ["-fuse-ld=bfd", "-shared", "-nostdlib", "-Wl,--no-undefined"]

        def build():
            with tempfile.TemporaryDirectory(dir=self.root, prefix="link-") as temporary:
                directory = Path(temporary)
                inputs = []
                for i, artifact in enumerate(compiled):
                    path = directory / f"part-{i}.o"
                    path.write_bytes(self.blob(artifact).read_bytes())
                    inputs.append(path.name)
                command(self.cc, *options, *inputs, "-o", "program.so", cwd=directory)
                symbols = command("nm", "-D", "--defined-only", "program.so", cwd=directory)
                assert symbols.split()[-2:] == ["T", f"run_{name}"]
                dynamic = command("readelf", "-dW", "program.so", cwd=directory)
                assert "(NEEDED)" not in dynamic
                return (directory / "program.so").read_bytes()

        return self.record_artifact([name, options, compiled], "link", build)

    def verify(self, name, artifact, partition, oracle_revision):
        contract = (PARTITIONS[partition], CONTRACT_ADDEND[name])
        scope = identity(name, artifact, contract, oracle_revision, self.toolchain, self.fixture)
        if scope not in self.entries:
            function = getattr(ctypes.CDLL(str(self.blob(artifact))), f"run_{name}")
            function.argtypes = [ctypes.c_uint8]
            function.restype = ctypes.c_uint8
            inputs = range(*contract[0])
            results = [function(value) for value in inputs]
            expected = [(value + contract[1]) % 256 for value in inputs]
            self.entries[scope] = {
                "count": len(results),
                "mismatches": sum(a != b for a, b in zip(results, expected)),
                "observations_sha256": digest(bytes(results)),
            }
            self.work["verify"] += 1
        return {"scope": scope, **self.entries[scope]}

    def persist(self):
        temporary = self.entry_path.with_suffix(".tmp")
        temporary.write_bytes(encode(self.entries))
        temporary.replace(self.entry_path)


def source(stage):
    exported = '__attribute__((visibility("default"))) unsigned char'
    return {
        "a": f"extern unsigned char bump(unsigned char);\n{exported} run_a(unsigned char x) {{ return bump(x); }}\n",
        "b": f"{exported} run_b(unsigned char x) {{ return x + 11u; }}\n",
        "bump": f"unsigned char bump(unsigned char x) {{ return x + {stage.dependency_body}u; }}\n",
    }


def execute(root, cc, toolchain, stage):
    store = Store(root, cc, toolchain)
    code = source(stage)
    objects = {name: store.compile(body) for name, body in code.items()}
    modules = {
        "a": store.link("a", [objects["a"], objects["bump"]]),
        "b": store.link("b", [objects["b"]]),
    }
    debug = {
        "a": store.compile(f'#line 50 "{stage.location}"\n' + code["a"], debug=True),
        "b": store.compile('#line 20 "b.llm"\n' + code["b"], debug=True),
    }
    for name, filename in (("a", stage.location), ("b", "b.llm")):
        positions = command("objdump", "--dwarf=decodedline", store.blob(debug[name]))
        assert filename in positions
    requested = {"a": stage.a_partitions, "b": ("low",)}
    evidence = {
        name: {
            part: store.verify(name, modules[name], part, stage.a_oracle_revision if name == "a" else 1)
            for part in parts
        }
        for name, parts in requested.items()
    }
    store.persist()
    return {
        "objects": objects, "modules": modules, "debug_objects": debug, "evidence": evidence,
        "admitted": {
            name: all(item["mismatches"] == 0 for item in rows.values())
            for name, rows in evidence.items()
        },
        "work": dict(store.work),
    }


def collect(root, cc, toolchain):
    base = Stage()
    moved = replace(base, location="a-new.llm")
    wide = replace(moved, a_partitions=("low", "high"))
    stages = (
        ("initial", base, (3, 2, 2, 2)),
        ("reopened", base, (0, 0, 0, 0)),
        ("source_location", moved, (0, 0, 1, 0)),
        ("wider_contract", wide, (0, 0, 0, 1)),
        ("changed_dependency", replace(wide, dependency_body=8), (1, 1, 0, 2)),
        ("restored_dependency", wide, (0, 0, 0, 0)),
        ("changed_oracle_scope", replace(wide, a_oracle_revision=2), (0, 0, 0, 2)),
    )
    results = {}
    work_names = ("release_compile", "link", "debug_compile", "verify")
    for name, stage, expected_work in stages:
        result = execute(root, cc, toolchain, stage)
        assert tuple(result["work"][key] for key in work_names) == expected_work, name
        results[name] = result

    first = results["initial"]
    after_move = results["source_location"]
    wider = results["wider_contract"]
    broken = results["changed_dependency"]
    restored = results["restored_dependency"]
    new_oracle = results["changed_oracle_scope"]
    assert first["modules"] == after_move["modules"] == wider["modules"]
    assert first["debug_objects"]["a"] != after_move["debug_objects"]["a"]
    assert first["debug_objects"]["b"] == after_move["debug_objects"]["b"]
    assert first["evidence"]["a"]["low"] == wider["evidence"]["a"]["low"]
    assert first["admitted"] == wider["admitted"] == restored["admitted"] == new_oracle["admitted"] == {
        "a": True, "b": True,
    }
    assert broken["admitted"] == {"a": False, "b": True}
    assert broken["modules"]["a"] != wider["modules"]["a"]
    assert [entry["mismatches"] for entry in broken["evidence"]["a"].values()] == [128, 128]
    assert all(
        row["modules"]["b"] == first["modules"]["b"] and row["evidence"]["b"] == first["evidence"]["b"]
        for row in results.values()
    )
    assert restored["evidence"] == wider["evidence"]
    assert new_oracle["modules"] == wider["modules"]
    assert all(
        new_oracle["evidence"]["a"][part]["scope"] != wider["evidence"]["a"][part]["scope"]
        for part in ("low", "high")
    )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    tools = {
        "driver": args.cc,
        **{tool: command(args.cc, f"-print-prog-name={tool}") for tool in ("cc1", "as", "ld.bfd")},
    }
    toolchain = {
        "target": command(args.cc, "-dumpmachine"),
        "compiler": command(args.cc, "--version").splitlines()[0],
        "linker": command(tools["ld.bfd"], "--version").splitlines()[0],
        "binaries": {
            name: digest(Path(shutil.which(path)).read_bytes()) for name, path in tools.items()
        },
    }
    with tempfile.TemporaryDirectory(prefix="rt09-incremental-") as directory:
        root = Path(directory)
        results = collect(root / "one", args.cc, identity(toolchain))
        assert results == collect(root / "two", args.cc, identity(toolchain))
    evidence = {
        "toolchain": toolchain,
        "fixture_sha256": digest(Path(__file__).read_bytes()),
        "independent_build_roots": 2,
        "phases": results,
    }
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
