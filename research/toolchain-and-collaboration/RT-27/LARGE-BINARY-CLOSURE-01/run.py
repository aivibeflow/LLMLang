#!/usr/bin/env python3
"""Compare complete Git binary snapshots with a detached artifact store."""

from hashlib import shake_256
import json
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASE = runpy.run_path(str(HERE.parent / "GIT-CLOSED-REPRESENTATION-01/run.py"))
git, encode, digest, members = (BASE[name] for name in ("git", "encode", "digest", "members"))
CHUNK = 1 << 20


class Refusal(ValueError):
    pass


def materialize(work, name, output):
    work.mkdir()
    source = f'#include <stdio.h>\nint main(void) {{ puts("{output}"); return 0; }}\n'
    (work / "main.c").write_text(source, encoding="utf-8")
    # The non-allocated section makes the physical artifact large and keeps the
    # selected fixture's runtime observation independent of the extra bytes.
    common = shake_256(b"llmlang large binary fixture common").digest(3 * CHUNK + 8192)
    extra = shake_256(name.encode()).digest(128)
    (work / "bulk.bin").write_bytes(common + extra)
    for args in (
        ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "main.c", "-o", "main"],
        ["objcopy", "--add-section", ".fixture.bulk=bulk.bin", "main", "large"],
    ):
        subprocess.run(args, cwd=work, capture_output=True, check=True)
    raw = (work / "large").read_bytes()
    assert len(raw) > 3 * CHUNK
    actual = subprocess.check_output(["./large"], cwd=work).decode()
    assert actual == output + "\n"
    semantic = {"operation": "fixture-print", "provider": name, "stdout": actual}
    return semantic, raw


def pack(semantic, artifact, layout):
    selected = digest(encode(semantic))
    subject = digest(artifact)
    chunks = [artifact[begin:begin + CHUNK] for begin in range(0, len(artifact), CHUNK)]
    inventory = [digest(data) for data in chunks] if layout == "chunks" else []
    manifest = {
        "schema": "fixture-binary-closure/1", "layout": layout,
        "selected_root": selected, "artifact": subject, "size": len(artifact),
        "media_type": "application/x-elf", "part_size": CHUNK, "parts": inventory,
    }
    payloads = {"semantic.json": encode(semantic), "manifest.json": encode(manifest)}
    if layout == "whole":
        payloads["artifacts/image"] = artifact
    if layout == "chunks":
        payloads.update({f"parts/{address}": data for data, address in zip(chunks, inventory, strict=True)})
    return payloads


def read(files, expected_root, external):
    manifest = json.loads(files["manifest.json"])
    if manifest["schema"] != "fixture-binary-closure/1":
        raise Refusal("unsupported layout version")
    if manifest["selected_root"] != expected_root or digest(files["semantic.json"]) != expected_root:
        raise Refusal("wrong exact semantic root")
    layout = manifest["layout"]
    if layout == "whole":
        rebuilt = files["artifacts/image"]
    elif layout == "detached":
        try:
            rebuilt = external[manifest["artifact"]]
        except KeyError as error:
            raise Refusal("detached artifact unavailable") from error
    elif layout == "chunks":
        parts = []
        for position, address in enumerate(manifest["parts"]):
            name = "parts/" + address
            if name not in files:
                raise Refusal("chunk unavailable")
            data = files[name]
            if digest(data) != address or len(data) > CHUNK:
                raise Refusal("chunk digest or size mismatch")
            if position + 1 < len(manifest["parts"]) and len(data) != CHUNK:
                raise Refusal("nonfinal chunk is shortened")
            parts.append(data)
        rebuilt = b"".join(parts)
    else:
        raise Refusal("unsupported layout version")
    if len(rebuilt) != manifest["size"] or digest(rebuilt) != manifest["artifact"]:
        raise Refusal("artifact digest or size mismatch")
    return rebuilt


