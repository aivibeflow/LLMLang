"""Compare Python package identity with an independent Go encoder and TOML parser."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-IDENTITY-01"
sys.path.insert(0, str(PROTOTYPE))
from package_identity import (
    PackageFormatError,
    canonical,
    logical_index_hash,
    package_content_root,
    parse_manifest,
    verify_manifest,
)
from test_package_identity import H1, H2, H3, manifest_text, sample_index


GO_VERSION = "go version go1.27.4 linux/amd64"


def bytes_digest(path):
    return sha256(path.read_bytes()).hexdigest()


def rewrite_root(raw, index):
    old = parse_manifest(raw.encode("utf-8"))["content"]["content_root"]
    new = package_content_root(parse_manifest(raw.encode("utf-8")), index)
    return raw.replace(f'content_root = "{old}"', f'content_root = "{new}"')


def fixture():
    index = sample_index()
    base = manifest_text(index)
    included = manifest_text(index, roots=[H1, H2])
    reversed_roots = manifest_text(index, roots=[H2, H1])
    reordered = {name: list(reversed(rows)) for name, rows in reversed(tuple(index.items()))}
    changed = deepcopy(index)
    changed["modules"][0]["module"] = "étude"
    repeated = deepcopy(index)
    repeated["dependencies"].append(deepcopy(repeated["dependencies"][0]))
    inputs = {
        "baseline": (base, index, True, True),
        "reordered-logical-index": (base, reordered, True, True),
        "root-order-forward": (included, index, True, True),
        "root-order-reversed": (reversed_roots, index, True, True),
        "manifest-comments": ("# comment\n" + base + "\n# trailing comment\n", index, True, True),
        "descriptive-metadata": (manifest_text(index, name="other", version="4.2.0"), index, True, True),
        "relocated-index": (base.replace('"index.bin"', '"subdir/data.idx"'), index, True, True),
        "omitted-cache": (manifest_text(index, cache=False), index, True, True),
        "changed-logical-record": (manifest_text(changed), changed, True, True),
        "duplicate-toml-key": (base.replace("schema_version = 1", "schema_version = 1\nschema_version = 1"),
                               index, False, False),
        "duplicate-package-roots": (base.replace(f"'{H1}'", f"'{H1}', '{H1}'"), index, False, False),
        "root-not-in-index": (base.replace(f"'{H1}'", f"'{H3}'"), index, False, False),
        "stale-logical-index": (base, changed, False, False),
        "duplicate-index-record": (base, repeated, False, False),
        "wrong-root-envelope": (base.replace(
            f'content_root = "{verify_manifest(base.encode(), index)}"', f'content_root = "{H3}"'
        ), index, False, False),
        "parent-segment-path": (base.replace('"index.bin"', '"../index.bin"'), index, False, False),
        "cache-path-collision": (base.replace('"cache/validation.index"', '"index.bin"'), index, False, False),
        "unknown-top-key": ('ignored = 3\n' + base, index, False, False),
        "unknown-required-version": (base.replace("schema_version = 1", "schema_version = 9"), index, False, False),
        "top-schema-boolean-true": (base.replace("schema_version = 1", "schema_version = true"), index, True, False),
        "index-schema-boolean-true": (base.replace("format_version = 1", "format_version = true"), index, True, False),
        "top-schema-float-one": (base.replace("schema_version = 1", "schema_version = 1.0"), index, True, False),
        "index-schema-float-one": (base.replace("format_version = 1", "format_version = 1.0"), index, True, False),
    }
    for name, value in {
        "integer": "1", "string": '"1"', "boolean": "true", "int64-min": "-9223372036854775808",
        "int64-max": "9223372036854775807", "over-int64": "9223372036854775808",
        "mixed-array": '[1, true, "1"]',
    }.items():
        raw = rewrite_root(base + f"\n[content.resolution_inputs]\nselector = {value}\n", index)
        inputs[f"resolution-{name}"] = (raw, index, True, name != "over-int64")
    values = {
        "null": None, "false": False, "true": True, "integer": 1, "string": "1", "bytes": b"1",
        "negative": -(2**127), "positive": 2**128 + 7, "composed-utf8": "é", "decomposed-utf8": "e\u0301",
        "forward-list": [False, 1, None], "reversed-list": [None, 1, False],
        "length-key-order": {"z": 2, "aa": 1, "é": 4, "中": 3},
        "length-key-order-reversed": {"中": 3, "é": 4, "aa": 1, "z": 2},
        "multibyte-keys": {"é": {"É": [True, b"".hex(), 0]}, "a": "value"},
        "unsupported-float": 0.5,
    }
    return inputs, values


def python_manifest(raw, index):
    source = raw.encode("utf-8")
    try:
        root = verify_manifest(source, index)
        parsed = parse_manifest(source)
        index_hash = logical_index_hash(index)
        profile = {
            "roots": sorted(parsed["content"]["roots"]),
            "dependency_policy": parsed["content"]["dependency_policy"],
            "explicit_resolution_inputs": parsed["content"].get("resolution_inputs", {}),
            "index_logical_hash": index_hash,
        }
        return {"admitted": True, "canonical_hex": canonical(profile).hex(),
                "index_hash": index_hash, "package_root": root}
    except PackageFormatError:
        return {"admitted": False}


def python_value(value):
    try:
        return {"admitted": True, "canonical_hex": canonical(value).hex()}
    except PackageFormatError:
        return {"admitted": False}


def command(args, directory, environment, payload=None):
    return subprocess.run(args, cwd=directory, env=environment, input=payload, check=True,
                          capture_output=True, text=True, encoding="utf-8", timeout=80).stdout


def verify(go, directory):
    fixtures, values = fixture()
    environment = {**os.environ, "CGO_ENABLED": "0", "GOTOOLCHAIN": "local", "GOENV": "off",
                   "GOPROXY": "off", "GOWORK": "off", "GOFLAGS": ""}
    version = command([go, "version"], directory, environment).strip()
    if version != GO_VERSION:
        raise ValueError(version)
    binary = directory / "candidate"
    command([go, "build", "-mod=readonly", "-trimpath", "-o", str(binary), "."], HERE, environment)

    data = {}
    expected = {}
    for name, (raw, index, python_ok, go_ok) in fixtures.items():
        data[name] = {"mode": "package", "manifest": raw, "index": index}
        expected[name] = (python_manifest(raw, index), python_ok, go_ok)
    for name, value in values.items():
        if isinstance(value, bytes):
            data[name] = {"mode": "bytes", "bytes_hex": value.hex()}
        else:
            data[name] = {"mode": "canonical", "value": value}
        expected[name] = (python_value(value), name != "unsupported-float", name != "unsupported-float")

    lines = json.loads(command([str(binary)], directory, environment,
                               payload=json.dumps(list(data.values()), ensure_ascii=False)))
    results = {}
    disagreements = []
    for (name, (py, python_ok, go_ok)), other in zip(expected.items(), lines, strict=True):
        if (py["admitted"], other["admitted"]) != (python_ok, go_ok):
            raise AssertionError((name, py, other, python_ok, go_ok))
        if python_ok == go_ok and py != other:
            raise AssertionError((name, "different binary representation", py, other))
        if python_ok != go_ok:
            disagreements.append(name)
        results[name] = {"python": py, "go": other}

    def root(name):
        return results[name]["python"]["package_root"]

    for unchanged in ("reordered-logical-index", "manifest-comments", "descriptive-metadata",
                      "relocated-index", "omitted-cache"):
        assert root(unchanged) == root("baseline")
    assert root("root-order-forward") == root("root-order-reversed") != root("baseline")
    assert root("changed-logical-record") != root("baseline")
    assert len({root(f"resolution-{kind}") for kind in ("integer", "string", "boolean")}) == 3
    assert results["length-key-order"] == results["length-key-order-reversed"]
    for left, right in (("integer", "true"), ("bytes", "string"),
                        ("forward-list", "reversed-list"), ("composed-utf8", "decomposed-utf8")):
        assert results[left] != results[right]

    sources = (HERE / "main.go", HERE / "go.mod", HERE / "go.sum", HERE / "run.py",
               PROTOTYPE / "package_identity.py", PROTOTYPE / "test_package_identity.py")
    root_dir = HERE.parents[3]
    return {
        "go": version,
        "manifest_cases": len(fixtures),
        "typed_value_cases": len(values),
        "agreement": len(expected) - len(disagreements),
        "per_gate_disagreements": disagreements,
        "sources": {path.relative_to(root_dir).as_posix(): bytes_digest(path) for path in sources},
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", default="go")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-independent-package-") as work:
        print(json.dumps(verify(args.go, Path(work)), indent=2))
