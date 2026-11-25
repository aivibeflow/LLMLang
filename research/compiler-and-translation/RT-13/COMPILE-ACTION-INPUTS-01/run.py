"""Compare compile results after controlled path and build-time changes."""

import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
MODES = ("pure", "unmapped-debug", "unmapped-macros", "mapped-macros-and-debug")
ROOTS = ("left", "right")
EPOCHS = ("0", "86400")
TARGET = "x86_64-pc-linux-gnu"
VIRTUAL = "/llmlang/compile"


def digest(data):
    return sha256(data).hexdigest()


def instrument(clang, folder, source, mode, epoch):
    root = folder.resolve()
    path = root / "source.c"
    path.write_bytes(source)
    object_file = root / "source.o"
    flags = ["--target=" + TARGET, "-O2", "-std=c17", "-fno-ident"]
    if mode in ("unmapped-debug", "mapped-macros-and-debug"):
        flags.append("-g")
    if mode == "mapped-macros-and-debug":
        flags.extend([f"-ffile-prefix-map={root}={VIRTUAL}", f"-fdebug-compilation-dir={VIRTUAL}"])
    env = {**os.environ, "LC_ALL": "C", "TZ": "UTC", "SOURCE_DATE_EPOCH": epoch}
    subprocess.run([clang, *flags, "-c", path, "-o", object_file], cwd=root,
                   capture_output=True, check=True, timeout=30, env=env)
    return object_file.read_bytes()


def action_key(tool, mode, source, root, epoch, *, controls):
    inputs = {"tool": tool, "target": TARGET, "recipe": mode, "source": digest(source)}
    if controls:
        if mode in ("unmapped-debug", "unmapped-macros"):
            if root is None:
                return None
            inputs["observed_path"] = root
        if mode in ("unmapped-macros", "mapped-macros-and-debug"):
            if epoch is None:
                return None
            inputs["source_date_epoch"] = epoch
    return digest(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode())


def review(clang):
    version = subprocess.check_output([clang, "--version"], text=True).splitlines()[0]
    assert version == "Debian clang version 19.1.7 (3+b1)"
    tool = digest(Path(clang).read_bytes())
    modes = {}
    with TemporaryDirectory(prefix="llmlang-compile-inputs-") as temp:
        for mode in MODES:
            groups = {}
            builds = []
            source = (HERE / ("pure.c" if mode in ("pure", "unmapped-debug") else "context.c")).read_bytes()
            for subdir, epoch in product(ROOTS, EPOCHS):
                folder = Path(temp) / subdir
                folder.mkdir(exist_ok=True)
                artifact = instrument(clang, folder, source, mode, epoch)
                assert instrument(clang, folder, source, mode, epoch) == artifact
                result = digest(artifact)
                group = groups.setdefault(result, len(groups))
                if mode == "unmapped-debug":
                    assert str(folder).encode() in artifact
                if mode == "mapped-macros-and-debug":
                    assert str(folder).encode() not in artifact
                if mode in ("unmapped-macros", "mapped-macros-and-debug"):
                    observed_path = VIRTUAL if mode == "mapped-macros-and-debug" else str(folder)
                    assert f"{observed_path}/source.c".encode() in artifact
                    day = 1 if epoch == "0" else 2
                    assert f"Jan  {day} 1970 00:00:00".encode() in artifact
                builds.append({"source_root": subdir, "epoch": epoch, "artifact_group": group,
                               "artifact_bytes": len(artifact) if mode in ("pure", "mapped-macros-and-debug") else None,
                               "source_recipe_key": action_key(tool, mode, source, subdir, epoch, controls=False),
                               "declared_input_key": action_key(tool, mode, source, subdir, epoch, controls=True)})
            keys = ("source_recipe_key", "declared_input_key")
            false_hits = {key: sum(a[key] == b[key] and a["artifact_group"] != b["artifact_group"]
                                   for a, b in product(builds, repeat=2)) for key in keys}
            assert false_hits["declared_input_key"] == 0
            uncaptured_key = action_key(tool, mode, source, None, None, controls=True)
            assert (uncaptured_key is None) == (mode != "pure")
            modes[mode] = {
                "shared_lookup_allowed_without_path_or_epoch": uncaptured_key is not None,
                "artifact_groups": len(groups), "deterministic_artifact_sha256":
                    sorted(groups) if mode in ("pure", "mapped-macros-and-debug") else None,
                "builds": builds, "false_hits": false_hits,
            }
    assert [modes[name]["artifact_groups"] for name in MODES] == [1, 2, 4, 2]
    return {
        "schema": "rt13-compile-action-inputs-v1",
        "tool": {"version": version, "clang_sha256": tool, "target": TARGET},
        "python": platform.python_version(), "source_sha256": {name: digest((HERE / name).read_bytes())
                                                for name in ("pure.c", "context.c", "run.py")},
        "build_repetitions": 2, "ordered_reuse_pairs_per_mode": 16, "modes": modes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.clang.resolve()), indent=2, sort_keys=True))