def history(work, layout, source):
    repo = work / f"{layout}-source"
    clone = work / f"{layout}-clone"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "research/all", "--object-format=sha256")
    previous = set()
    pins = []
    for i, (semantic, asset) in enumerate(source):
        files = pack(semantic, asset, layout)
        for path in previous - set(files):
            (repo / path).unlink()
        for name, data in files.items():
            path = repo / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        git(repo, "add", "-A")
        git(repo, "-c", "commit.gpgsign=false", "commit", "-m", f"publish {i}")
        pins.append(git(repo, "rev-parse", "HEAD").decode().strip())
        previous = set(files)
    assert git(repo, "branch", "--show-current").strip() == b"research/all"
    git(work, "clone", "-q", "--no-local", str(repo), str(clone))
    git(clone, "fsck", "--full")
    git(clone, "remote", "remove", "origin")
    repo.rename(work / f"{layout}-origin-unavailable")
    return clone, pins


def replay(work, raw, expected):
    image = work / "copied-image"
    image.write_bytes(raw)
    image.chmod(0o700)
    output = subprocess.check_output([str(image)], cwd=work).decode()
    assert output == expected


def experiment(work):
    sources = [materialize(work / name, name, output)
               for name, output in (("first", "bounded first"), ("second", "bounded second"))]
    assert sources[0][1] != sources[1][1]
    external = {digest(asset): asset for _, asset in sources}
    cases = []
    controls = []

    def refuse(label, expected, function):
        try:
            function()
        except Refusal as error:
            assert str(error) == expected, (label, str(error))
        else:
            raise AssertionError(label)
        controls.append({"case": label, "decision": expected})

    for layout in ("whole", "chunks", "detached"):
        clone, pins = history(work, layout, sources)
        manifests = []
        records = []
        for (semantic, original), pin in zip(sources, pins, strict=True):
            files = members(clone, pin)
            root = digest(encode(semantic))
            if layout == "detached":
                refuse(f"{layout}/{pin}/offline", "detached artifact unavailable", lambda: read(files, root, {}))
            supplied = external if layout == "detached" else {}
            restored = read(files, root, supplied)
            assert restored == original
            replay(work, restored, semantic["stdout"])
            info = json.loads(files["manifest.json"])
            manifests.append(info)
            records.append(files)
            cases.append({
                "layout": layout, "commit": pin, "root": root, "bytes": len(restored),
                "artifact": digest(restored), "files": len(files),
                "restored_with": "detached-exact-source" if layout == "detached" else "Git-alone",
            })
        second = manifests[-1]
        second_root = second["selected_root"]
        last = records[-1]
        refuse(layout + "/historical-root", "wrong exact semantic root",
               lambda: read(last, manifests[0]["selected_root"], external))
        if layout == "chunks":
            reused = set(manifests[0]["parts"]) & set(second["parts"])
            assert reused == {second["parts"][1], second["parts"][2]}
            assert len(second["parts"]) == 4 and len(set(second["parts"])) == 4
            one_missing = dict(last)
            sample = "parts/" + second["parts"][1]
            one_missing.pop(sample)
            refuse("a missing required chunk", "chunk unavailable", lambda: read(one_missing, second_root, {}))
            refuse("altered chunk", "chunk digest or size mismatch",
                   lambda: read(last | {sample: b"incorrect"}, second_root, {}))
            changed_order = second | {"parts": [second["parts"][1], second["parts"][0], *second["parts"][2:]]}
            refuse("correct chunks in a different order", "artifact digest or size mismatch",
                   lambda: read(last | {"manifest.json": encode(changed_order)}, second_root, {}))
        if layout == "detached":
            wrong = {second["artifact"]: sources[0][1]}
            refuse("detached valid artifact from a different revision", "artifact digest or size mismatch",
                   lambda: read(last, second_root, wrong))
    return {
        "format": "large-binary-closure-01", "git": git(work, "--version").decode().strip(),
        "reused_chunks": len(reused), "chunk_bytes": CHUNK, "cases": cases, "controls": controls,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-large-git-binary-") as directory:
        report = experiment(Path(directory))
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
