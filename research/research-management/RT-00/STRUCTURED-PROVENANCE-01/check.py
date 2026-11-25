"""Identify archived structured artifacts and their explicitly recorded provenance."""

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import PurePosixPath
import posixpath
import re
import subprocess

BASE = "93aa2261b387cc2f05763a84e1f86255991ef2a8"
FORMATS = {".json", ".jsonl", ".ndjson", ".csv", ".tsv"}
SOURCE_MAPS = {
    "file_sha256", "fixture_sha256", "input_sha256", "inputs_sha256",
    "source_sha256", "sources_sha256", "script_sha256", "runner_sha256",
}
CONTEXTS = {
    "archive", "build_environment", "environment", "host", "metadata",
    "platform", "provenance", "runner", "toolchain", "tools", "versions",
}
FIELDS = {
    "revision": re.compile(r"(?:base(?:line)?|commit|revision|git_(?:sha|head)|source_(?:commit|revision))$"),
    "tool": re.compile(
        r"(?:tools?|toolchain|(?:python|git|clang|llvm|gcc|rustc|lean|dafny|isabelle|"
        r"java|go|compiler|linker|sqlite|qemu|z3|cvc5|openssl|node)(?:_version)?)$"
    ),
    "host": re.compile(
        r"(?:host|platform|os|kernel|kernel_release|architecture|cpu_model|cpu_affinity|"
        r"runner_(?:os|arch)|host_.+)$"
    ),
}
SHA256 = re.compile(r"[a-f0-9]{64}$")
REPLAY = "09bb147f0d8cfd054956dd385889e7853e2011c0"
MAPPINGS = {
    ("LLVM-F64-I64-LOWERING-01", "source_sha256", "evidence.json"): (
        BASE, "research/semantic-representation/RT-05/F64-I64-CONVERSION-01/evidence.json"),
    ("LLVM-FP-FLAGS-01", "source_sha256", "run.py"): (
        BASE, "research/compiler-and-translation/RT-13/BINARY64-CONTRACTION-01/run.py"),
    ("cortex-m3-timer", "source_sha256", "run.py"): (
        BASE, "research/runtime-and-systems/RT-37/cortex-m3-closure/run.py"),
    ("cortex-m3-timer", "source_sha256", "timer-run.py"): (
        BASE, "research/runtime-and-systems/RT-37/cortex-m3-timer/run.py"),
    **{
        ("NATIVE-MERGE-DRIVER-REPLAY-01", "fixture_sha256", name): (
            REPLAY, f"research/toolchain-and-collaboration/RT-24/NATIVE-MERGE-DRIVER-01/{name}")
        for name in ("run.py", "driver.py", "evidence.json", "chart.py")
    },
}


def git(*args, data=None):
    return subprocess.check_output(["git", *args], input=data)


def tree():
    entries = {}
    for row in git("ls-tree", "-r", "-l", "-z", BASE).split(b"\0"):
        if row:
            metadata, path = row.decode().split("\t", 1)
            _, kind, oid, size = metadata.split()
            if kind == "blob":
                entries[path] = (oid, int(size))
    return entries


def load_blobs(entries):
    ordered = sorted(set(entries))
    query = "".join(oid + "\n" for oid in ordered).encode()
    stream = io.BytesIO(git("cat-file", "--batch", data=query))
    blobs = {}
    for expected in ordered:
        oid, kind, size = stream.readline().decode().split()
        assert oid == expected and kind == "blob"
        data = stream.read(int(size))
        assert stream.read(1) == b"\n"
        assert hashlib.sha1(b"blob " + size.encode() + b"\0" + data).hexdigest() == oid
        blobs[oid] = data
    assert not stream.read()
    return blobs


