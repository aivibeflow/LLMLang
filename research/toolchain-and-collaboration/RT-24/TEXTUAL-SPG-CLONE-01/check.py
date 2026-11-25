"""Restore a typed textual source fixture with exact dependencies from clean Git clones."""

from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory


BASE = "2546379f0bed8a44ef80ef40597d9c7d9ca8f16b"
MIN_I64 = -(1 << 63)
MAX_I64 = (1 << 63) - 1
APP = "src/entry.llm"
DEPENDENCY = "vendor/math.llm"
MANIFEST = "llmlang-manifest.json"
APP_SOURCE = b"import math.inc\nfn entry(x: I64) -> Result<I64, Overflow> = math.inc(x)\n"
DEPENDENCY_SYNTAX = re.compile(
    rb"fn inc\(x: I64\) -> Result<I64, Overflow> = checked_add\(x, ([1-9][0-9]?)\)\n"
)
INPUTS = (MIN_I64, -2, 0, 3, MAX_I64 - 2, MAX_I64 - 1, MAX_I64)


def digest(raw):
    return sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def graph_from_increment(increment):
    child = digest(encoded(["body", "I64", "checked_add", increment, "Overflow"]))
    body = digest(encoded(["direct-call", "entry", "I64", "Result<I64, Overflow>", child]))
    return {"body": body, "callee": child, "root": digest(encoded(["textual-spg/1", body, child]))}


def export_text(increment):
    caller = APP_SOURCE
    provider = f"fn inc(x: I64) -> Result<I64, Overflow> = checked_add(x, {increment})\n".encode()
    manifest = {
        "profile": "textual-spg/1", "entries": {APP: digest(caller), DEPENDENCY: digest(provider)},
        "dependencies": {"math.inc": {"source": DEPENDENCY, "sha256": digest(provider),
                                     "contract": "checked-add-i64/1"}},
        "root": graph_from_increment(increment)["root"],
    }
    return {APP: caller, DEPENDENCY: provider, MANIFEST: encoded(manifest)}


def load(files):
    if set(files) != {APP, DEPENDENCY, MANIFEST}:
        return "inventory", None
    try:
        manifest = json.loads(files[MANIFEST])
    except (UnicodeError, json.JSONDecodeError):
        return "profile", None
    if not isinstance(manifest, dict) or manifest.get("profile") != "textual-spg/1" or encoded(manifest) != files[MANIFEST]:
        return "profile", None
    if manifest.get("entries") != {key: digest(files[key]) for key in (APP, DEPENDENCY)}:
        return "file-pin", None
    lock = {"math.inc": {"source": DEPENDENCY, "sha256": digest(files[DEPENDENCY]),
                         "contract": "checked-add-i64/1"}}
    if manifest.get("dependencies") != lock:
        return "dependency-pin", None
    provider = DEPENDENCY_SYNTAX.fullmatch(files[DEPENDENCY])
    if files[APP] != APP_SOURCE or not provider:
        return "unsupported-source", None
    step = int(provider.group(1))
    graph = graph_from_increment(step)
    if manifest.get("root") != graph["root"] or export_text(step) != files:
        return "root-or-roundtrip", None
    return "exact", (graph, step)


def git(repo, *args):
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "LC_ALL": "C"}
    return subprocess.check_output(["git", *args], cwd=repo, env=environment, timeout=10)


def clone_case(directory, shape, increment, control):
    files = export_text(increment)
    if control == "missing-entry":
        files.pop(DEPENDENCY)
    elif control == "dependency-pin":
        previous = json.loads(files[MANIFEST])
        previous["dependencies"]["math.inc"]["sha256"] = "0" * 64
        files[MANIFEST] = encoded(previous)
    elif control == "unsupported-call":
        files[APP] = APP_SOURCE.replace(b"math.inc(x)", b"math.ext(x)")
        previous = json.loads(files[MANIFEST])
        previous["entries"][APP] = digest(files[APP])
        files[MANIFEST] = encoded(previous)
    elif control == "stale-source-pin":
        files[DEPENDENCY] = export_text(increment + 1)[DEPENDENCY]
    elif control == "wrong-root":
        previous = json.loads(files[MANIFEST])
        previous["root"] = graph_from_increment(increment + 10)["root"]
        files[MANIFEST] = encoded(previous)
    origin = directory / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main", f"--object-format={shape}")
    for path, raw in files.items():
        filename = origin / path
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_bytes(raw)
    if control == "wrong-mode":
        (origin / DEPENDENCY).chmod(0o755)
    git(origin, "add", ".")
    git(origin, "-c", "user.name=Fixture", "-c", "user.email=fixture@local.example", "commit", "-qm", control)
    selected = git(origin, "rev-parse", "HEAD").decode().strip()
    destination = directory / "clone"
    git(directory, "clone", "-q", "--no-local", str(origin), str(destination))
    git(destination, "remote", "remove", "origin")
    assert not (destination / ".git/objects/info/alternates").exists()
    assert git(destination, "rev-parse", "HEAD").decode().strip() == selected
    assert not git(destination, "status", "--porcelain")
    tree = [entry.split(b"\t", 1) for entry in git(destination, "ls-tree", "-rz", selected).split(b"\0") if entry]
    tracked = {path.decode(): git(destination, "show", f"{selected}:{path.decode()}") for _, path in tree}
    if any(not descriptor.startswith(b"100644 blob ") for descriptor, _ in tree):
        outcome, contents = "file-mode", None
    else:
        outcome, contents = load(tracked)
    expected = {
        "valid": "exact", "missing-entry": "inventory", "dependency-pin": "dependency-pin",
        "unsupported-call": "unsupported-source", "wrong-root": "root-or-roundtrip",
        "stale-source-pin": "file-pin", "wrong-mode": "file-mode",
    }[control]
    assert outcome == expected
    if contents is None:
        return {"status": outcome}
    graph, step = contents
    actual = [("overflow", None) if value > MAX_I64 - step else ("ok", value + step) for value in INPUTS]
    oracle = [("ok", value + increment) if MIN_I64 <= value + increment <= MAX_I64 else ("overflow", None)
              for value in INPUTS]
    assert actual == oracle and export_text(step) == tracked
    return {"status": outcome, "root": graph["root"], "observations": actual}


def run():
    results = {}
    for shape, increment, control in product(
        ("sha1", "sha256"), (1, 2),
        ("valid", "missing-entry", "dependency-pin", "unsupported-call",
         "wrong-root", "stale-source-pin", "wrong-mode"),
    ):
        with TemporaryDirectory() as root:
            name = f"{shape}/{increment}/{control}"
            results[name] = clone_case(Path(root), shape, increment, control)
    for increment in (1, 2):
        assert results[f"sha1/{increment}/valid"] == results[f"sha256/{increment}/valid"]
    assert results["sha1/1/valid"]["root"] != results["sha1/2/valid"]["root"]
    return {
        "baseline": BASE, "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "python": platform.python_version(), "runner_sha256": digest(Path(__file__).read_bytes()),
        "source_inventory": sorted(export_text(1)), "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
