"""Compare a strict manifest scalar gate with the independent Go reader."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
INDEPENDENT = HERE.parent / "INDEPENDENT-PACKAGE-IDENTITY-01"
MIN, MAX = -(2**63), 2**63 - 1
spec = importlib.util.spec_from_file_location("independent_manifest", INDEPENDENT / "run.py")
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)


def portable_resolution(value):
    if type(value) is int:
        return MIN <= value <= MAX
    if isinstance(value, list):
        return all(portable_resolution(item) for item in value)
    if isinstance(value, dict):
        return all(portable_resolution(item) for item in value.values())
    return isinstance(value, (str, bool))


def portable_manifest(raw, index):
    try:
        parsed = previous.parse_manifest(raw.encode())
    except previous.PackageFormatError:
        return {"admitted": False}
    if type(parsed["schema_version"]) is not int or type(parsed["index"]["format_version"]) is not int:
        return {"admitted": False}
    if not portable_resolution(parsed["content"].get("resolution_inputs", {})):
        return {"admitted": False}
    return previous.python_manifest(raw, index)


def fixtures():
    archived, _ = previous.fixture()
    baseline, index, _, _ = archived["baseline"]
    result = {name: (raw, record, accepted)
              for name, (raw, record, _, accepted) in archived.items()}

    for name, target, replacement, accepted in (
        ("hexadecimal-schema-version", "schema_version = 1", "schema_version = 0x1", True),
        ("positive-signed-index-version", "format_version = 1", "format_version = +1", True),
        ("boolean-false-schema-version", "schema_version = 1", "schema_version = false", False),
        ("string-index-version", "format_version = 1", 'format_version = "1"', False),
    ):
        result[name] = (baseline.replace(target, replacement), index, accepted)
    expressions = (
        ("decimal-with-separators", "9_223_372_036_854_775_807", True),
        ("hexadecimal-max", "0x7fff_ffff_ffff_ffff", True),
        ("hexadecimal-above", "0x8000_0000_0000_0000", False),
        ("negative-below", "-9223372036854775809", False),
        ("nested-endpoints", "{ entries = [-9223372036854775808, 9223372036854775807] }", True),
        ("nested-above", "{ entries = [0, 9223372036854775808] }", False),
        ("nested-below", "{ entries = [-9223372036854775809] }", False),
    )
    for name, literal, accepted in expressions:
        raw = baseline + f"\n[content.resolution_inputs]\nselector = {literal}\n"
        result[name] = (previous.rewrite_root(raw, index), index, accepted)
    return result


def run(go, temp):
    source = temp / "reader"
    source.mkdir()
    for name in ("go.mod", "go.sum", "main.go"):
        shutil.copyfile(INDEPENDENT / name, source / name)
    environment = {**os.environ, "CGO_ENABLED": "0", "GOTOOLCHAIN": "local", "GOENV": "off",
                   "GOPROXY": "off", "GOWORK": "off", "GOFLAGS": ""}
    go_version = previous.command([go, "version"], temp, environment).strip()
    if go_version.startswith("go version go1.24."):
        previous.command([go, "mod", "edit", "-go=1.24"], source, environment)

    binary = temp / "reader-bin"
    previous.command([go, "build", "-mod=readonly", "-buildvcs=false", "-trimpath",
                      "-o", str(binary), "."], source, environment)
    cases = fixtures()
    payload = [{"mode": "package", "manifest": raw, "index": index}
               for raw, index, _ in cases.values()]
    checks = json.loads(previous.command([binary], temp, environment, payload=json.dumps(payload)))
    result = {}
    counts = Counter()
    for (name, (raw, index, accepted)), go_result in zip(cases.items(), checks, strict=True):
        python = portable_manifest(raw, index)
        assert go_result == python and python["admitted"] is accepted, (name, python, go_result)
        former = previous.python_manifest(raw, index)
        counts["accepted" if accepted else "refused"] += 1
        counts["previous_python_differences"] += former != python
        result[name] = {"portable": python, "previous_python_admitted": former["admitted"]}
    max_roots = {result[name]["portable"]["package_root"] for name in
                 ("resolution-int64-max", "decimal-with-separators", "hexadecimal-max")}
    assert len(max_roots) == 1
    paths = [HERE / "check.py", *(INDEPENDENT / name for name in ("run.py", "main.go", "go.mod", "go.sum")),
             previous.PROTOTYPE / "package_identity.py"]
    return {"go": go_version, "python": platform.python_version(), "totals": counts, "results": result,
            "go_build_module": (source / "go.mod").read_text(),
            "sources": {str(p.relative_to(HERE.parents[1])): sha256(p.read_bytes()).hexdigest()
                        for p in paths}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt12-manifest-portable-") as temp:
        print(json.dumps(run(str(Path(args.go).resolve()), Path(temp)), indent=2, sort_keys=True))