def provenance_fields(document):
    fields = {kind: [] for kind in FIELDS}
    if isinstance(document, dict):
        for key, value in document.items():
            if value is None or isinstance(value, bool):
                continue
            for kind, pattern in FIELDS.items():
                if pattern.fullmatch(key):
                    fields[kind].append(key)
            if key in CONTEXTS and isinstance(value, dict):
                for child in value:
                    for kind, pattern in FIELDS.items():
                        if pattern.fullmatch(child):
                            fields[kind].append(f"{key}.{child}")
    return {kind: sorted(names) for kind, names in fields.items() if names}


def tracked_name(entries, path, label):
    candidates = {label, posixpath.normpath(posixpath.join(posixpath.dirname(path), label))}
    found = sorted(candidates & entries.keys())
    return found[0] if len(found) == 1 else None


def inspect(path, data, entries, digests):
    base = PurePosixPath(path)
    suffix = base.suffix
    if suffix in {".csv", ".tsv"}:
        reader = csv.reader(io.StringIO(data.decode()), delimiter="," if suffix == ".csv" else "\t",
                            strict=True)
        header = next(reader, [])
        return {"format": suffix[1:], "rows": sum(bool(row) for row in reader),
                "columns": header, "fields": provenance_fields(dict.fromkeys(header, ""))}
    if suffix != ".json":
        records = [json.loads(line) for line in data.splitlines() if line.strip()]
        return {"format": suffix[1:], "rows": len(records)}
    document = json.loads(data)
    result = {"format": "json", "shape": type(document).__name__,
              "fields": provenance_fields(document)}
    if not isinstance(document, dict):
        return result
    checks = []
    unbound = []
    for field in sorted(SOURCE_MAPS & document.keys()):
        values = document[field]
        if not isinstance(values, dict):
            continue
        for label, advertised in sorted(values.items()):
            if not isinstance(advertised, str) or not SHA256.fullmatch(advertised):
                continue
            mapping = MAPPINGS.get((base.parent.name, field, label))
            revision, resolved = mapping or (BASE, tracked_name(entries, path, label))
            if resolved is None:
                unbound.append({"field": field, "label": label, "advertised": advertised})
                continue
            oid = entries[resolved][0] if revision == BASE else None
            actual = digests.get(oid)
            if actual is None:
                actual = hashlib.sha256(git("show", f"{revision}:{resolved}")).hexdigest()
                if oid is not None:
                    digests[oid] = actual
            checks.append({"field": field, "label": label, "path": resolved,
                           "revision": revision, "resolution": "producer" if mapping else "direct",
                           "advertised": advertised, "actual": actual,
                           "matches": advertised == actual})
    if checks:
        result["direct_checks"] = checks
    if unbound:
        result["map_labels_without_unique_direct_path"] = unbound
    return result


def counter(rows):
    return {
        "formats": dict(Counter(row["format"] for row in rows)),
        "field_presence": {
            kind: sum(kind in row["fields"] for row in rows if "fields" in row)
            for kind in FIELDS
        },
        "digest_outcomes": dict(Counter(
            "match" if check["matches"] else "baseline_differs"
            for row in rows for check in row.get("direct_checks", [])
        )),
        "labels_without_unique_direct_path": sum(
            len(row.get("map_labels_without_unique_direct_path", [])) for row in rows),
    }


def main():
    entries = tree()
    population = {path: record for path, record in entries.items()
                  if path.startswith("research/") and PurePosixPath(path).suffix in FORMATS}
    blobs = load_blobs(record[0] for record in population.values())
    digests = {oid: hashlib.sha256(data).hexdigest() for oid, data in blobs.items()}
    rows = []
    for path, (oid, size) in population.items():
        data = blobs[oid]
        assert len(data) == size
        try:
            record = inspect(path, data, entries, digests)
        except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as error:
            record = {"format": PurePosixPath(path).suffix[1:], "parse_status": type(error).__name__}
        rows.append({"path": path, "git_blob": oid, "size": size,
                     "sha256": digests[oid], **record})
    print(json.dumps({"base": BASE, "artifacts": len(rows), **counter(rows)}, sort_keys=True))
    for row in rows:
        print(json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
